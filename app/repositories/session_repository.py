"""Persistent session repository for CHIMERA Studio interviews."""

from __future__ import annotations

from typing import Optional

from app.repositories.storage import FilesystemStorage
from app.interview.engine import InterviewEngine, InterviewSession


_DOMAIN = "sessions"


class SessionRepository:
    """Persists interview sessions to the filesystem, scoped by owner.

    Uses InterviewEngine.serialize_session() / deserialize_session()
    for canonical serialization.  Every method requires an owner_user_id
    to enforce user isolation at the storage boundary.

    Storage layout::

        sessions/
            {owner_user_id}/
                {session_id}.json
    """

    def __init__(self, storage: FilesystemStorage, engine: InterviewEngine) -> None:
        self._storage = storage
        self._engine = engine
        self._cache: dict[tuple[str, str], InterviewSession] = {}

    def _domain(self, owner_user_id: str) -> str:
        return f"{_DOMAIN}/{owner_user_id}"

    def save(self, session: InterviewSession, owner_user_id: str) -> None:
        """Persist a session to disk and update the cache."""
        data = self._engine.serialize_session(session)
        self._storage.write(self._domain(owner_user_id), session.session_id, data)
        self._cache[(owner_user_id, session.session_id)] = session

    def load(self, session_id: str, owner_user_id: str) -> Optional[InterviewSession]:
        """Load a session from cache or disk."""
        key = (owner_user_id, session_id)
        if key in self._cache:
            return self._cache[key]
        data = self._storage.read(self._domain(owner_user_id), session_id)
        if data is None:
            return None
        session = self._engine.deserialize_session(data)
        self._cache[key] = session
        return session

    def exists(self, session_id: str, owner_user_id: str) -> bool:
        """Check if a session exists in cache or on disk."""
        key = (owner_user_id, session_id)
        if key in self._cache:
            return True
        return self._storage.exists(self._domain(owner_user_id), session_id)

    def delete(self, session_id: str, owner_user_id: str) -> bool:
        """Remove a session from cache and disk."""
        key = (owner_user_id, session_id)
        self._cache.pop(key, None)
        return self._storage.delete(self._domain(owner_user_id), session_id)

    def list_ids(self, owner_user_id: str) -> list[str]:
        """List all persisted session IDs for a user."""
        return self._storage.list_keys(self._domain(owner_user_id))

    def load_all(self, owner_user_id: str) -> dict[str, InterviewSession]:
        """Load all sessions for a user from disk into cache."""
        domain = self._domain(owner_user_id)
        for sid in self._storage.list_keys(domain):
            key = (owner_user_id, sid)
            if key not in self._cache:
                data = self._storage.read(domain, sid)
                if data is not None:
                    session = self._engine.deserialize_session(data)
                    self._cache[key] = session
        return {
            sid: sess
            for (uid, sid), sess in self._cache.items()
            if uid == owner_user_id
        }

    def clear_cache(self) -> None:
        """Clear the in-memory cache (does not affect disk)."""
        self._cache.clear()
