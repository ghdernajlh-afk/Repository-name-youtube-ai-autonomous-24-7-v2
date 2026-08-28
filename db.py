import sqlite3, os, json
from pathlib import Path
DB=Path("data/agent.db")
DB.parent.mkdir(parents=True,exist_ok=True)

def conn():
    c=sqlite3.connect(DB, timeout=30)
    c.row_factory=sqlite3.Row
    return c

def init():
    with conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY, value TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT UNIQUE NOT NULL,
            language TEXT NOT NULL,
            status TEXT NOT NULL,
            title TEXT,
            description TEXT,
            script TEXT,
            video_path TEXT,
            thumbnail_path TEXT,
            youtube_id TEXT,
            sources TEXT,
            error TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            published_at DATETIME)""")

def setting(k, default=None):
    with conn() as c:
        r=c.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone()
        return r["value"] if r else default

def set_setting(k,v):
    with conn() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))

def add_job(topic,language):
    with conn() as c:
        try:
            r=c.execute("INSERT INTO jobs(topic,language,status) VALUES(?,?,?)",(topic,language,"queued"))
            return r.lastrowid
        except sqlite3.IntegrityError:
            return None

def update_job(i,**kw):
    allowed={"status","title","description","script","video_path","thumbnail_path","youtube_id","sources","error","published_at"}
    kw={k:v for k,v in kw.items() if k in allowed}
    if not kw:return
    with conn() as c:
        c.execute("UPDATE jobs SET "+",".join(f"{k}=?" for k in kw)+" WHERE id=?",(*kw.values(),i))

def get_job(i):
    with conn() as c:
        r=c.execute("SELECT * FROM jobs WHERE id=?",(i,)).fetchone()
        return dict(r) if r else None

def jobs(limit=100):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM jobs ORDER BY id DESC LIMIT ?",(limit,))]

def recent_topics(limit=30):
    with conn() as c:
        return [r["topic"] for r in c.execute("SELECT topic FROM jobs ORDER BY id DESC LIMIT ?",(limit,))]

def jobs_today():
    with conn() as c:
        return c.execute("SELECT COUNT(*) n FROM jobs WHERE date(created_at)=date('now')").fetchone()["n"]
