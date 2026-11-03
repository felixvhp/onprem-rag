"""MediaWiki connector: pages are fetched through the MediaWiki API, wikitext is
reduced to plain text (infoboxes become key: value lines) and chunked by section.

Requires the ``mediawiki`` extra (mwparserfromhell).
"""

from __future__ import annotations

import os
import re
from typing import Iterable

import requests
from llama_index.core import Document

from ..chunking import SemanticChunker
from ..logging_setup import logger
from .base import BaseSource


class MediaWikiSource(BaseSource):
    name = "mediawiki"

    def __init__(
        self,
        api_url: str,
        chunker: SemanticChunker,
        namespaces: Iterable[int] = (0,),
        blacklist: Iterable[str] = (),
        skip_obsolete: bool = True,
        verify_ssl: bool = True,
        batch_size: int = 50,
    ) -> None:
        self.api_url = api_url
        self.chunker = chunker
        self.namespaces = {int(n) for n in namespaces}
        self.blacklist = set(blacklist)
        self.skip_obsolete = skip_obsolete
        self.verify_ssl = verify_ssl
        self.batch_size = batch_size
        self.session = requests.Session()

    @classmethod
    def from_env(cls, chunker: SemanticChunker) -> "MediaWikiSource":
        blacklist: set[str] = set()
        blacklist_file = os.getenv("BLACKLIST_FILE", "")
        if blacklist_file and os.path.exists(blacklist_file):
            with open(blacklist_file, encoding="utf-8") as handle:
                blacklist = {line.strip() for line in handle if line.strip()}
        return cls(
            api_url=os.environ["MEDIAWIKI_API_URL"],
            chunker=chunker,
            namespaces=[int(n) for n in os.getenv("MEDIAWIKI_NAMESPACES", "0").split(",") if n.strip()],
            blacklist=blacklist,
            skip_obsolete=os.getenv("MEDIAWIKI_SKIP_OBSOLETE", "true").lower() == "true",
            verify_ssl=os.getenv("MEDIAWIKI_VERIFY_SSL", "true").lower() == "true",
        )

    # ------------------------------------------------------------------ source
    def load_all(self) -> list[Document]:
        documents: list[Document] = []
        for ns_id, ns_name in self.get_namespaces().items():
            if ns_id not in self.namespaces:
                continue
            logger.info("Fetching namespace %s (%s)", ns_id, ns_name or "main")
            titles = [p["title"] for p in self._all_pages_in_namespace(ns_id)]
            documents.extend(self._process_titles(titles, ns_name or "main"))
            logger.info("Namespace %s done, %d chunks so far", ns_id, len(documents))
        return documents

    def load_one(self, ref: str) -> list[Document]:
        title = ref.rstrip("/").split("/")[-1].replace("_", " ")
        return self._process_titles([title], "main")

    # --------------------------------------------------------------- API calls
    def _get(self, params: dict) -> dict:
        response = self.session.get(self.api_url, params={"format": "json", **params}, verify=self.verify_ssl, timeout=60)
        response.raise_for_status()
        return response.json()

    def get_namespaces(self) -> dict[int, str]:
        data = self._get({"action": "query", "meta": "siteinfo", "siprop": "namespaces"})
        return {int(k): v.get("*", "") for k, v in data["query"]["namespaces"].items()}

    def _all_pages_in_namespace(self, ns_id: int) -> list[dict]:
        pages: list[dict] = []
        params = {"action": "query", "list": "allpages", "aplimit": "max", "apnamespace": ns_id}
        while True:
            data = self._get(params)
            pages.extend(data.get("query", {}).get("allpages", []))
            if "continue" not in data:
                return pages
            params["apcontinue"] = data["continue"]["apcontinue"]

    def _process_titles(self, titles: list[str], namespace: str) -> list[Document]:
        documents: list[Document] = []
        for start in range(0, len(titles), self.batch_size):
            batch = titles[start : start + self.batch_size]
            try:
                data = self._get(
                    {
                        "action": "query",
                        "titles": "|".join(batch),
                        "prop": "revisions|categories|info",
                        "rvprop": "content|timestamp",
                        "inprop": "url",
                    }
                )
            except requests.RequestException as exc:
                logger.error("Batch starting at %d failed: %s", start, exc)
                continue
            for page in data.get("query", {}).get("pages", {}).values():
                if "missing" in page:
                    continue
                try:
                    documents.extend(self._process_page(page, namespace))
                except Exception as exc:  # noqa: BLE001
                    logger.error("Page %r failed: %s", page.get("title"), exc)
        return documents

    # ------------------------------------------------------------ page parsing
    def _process_page(self, page: dict, namespace: str) -> list[Document]:
        title = page.get("title", "")
        url = page.get("fullurl", "")
        if url in self.blacklist or title in self.blacklist:
            return []
        revisions = page.get("revisions") or []
        if not revisions:
            return []
        wikitext = revisions[0].get("*", "") or revisions[0].get("slots", {}).get("main", {}).get("*", "")
        text = clean_wikitext(wikitext)
        if self.skip_obsolete and is_obsolete(title, wikitext, text):
            logger.info("Skipping obsolete page %r", title)
            return []
        if not text.strip():
            return []
        metadata = {
            "title": title,
            "page_id": page.get("pageid"),
            "namespace": namespace,
            "url": url,
            "categories": [c["title"] for c in page.get("categories", [])],
            "last_modified": revisions[0].get("timestamp", ""),
            "source": self.name,
        }
        return self.chunker.chunk(text, doc_id=url or title, metadata=metadata)

    def doc_prefix(self, ref: str) -> str:
        return ref


def clean_wikitext(wikitext: str) -> str:
    """Reduce wikitext to plain text, keeping section headings and infobox fields."""
    if not wikitext:
        return ""
    import mwparserfromhell

    code = mwparserfromhell.parse(wikitext)
    for template in code.filter_templates():
        if "infobox" in str(template.name).strip().lower():
            lines = []
            for param in template.params:
                key, _, value = str(param).partition("=")
                value = mwparserfromhell.parse(value).strip_code().strip()
                if value:
                    lines.append(f"{key.strip()}: {value}")
            code.replace(template, "\n".join(lines))
        else:
            code.remove(template)
    text = code.strip_code(keep_template_params=False)
    # strip_code keeps ``== Heading ==`` markers, which the chunker uses as section breaks
    text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)
    return text.strip()


def is_obsolete(title: str, wikitext: str, text: str) -> bool:
    if "obsolete" in title.lower():
        return True
    if "OBSOLETE PAGE" in wikitext or ("background-color: yellow" in wikitext and "OBSOLETE" in wikitext):
        return True
    return "obsolete" in text[:200].lower()
