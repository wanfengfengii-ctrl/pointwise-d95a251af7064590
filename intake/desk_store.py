import sqlite3
from pathlib import Path

from handoff.ledger import initialize_ledger
from intake.archive import initialize_archive
from intake.receipts import initialize_receipts
from reports.publish import initialize_reports


def initialize_desk(db: sqlite3.Connection) -> None:
    with db:
        initialize_ledger(db)
        initialize_receipts(db)
        initialize_archive(db)
        initialize_reports(db)


def open_desk(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    try:
        db.execute('PRAGMA foreign_keys = ON')
        initialize_desk(db)
    except Exception:
        db.close()
        raise
    return db
