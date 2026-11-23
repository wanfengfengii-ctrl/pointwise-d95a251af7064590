from dataclasses import dataclass
from sqlite3 import Connection

from records.runs import lookup_number


@dataclass(frozen=True)
class Receipt:
    receipt_id: int
    version: int
    certificate_id: str
    run_id: str
    revision_id: int
    body_sha256: str


def initialize_receipts(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id INTEGER PRIMARY KEY,
            version INTEGER NOT NULL,
            certificate_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            revision_id INTEGER NOT NULL CHECK (revision_id > 0),
            body_sha256 TEXT NOT NULL
        )
    ''')


def create_receipt(db: Connection, *, version: int, certificate_id: str, run_id: str,
                   revision_id: int, body_sha256: str) -> int:
    cursor = db.execute(
        '''INSERT INTO receipts (version, certificate_id, run_id, revision_id, body_sha256)
           VALUES (?, ?, ?, ?, ?)''',
        (version, certificate_id, run_id, revision_id, body_sha256),
    )
    return cursor.lastrowid


def get_receipt(db: Connection, receipt_id: int) -> Receipt:
    number = lookup_number(receipt_id, 'receipt')
    row = db.execute(
        '''SELECT version, certificate_id, run_id, revision_id, body_sha256
           FROM receipts WHERE receipt_id = ?''',
        (number,),
    ).fetchone()
    if row is None:
        raise KeyError(f'receipt not found: {number}')
    return Receipt(number, *row)
