import json
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from string import hexdigits

from handoff.loads import pack_tension, unpack_tension
from records.runs import validate_run_id


CycleRows = tuple[tuple[str, Fraction, int], ...]


@dataclass(frozen=True)
class ResponseBand:
    upper: Fraction
    rows: CycleRows


@dataclass(frozen=True)
class Certificate:
    certificate_id: str
    run_id: str
    revision_id: int
    seam: Fraction
    station_rows: tuple[tuple[Fraction, int], ...]
    bands: tuple[ResponseBand, ...]


@dataclass(frozen=True)
class Envelope:
    version: int
    certificate_id: str
    run_id: str
    revision_id: int
    body_sha256: str
    body: bytes


def _validate_rows(rows: Iterable[tuple[str, Fraction, int]]) -> None:
    previous = None
    for owner, span, count in rows:
        if owner not in ('front', 'rear') or not isinstance(span, Fraction) or span <= 0:
            raise ValueError('invalid cycle owner or range')
        if type(count) is not int or count <= 0:
            raise ValueError('cycle count must be a positive integer')
        key = owner, span
        if previous is not None and key <= previous:
            raise ValueError('cycle ledger must be unique and sorted')
        previous = key


def validate_certificate(certificate: Certificate) -> Certificate:
    identity = certificate.certificate_id
    if type(identity) is not str or len(identity) != 32 or any(c not in hexdigits for c in identity):
        raise ValueError('invalid certificate identity')
    validate_run_id(certificate.run_id)
    if type(certificate.revision_id) is not int or not 0 < certificate.revision_id < 1 << 63:
        raise ValueError('invalid certificate revision')
    if not isinstance(certificate.seam, Fraction) or certificate.seam <= 0:
        raise ValueError('invalid certificate seam')
    _validate_rows(('rear', span, count) for span, count in certificate.station_rows)
    if not certificate.bands or certificate.bands[-1].upper != certificate.seam:
        raise ValueError('certificate response must cover the whole start domain')
    previous = None
    for band in certificate.bands:
        if not isinstance(band.upper, Fraction) or not 0 <= band.upper <= certificate.seam:
            raise ValueError('invalid response bound')
        if previous is not None:
            if band.upper <= previous.upper:
                raise ValueError('response bounds must increase strictly')
            if band.rows == previous.rows:
                raise ValueError('adjacent equal responses must share one band')
        _validate_rows(band.rows)
        previous = band
    return certificate


def encode_certificate(certificate: Certificate) -> bytes:
    validate_certificate(certificate)
    payload = {
        'certificate_id': certificate.certificate_id,
        'run_id': certificate.run_id,
        'revision_id': certificate.revision_id,
        'seam': pack_tension(certificate.seam),
        'station': [[pack_tension(span), count] for span, count in certificate.station_rows],
        'bands': [
            [pack_tension(band.upper), [[owner, pack_tension(span), count]
                                       for owner, span, count in band.rows]]
            for band in certificate.bands
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('duplicate field in certificate')
        obj[key] = value
    return obj


def _array(value: object) -> list:
    if type(value) is not list:
        raise ValueError('certificate evidence must contain arrays')
    return value


def _entry(value: object, size: int) -> list:
    entry = _array(value)
    if len(entry) != size:
        raise ValueError('incorrect evidence entry width')
    return entry


def _station_rows(wire: object) -> tuple[tuple[Fraction, int], ...]:
    rows = []
    for entry in _array(wire):
        span, count = _entry(entry, 2)
        rows.append((unpack_tension(span), count))
    return tuple(rows)


def _band(wire: object) -> ResponseBand:
    upper, ledger = _entry(wire, 2)
    rows = []
    for entry in _array(ledger):
        owner, span, count = _entry(entry, 3)
        rows.append((owner, unpack_tension(span), count))
    return ResponseBand(unpack_tension(upper), tuple(rows))


def decode_certificate(body: bytes) -> Certificate:
    if type(body) is not bytes:
        raise ValueError('certificate body must be bytes')
    try:
        payload = json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as exc:
        raise ValueError('certificate body is not valid JSON evidence') from exc
    expected = {'certificate_id', 'run_id', 'revision_id', 'seam', 'station', 'bands'}
    if type(payload) is not dict or set(payload) != expected:
        raise ValueError('certificate body has incorrect fields')
    certificate = Certificate(
        certificate_id=payload['certificate_id'],
        run_id=payload['run_id'],
        revision_id=payload['revision_id'],
        seam=unpack_tension(payload['seam']),
        station_rows=_station_rows(payload['station']),
        bands=tuple(_band(entry) for entry in _array(payload['bands'])),
    )
    return validate_certificate(certificate)
