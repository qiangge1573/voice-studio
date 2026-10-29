"""SQLite 数据访问层：每操作新建连接，天然支持多线程。"""
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    openid      TEXT UNIQUE NOT NULL,
    nickname    TEXT DEFAULT '',
    created_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS voices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    name            TEXT NOT NULL,
    sample_path     TEXT NOT NULL,
    sample_duration REAL DEFAULT 0,
    lang            TEXT DEFAULT 'zh',
    consent         INTEGER DEFAULT 1,
    created_at      REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS tts_tasks (
    id          TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    voice_id    INTEGER,
    voice_name  TEXT DEFAULT '',
    text        TEXT NOT NULL,
    language    TEXT DEFAULT 'zh',
    status      TEXT DEFAULT 'pending',  -- pending / running / done / failed
    output_path TEXT,
    error       TEXT,
    created_at  REAL NOT NULL,
    finished_at REAL
);

CREATE INDEX IF NOT EXISTS idx_voices_user ON voices (user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_user ON tts_tasks (user_id, created_at);

CREATE TABLE IF NOT EXISTS dubbing_tasks (
    id          TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    voice_id    INTEGER,
    voice_name  TEXT DEFAULT '',
    video_path  TEXT NOT NULL,
    script      TEXT NOT NULL,
    mode        TEXT DEFAULT 'overlay',  -- overlay(配音叠加压低原声) / replace(替换原音轨)
    status      TEXT DEFAULT 'pending',  -- pending / running / done / failed
    output_path TEXT,
    error       TEXT,
    created_at  REAL NOT NULL,
    finished_at REAL
);

CREATE TABLE IF NOT EXISTS batch_tasks (
    id          TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    voice_id    INTEGER,
    voice_name  TEXT DEFAULT '',
    language    TEXT DEFAULT 'zh',
    items       TEXT NOT NULL,           -- JSON: [{text,status,error,output_path}]
    status      TEXT DEFAULT 'pending',  -- pending / running / done / failed
    created_at  REAL NOT NULL,
    finished_at REAL
);
"""


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    return dict(row) if row is not None else None


class Database:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self.init()

    def init(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ---------- users ----------
    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row_to_dict(row)

    def get_user_by_openid(self, openid: str) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE openid = ?", (openid,)).fetchone()
        return row_to_dict(row)

    def create_user(self, openid: str, nickname: str = "") -> dict:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (openid, nickname, created_at) VALUES (?, ?, ?)",
                (openid, nickname, __import__("time").time()),
            )
            user_id = cur.lastrowid
        user = self.get_user_by_openid(openid)
        assert user is not None
        return user

    # ---------- voices ----------
    def create_voice(self, user_id: int, name: str, sample_path: str,
                     duration: float, lang: str, consent: int) -> dict:
        import time
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO voices (user_id, name, sample_path, sample_duration, lang, consent, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, sample_path, duration, lang, consent, time.time()),
            )
            voice_id = cur.lastrowid
        return self.get_voice(voice_id)  # type: ignore[return-value]

    def get_voice(self, voice_id: int) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM voices WHERE id = ?", (voice_id,)).fetchone()
        return row_to_dict(row)

    def list_voices(self, user_id: int) -> list:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM voices WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_voice(self, voice_id: int, user_id: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM voices WHERE id = ? AND user_id = ?", (voice_id, user_id)
            )
            return cur.rowcount > 0

    # ---------- tts tasks ----------
    def create_task(self, task_id: str, user_id: int, voice_id: int, voice_name: str,
                    text: str, language: str) -> None:
        import time
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO tts_tasks (id, user_id, voice_id, voice_name, text, language, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
                (task_id, user_id, voice_id, voice_name, text, language, time.time()),
            )

    def update_task(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [task_id]
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE tts_tasks SET {cols} WHERE id = ?", values)

    def get_task(self, task_id: str, user_id: int) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tts_tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
            ).fetchone()
        return row_to_dict(row)

    def list_tasks(self, user_id: int, limit: int = 50) -> list:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tts_tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_task(self, task_id: str, user_id: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM tts_tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
            )
            return cur.rowcount > 0

    # ---------- dubbing tasks ----------
    def create_dubbing(self, task_id: str, user_id: int, voice_id: int, voice_name: str,
                       video_path: str, script: str, mode: str) -> None:
        import time
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO dubbing_tasks (id, user_id, voice_id, voice_name, video_path, script, mode, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                (task_id, user_id, voice_id, voice_name, video_path, script, mode, time.time()),
            )

    def update_dubbing(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [task_id]
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE dubbing_tasks SET {cols} WHERE id = ?", values)

    def get_dubbing(self, task_id: str, user_id: int) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM dubbing_tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
            ).fetchone()
        return row_to_dict(row)

    def list_dubbing(self, user_id: int, limit: int = 10) -> list:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM dubbing_tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------- batch tasks ----------
    def create_batch(self, task_id: str, user_id: int, voice_id: int, voice_name: str,
                     language: str, items_json: str) -> None:
        import time
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO batch_tasks (id, user_id, voice_id, voice_name, language, items, status, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
                (task_id, user_id, voice_id, voice_name, language, items_json, time.time()),
            )

    def update_batch(self, task_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [task_id]
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE batch_tasks SET {cols} WHERE id = ?", values)

    def get_batch(self, task_id: str, user_id: int) -> Optional[dict]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM batch_tasks WHERE id = ? AND user_id = ?", (task_id, user_id)
            ).fetchone()
        return row_to_dict(row)

    def list_batch(self, user_id: int, limit: int = 10) -> list:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM batch_tasks WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]
