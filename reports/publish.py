import sqlite3

from handoff.loads import pack_tension
from reports.assignments import MaintenanceRow
from reports.reconcile import reconcile
from reports.select import ReportInputs, select_report_inputs


class ReportWriteError(RuntimeError):
    """The maintenance report could not be committed."""


def initialize_reports(db: sqlite3.Connection) -> None:
    db.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            report_id INTEGER PRIMARY KEY
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS report_sources (
            report_id INTEGER PRIMARY KEY REFERENCES reports(report_id),
            run_id TEXT NOT NULL,
            prefix_id INTEGER NOT NULL REFERENCES prefixes(prefix_id),
            prefix_start TEXT NOT NULL,
            prefix_seam TEXT NOT NULL,
            prefix_corrects INTEGER,
            receipt_id INTEGER NOT NULL REFERENCES receipts(receipt_id),
            receipt_version INTEGER NOT NULL,
            certificate_id TEXT NOT NULL,
            revision_id INTEGER NOT NULL,
            body_sha256 TEXT NOT NULL,
            rear_seam TEXT NOT NULL
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS maintenance_rows (
            report_id INTEGER NOT NULL REFERENCES reports(report_id),
            owner TEXT NOT NULL CHECK (owner IN ('front', 'rear')),
            span TEXT NOT NULL,
            count TEXT NOT NULL CHECK (count GLOB '[1-9]*' AND count NOT GLOB '*[^0-9]*'),
            PRIMARY KEY (report_id, owner, span)
        )
    ''')


def _store_sources(db: sqlite3.Connection, number: int, inputs: ReportInputs) -> None:
    prefix = inputs.prefix
    receipt = inputs.receipt
    db.execute(
        '''INSERT INTO report_sources (
               report_id, run_id, prefix_id, prefix_start, prefix_seam, prefix_corrects,
               receipt_id, receipt_version, certificate_id, revision_id, body_sha256, rear_seam
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (
            number, prefix.run_id, prefix.prefix_id, pack_tension(prefix.load.start),
            pack_tension(prefix.load.seam), prefix.corrects, receipt.receipt_id,
            receipt.version, receipt.certificate_id, receipt.revision_id,
            receipt.body_sha256, pack_tension(inputs.certificate.seam),
        ),
    )


def _store_rows(db: sqlite3.Connection, number: int, rows: tuple[MaintenanceRow, ...]) -> None:
    db.executemany(
        'INSERT INTO maintenance_rows (report_id, owner, span, count) VALUES (?, ?, ?, ?)',
        ((number, row.owner, pack_tension(row.span), str(row.count)) for row in rows),
    )


def publish(db: sqlite3.Connection, prefix_id: int, receipt_id: int) -> int:
    inputs = select_report_inputs(db, prefix_id, receipt_id)
    rows = reconcile(inputs)
    try:
        with db:
            number = db.execute('INSERT INTO reports DEFAULT VALUES').lastrowid
            _store_sources(db, number, inputs)
            _store_rows(db, number, rows)
    except sqlite3.Error as exc:
        db.rollback()
        raise ReportWriteError('could not commit maintenance report') from exc
    return number
