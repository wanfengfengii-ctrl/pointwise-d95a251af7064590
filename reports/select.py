from dataclasses import dataclass
from sqlite3 import Connection

from analysis.certificates import Certificate
from handoff.ledger import PrefixRecord, get_prefix
from handoff.seams import require_common_seam, require_same_trial
from intake.archive import get_original
from intake.envelopes import Envelope, verify_envelope
from intake.receipts import Receipt, get_receipt


@dataclass(frozen=True)
class ReportInputs:
    prefix: PrefixRecord
    receipt: Receipt
    certificate: Certificate


def select_report_inputs(db: Connection, prefix_id: int, receipt_id: int) -> ReportInputs:
    prefix = get_prefix(db, prefix_id)
    receipt = get_receipt(db, receipt_id)
    body = get_original(db, receipt.receipt_id)
    envelope = Envelope(
        receipt.version, receipt.certificate_id, receipt.run_id,
        receipt.revision_id, receipt.body_sha256, body,
    )
    certificate = verify_envelope(envelope).certificate
    require_same_trial(prefix.run_id, certificate.run_id)
    require_common_seam(prefix.load.seam, certificate.seam)
    return ReportInputs(prefix, receipt, certificate)
