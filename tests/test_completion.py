import json
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256

from analysis.completions import decode_completion
from analysis.issue import (
    get_issued_completion,
    initialize_issuance,
    issue,
    issue_completion,
)
from handoff.corrections import register
from intake.accept import receive, receive_completion
from intake.archive import get_original
from intake.envelopes import verify_completion_envelope
from intake.receipts import get_receipt
from records.freeze import record
from reports.history import read, read_completion
from reports.publish import ReportWriteError, publish, publish_completion
from tests.support import RUN, DeskCase, bill, counts, scenario


class CompletionIssueTests(DeskCase):
    def test_completion_piece_freezes_ordered_turns(self):
        revision = self.rear((6, 2))
        piece = issue_completion(self.source, revision.revision_id)
        self.assertEqual(piece.version, 2)
        again = issue_completion(self.source, revision.revision_id)
        self.assertEqual(again, piece)
        certificate = decode_completion(piece.body)
        self.assertEqual(
            (certificate.run_id, certificate.revision_id, certificate.seam, certificate.endpoint),
            (RUN, revision.revision_id, Fraction(6), Fraction(2)),
        )
        self.assertEqual(certificate.reversals, (Fraction(6), Fraction(2)))
        self.assertEqual(
            (certificate.start_max, certificate.peak_min, certificate.end_min),
            (Fraction(6), Fraction(2), Fraction(0)),
        )
        self.assertNotIn(b'station-time', piece.body)
        self.assertEqual(get_issued_completion(self.source, revision.revision_id), piece)
        scenario('c1', {'rear_kn': [6, 2]},
                 [['6', 1], ['2', 1]],
                 [[str(v), 1] for v in certificate.reversals],
                 {'version': 2, 'endpoint': '2'},
                 {'version': piece.version, 'endpoint': str(certificate.endpoint)},
                 ['analysis/completions.py', 'analysis/issue.py'],
                 'The V2 piece binds seam, endpoint and the ordered rear reversals and replays identically.')

    def test_v1_and_v2_issue_independently_for_one_revision(self):
        revision = self.rear((6, 2, 6, 1))
        v1 = issue(self.source, revision.revision_id)
        v2 = issue_completion(self.source, revision.revision_id)
        self.assertEqual(v1.version, 1)
        self.assertEqual(v2.version, 2)
        self.assertNotEqual(v1.certificate_id, v2.certificate_id)
        self.assertNotEqual(v1.body, v2.body)
        self.assertEqual(issue(self.source, revision.revision_id), v1)
        self.assertEqual(issue_completion(self.source, revision.revision_id), v2)

    def test_last_segment_must_descend_strictly(self):
        revision = self.rear((6, 2, 3))
        before = self.source_counts()
        with self.assertRaisesRegex(ValueError, 'descend strictly'):
            issue_completion(self.source, revision.revision_id)
        with self.assertRaises(KeyError):
            get_issued_completion(self.source, revision.revision_id)
        self.assertEqual(self.source_counts(), before)

    def test_plateau_revision_still_ends_with_a_descent(self):
        revision = record(
            self.source, RUN, 6,
            [(1, 6), (2, 6), (3, Fraction(5, 2)), (4, Fraction(5, 2)),
             (5, 3), (6, 3), (7, 2)],
        )
        piece = issue_completion(self.source, revision.revision_id)
        certificate = decode_completion(piece.body)
        self.assertEqual(certificate.reversals,
                         (Fraction(6), Fraction(5, 2), Fraction(3), Fraction(2)))


