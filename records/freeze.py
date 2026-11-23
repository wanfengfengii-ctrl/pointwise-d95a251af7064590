from collections.abc import Iterable
from sqlite3 import Connection

from handoff.loads import TensionInput
from records.revisions import Revision, create_revision
from records.runs import get_run, register_run
from records.samples import Sample, SampleInput, validate_samples, write_samples


def _freeze(db: Connection, run_id: str, batch: tuple[Sample, ...],
            corrects: int | None) -> Revision:
    revision = create_revision(db, run_id, corrects)
    write_samples(db, revision.revision_id, batch)
    return revision


def record(db: Connection, run_id: str, seam: TensionInput,
           samples: Iterable[SampleInput], *, corrects: int | None = None) -> Revision:
    """Register the trial if needed and commit one complete frozen revision."""
    batch = validate_samples(samples)
    with db:
        run = register_run(db, run_id, seam)
        revision = _freeze(db, run.run_id, batch, corrects)
    return revision


def freeze_revision(db: Connection, run_id: str, samples: Iterable[SampleInput], *,
                    corrects: int | None = None) -> Revision:
    """Freeze a batch against the expected seam of an already registered trial."""
    batch = validate_samples(samples)
    run = get_run(db, run_id)
    with db:
        revision = _freeze(db, run.run_id, batch, corrects)
    return revision
