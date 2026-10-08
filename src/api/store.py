import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=lambda item: item.model_dump(mode="json"))


class Store:
    """Transactions serialize decisions and persist response receipts with job state."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as db:
            db.execute("PRAGMA journal_mode=WAL")
        with self.transaction() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    request TEXT NOT NULL,
                    snapshot TEXT NOT NULL,
                    execution TEXT,
                    decision TEXT,
                    work TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    scope TEXT NOT NULL,
                    key TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status INTEGER NOT NULL,
                    response TEXT NOT NULL,
                    PRIMARY KEY (scope, key)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS request_attempt
                    ON analyses(json_extract(request, '$.request_id'), json_extract(request, '$.attempt'));
            """)

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def read(db, analysis_id):
        row = db.execute("SELECT * FROM analyses WHERE id=?", (analysis_id,)).fetchone()
        if row is None:
            return None
        return {key: json.loads(row[key]) if row[key] is not None else None
                for key in ("request", "snapshot", "execution", "decision")} | {"id": row["id"], "work": row["work"]}

    def get(self, analysis_id):
        with self.transaction() as db:
            return self.read(db, analysis_id)

    def next_job(self):
        with self.transaction() as db:
            row = db.execute("SELECT id FROM analyses WHERE work IS NOT NULL ORDER BY created_at, rowid LIMIT 1").fetchone()
            return self.read(db, row["id"]) if row else None

    @staticmethod
    def save(db, job):
        db.execute("UPDATE analyses SET snapshot=?,execution=?,decision=?,work=? WHERE id=?", (
            dumps(job["snapshot"]), dumps(job["execution"]) if job["execution"] is not None else None,
            dumps(job["decision"]) if job["decision"] is not None else None, job["work"], job["id"],
        ))
