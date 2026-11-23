from dataclasses import dataclass
from sqlite3 import Connection

from handoff.loads import PrefixLoad, pack_tension, unpack_tension
from records.runs import lookup_number


@dataclass(frozen=True)
class PrefixRecord:
    prefix_id: int
    run_id: str
    load: PrefixLoad
    corrects: int | None


def initialize_ledger(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS prefixes (
            prefix_id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL,
            start TEXT NOT NULL,
            seam TEXT NOT NULL,
            corrects INTEGER,
            UNIQUE (run_id, prefix_id),
            FOREIGN KEY (run_id, corrects) REFERENCES prefixes(run_id, prefix_id)
        )
    ''')


def insert_prefix(db: Connection, run_id: str, load: PrefixLoad,
                  corrects: int | None = None) -> int:
    cursor = db.execute(
        'INSERT INTO prefixes (run_id, start, seam, corrects) VALUES (?, ?, ?, ?)',
        (run_id, pack_tension(load.start), pack_tension(load.seam), corrects),
    )
    return cursor.lastrowid


def get_prefix(db: Connection, prefix_id: int) -> PrefixRecord:
    number = lookup_number(prefix_id, 'prefix')
    row = db.execute(
        'SELECT run_id, start, seam, corrects FROM prefixes WHERE prefix_id = ?', (number,),
    ).fetchone()
    if row is None:
        raise KeyError(f'prefix not found: {number}')
    run_id, start, seam, corrects = row
    return PrefixRecord(number, run_id, PrefixLoad(unpack_tension(start), unpack_tension(seam)), corrects)
