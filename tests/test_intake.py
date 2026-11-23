import json
from dataclasses import replace
from hashlib import sha256

from intake.accept import receive
from intake.archive import get_original
from intake.receipts import get_receipt
from tests.support import DeskCase


class IntakeTests(DeskCase):
    def test_wrong_origin(self):
        revision, piece, receipt = self.capture()
        before = self.receipt_counts()
        for changed in (replace(piece, run_id='another-trial'),
                        replace(piece, revision_id=revision.revision_id + 1),
                        replace(piece, certificate_id='0' * 32)):
            with self.subTest(origin=(changed.run_id, changed.revision_id, changed.certificate_id)):
                with self.assertRaisesRegex(ValueError, 'origin'):
                    receive(self.desk, changed)
                self.assertEqual(self.receipt_counts(), before)
        self.assertEqual(get_receipt(self.desk, receipt).revision_id, revision.revision_id)
        self.assertEqual(get_original(self.desk, receipt), piece.body)

    def test_bad_body(self):
        _, piece, receipt = self.capture()
        before = self.receipt_counts()
        payload = json.loads(piece.body)
        del payload['bands']
        invalid = json.dumps(payload).encode('utf-8')
        changed = replace(piece, body=invalid, body_sha256=sha256(invalid).hexdigest())
        with self.assertRaisesRegex(ValueError, 'incorrect fields'):
            receive(self.desk, changed)
        self.assertEqual(self.receipt_counts(), before)
        self.assertEqual(get_original(self.desk, receipt), piece.body)

    def test_invalid_digest_and_evidence(self):
        _, piece, receipt = self.capture()
        with self.assertRaisesRegex(ValueError, 'digest'):
            receive(self.desk, replace(piece, body=piece.body + b' '))
        with self.assertRaisesRegex(ValueError, 'version'):
            receive(self.desk, replace(piece, version=True))
        payload = json.loads(piece.body)
        payload['bands'][0][1][0][2] = True
        invalid = json.dumps(payload).encode('utf-8')
        with self.assertRaisesRegex(ValueError, 'positive integer'):
            receive(self.desk, replace(piece, body=invalid, body_sha256=sha256(invalid).hexdigest()))
        self.assertEqual(self.receipt_counts(), (1, 1))
        self.assertEqual(get_original(self.desk, receipt), piece.body)

    def test_archive_write_failure_rolls_back_receipt(self):
        _, piece, receipt = self.capture()
        self.desk.execute('''
            CREATE TEMP TRIGGER stop_archive BEFORE INSERT ON main.archived_originals
            BEGIN SELECT RAISE(ABORT, 'archive write blocked'); END
        ''')
        from sqlite3 import IntegrityError

        with self.assertRaisesRegex(IntegrityError, 'archive write blocked'):
            receive(self.desk, piece)
        self.reopen_desk()
        self.assertEqual(self.receipt_counts(), (1, 1))
        self.assertEqual(get_original(self.desk, receipt), piece.body)
