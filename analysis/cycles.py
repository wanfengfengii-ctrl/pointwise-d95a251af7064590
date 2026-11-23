from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from fractions import Fraction

from analysis.reversals import Reversal


StationRows = tuple[tuple[Fraction, int], ...]


@dataclass(frozen=True)
class StationCycleSummary:
    rows: StationRows


def closed_cycles(tensions: Iterable[Fraction]) -> Iterator[tuple[int, Fraction]]:
    """Yield the input index of the first removed point and its cycle range."""
    stack: list[tuple[int, Fraction]] = []
    for index, tension in enumerate(tensions):
        stack.append((index, tension))
        while len(stack) >= 4:
            (_, left), (first, low_or_high), (_, high_or_low), (_, right) = stack[-4:]
            span = abs(low_or_high - high_or_low)
            if span > abs(left - low_or_high) or span > abs(high_or_low - right):
                break
            del stack[-3:-1]
            yield first, span


def count_station_cycles(reversals: Iterable[Reversal]) -> StationCycleSummary:
    counts = Counter(span for _, span in closed_cycles(point.tension for point in reversals))
    return StationCycleSummary(tuple(sorted(counts.items())))
