from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class MaintenanceRow:
    owner: str
    span: Fraction
    count: int


def aggregate_assignments(contributions: Iterable[MaintenanceRow]) -> tuple[MaintenanceRow, ...]:
    totals = Counter()
    for row in contributions:
        if row.owner not in ('front', 'rear'):
            raise ValueError('unknown maintenance shift')
        if not isinstance(row.span, Fraction) or row.span <= 0:
            raise ValueError('maintenance range must be a positive rational')
        if type(row.count) is not int or row.count <= 0:
            raise ValueError('maintenance count must be a positive integer')
        totals[row.owner, row.span] += row.count
    return tuple(
        MaintenanceRow(owner, span, count) for (owner, span), count in sorted(totals.items())
    )
