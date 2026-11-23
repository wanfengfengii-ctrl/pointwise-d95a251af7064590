from dataclasses import dataclass
from sqlite3 import Connection

from records.runs import lookup_number
from records.samples import Sample, load_samples


@dataclass(frozen=True)
class Revision:
    revision_id: int
    run_id: str
    corrects: int | None


def initialize_revisions(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS revisions (
            revision_id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES runs(run_id),
            corrects INTEGER,
            UNIQUE (run_id, revision_id),
            FOREIGN KEY (run_id, corrects) REFERENCES revisions(run_id, revision_id)
        )
    ''')


def create_revision(db: Connection, run_id: str, corrects: int | None = None) -> Revision:
    if corrects is not None:
        original = get_revision(db, corrects)
        if original.run_id != run_id:
            raise ValueError('revision correction belongs to a different trial')
    cursor = db.execute(
        'INSERT INTO revisions (run_id, corrects) VALUES (?, ?)',
        (run_id, corrects),
    )
    return Revision(cursor.lastrowid, run_id, corrects)


def get_revision(db: Connection, revision_id: int) -> Revision:
    number = lookup_number(revision_id, 'revision')
    row = db.execute(
        'SELECT run_id, corrects FROM revisions WHERE revision_id = ?', (number,),
    ).fetchone()
    if row is None:
        raise KeyError(f'revision not found: {number}')
    return Revision(number, *row)


def load_revision_samples(db: Connection, revision_id: int) -> tuple[Sample, ...]:
    revision = get_revision(db, revision_id)
    return load_samples(db, revision.revision_id)
