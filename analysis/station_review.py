from dataclasses import dataclass
from fractions import Fraction
from sqlite3 import Connection

from analysis.cycles import StationCycleSummary, count_station_cycles
from analysis.reversals import Reversal, extract_reversals
from records.revisions import Revision, get_revision, load_revision_samples
from records.runs import get_run


@dataclass(frozen=True)
class StationReview:
    revision: Revision
    seam: Fraction
    reversals: tuple[Reversal, ...]
    summary: StationCycleSummary


def review_frozen_revision(db: Connection, revision_id: int) -> StationReview:
    revision = get_revision(db, revision_id)
    run = get_run(db, revision.run_id)
    turns = extract_reversals(load_revision_samples(db, revision.revision_id))
    if len(turns) < 2 or turns[0].tension != run.seam:
        raise ValueError('rear reversals must begin at the expected trial seam and change tension')
    if turns[1].tension >= run.seam:
        raise ValueError('first effective rear direction must descend from the seam')
    return StationReview(revision, run.seam, turns, count_station_cycles(turns))
