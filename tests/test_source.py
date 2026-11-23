from fractions import Fraction

from analysis.certificates import decode_certificate
from analysis.issue import get_issued_certificate, initialize_issuance, issue
from analysis.station_review import review_frozen_revision
from records.freeze import freeze_revision, record
from records.revisions import get_revision, load_revision_samples
from records.runs import get_run, register_run
from records.samples import Sample
from records.source_store import initialize_source, open_source
from tests.support import A, RUN, SourceCase, scenario


class SourceTests(SourceCase):
    def test_fixed_revision(self):
        revision = self.rear()
        review = review_frozen_revision(self.source, revision.revision_id)
        self.assertEqual(review.revision, revision)
        self.assertEqual(tuple(item.tension for item in review.reversals), A)
        self.assertEqual(review.summary.rows, ((Fraction(4), 1),))
        envelope = issue(self.source, revision.revision_id)
        certificate = decode_certificate(envelope.body)
        self.assertEqual((certificate.run_id, certificate.revision_id, certificate.seam),
                         (RUN, revision.revision_id, Fraction(6)))
        self.assertEqual(certificate.station_rows, ((Fraction(4), 1),))
        self.assertEqual(envelope, get_issued_certificate(self.source, revision.revision_id))
        scenario('v1', {'rear_kn': A}, [['4', 1]],
                 [[str(span), count] for span, count in review.summary.rows],
                 {'revision_id': revision.revision_id, 'station_rows': [['4', 1]]},
                 {'revision_id': certificate.revision_id,
                  'station_rows': [[str(span), count] for span, count in certificate.station_rows]},
                 ['records/freeze.py', 'analysis/cycles.py', 'analysis/issue.py'],
                 'The three adjacent ranges are 4, 4, 5 kN, so the interior 4 closes once.')

    def test_duplicate_sample(self):
        original = self.rear()
        original_envelope = issue(self.source, original.revision_id)
        before = self.source_counts()
        with self.assertRaisesRegex(ValueError, 'strictly increasing'):
            record(self.source, RUN, 6, [(1, 6), (2, 2), (2, 3), (3, 6), (4, 1)])
        self.assertEqual(self.source_counts(), before)
        self.assertEqual(tuple(s.tension for s in load_revision_samples(self.source, original.revision_id)), A)
        self.assertEqual(get_issued_certificate(self.source, original.revision_id), original_envelope)

    def test_bad_sample_values(self):
        original = self.rear()
        saved = issue(self.source, original.revision_id)
        before = self.source_counts()
        batches = ([(2, 6), (1, 2)], [(1, 6), (2, None)], [(1, 6), (2, '1/0')], [], [(1, 6.0)])
        for batch in batches:
            with self.subTest(batch=batch), self.assertRaises(ValueError):
                record(self.source, RUN, 6, batch, corrects=original.revision_id)
            self.assertEqual(self.source_counts(), before)
            self.assertEqual(get_revision(self.source, original.revision_id), original)
            self.assertEqual(get_issued_certificate(self.source, original.revision_id), saved)

    def test_named_revision(self):
        old = self.rear()
        old_piece = issue(self.source, old.revision_id)
        new = self.rear((6, 3, 6, 1), corrects=old.revision_id)
        new_piece = issue(self.source, new.revision_id)
        self.assertNotEqual(old_piece.certificate_id, new_piece.certificate_id)
        self.assertEqual(get_revision(self.source, new.revision_id).corrects, old.revision_id)
        self.assertEqual(decode_certificate(new_piece.body).station_rows, ((Fraction(3), 1),))
        self.assertEqual(decode_certificate(old_piece.body).station_rows, ((Fraction(4), 1),))
        self.assertEqual(issue(self.source, old.revision_id), old_piece)
        self.assertEqual(old_piece.revision_id, old.revision_id)
        self.assertEqual(new_piece.revision_id, new.revision_id)
        before = self.source_counts()
        with self.assertRaisesRegex(ValueError, 'different trial'):
            self.rear(run_id='another-strip', corrects=old.revision_id)
        self.assertEqual(self.source_counts(), before)
        with self.assertRaises(KeyError):
            get_run(self.source, 'another-strip')

    def test_plateau_and_fraction(self):
        values = (6, 6, '3/2', '3/2', 6, 6, 1)
        rows = [(index, value, f'station-time-{index}') for index, value in enumerate(values, 1)]
        revision = record(self.source, RUN, 6, rows)
        samples = load_revision_samples(self.source, revision.revision_id)
        self.assertEqual(samples, tuple(Sample(i, Fraction(x), t) for i, x, t in rows))
        review = review_frozen_revision(self.source, revision.revision_id)
        self.assertEqual([point.sequence for point in review.reversals], [1, 3, 5, 7])
        self.assertEqual(review.summary.rows, ((Fraction(9, 2), 1),))
        piece = issue(self.source, revision.revision_id)
        self.assertNotIn(b'station-time-', piece.body)
        self.assertEqual(decode_certificate(piece.body).station_rows, ((Fraction(9, 2), 1),))

    def test_cascade_count(self):
        revision = self.rear((6, 1, 5, 2, 4, 0))
        expected = ((Fraction(2), 1), (Fraction(4), 1))
        self.assertEqual(review_frozen_revision(self.source, revision.revision_id).summary.rows, expected)
        certificate = decode_certificate(issue(self.source, revision.revision_id).body)
        self.assertEqual(certificate.station_rows, expected)

    def test_fixed_reissue(self):
        revision = self.rear()
        first = issue(self.source, revision.revision_id)
        again = issue(self.source, revision.revision_id)
        self.assertEqual((again.certificate_id, again.body), (first.certificate_id, first.body))
        self.assertEqual(self.source_counts(), (1, 4, 1))

    def test_invalid_start(self):
        for values in ((5, 2), (6, 7), (6, 6)):
            with self.subTest(values=values):
                revision = self.rear(values)
                with self.assertRaises(ValueError):
                    issue(self.source, revision.revision_id)
                with self.assertRaises(KeyError):
                    get_issued_certificate(self.source, revision.revision_id)
        with self.assertRaises(KeyError):
            issue(self.source, 999)
        self.assertEqual(self.source_counts(), (3, 6, 0))

    def test_init_keeps_source(self):
        with self.source:
            self.assertEqual(register_run(self.source, RUN, '12/2').seam, Fraction(6))
        revision = freeze_revision(self.source, RUN, enumerate(A, 1))
        original = load_revision_samples(self.source, revision.revision_id)
        certificate = issue(self.source, revision.revision_id)
        initialize_source(self.source)
        initialize_issuance(self.source)
        self.close_source()
        self.source = open_source(self.source_path)
        initialize_issuance(self.source)
        with self.assertRaisesRegex(ValueError, 'different expected seam'):
            self.rear(seam=5)
        self.assertEqual(get_run(self.source, RUN).seam, Fraction(6))
        self.assertEqual(get_revision(self.source, revision.revision_id), revision)
        self.assertEqual(load_revision_samples(self.source, revision.revision_id), original)
        self.assertEqual(issue(self.source, revision.revision_id), certificate)
        self.assertEqual(self.source_counts(), (1, 4, 1))
