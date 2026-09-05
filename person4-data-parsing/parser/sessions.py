"""Per-upload-session storage lifecycle.

Each session gets its own **in-memory** SQLite connection
(`sqlite3.connect(":memory:")`) — nothing a session stores is ever written
to a file or any external database. Offer letters carry real compensation
data, so the guarantee this module exists to provide is simple: once a
session ends — by explicit close, by idle timeout, or by the process
stopping — every offer parsed inside it is gone. There is no disk file to
delete because there was never one to begin with.
"""
from __future__ import annotations

import sqlite3
import threading
import time
import uuid

from . import storage

SESSION_IDLE_TIMEOUT_SECONDS = 30 * 60  # a session with no activity for 30 minutes is dropped


class _Session:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        storage.init_schema(self.conn)
        self.last_used = time.monotonic()


class SessionStore:
    """In-process registry of active sessions.

    Not shared across worker processes: if this API is ever run with
    multiple uvicorn workers, a session's data lives only in the memory of
    the worker that created it — by design, since nothing is ever written
    anywhere a second worker could read it. Run with a single worker, or
    put session-affinity routing in front of it, if that matters for a demo.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        session_id = str(uuid.uuid4())
        with self._lock:
            self._sessions[session_id] = _Session()
        return session_id

    def get_conn(self, session_id: str) -> sqlite3.Connection | None:
        with self._lock:
            self._evict_idle_locked()
            session = self._sessions.get(session_id)
            if session is None:
                return None
            session.last_used = time.monotonic()
            return session.conn

    def close(self, session_id: str) -> bool:
        """Ends a session immediately, closing its in-memory connection —
        this is the point of no return for that session's data."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        session.conn.close()
        return True

    def active_session_count(self) -> int:
        with self._lock:
            self._evict_idle_locked()
            return len(self._sessions)

    def _evict_idle_locked(self) -> None:
        now = time.monotonic()
        stale_ids = [sid for sid, s in self._sessions.items()
                     if now - s.last_used > SESSION_IDLE_TIMEOUT_SECONDS]
        for sid in stale_ids:
            self._sessions.pop(sid).conn.close()


store = SessionStore()
