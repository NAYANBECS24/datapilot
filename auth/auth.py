import hashlib
import os
import sqlite3
from typing import Any, Dict, Optional

_AUTH_DIR = os.path.join(os.path.dirname(__file__))
_AUTH_DB = os.path.join(_AUTH_DIR, "users.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_AUTH_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    # auto-seed default users if table is empty (survives cloud deploys)
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing == 0:
        for u, p in [("admin", "admin123"), ("nayan", "nayan")]:
            conn.execute(
                "INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)",
                (u, _hash(p)),
            )
            _ensure_upload_dir(u)
        conn.commit()
    return conn


def _ensure_upload_dir(username: str) -> None:
    user_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", username)
    os.makedirs(user_dir, exist_ok=True)

def _hash(password: str, salt: str = "datapilot_salt_2026") -> str:
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def register(username: str, password: str) -> Dict[str, Any]:
    username = username.strip().lower()
    if not username or len(username) < 3:
        return {"success": False, "error": "Username must be at least 3 characters."}
    if not password or len(password) < 4:
        return {"success": False, "error": "Password must be at least 4 characters."}
    try:
        conn = _get_conn()
        existing = conn.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            conn.close()
            return {"success": False, "error": "Username already exists."}
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, _hash(password)))
        conn.commit()
        conn.close()
        user_dir = os.path.join(os.path.dirname(_AUTH_DIR), "uploads", username)
        os.makedirs(user_dir, exist_ok=True)
        return {"success": True, "username": username}
    except Exception as e:
        return {"success": False, "error": str(e)}


def login(username: str, password: str) -> Dict[str, Any]:
    username = username.strip().lower()
    try:
        conn = _get_conn()
        row = conn.execute("SELECT username, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if not row:
            return {"success": False, "error": "Invalid username or password."}
        if row[1] != _hash(password):
            return {"success": False, "error": "Invalid username or password."}
        return {"success": True, "username": row[0]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_user(username: str) -> Optional[Dict[str, Any]]:
    try:
        conn = _get_conn()
        row = conn.execute("SELECT username, created_at FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
        conn.close()
        if row:
            return {"username": row[0], "created_at": row[1]}
        return None
    except Exception:
        return None
