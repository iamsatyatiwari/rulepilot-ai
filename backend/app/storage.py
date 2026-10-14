"""Minimal document storage used by governance: local JSON files or Firestore.

Both backends store JSON-compatible dicts by (collection, document id). Local
files suit development; Firestore keeps state across Cloud Run restarts and
instances.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Protocol

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _check(collection: str, doc_id: str) -> None:
    if not _SAFE_ID.match(collection) or not _SAFE_ID.match(doc_id):
        raise ValueError("invalid collection or document id")


class DocumentBackend(Protocol):
    def put(self, collection: str, doc_id: str, data: dict[str, Any]) -> None: ...
    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None: ...
    def delete(self, collection: str, doc_id: str) -> None: ...
    def all(self, collection: str) -> list[dict[str, Any]]: ...


class LocalJsonBackend:
    """One JSON file per document under ``root/collection/doc_id.json``."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.Lock()

    def _path(self, collection: str, doc_id: str) -> Path:
        _check(collection, doc_id)
        return self.root / collection / f"{doc_id}.json"

    def put(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        path = self._path(collection, doc_id)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temporary.replace(path)

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        path = self._path(collection, doc_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def delete(self, collection: str, doc_id: str) -> None:
        path = self._path(collection, doc_id)
        with self._lock:
            path.unlink(missing_ok=True)

    def all(self, collection: str) -> list[dict[str, Any]]:
        _check(collection, "x")
        folder = self.root / collection
        if not folder.is_dir():
            return []
        documents = []
        for path in sorted(folder.glob("*.json")):
            try:
                documents.append(json.loads(path.read_text(encoding="utf-8")))
            except ValueError:
                continue
        return documents


class FirestoreBackend:
    """Firestore documents under ``{prefix}_{collection}`` collections."""

    def __init__(self, client: Any, prefix: str = "rulepilot") -> None:
        self.client = client
        self.prefix = prefix

    def _collection(self, collection: str) -> Any:
        return self.client.collection(f"{self.prefix}_{collection}")

    def put(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        _check(collection, doc_id)
        self._collection(collection).document(doc_id).set(data)

    def get(self, collection: str, doc_id: str) -> dict[str, Any] | None:
        _check(collection, doc_id)
        snapshot = self._collection(collection).document(doc_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def delete(self, collection: str, doc_id: str) -> None:
        _check(collection, doc_id)
        self._collection(collection).document(doc_id).delete()

    def all(self, collection: str) -> list[dict[str, Any]]:
        _check(collection, "x")
        return [snapshot.to_dict() for snapshot in self._collection(collection).stream()]


def create_backend(kind: str, data_dir: Path, project: str | None = None) -> DocumentBackend:
    if kind == "firestore":
        from google.cloud import firestore  # Imported only when Firestore is configured.

        return FirestoreBackend(firestore.Client(project=project))
    return LocalJsonBackend(data_dir)
