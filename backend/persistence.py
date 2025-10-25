# backend/persistence.py
import os
import sqlite3
import threading
from datetime import datetime
from typing import List, Dict, Optional
from uuid import uuid4

_DB_PATH = os.path.join("data", "app.db")
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

# 为了 Tk/线程安全，允许跨线程；用简单互斥锁保护
_conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
_conn.row_factory = sqlite3.Row
_lock = threading.RLock()

def _exec(sql: str, args: tuple = ()) -> None:
    with _lock:
        _conn.execute(sql, args)
        _conn.commit()

def _query(sql: str, args: tuple = ()) -> List[sqlite3.Row]:
    with _lock:
        cur = _conn.execute(sql, args)
        return cur.fetchall()

def init_db() -> None:
    _exec("""
    CREATE TABLE IF NOT EXISTS sessions(
      id TEXT PRIMARY KEY,
      title TEXT,
      created_at TEXT,
      meta_json TEXT
    );
    """)
    _exec("""
    CREATE TABLE IF NOT EXISTS messages(
      id TEXT PRIMARY KEY,
      session_id TEXT,
      role TEXT,
      content TEXT,
      ts TEXT,
      msg_type TEXT,
      model TEXT,
      extra_json TEXT,
      FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
    );
    """)
    # 打开外键
    _exec("PRAGMA foreign_keys = ON;")

def create_session(title: Optional[str] = None, meta_json: str = "{}") -> str:
    sid = str(uuid4())
    title = title or datetime.now().strftime("Session %Y-%m-%d %H:%M:%S")
    ts = datetime.utcnow().isoformat()
    _exec("INSERT INTO sessions(id,title,created_at,meta_json) VALUES(?,?,?,?)",
          (sid, title, ts, meta_json))
    return sid

def list_sessions() -> List[Dict]:
    rows = _query("SELECT id,title,created_at FROM sessions ORDER BY created_at DESC")
    return [dict(r) for r in rows]

def delete_session(session_id: str) -> None:
    # 级联删除 messages（已启用外键）
    _exec("DELETE FROM sessions WHERE id=?", (session_id,))

def add_message(session_id: str, role: str, content: str,
                msg_type: str = "normal", model: Optional[str] = None,
                ts_iso: Optional[str] = None, extra_json: str = "{}") -> str:
    mid = str(uuid4())
    ts_iso = ts_iso or datetime.utcnow().isoformat()
    _exec("""INSERT INTO messages
             (id,session_id,role,content,ts,msg_type,model,extra_json)
             VALUES(?,?,?,?,?,?,?,?)""",
          (mid, session_id, role, content, ts_iso, msg_type, model, extra_json))
    return mid

def get_messages(session_id: str) -> List[Dict]:
    rows = _query("""SELECT id,role,content,ts,msg_type,model
                     FROM messages WHERE session_id=?
                     ORDER BY datetime(ts) ASC""", (session_id,))
    return [dict(r) for r in rows]
