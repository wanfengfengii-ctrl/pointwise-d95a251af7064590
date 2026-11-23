from sqlite3 import Connection

from intake.archive import store_original
from intake.envelopes import Envelope, verify_envelope
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