class CompletionIntakeTests(DeskCase):
    def _completion_piece(self, values=(6, 2)):
        revision = self.rear(values)
        return revision, issue_completion(self.source, revision.revision_id)

    def test_receive_completion_returns_v2_receipt_and_bytes(self):
        revision, piece = self._completion_piece()
        receipt = receive_completion(self.desk, piece)
        self.assertEqual(get_receipt(self.desk, receipt).version, 2)
        self.assertEqual(get_original(self.desk, receipt), piece.body)
        self.assertEqual(verify_completion_envelope(piece).certificate.revision_id,
                         revision.revision_id)

    def test_version_mixing_is_rejected(self):
        _, v2 = self._completion_piece()
        v1 = issue(self.source, self.rear().revision_id)
        with self.assertRaisesRegex(ValueError, 'version'):
            receive_completion(self.desk, v1)
        with self.assertRaisesRegex(ValueError, 'version'):
            receive(self.desk, v2)
        self.assertEqual(self.receipt_counts(), (0, 0))

    def test_corrupt_completion_leaves_no_partial_piece(self):
        _, piece = self._completion_piece()
        before = self.receipt_counts()
        payload = json.loads(piece.body)
        del payload['endpoint']
        invalid = json.dumps(payload).encode('utf-8')
        broken = replace(piece, body=invalid, body_sha256=sha256(invalid).hexdigest())
        with self.assertRaisesRegex(ValueError, 'fields'):
            receive_completion(self.desk, broken)
        with self.assertRaisesRegex(ValueError, 'digest'):
            receive_completion(self.desk, replace(piece, body=piece.body + b'!'))
        for changed in (replace(piece, run_id='another-trial'),
                        replace(piece, certificate_id='f' * 32)):
            with self.assertRaisesRegex(ValueError, 'origin'):
                receive_completion(self.desk, changed)
        self.assertEqual(self.receipt_counts(), before)

    def test_tampered_reversal_domain_is_rejected(self):
        _, piece = self._completion_piece()
        payload = json.loads(piece.body)
        payload['reversals'] = ['6/1', '3/1']
        invalid = json.dumps(payload).encode('utf-8')
        broken = replace(piece, body=invalid, body_sha256=sha256(invalid).hexdigest())
        with self.assertRaisesRegex(ValueError, 'endpoint'):
            receive_completion(self.desk, broken)
        self.assertEqual(self.receipt_counts(), (0, 0))


