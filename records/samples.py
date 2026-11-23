from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from sqlite3 import Connection

from handoff.loads import TensionInput, pack_tension, parse_tension, unpack_tension


@dataclass(frozen=True)
class Sample:
    sequence: int
    tension: Fraction
    sampled_at: str | None = None


SampleInput = Sample | tuple[int, TensionInput] | tuple[int, TensionInput, str | None]


def initialize_samples(db: Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS samples (
            revision_id INTEGER NOT NULL REFERENCES revisions(revision_id),
            position INTEGER NOT NULL CHECK (position >= 0),
            sequence TEXT NOT NULL,
            tension TEXT NOT NULL,
            sampled_at TEXT,
            PRIMARY KEY (revision_id, position),
            UNIQUE (revision_id, sequence)
        )
    ''')


def validate_samples(samples: Iterable[SampleInput]) -> tuple[Sample, ...]:
    batch = []
    previous = None
    for item in samples:
        if isinstance(item, Sample):
            sequence, tension, sampled_at = item.sequence, item.tension, item.sampled_at
        elif isinstance(item, (tuple, list)) and len(item) in (2, 3):
            sequence, tension = item[:2]
            sampled_at = item[2] if len(item) == 3 else None
        else:
            raise ValueError('sample must contain a sequence and a tension')
        if type(sequence) is not int:
            raise ValueError('sample sequence must be an integer')
        if previous is not None and sequence <= previous:
            raise ValueError('sample sequences must be strictly increasing')
        if sampled_at is not None and (type(sampled_at) is not str or not sampled_at.strip()):
            raise ValueError('sample time must be nonempty text when supplied')
        batch.append(Sample(sequence, parse_tension(tension), sampled_at))
        previous = sequence
    if not batch:
        raise ValueError('a frozen revision requires at least one sample')
    return tuple(batch)


def write_samples(db: Connection, revision_id: int, samples: tuple[Sample, ...]) -> None:
    db.executemany(
        '''INSERT INTO samples (revision_id, position, sequence, tension, sampled_at)
           VALUES (?, ?, ?, ?, ?)''',
        (
            (revision_id, position, format(sample.sequence, 'x'),
             pack_tension(sample.tension), sample.sampled_at)
            for position, sample in enumerate(samples)
        ),
    )


def load_samples(db: Connection, revision_id: int) -> tuple[Sample, ...]:
    rows = db.execute(
        '''SELECT sequence, tension, sampled_at FROM samples
           WHERE revision_id = ? ORDER BY position''',
        (revision_id,),
    )
    return tuple(
        Sample(int(sequence, 16), unpack_tension(tension), sampled_at)
        for sequence, tension, sampled_at in rows
    )
