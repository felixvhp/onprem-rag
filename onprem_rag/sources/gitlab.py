"""GitLab connector: README files, documentation folders and issues of selected
projects, through python-gitlab and LlamaIndex's GitLab readers.

Requires the ``gitlab`` extra.
"""

from __future__ import annotations

import os
from typing import Iterable

from llama_index.core import Document

from ..chunking import SemanticChunker
from ..logging_setup import logger
from .base import BaseSource


class GitLabSource(BaseSource):
    name = "gitlab"

    def __init__(
        self,
        url: str,
        token: str,
        chunker: SemanticChunker,
        project_ids: Iterable[int] = (),
        max_projects: int = 50,
        index_issues: bool = True,
        index_readme: bool = True,
        index_docs: bool = True,
        doc_folders: Iterable[str] = ("docs", "documentation"),
        verify_ssl: bool = True,
    ) -> None:
        import gitlab  # lazy: optional dependency

        self.client = gitlab.Gitlab(url=url, private_token=token, ssl_verify=verify_ssl)
        self.chunker = chunker
        self.project_ids = list(project_ids)
        self.max_projects = max_projects
        self.index_issues = index_issues
        self.index_readme = index_readme
        self.index_docs = index_docs
        self.doc_folders = list(doc_folders)

    @classmethod
    def from_env(cls, chunker: SemanticChunker) -> "GitLabSource":
        ids = [int(p) for p in os.getenv("GITLAB_PROJECT_IDS", "").split(",") if p.strip()]
        flag = lambda name: os.getenv(name, "true").lower() == "true"  # noqa: E731
        return cls(
            url=os.environ["GITLAB_URL"],
            token=os.environ["GITLAB_TOKEN"],
            chunker=chunker,
            project_ids=ids,
            max_projects=int(os.getenv("MAX_PROJECTS", "50")),
            index_issues=flag("INDEX_ISSUES"),
            index_readme=flag("INDEX_README"),
            index_docs=flag("INDEX_DOCS"),
            verify_ssl=flag("GITLAB_VERIFY_SSL"),
        )

    def load_all(self) -> list[Document]:
        ids = self.project_ids or [p.id for p in self.client.projects.list(get_all=True)]
        documents: list[Document] = []
        for project_id in ids[: self.max_projects]:
            try:
                documents.extend(self.load_one(str(project_id)))
            except Exception as exc:  # noqa: BLE001
                logger.error("Project %s failed: %s", project_id, exc)
        logger.info("Loaded %d chunks from %d GitLab projects", len(documents), len(ids[: self.max_projects]))
        return documents

    def load_one(self, ref: str) -> list[Document]:
        from llama_index.readers.gitlab import GitLabIssuesReader, GitLabRepositoryReader

        project_id = int(ref)
        project = self.client.projects.get(project_id)
        base = {"project_id": project_id, "project_name": project.name, "source": self.name}
        documents: list[Document] = []

        if self.index_readme:
            try:
                readme = project.files.get("README.md", ref=project.default_branch).decode().decode("utf-8")
                metadata = {**base, "title": f"{project.name} README", "url": project.web_url, "type": "readme"}
                documents.extend(self.chunker.chunk(readme, doc_id=f"{self.doc_prefix(ref)}/README.md", metadata=metadata))
            except Exception:  # noqa: BLE001 - no README is normal
                logger.debug("Project %s has no README", project_id)

        if self.index_docs:
            reader = GitLabRepositoryReader(gitlab_client=self.client, project_id=project_id, verbose=False)
            for folder in self.doc_folders:
                try:
                    files = reader.load_data(ref=project.default_branch, path=folder, recursive=True)
                except Exception:  # noqa: BLE001 - folder absent
                    continue
                for i, doc in enumerate(files):
                    path = doc.metadata.get("file_path", f"{folder}/{i}")
                    metadata = {**base, **doc.metadata, "title": f"{project.name}: {path}", "url": f"{project.web_url}/-/blob/{project.default_branch}/{path}", "type": "doc"}
                    documents.extend(self.chunker.chunk(doc.text, doc_id=f"{self.doc_prefix(ref)}/{path}", metadata=metadata))
                if files:
                    break

        if self.index_issues:
            try:
                reader = GitLabIssuesReader(gitlab_client=self.client, project_id=project_id, verbose=False)
                for doc in reader.load_data(state=GitLabIssuesReader.IssueState.ALL):
                    metadata = {**base, **doc.metadata, "title": f"{project.name} issue {doc.metadata.get('iid', '')}".strip(), "type": "issue"}
                    documents.extend(self.chunker.chunk(doc.text, doc_id=f"{self.doc_prefix(ref)}/issues/{doc.metadata.get('iid', doc.doc_id)}", metadata=metadata))
            except Exception as exc:  # noqa: BLE001
                logger.error("Issues of project %s failed: %s", project_id, exc)
        return documents

    def doc_prefix(self, ref: str) -> str:
        return f"gitlab-project-{int(ref)}"
