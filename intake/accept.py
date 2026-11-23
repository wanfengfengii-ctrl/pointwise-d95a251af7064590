from sqlite3 import Connection

from intake.archive import store_original
from intake.envelopes import Envelope, verify_completion_envelope, verify_envelope
from intake.receipts import create_receipt


def receive(db: Connection, envelope: Envelope) -> int:
    verified = verify_envelope(envelope)
    origin = verified.certificate
    original = verified.envelope
    with db:
        number = create_receipt(
            db, version=original.version, certificate_id=origin.certificate_id,
            run_id=origin.run_id, revision_id=origin.revision_id, body_sha256=original.body_sha256,
        )
        store_original(db, number, original.body)
    return number


def receive_completion(db: Connection, envelope: Envelope) -> int:
    """Accept a V2 completion piece; rejection leaves no partial receipt or archive row."""
    verified = verify_completion_envelope(envelope)
    origin = verified.certificate
    original = verified.envelope
    with db:
        number = create_receipt(
            db, version=original.version, certificate_id=origin.certificate_id,
            run_id=origin.run_id, revision_id=origin.revision_id, body_sha256=original.body_sha256,
        )
        store_original(db, number, original.body)
    return number
