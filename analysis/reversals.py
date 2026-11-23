from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from records.samples import Sample


@dataclass(frozen=True)
class Reversal:
    sequence: int
    tension: Fraction


def extract_reversals(samples: Iterable[Sample]) -> tuple[Reversal, ...]:
    """Read validated samples in order, using the first position of each plateau."""
    turns: list[Reversal] = []
    previous: Reversal | None = None
    direction = 0
    for sample in samples:
        point = Reversal(sample.sequence, sample.tension)
        if previous is None:
            turns.append(point)
        elif point.tension == previous.tension:
            continue
        else:
            next_direction = 1 if point.tension > previous.tension else -1
            if direction and next_direction != direction:
                turns.append(previous)
            direction = next_direction
        previous = point
    if previous is not None and direction:
        turns.append(previous)
    return tuple(turns)
