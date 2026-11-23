from dataclasses import dataclass
from fractions import Fraction
from sqlite3 import Connection

from handoff.loads import TensionInput, pack_tension, parse_tension, unpack_tension


@dataclass(frozen=True)
class Run:
    run_id: str
    seam: Fraction


def validate_run_id(run_id: str) -> str:
    if type(run_id) is not str or not run_id or run_id != run_id.strip():
        raise ValueError('trial identity must be nonempty text without surrounding whitespace')
    return run_id


def lookup_number(value: int, kind: str) -> int:
    if type(value) is not int or not 0 < value <= (1 << 63) - 1:
        raise KeyError(f'{kind} not found: {value!r}')
    return value


def initialize_runs(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY NOT NULL,
            seam TEXT NOT NULL
        )
    ''')


def register_run(db: Connection, run_id: str, seam: TensionInput) -> Run:
    identity = validate_run_id(run_id)
    expected = parse_tension(seam)
    if expected <= 0:
        raise ValueError('trial seam must be positive')
    db.execute(
        'INSERT INTO runs (run_id, seam) VALUES (?, ?) ON CONFLICT(run_id) DO NOTHING',
        (identity, pack_tension(expected)),
    )
    registered = get_run(db, identity)
    if registered.seam != expected:
        raise ValueError('trial already has a different expected seam')
    return registered


def get_run(db: Connection, run_id: str) -> Run:
    identity = validate_run_id(run_id)
    record = db.execute('SELECT seam FROM runs WHERE run_id = ?', (identity,)).fetchone()
    if record is None:
        raise KeyError(f'trial not found: {identity}')
    return Run(identity, unpack_tension(record[0]))
