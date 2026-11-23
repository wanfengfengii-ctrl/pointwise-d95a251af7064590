from fractions import Fraction

from analysis.certificates import decode_certificate
from handoff.corrections import register
from handoff.ledger import get_prefix
from intake.archive import get_original
from intake.receipts import get_receipt
from reports.history import read
from reports.publish import publish
from tests.support import A, B, RUN, DeskCase, bill, counts, scenario


class ReportTests(DeskCase):
    def test_unclosed(self):
        revision, _, receipt = self.capture((6, 2))
        self.close_source()
        prefix = register(self.desk, RUN, 0, 6)
        report = read(self.desk, publish(self.desk, prefix, receipt))
        self.assertEqual(bill(report), ())
        self.assertEqual(report.prefix, get_prefix(self.desk, prefix))
        self.assertEqual(report.receipt, get_receipt(self.desk, receipt))
        self.assertEqual(report.receipt.revision_id, revision.revision_id)
        self.assertEqual(report.rear_seam, Fraction(6))
        scenario('v3', {'start_kn': '0', 'rear_kn': [6, 2]}, [], bill(report),
                 [prefix, receipt, revision.revision_id],
                 [report.prefix.prefix_id, report.receipt.receipt_id, report.receipt.revision_id],
                 ['intake/accept.py', 'reports/select.py', 'reports/publish.py', 'reports/history.py'],
                 'The shared seam leaves three distinct points, so no four-point window exists.')

    def test_receipt_pinned(self):
        first, old_piece, old_receipt = self.capture((6, 2))
        second, new_piece, new_receipt = self.capture(corrects=first.revision_id)
        self.close_source()
        self.reopen_desk()
        self.assertEqual(get_original(self.desk, old_receipt), old_piece.body)
        self.assertEqual(get_original(self.desk, new_receipt), new_piece.body)
        prefix = register(self.desk, RUN, 0, 6)
        old = read(self.desk, publish(self.desk, prefix, old_receipt))
        new = read(self.desk, publish(self.desk, prefix, new_receipt))
        self.assertEqual(bill(old), ())
        self.assertEqual(bill(new), (('front', '4', 1),))
        self.assertEqual((old.receipt.receipt_id, old.receipt.revision_id), (old_receipt, first.revision_id))
        self.assertEqual((new.receipt.receipt_id, new.receipt.revision_id), (new_receipt, second.revision_id))

    def test_seam_cycle(self):
        revision, piece, receipt = self.capture()
        self.close_source()
        measured = []
        sources = []
        selections = []
        expected = [(('front', '4', 1),), (('front', '4', 1),), (('rear', '4', 1),)]
        for start, expected_rows in zip((0, 2, 4), expected, strict=True):
            with self.subTest(start=start):
                prefix = register(self.desk, RUN, start, 6)
                number = publish(self.desk, prefix, receipt)
                report = read(self.desk, number)
                self.assertEqual(bill(report), expected_rows)
                self.assertEqual(report.prefix, get_prefix(self.desk, prefix))
                self.assertEqual(report.prefix.load.start, Fraction(start))
                self.assertEqual(report.receipt, get_receipt(self.desk, receipt))
                self.assertEqual(report.receipt.certificate_id, piece.certificate_id)
                self.assertEqual(report.receipt.revision_id, revision.revision_id)
                measured.append(bill(report))
                selections.append([prefix, receipt, revision.revision_id])
                sources.append([report.prefix.prefix_id, report.receipt.receipt_id, report.receipt.revision_id])
        scenario('v5', {'starts_kn': ['0', '2', '4'], 'rear_kn': A}, expected, measured,
                 selections, sources,
                 ['analysis/issue.py', 'reports/select.py', 'reports/reconcile.py', 'reports/history.py'],
                 'The first window closes on the front seam when 6-x >= 4. Otherwise the rear window closes.')

    def test_threshold_sides(self):
        _, _, receipt = self.capture()
        self.close_source()
        for start, owner in (('3/2', 'front'), ('2', 'front'), ('5/2', 'rear')):
            with self.subTest(start=start):
                prefix = register(self.desk, RUN, start, 6)
                report = read(self.desk, publish(self.desk, prefix, receipt))
                self.assertEqual(bill(report), ((owner, '4', 1),))
        self.assertEqual(self.report_counts(), (3, 3, 3))

    def test_zero_threshold_and_rational_precision(self):
        _, _, receipt = self.capture((6, 0, 6, 0))
        self.close_source()
        for start, owner in ((Fraction(0), 'front'), (Fraction(1, 1 << 15000), 'rear')):
            with self.subTest(owner=owner):
                prefix = register(self.desk, RUN, start, 6)
                result = read(self.desk, publish(self.desk, prefix, receipt))
                self.assertEqual(result.prefix.load.start, start)
                self.assertEqual(bill(result), ((owner, '6', 1),))

    def test_same_station_histogram(self):
        _, piece_a, receipt_a = self.capture(A)
        _, piece_b, receipt_b = self.capture(B)
        for piece in (piece_a, piece_b):
            self.assertEqual(decode_certificate(piece.body).station_rows, ((Fraction(4), 1),))
        self.close_source()
        prefix = register(self.desk, RUN, 0, 6)
        a = read(self.desk, publish(self.desk, prefix, receipt_a))
        b = read(self.desk, publish(self.desk, prefix, receipt_b))
        self.assertEqual(bill(a), (('front', '4', 1),))
        self.assertEqual(bill(b), (('rear', '4', 1),))
        self.assertEqual((a.receipt.receipt_id, b.receipt.receipt_id), (receipt_a, receipt_b))

    def test_cascade_at_seam(self):
        _, _, receipt = self.capture((6, 2, 5, 3, 6, 1))
        self.close_source()
        prefix = register(self.desk, RUN, 0, 6)
        result = read(self.desk, publish(self.desk, prefix, receipt))
        self.assertEqual(bill(result), (('front', '4', 1), ('rear', '2', 1)))

    def test_same_range_owners(self):
        _, _, receipt = self.capture((6, 2, 6, 2, 6, 1))
        self.close_source()
        prefix = register(self.desk, RUN, 0, 6)
        result = read(self.desk, publish(self.desk, prefix, receipt))
        self.assertEqual(bill(result), (('front', '4', 1), ('rear', '4', 1)))
        later = register(self.desk, RUN, 4, 6)
        other = read(self.desk, publish(self.desk, later, receipt))
        self.assertEqual(bill(other), (('rear', '4', 2),))

    def test_mismatched_join(self):
        _, _, receipt = self.capture()
        self.close_source()
        prefix = register(self.desk, RUN, 0, 5)
        with self.assertRaisesRegex(ValueError, 'seam'):
            publish(self.desk, prefix, receipt)
        self.assertEqual(self.report_counts(), (0, 0, 0))

    def test_exact_seam(self):
        _, _, receipt = self.capture()
        self.close_source()
        prefix = register(self.desk, RUN, 0, '12/2')
        good = read(self.desk, publish(self.desk, prefix, receipt))
        self.assertEqual((good.prefix.load.seam, good.rear_seam), (Fraction(6), Fraction(6)))
        self.assertEqual(bill(good), (('front', '4', 1),))
        wrong = register(self.desk, RUN, 0, 5)
        with self.assertRaises(ValueError):
            publish(self.desk, wrong, receipt)
        self.assertEqual(self.report_counts(), (1, 1, 1))

    def test_foreign_run(self):
        _, _, receipt = self.capture(run_id='another-trial')
        self.close_source()
        prefix = register(self.desk, RUN, 0, 6)
        with self.assertRaisesRegex(ValueError, 'different trials'):
            publish(self.desk, prefix, receipt)
        self.assertEqual(self.report_counts(), (0, 0, 0))

    def test_invalid_prefix(self):
        for start in (-1, 6):
            with self.subTest(start=start), self.assertRaises(ValueError):
                register(self.desk, RUN, start, 6)
        self.assertEqual(counts(self.desk, 'prefixes'), (0,))

    def test_missing_inputs(self):
        _, _, receipt = self.capture()
        self.close_source()
        prefix = register(self.desk, RUN, 0, 6)
        with self.assertRaisesRegex(KeyError, 'prefix'):
            publish(self.desk, 999, receipt)
        with self.assertRaisesRegex(KeyError, 'receipt'):
            publish(self.desk, prefix, 999)
        self.assertEqual(self.report_counts(), (0, 0, 0))
