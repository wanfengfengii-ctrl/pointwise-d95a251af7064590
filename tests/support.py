import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis.issue import initialize_issuance, issue
from intake.accept import receive
from intake.desk_store import open_desk
from records.freeze import record
from records.source_store import open_source


RUN = 'strip-A'
A = (6, 2, 6, 1)
B = (6, 1, 5, 1)


class SourceCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        directory = self.enterContext(TemporaryDirectory(prefix='strip-ledger-test-'))
        self.directory = Path(directory)
        self.source_path = self.directory / 'source.sqlite'
        self.source = open_source(self.source_path)
        self.addCleanup(self.close_source)
        initialize_issuance(self.source)

    def close_source(self):
        if self.source is not None:
            self.source.close()
            self.source = None

    def rear(self, values=A, *, run_id=RUN, seam=6, corrects=None):
        return record(self.source, run_id, seam, enumerate(values, 1), corrects=corrects)

    def source_counts(self):
        return counts(self.source, 'revisions', 'samples', 'issued_certificates')


class DeskCase(SourceCase):
    def setUp(self):
        super().setUp()
        self.desk_path = self.directory / 'desk.sqlite'
        self.desk = open_desk(self.desk_path)
        self.addCleanup(self.close_desk)

    def close_desk(self):
        if self.desk is not None:
            self.desk.close()
            self.desk = None

    def reopen_desk(self):
        self.close_desk()
        self.desk = open_desk(self.desk_path)

    def capture(self, values=A, *, run_id=RUN, seam=6, corrects=None):
        revision = self.rear(values, run_id=run_id, seam=seam, corrects=corrects)
        envelope = issue(self.source, revision.revision_id)
        return revision, envelope, receive(self.desk, envelope)

    def report_counts(self):
        return counts(self.desk, 'reports', 'report_sources', 'maintenance_rows')

    def receipt_counts(self):
        return counts(self.desk, 'receipts', 'archived_originals')


def counts(db, *tables):
    return tuple(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in tables)


def bill(report):
    return tuple((row.owner, str(row.span), row.count) for row in report.rows)


def scenario(case_id, input_data, expected, actual, downstream_expected, downstream_actual,
             code_paths, oracle):
    evidence = {
        'case_id': case_id,
        'input': input_data,
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': code_paths,
        'oracle': oracle,
    }
    print('POINTWISE_SCENARIO ' + json.dumps(evidence, sort_keys=True, ensure_ascii=False))
