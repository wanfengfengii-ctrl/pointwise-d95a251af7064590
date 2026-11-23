from sqlite3 import Connection

from handoff.ledger import get_prefix, insert_prefix
from handoff.loads import TensionInput, validate_prefix_load
from handoff.seams import require_same_trial
from records.runs import validate_run_id


def register(db: Connection, run_id: str, start: TensionInput, seam: TensionInput, *,
             corrects: int | None = None) -> int:
    identity = validate_run_id(run_id)
    load = validate_prefix_load(start, seam)
    with db:
        if corrects is not None:
            original = get_prefix(db, corrects)
            require_same_trial(identity, original.run_id)
        number = insert_prefix(db, identity, load, corrects)
    return number
