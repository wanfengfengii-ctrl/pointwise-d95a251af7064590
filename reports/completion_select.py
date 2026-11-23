from dataclasses import dataclass
from fractions import Fraction
from sqlite3 import Connection

from analysis.completions import CompletionCertificate
from handoff.ledger import PrefixRecord, get_prefix
from handoff.loads import TensionInput, parse_tension
from handoff.seams import require_common_seam, require_same_trial
from intake.archive import get_original
from intake.envelopes import Envelope, verify_completion_envelope
from intake.receipts import Receipt, get_receipt


@dataclass(frozen=True)
class CompletionInputs:
    prefix: PrefixRecord
    receipt: Receipt
    certificate: CompletionCertificate
    peak: Fraction
    end: Fraction


def _validate_offline_loads(certificate: CompletionCertificate,
                            peak: TensionInput, end: TensionInput):
    peak_value = parse_tension(peak)
    end_value = parse_tension(end)
    endpoint = certificate.endpoint
    if not peak_value > endpoint:
        raise ValueError('reload peak must be strictly above the frozen rear endpoint')
    if end_value < 0 or end_value >= peak_value:
        raise ValueError('unload end must satisfy 0 <= end < peak')
    return peak_value, end_value


def select_completion_inputs(db: Connection, prefix_id: int, receipt_id: int,
                             peak: TensionInput, end: TensionInput) -> CompletionInputs:
    prefix = get_prefix(db, prefix_id)
    receipt = get_receipt(db, receipt_id)
    if receipt.version != 2:
        raise ValueError('completion reports require a V2 receipt')
    body = get_original(db, receipt.receipt_id)
    envelope = Envelope(
        receipt.version, receipt.certificate_id, receipt.run_id,
        receipt.revision_id, receipt.body_sha256, body,
    )
    certificate = verify_completion_envelope(envelope).certificate
    require_same_trial(prefix.run_id, certificate.run_id)
    require_common_seam(prefix.load.seam, certificate.seam)
    peak_value, end_value = _validate_offline_loads(certificate, peak, end)
    return CompletionInputs(prefix, receipt, certificate, peak_value, end_value)