class CompletionReportTests(DeskCase):
    def _captured(self, values=(6, 2)):
        revision = self.rear(values)
        piece = issue_completion(self.source, revision.revision_id)
        receipt = receive_completion(self.desk, piece)
        self.close_source()
        return revision, piece, receipt

    def test_empty_ledger_is_signed_with_both_sources(self):
        _, piece, receipt = self._captured()
        prefix = register(self.desk, RUN, 0, 6)
        number = publish_completion(self.desk, prefix, receipt, 5, '9/4')
        report = read_completion(self.desk, number)
        self.assertEqual(bill(report), ())
        self.assertEqual(report.prefix.prefix_id, prefix)
        self.assertEqual(report.receipt, get_receipt(self.desk, receipt))
        self.assertEqual(report.receipt.version, 2)
        self.assertEqual((report.peak, report.end), (Fraction(5), Fraction(9, 4)))
        self.assertEqual(report.rear_seam, Fraction(6))
        scenario('c2', {'rear_kn': [6, 2], 'peak_kn': '5', 'end_kn': '9/4'},
                 [], bill(report),
                 [prefix, receipt, piece.revision_id],
                 [report.prefix.prefix_id, report.receipt.receipt_id,
                  report.receipt.revision_id],
                 ['reports/completion_select.py', 'reports/publish.py', 'reports/history.py'],
                 'An empty completion ledger is still signed and keeps prefix and V2 receipt.')

    def test_reopen_reads_original_numbers_and_stored_values(self):
        _, _, receipt = self._captured((6, 1, 5, 2))
        prefix = register(self.desk, RUN, 0, 6)
        number = publish_completion(self.desk, prefix, receipt, 5, 0)
        self.reopen_desk()
        report = read_completion(self.desk, number)
        self.assertEqual(bill(report), (('rear', '3', 1), ('rear', '4', 1)))
        self.assertEqual((report.peak, report.end), (Fraction(5), Fraction(0)))
        self.assertEqual(report.prefix.prefix_id, prefix)
        self.assertEqual(report.receipt.receipt_id, receipt)

    def test_seam_owned_once_by_front_and_appended_points_by_rear(self):
        _, _, receipt = self._captured()
        front = register(self.desk, RUN, 0, 6)
        rear = register(self.desk, RUN, 4, 6)
        front_report = read_completion(
            self.desk, publish_completion(self.desk, front, receipt, 6, 0))
        rear_report = read_completion(
            self.desk, publish_completion(self.desk, rear, receipt, 6, 0))
        self.assertEqual(bill(front_report), (('front', '4', 1),))
        self.assertEqual(bill(rear_report), (('rear', '4', 1),))

    def test_same_rational_range_merges_into_one_counted_row(self):
        _, _, receipt = self._captured((6, 4, 5, 2))
        prefix = register(self.desk, RUN, 0, 6)
        report = read_completion(
            self.desk, publish_completion(self.desk, prefix, receipt, 3, 0))
        self.assertEqual(bill(report), (('rear', '1', 2),))

    def test_illegal_loads_are_rejected_without_rows(self):
        _, _, receipt = self._captured()
        prefix = register(self.desk, RUN, 0, 6)
        for peak, end in ((2, 0), (1, 0), (5, 5), (5, 6), (5, -1)):
            with self.subTest(peak=peak, end=end), self.assertRaises(ValueError):
                publish_completion(self.desk, prefix, receipt, peak, end)
        self.assertEqual(self.report_counts(), (0, 0, 0))

    def test_pairing_and_version_mismatches_are_rejected(self):
        other = self.rear(run_id='another-trial')
        v1_piece = issue(self.source, other.revision_id)
        _, _, receipt = self._captured()
        v1_receipt = receive(self.desk, v1_piece)
        wrong_run = register(self.desk, 'another-trial', 0, 6)
        with self.assertRaisesRegex(ValueError, 'different trials'):
            publish_completion(self.desk, wrong_run, receipt, 5, 0)
        wrong_seam = register(self.desk, RUN, 0, 5)
        with self.assertRaisesRegex(ValueError, 'seam'):
            publish_completion(self.desk, wrong_seam, receipt, 5, 0)
        good = register(self.desk, RUN, 0, 6)
        with self.assertRaisesRegex(ValueError, 'V2'):
            publish_completion(self.desk, good, v1_receipt, 5, 0)
        self.assertEqual(self.report_counts(), (0, 0, 0))

    def test_legacy_entry_refuses_v2_receipt(self):
        _, _, v2_receipt = self._captured()
        prefix = register(self.desk, RUN, 0, 6)
        with self.assertRaisesRegex(ValueError, 'version'):
            publish(self.desk, prefix, v2_receipt)
        self.assertEqual(self.report_counts(), (0, 0, 0))

    def test_missing_numbers_raise_key_error(self):
        _, _, receipt = self._captured()
        prefix = register(self.desk, RUN, 0, 6)
        with self.assertRaisesRegex(KeyError, 'prefix'):
            publish_completion(self.desk, 999, receipt, 5, 0)
        with self.assertRaisesRegex(KeyError, 'receipt'):
            publish_completion(self.desk, prefix, 999, 5, 0)
        with self.assertRaisesRegex(KeyError, 'completion report'):
            read_completion(self.desk, 999)
        self.assertEqual(self.report_counts(), (0, 0, 0))

    def test_failed_publish_can_be_retried_without_extra_rows(self):
        _, _, receipt = self._captured()
        prefix = register(self.desk, RUN, 0, 6)
        self.desk.execute('''
            CREATE TEMP TRIGGER fail_completion BEFORE INSERT ON main.completion_sources
            BEGIN SELECT RAISE(ABORT, 'completion snapshot blocked'); END
        ''')
        with self.assertRaises(ReportWriteError):
            publish_completion(self.desk, prefix, receipt, 5, 0)
        self.reopen_desk()
        before = counts(self.desk, 'reports', 'completion_sources', 'maintenance_rows')
        number = publish_completion(self.desk, prefix, receipt, 5, 0)
        report = read_completion(self.desk, number)
        self.assertEqual(bill(report), (('rear', '3', 1),))
        self.assertEqual(tuple(x + 1 for x in before),
                         counts(self.desk, 'reports', 'completion_sources', 'maintenance_rows'))

    def test_legacy_and_completion_reports_coexist_and_keep_separate_readers(self):
        revision = self.rear((6, 2, 6, 1))
        v1 = issue(self.source, revision.revision_id)
        v2 = issue_completion(self.source, revision.revision_id)
        v1_receipt = receive(self.desk, v1)
        v2_receipt = receive_completion(self.desk, v2)
        self.close_source()
        prefix = register(self.desk, RUN, 0, 6)
        legacy_id = publish(self.desk, prefix, v1_receipt)
        completion_id = publish_completion(self.desk, prefix, v2_receipt, 5, 0)
        legacy = read(self.desk, legacy_id)
        completion = read_completion(self.desk, completion_id)
        self.assertEqual(bill(legacy), (('front', '4', 1),))
        self.assertEqual(bill(completion), (('front', '4', 1), ('rear', '4', 1)))
        with self.assertRaises(KeyError):
            read_completion(self.desk, legacy_id)
        with self.assertRaises(KeyError):
            read(self.desk, completion_id)
        self.assertEqual(counts(self.desk, 'reports', 'report_sources',
                                'completion_sources', 'maintenance_rows'), (2, 1, 1, 3))
