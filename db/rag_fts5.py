# backend/rag_fts5.py
import os, sqlite3, threading
from typing import List, Tuple

_DB = os.path.join("data", "app.db")
_conn = sqlite3.connect(_DB, check_same_thread=False)
_conn.row_factory = sqlite3.Row
_lock = threading.RLock()

def init():
    with _lock:
        _conn = _conn_global()
        _conn.execute("""CREATE TABLE IF NOT EXISTS docs(
            id TEXT PRIMARY KEY,
            title TEXT, body TEXT, source TEXT, tags TEXT
        );""")
        _conn.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts
            USING fts5(title, body, content='docs', content_rowid='rowid');""")
        _conn.execute("""CREATE TRIGGER IF NOT EXISTS docs_ai
            AFTER INSERT ON docs BEGIN
              INSERT INTO docs_fts(rowid,title,body) VALUES (new.rowid,new.title,new.body);
            END;""")
        _conn.execute("""CREATE TRIGGER IF NOT EXISTS docs_ad
            AFTER DELETE ON docs BEGIN
              INSERT INTO docs_fts(docs_fts, rowid, title, body)
              VALUES('delete', old.rowid, old.title, old.body);
            END;""")
        _conn.execute("""CREATE TRIGGER IF NOT EXISTS docs_au
            AFTER UPDATE ON docs BEGIN
              INSERT INTO docs_fts(docs_fts,rowid,title,body) VALUES('delete', old.rowid, old.title, old.body);
              INSERT INTO docs_fts(rowid,title,body) VALUES (new.rowid,new.title,new.body);
            END;""")
        _conn.commit()

def _conn_global():
    global _conn
    return _conn

def add_doc(id:str, title:str, body:str, source:str="", tags:str=""):
    with _lock:
        c=_conn_global()
        c.execute("INSERT OR REPLACE INTO docs(id,title,body,source,tags) VALUES(?,?,?,?,?)",
                  (id,title,body,source,tags))
        c.commit()

def search(query:str, k:int=5) -> List[Tuple[str,str,str]]:
    # 返回 [(title, snippet, source)]
    with _lock:
        c=_conn_global()
        rows=c.execute("""
          SELECT d.title,d.source, snippet(docs_fts,1,'','…','…',8) AS snip
          FROM docs_fts JOIN docs d ON d.rowid=docs_fts.rowid
          WHERE docs_fts MATCH ?
          ORDER BY rank LIMIT ?;
        """,(query,k)).fetchall()
        return [(r["title"], r["snip"], r["source"]) for r in rows]
