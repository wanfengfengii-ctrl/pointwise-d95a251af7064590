import sqlite3
from pathlib import Path

from records.revisions import initialize_revisions
from records.runs import initialize_runs
from records.samples import initialize_samples


def initialize_source(db: sqlite3.Connection) -> None:
    with db:
        initialize_runs(db)
        initialize_revisions(db)
        initialize_samples(db)


def open_source(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    try:
        db.execute('PRAGMA foreign_keys = ON')
        initialize_source(db)
    except Exception:
        db.close()
        raise
    return db
