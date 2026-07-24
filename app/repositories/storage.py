"""Filesystem-backed JSON storage for CHIMERA Studio persistence."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Optional

_SAFE_COMPONENT_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_component(value: str, label: str = "path component") -> None:
    """Reject path traversal and unsafe characters in a single path component.

    Allows only alphanumeric, hyphen, and underscore characters.
    Raises ValueError on any unsafe input.
    """
    if not value:
        raise ValueError(f"{label} must not be empty")
    if ".." in value:
        raise ValueError(f"{label} contains illegal '..' traversal: {value!r}")
    if not _SAFE_COMPONENT_RE.match(value):
        raise ValueError(
            f"{label} contains illegal characters: {value!r} "
            f"(allowed: a-z, A-Z, 0-9, hyphen, underscore)"
        )


def _validate_domain(domain: str) -> None:
    """Validate a domain path (may contain '/' separators for nested dirs)."""
    for part in domain.split("/"):
        _validate_component(part, "domain component")


def _validate_key(key: str) -> None:
    """Validate a storage key (single path component, no separators)."""
    _validate_component(key, "key")


class FilesystemStorage:
    """Low-level JSON file storage on the local filesystem.

    Provides atomic read/write for JSON documents organized by domain.
    All paths are resolved relative to a root data directory.

    Security: all domain and key arguments are validated to prevent
    path traversal and cross-directory access.  Resolved paths are
    checked to ensure they remain within the storage root.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def _safe_path(self, domain: str, key: str) -> Path:
        """Resolve a domain+key to an absolute path, validating safety."""
        _validate_domain(domain)
        _validate_key(key)
        path = (self._root / domain / f"{key}.json").resolve()
        if not str(path).startswith(str(self._root) + os.sep) and path != self._root:
            raise ValueError(f"Resolved path escapes storage root: {path}")
        return path

    def _safe_domain_path(self, domain: str) -> Path:
        """Resolve a domain path, validating safety."""
        _validate_domain(domain)
        path = (self._root / domain).resolve()
        if not str(path).startswith(str(self._root) + os.sep) and path != self._root:
            raise ValueError(f"Resolved domain path escapes storage root: {path}")
        return path

    def ensure_domain(self, domain: str) -> Path:
        """Ensure a domain directory exists and return its path."""
        _validate_domain(domain)
        domain_path = self._root / domain
        domain_path.mkdir(parents=True, exist_ok=True)
        return domain_path

    def read(self, domain: str, key: str) -> Optional[dict[str, Any]]:
        """Read a JSON document by domain and key (filename without .json)."""
        path = self._safe_path(domain, key)
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write(self, domain: str, key: str, data: dict[str, Any]) -> None:
        """Write a JSON document atomically (write-then-rename)."""
        path = self._safe_path(domain, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        shutil.move(str(tmp), str(path))

    def delete(self, domain: str, key: str) -> bool:
        """Delete a JSON document. Returns True if it existed."""
        path = self._safe_path(domain, key)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_keys(self, domain: str) -> list[str]:
        """List all keys (filenames without .json) in a domain directory."""
        domain_path = self._safe_domain_path(domain)
        if not domain_path.exists():
            return []
        return sorted(
            p.stem for p in domain_path.iterdir()
            if p.suffix == ".json" and p.is_file()
        )

    def list_all(self, domain: str) -> list[dict[str, Any]]:
        """Read all JSON documents in a domain directory."""
        results = []
        for key in self.list_keys(domain):
            doc = self.read(domain, key)
            if doc is not None:
                results.append(doc)
        return results

    def exists(self, domain: str, key: str) -> bool:
        """Check if a document exists."""
        path = self._safe_path(domain, key)
        return path.exists()

    def read_index(self, domain: str, filename: str = "_index") -> dict[str, str]:
        """Read a JSON index file (key→value mapping)."""
        _validate_component(filename, "index filename")
        path = self._safe_path(domain, filename)
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_index(self, domain: str, index: dict[str, str], filename: str = "_index") -> None:
        """Write a JSON index file atomically."""
        _validate_component(filename, "index filename")
        path = self._safe_path(domain, filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
        shutil.move(str(tmp), str(path))
