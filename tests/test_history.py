from fractions import Fraction
from sqlite3 import IntegrityError

from handoff.corrections import register
from handoff.ledger import get_prefix
from intake.archive import get_original
from intake.desk_store import initialize_desk
from intake.receipts import get_receipt
from reports.history import read
from reports.publish import ReportWriteError, publish
from tests.support import A, RUN, DeskCase, bill, counts, scenario


class HistoryTests(DeskCase):
    def _signed_original(self):
        _, piece, receipt = self.capture()
        self.close_source()
        prefix = register(self.desk, RUN, 0, 6)
        report = read(self.desk, publish(self.desk, prefix, receipt))
        self.assertEqual(bill(report), (('front', '4', 1),))
        return piece, report

    def _correct_and_publish(self, original):
        prefix = register(self.desk, RUN, 4, 6, corrects=original.prefix.prefix_id)
        return read(self.desk, publish(self.desk, prefix, original.receipt.receipt_id))

    def test_corrected_prefix(self):
        piece, original = self._signed_original()
        corrected = self._correct_and_publish(original)
        self.assertNotEqual(original.report_id, corrected.report_id)
        self.assertNotEqual(original.prefix.prefix_id, corrected.prefix.prefix_id)
        self.assertEqual(corrected.prefix.corrects, original.prefix.prefix_id)
        self.assertEqual(corrected.receipt, original.receipt)
        self.assertEqual(corrected.receipt.certificate_id, piece.certificate_id)
        self.assertEqual(bill(corrected), (('rear', '4', 1),))
        self.reopen_desk()
        old = read(self.desk, original.report_id)
        new = read(self.desk, corrected.report_id)
        self.assertEqual((old, new), (original, corrected))
        self.assertEqual((old.prefix.load.start, new.prefix.load.start), (Fraction(0), Fraction(4)))
        self.assertEqual(get_original(self.desk, old.receipt.receipt_id), piece.body)
        scenario('v7', {'starts_kn': ['0', '4'], 'rear_kn': A},
                 [(('front', '4', 1),), (('rear', '4', 1),)], [bill(old), bill(new)],
                 [original.prefix.prefix_id, corrected.prefix.prefix_id, original.receipt.receipt_id],
                 [old.prefix.prefix_id, new.prefix.prefix_id, new.receipt.receipt_id],
                 ['handoff/corrections.py', 'reports/reconcile.py', 'reports/publish.py', 'reports/history.py'],
                 'The first four-point window closes at start 0 only. Each signed number retains its sources.')

    def test_foreign_correction(self):
        original = register(self.desk, RUN, 0, 6)
        before = get_prefix(self.desk, original)
        with self.assertRaisesRegex(ValueError, 'different trials'):
            register(self.desk, 'other-strip', 4, 6, corrects=original)
        with self.assertRaisesRegex(KeyError, 'prefix'):
            register(self.desk, RUN, 4, 6, corrects=999)
        self.assertEqual(get_prefix(self.desk, original), before)
        self.assertEqual(counts(self.desk, 'prefixes'), (1,))

    def test_old_prefix_selection(self):
        _, original = self._signed_original()
        corrected = self._correct_and_publish(original)
        republished = read(self.desk, publish(self.desk, original.prefix.prefix_id,
                                             original.receipt.receipt_id))
        self.assertNotIn(republished.report_id, (original.report_id, corrected.report_id))
        self.assertEqual(republished.prefix, original.prefix)
        self.assertEqual(republished.prefix.load.start, Fraction(0))
        self.assertEqual(republished.receipt, original.receipt)
        self.assertEqual(bill(republished), (('front', '4', 1),))
        self.assertEqual(bill(corrected), (('rear', '4', 1),))

    def test_missing_report(self):
        _, original = self._signed_original()
        self.reopen_desk()
        with self.assertRaisesRegex(KeyError, 'report not found'):
            read(self.desk, original.report_id + 1)
        self.assertEqual(read(self.desk, original.report_id), original)

    def test_init_keeps_desk(self):
        piece, original = self._signed_original()
        corrected = self._correct_and_publish(original)
        initialize_desk(self.desk)
        initialize_desk(self.desk)
        self.reopen_desk()
        self.assertEqual(self.report_counts(), (2, 2, 2))
        self.assertEqual(self.receipt_counts(), (1, 1))
        self.assertEqual(get_prefix(self.desk, original.prefix.prefix_id), original.prefix)
        self.assertEqual(get_prefix(self.desk, corrected.prefix.prefix_id), corrected.prefix)
        self.assertEqual(get_receipt(self.desk, original.receipt.receipt_id), original.receipt)
        self.assertEqual(get_original(self.desk, original.receipt.receipt_id), piece.body)
        self.assertEqual(read(self.desk, original.report_id), original)
        self.assertEqual(read(self.desk, corrected.report_id), corrected)

    def test_failed_publish(self):
        _, original = self._signed_original()
        prefix = register(self.desk, RUN, 4, 6, corrects=original.prefix.prefix_id)
        self.desk.execute('''
            CREATE TEMP TRIGGER fail_sources BEFORE INSERT ON main.report_sources
            BEGIN SELECT RAISE(ABORT, 'fixture refused source snapshot'); END
        ''')
        with self.assertRaises(ReportWriteError) as failure:
            publish(self.desk, prefix, original.receipt.receipt_id)
        self.assertIsInstance(failure.exception.__cause__, IntegrityError)
        self.assertIn('fixture refused source snapshot', str(failure.exception.__cause__))
        self.assertEqual(self.report_counts(), (1, 1, 1))
        self.reopen_desk()
        self.assertEqual(self.report_counts(), (1, 1, 1))
        self.assertEqual(read(self.desk, original.report_id), original)

    def test_publish_rollback(self):
        _, original = self._signed_original()
        prefix = register(self.desk, RUN, 4, 6, corrects=original.prefix.prefix_id)
        self.desk.execute('CREATE TEMP TABLE fixture_allowed (report_id INTEGER PRIMARY KEY)')
        self.desk.execute('''
            CREATE TEMP TABLE fixture_gate (
                report_id INTEGER REFERENCES fixture_allowed(report_id) DEFERRABLE INITIALLY DEFERRED
            )
        ''')
        self.desk.execute('''
            CREATE TEMP TRIGGER gate_commit AFTER INSERT ON main.maintenance_rows
            BEGIN INSERT INTO fixture_gate (report_id) VALUES (NEW.report_id); END
        ''')
        before = self.report_counts()
        self.assertEqual(before, (1, 1, 1))
        with self.assertRaises(ReportWriteError) as failure:
            publish(self.desk, prefix, original.receipt.receipt_id)
        self.assertIsInstance(failure.exception.__cause__, IntegrityError)
        self.assertIn('FOREIGN KEY', str(failure.exception.__cause__))
        self.assertFalse(self.desk.in_transaction)
        self.assertEqual(counts(self.desk, 'fixture_gate'), (0,))
        self.assertEqual(self.report_counts(), before)
        self.reopen_desk()
        after = self.report_counts()
        historical = read(self.desk, original.report_id)
        self.assertEqual(after, before)
        self.assertEqual(historical, original)
        with self.assertRaises(KeyError):
            read(self.desk, original.report_id + 1)
        self.assertEqual(get_prefix(self.desk, prefix).load.start, Fraction(4))
        recovered = read(self.desk, publish(self.desk, prefix, original.receipt.receipt_id))
        self.assertEqual(bill(recovered), (('rear', '4', 1),))
        scenario('v8.publish_rollback', {'prefix_id': prefix, 'receipt_id': original.receipt.receipt_id},
                 before, after, (('front', '4', 1),), bill(historical),
                 ['handoff/corrections.py', 'reports/publish.py', 'reports/history.py'],
                 'A deferred foreign key fails at commit. Reopen and count heads, snapshots and detail rows.')
