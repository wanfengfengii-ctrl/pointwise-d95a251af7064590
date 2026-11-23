from sqlite3 import Connection

from records.runs import lookup_number


def initialize_archive(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS archived_originals (
            receipt_id INTEGER PRIMARY KEY REFERENCES receipts(receipt_id),
            body BLOB NOT NULL
        )
    ''')


def store_original(db: Connection, receipt_id: int, body: bytes) -> None:
    db.execute('INSERT INTO archived_originals (receipt_id, body) VALUES (?, ?)', (receipt_id, body))


def get_original(db: Connection, receipt_id: int) -> bytes:
    number = lookup_number(receipt_id, 'original receipt')
    row = db.execute(
        'SELECT body FROM archived_originals WHERE receipt_id = ?', (number,),
    ).fetchone()
    if row is None:
        raise KeyError(f'original not found for receipt: {number}')
    return row[0]
