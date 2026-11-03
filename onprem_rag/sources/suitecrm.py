"""SuiteCRM connector (REST API v4.1). Which modules, fields and relationships
to index is configured in a JSON file, so the connector carries no knowledge of
any particular CRM customisation. Each record becomes one document that reads
like a fact sheet, with related records numbered ``[i/n]`` so a model can count
them reliably.

Example configuration::

    {
      "accounts": {
        "label": "Account",
        "fields": {"name": "Name", "industry": "Industry", "billing_address_city": "City",
                   "description": "Description"},
        "relationships": {
          "contacts": {"label": "Contacts", "fields": {"name": "Name", "title": "Title"}},
          "opportunities": {"label": "Opportunities",
                            "fields": {"name": "Name", "sales_stage": "Stage", "amount": "Amount"}}
        }
      }
    }
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta

import requests
from llama_index.core import Document

from ..logging_setup import logger
from .base import BaseSource


class SuiteCRMSource(BaseSource):
    name = "suitecrm"

    def __init__(self, api_url: str, username: str, password: str, entities: dict, verify_ssl: bool = True, page_size: int = 100) -> None:
        self.api_url = api_url
        self.username = username
        self.password = password
        self.entities = entities
        self.verify_ssl = verify_ssl
        self.page_size = page_size
        self.session = requests.Session()
        self.session_id: str | None = None
        self.session_expires: datetime | None = None

    @classmethod
    def from_env(cls) -> "SuiteCRMSource":
        with open(os.environ["SUITECRM_ENTITIES"], encoding="utf-8") as handle:
            entities = json.load(handle)
        return cls(
            api_url=os.environ["SUITECRM_API_URL"],
            username=os.environ["SUITECRM_USER"],
            password=os.environ["SUITECRM_PASSWORD"],
            entities=entities,
            verify_ssl=os.getenv("SUITECRM_VERIFY_SSL", "true").lower() == "true",
        )

    # ------------------------------------------------------------------ source
    def load_all(self) -> list[Document]:
        self._ensure_session()
        documents: list[Document] = []
        for module in self.entities:
            docs = self._load_module(module)
            logger.info("Loaded %d %s records", len(docs), module)
            documents.extend(docs)
        return documents

    def load_one(self, ref: str) -> list[Document]:
        module, _, record_id = ref.partition(":")
        if module not in self.entities or not record_id:
            raise ValueError("ref must look like '<module>:<record id>'")
        self._ensure_session()
        return self._load_module(module, query=f"{module}.id = '{record_id}'")

    def doc_prefix(self, ref: str) -> str:
        return ref.replace(":", "_", 1)

    def recent_changes(self, module: str, since: datetime) -> list[Document]:
        self._ensure_session()
        return self._load_module(module, query=f"{module}.date_modified > '{since:%Y-%m-%d %H:%M:%S}'")

    # --------------------------------------------------------------- API calls
    def _ensure_session(self) -> None:
        if self.session_id and self.session_expires and datetime.now() < self.session_expires:
            return
        params = {
            "user_auth": {"user_name": self.username, "password": hashlib.md5(self.password.encode()).hexdigest(), "version": "1.1"},
            "application_name": "onprem-rag",
            "name_value_list": [],
        }
        response = self._request("login", params)
        if not response or "id" not in response:
            raise RuntimeError(f"SuiteCRM login failed: {response}")
        self.session_id = response["id"]
        self.session_expires = datetime.now() + timedelta(hours=1)

    def _request(self, method: str, params: dict) -> dict:
        post = {"method": method, "input_type": "JSON", "response_type": "JSON", "rest_data": json.dumps(params)}
        response = self.session.post(self.api_url, data=post, verify=self.verify_ssl, timeout=30)
        response.raise_for_status()
        result = response.json()
        if isinstance(result, dict) and result.get("name") == "Invalid Session ID":
            self.session_id = None
            self._ensure_session()
            post["rest_data"] = json.dumps({**params, "session": self.session_id})
            result = self.session.post(self.api_url, data=post, verify=self.verify_ssl, timeout=30).json()
        return result

    def _load_module(self, module: str, query: str = "") -> list[Document]:
        config = self.entities[module]
        fields = ["id", "date_modified", *config.get("fields", {})]
        links = [{"name": rel, "value": list(spec.get("fields", {}))} for rel, spec in config.get("relationships", {}).items()]
        documents: list[Document] = []
        offset = 0
        while True:
            response = self._request(
                "get_entry_list",
                {
                    "session": self.session_id,
                    "module_name": module,
                    "query": query,
                    "order_by": "date_modified ASC",
                    "offset": offset,
                    "select_fields": fields,
                    "link_name_to_fields_array": links,
                    "max_results": self.page_size,
                    "deleted": 0,
                },
            )
            entries = (response or {}).get("entry_list") or []
            relationship_list = (response or {}).get("relationship_list") or []
            for i, entry in enumerate(entries):
                related: dict[str, list] = {}
                if i < len(relationship_list):
                    for link in relationship_list[i].get("link_list", []):
                        related[link.get("name", "")] = link.get("records", [])
                doc = self._to_document(module, config, entry, related)
                if doc is not None:
                    documents.append(doc)
            if len(entries) < self.page_size:
                return documents
            offset += self.page_size

    # ------------------------------------------------------------- formatting
    @staticmethod
    def _values(name_value_list: dict) -> dict:
        return {k: (v.get("value") if isinstance(v, dict) else v) for k, v in (name_value_list or {}).items()}

    def _to_document(self, module: str, config: dict, entry: dict, related: dict) -> Document | None:
        data = self._values(entry.get("name_value_list", {}))
        record_id = entry.get("id") or data.get("id", "")
        label = config.get("label", module)
        name = data.get("name") or record_id
        lines = [f"{label}: {name}"]
        for field, field_label in config.get("fields", {}).items():
            if field != "name" and data.get(field):
                lines.append(f"{field_label}: {data[field]}")
        for rel, spec in config.get("relationships", {}).items():
            records = related.get(rel) or []
            if not records:
                continue
            lines.append(f"\nRelated {spec.get('label', rel)} for {name} ({len(records)} total):")
            for i, record in enumerate(records, start=1):
                values = self._values(record.get("link_value", {}))
                parts = [f"{flabel}: {values[f]}" for f, flabel in spec.get("fields", {}).items() if values.get(f)]
                lines.append(f"- [{i}/{len(records)}] {name} | " + " - ".join(parts))
        text = "\n".join(lines).strip()
        if not text:
            return None
        metadata = {"entity_type": module, "entity_id": record_id, "title": f"{label} {name}", "name": name, "url": f"{module}:{record_id}", "source": self.name}
        return Document(text=text, doc_id=f"{module}_{record_id}", metadata=metadata)
