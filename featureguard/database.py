import json, sqlite3
from pathlib import Path
DB_PATH = Path(__file__).resolve().parent.parent / "featureguard.db"

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            success INTEGER NOT NULL,
            value REAL NOT NULL,
            metadata TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
        db.commit()

def save_event(event_name, feature_name, success, value, metadata):
    with connect() as db:
        cur = db.execute(
            "INSERT INTO events(event_name, feature_name, success, value, metadata) VALUES(?,?,?,?,?)",
            (event_name, feature_name, int(success), value, json.dumps(metadata))
        )
        db.commit()
        return cur.lastrowid

def recent_events(limit=100):
    with connect() as db:
        rows = db.execute(
            "SELECT id,event_name,feature_name,success,value,metadata,created_at FROM events ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item["metadata"])
        item["success"] = bool(item["success"])
        result.append(item)
    return result

def event_summary():
    with connect() as db:
        rows = db.execute("""
            SELECT feature_name, COUNT(*) AS events,
                   SUM(success) AS successes,
                   ROUND(AVG(value), 3) AS average_value
            FROM events GROUP BY feature_name ORDER BY events DESC
        """).fetchall()
    return [dict(row) for row in rows]
