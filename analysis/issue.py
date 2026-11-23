from collections import Counter
from fractions import Fraction
from hashlib import sha256
from sqlite3 import Connection
from uuid import uuid4

from analysis.certificates import Certificate, CycleRows, Envelope, ResponseBand, encode_certificate
from analysis.completions import CompletionCertificate, encode_completion
from analysis.cycles import closed_cycles
from analysis.station_review import StationReview, review_frozen_revision
from records.runs import lookup_number


def initialize_issuance(db: Connection) -> None:
    with db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS issued_certificates (
                revision_id INTEGER PRIMARY KEY REFERENCES revisions(revision_id),
                certificate_id TEXT NOT NULL UNIQUE,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                version INTEGER NOT NULL,
                body_sha256 TEXT NOT NULL,
                body BLOB NOT NULL
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS issued_completions (
                revision_id INTEGER PRIMARY KEY REFERENCES revisions(revision_id),
                certificate_id TEXT NOT NULL UNIQUE,
                run_id TEXT NOT NULL REFERENCES runs(run_id),
                version INTEGER NOT NULL,
                body_sha256 TEXT NOT NULL,
                body BLOB NOT NULL
            )
        ''')


def _ledger(tensions: tuple[Fraction, ...], start: Fraction) -> CycleRows:
    counts = Counter()
    for first, span in closed_cycles((start, *tensions)):
        # Index 0 is the permanent left endpoint, and index 1 is the shared seam.
        owner = 'front' if first == 1 else 'rear'
        counts[owner, span] += 1
    return tuple((owner, span, count) for (owner, span), count in sorted(counts.items()))


def _response(review: StationReview) -> tuple[ResponseBand, ...]:
    tensions = tuple(point.tension for point in review.reversals)
    seam = review.seam
    # A deletion preserves alternation. In any active window [x, a, b, c],
    # a > x and a > b. Its variable comparison is a-b <= a-x, or x <= b.
    # Every other comparison uses station tensions alone. The same sequence
    # of deletions therefore holds throughout each right-closed start band.
    cuts = sorted({value for value in tensions if 0 <= value < seam})
    last_cut = cuts[-1] if cuts else Fraction(0)
    samples = [(cut, cut) for cut in cuts]
    samples.append((seam, (last_cut + seam) / 2))
    bands: list[ResponseBand] = []
    for upper, start in samples:
        rows = _ledger(tensions, start)
        band = ResponseBand(upper, rows)
        if bands and bands[-1].rows == rows:
            bands[-1] = band
        else:
            bands.append(band)
    return tuple(bands)


def _find_issued(db: Connection, number: int) -> Envelope | None:
    row = db.execute(
        '''SELECT version, certificate_id, run_id, revision_id, body_sha256, body
           FROM issued_certificates WHERE revision_id = ?''',
        (number,),
    ).fetchone()
    return None if row is None else Envelope(*row)


def get_issued_certificate(db: Connection, revision_id: int) -> Envelope:
    number = lookup_number(revision_id, 'issued revision')
    envelope = _find_issued(db, number)
    if envelope is None:
        raise KeyError(f'certificate not issued for revision: {number}')
    return envelope


def issue(db: Connection, revision_id: int) -> Envelope:
    number = lookup_number(revision_id, 'revision')
    existing = _find_issued(db, number)
    if existing is not None:
        return existing
    review = review_frozen_revision(db, number)
    certificate = Certificate(
        uuid4().hex, review.revision.run_id, number, review.seam,
        review.summary.rows, _response(review),
    )
    body = encode_certificate(certificate)
    digest = sha256(body).hexdigest()
    with db:
        db.execute(
            '''INSERT INTO issued_certificates
               (revision_id, certificate_id, run_id, version, body_sha256, body)
               VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(revision_id) DO NOTHING''',
            (number, certificate.certificate_id, certificate.run_id, 1, digest, body),
        )
    return get_issued_certificate(db, number)


def _find_completion(db: Connection, number: int) -> Envelope | None:
    row = db.execute(
        '''SELECT version, certificate_id, run_id, revision_id, body_sha256, body
           FROM issued_completions WHERE revision_id = ?''',
        (number,),
    ).fetchone()
    return None if row is None else Envelope(*row)


def get_issued_completion(db: Connection, revision_id: int) -> Envelope:
    number = lookup_number(revision_id, 'issued completion revision')
    envelope = _find_completion(db, number)
    if envelope is None:
        raise KeyError(f'completion not issued for revision: {number}')
    return envelope


def issue_completion(db: Connection, revision_id: int) -> Envelope:
    """Issue the frozen V2 completion piece, reissuing the same identity and bytes."""
    number = lookup_number(revision_id, 'revision')
    existing = _find_completion(db, number)
    if existing is not None:
        return existing
    review = review_frozen_revision(db, number)
    tensions = tuple(point.tension for point in review.reversals)
    endpoint = tensions[-1]
    if tensions[-2] <= endpoint:
        raise ValueError('the last rear segment must descend strictly')
    certificate = CompletionCertificate(
        uuid4().hex, review.revision.run_id, number, review.seam, endpoint, tensions,
        start_max=review.seam, peak_min=endpoint, end_min=Fraction(0),
    )
    body = encode_completion(certificate)
    digest = sha256(body).hexdigest()
    with db:
        db.execute(
            '''INSERT INTO issued_completions
               (revision_id, certificate_id, run_id, version, body_sha256, body)
               VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(revision_id) DO NOTHING''',
            (number, certificate.certificate_id, certificate.run_id, 2, digest, body),
        )
    return get_issued_completion(db, number)
