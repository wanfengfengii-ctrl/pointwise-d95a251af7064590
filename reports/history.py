from dataclasses import dataclass
from fractions import Fraction
from sqlite3 import Connection

from handoff.ledger import PrefixRecord
from handoff.loads import PrefixLoad, unpack_tension
from intake.receipts import Receipt
from records.runs import lookup_number
from reports.assignments import MaintenanceRow


@dataclass(frozen=True)
class StoredReport:
    report_id: int
    prefix: PrefixRecord
    receipt: Receipt
    rear_seam: Fraction
    rows: tuple[MaintenanceRow, ...]


@dataclass(frozen=True)
class StoredCompletion:
    report_id: int
    prefix: PrefixRecord
    receipt: Receipt
    rear_seam: Fraction
    rows: tuple[MaintenanceRow, ...]
    peak: Fraction
    end: Fraction


def _load_rows(db: Connection, number: int) -> tuple[MaintenanceRow, ...]:
    stored_rows = db.execute(
        'SELECT owner, span, count FROM maintenance_rows WHERE report_id = ?', (number,),
    )
    details = [
        MaintenanceRow(owner, unpack_tension(span), int(count)) for owner, span, count in stored_rows
    ]
    details.sort(key=lambda detail: (detail.owner, detail.span))
    return tuple(details)


def read(db: Connection, report_id: int) -> StoredReport:
    number = lookup_number(report_id, 'report')
    row = db.execute(
        '''SELECT s.run_id, s.prefix_id, s.prefix_start, s.prefix_seam, s.prefix_corrects,
                  s.receipt_id, s.receipt_version, s.certificate_id, s.revision_id,
                  s.body_sha256, s.rear_seam
           FROM reports AS r JOIN report_sources AS s ON s.report_id = r.report_id
           WHERE r.report_id = ?''',
        (number,),
    ).fetchone()
    if row is None:
        raise KeyError(f'report not found: {number}')
    (run_id, prefix_id, start, prefix_seam, corrects, receipt_id, version,
     certificate, revision, digest, rear_seam) = row
    prefix = PrefixRecord(
        prefix_id, run_id, PrefixLoad(unpack_tension(start), unpack_tension(prefix_seam)), corrects,
    )
    receipt = Receipt(receipt_id, version, certificate, run_id, revision, digest)
    return StoredReport(number, prefix, receipt, unpack_tension(rear_seam), _load_rows(db, number))


def read_completion(db: Connection, report_id: int) -> StoredCompletion:
    number = lookup_number(report_id, 'completion report')
    row = db.execute(
        '''SELECT s.run_id, s.prefix_id, s.prefix_start, s.prefix_seam, s.prefix_corrects,
                  s.receipt_id, s.receipt_version, s.certificate_id, s.revision_id,
                  s.body_sha256, s.rear_seam, s.peak, s.end_load
           FROM reports AS r JOIN completion_sources AS s ON s.report_id = r.report_id
           WHERE r.report_id = ?''',
        (number,),
    ).fetchone()
    if row is None:
        raise KeyError(f'completion report not found: {number}')
    (run_id, prefix_id, start, prefix_seam, corrects, receipt_id, version,
     certificate, revision, digest, rear_seam, peak, end_load) = row
    prefix = PrefixRecord(
        prefix_id, run_id, PrefixLoad(unpack_tension(start), unpack_tension(prefix_seam)), corrects,
    )
    receipt = Receipt(receipt_id, version, certificate, run_id, revision, digest)
    return StoredCompletion(
        number, prefix, receipt, unpack_tension(rear_seam), _load_rows(db, number),
        unpack_tension(peak), unpack_tension(end_load),
    )
