"""Version 2 exchange evidence for the offline reload (completion) work order.

A completion piece freezes a rear revision whose last segment is strictly
descending. It carries the ordered rear reversals, so the closed desk can
rebuild any continuation waveform (reload peak and unload end) without the
station database. The legal metering domain is recorded as explicit rational
conditions and exact ranges.
"""
import json
from dataclasses import dataclass
from fractions import Fraction
from string import hexdigits

from handoff.loads import pack_tension, unpack_tension
from records.runs import validate_run_id


@dataclass(frozen=True)
class CompletionCertificate:
    certificate_id: str
    run_id: str
    revision_id: int
    seam: Fraction
    endpoint: Fraction
    reversals: tuple[Fraction, ...]
    start_max: Fraction
    peak_min: Fraction
    end_min: Fraction


def validate_completion(certificate: CompletionCertificate) -> CompletionCertificate:
    identity = certificate.certificate_id
    if type(identity) is not str or len(identity) != 32 or any(c not in hexdigits for c in identity):
        raise ValueError('invalid completion certificate identity')
    validate_run_id(certificate.run_id)
    if type(certificate.revision_id) is not int or not 0 < certificate.revision_id < 1 << 63:
        raise ValueError('invalid completion revision')
    seam = certificate.seam
    endpoint = certificate.endpoint
    if not isinstance(seam, Fraction) or seam <= 0:
        raise ValueError('invalid completion seam')
    if not isinstance(endpoint, Fraction) or endpoint < 0 or endpoint >= seam:
        raise ValueError('completion endpoint must satisfy 0 <= endpoint < seam')
    reversals = certificate.reversals
    if (not isinstance(reversals, tuple) or len(reversals) < 2
            or any(not isinstance(value, Fraction) for value in reversals)):
        raise ValueError('completion must carry the ordered rear reversals')
    if reversals[0] != seam or reversals[-1] != endpoint:
        raise ValueError('completion reversals must start at the seam and end at the frozen endpoint')
    if any(left == right for left, right in zip(reversals, reversals[1:])):
        raise ValueError('completion reversals must be strict turns')
    if reversals[-2] <= endpoint:
        raise ValueError('the last rear segment must descend strictly')
    domain = certificate.start_max, certificate.peak_min, certificate.end_min
    if any(not isinstance(value, Fraction) for value in domain):
        raise ValueError('completion domain bounds must be rational')
    if certificate.start_max != seam or certificate.peak_min != endpoint or certificate.end_min != 0:
        raise ValueError('completion domain does not match the frozen seam and endpoint')
    return certificate


def encode_completion(certificate: CompletionCertificate) -> bytes:
    validate_completion(certificate)
    payload = {
        'certificate_id': certificate.certificate_id,
        'run_id': certificate.run_id,
        'revision_id': certificate.revision_id,
        'seam': pack_tension(certificate.seam),
        'endpoint': pack_tension(certificate.endpoint),
        'reversals': [pack_tension(value) for value in certificate.reversals],
        'domain': {
            'start_max': pack_tension(certificate.start_max),
            'peak_min': pack_tension(certificate.peak_min),
            'end_min': pack_tension(certificate.end_min),
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('duplicate field in completion evidence')
        obj[key] = value
    return obj


def _array(value: object) -> list:
    if type(value) is not list or not value:
        raise ValueError('completion evidence must contain nonempty arrays')
    return value


def _tensions(wire: object) -> tuple[Fraction, ...]:
    return tuple(unpack_tension(entry) for entry in _array(wire))


def decode_completion(body: bytes) -> CompletionCertificate:
    if type(body) is not bytes:
        raise ValueError('completion body must be bytes')
    try:
        payload = json.loads(body.decode('utf-8'), object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as exc:
        raise ValueError('completion body is not valid JSON evidence') from exc
    expected = {'certificate_id', 'run_id', 'revision_id', 'seam', 'endpoint', 'reversals', 'domain'}
    if type(payload) is not dict or set(payload) != expected:
        raise ValueError('completion body has incorrect fields')
    domain = payload['domain']
    if type(domain) is not dict or set(domain) != {'start_max', 'peak_min', 'end_min'}:
        raise ValueError('completion domain has incorrect fields')
    certificate = CompletionCertificate(
        certificate_id=payload['certificate_id'],
        run_id=payload['run_id'],
        revision_id=payload['revision_id'],
        seam=unpack_tension(payload['seam']),
        endpoint=unpack_tension(payload['endpoint']),
        reversals=_tensions(payload['reversals']),
        start_max=unpack_tension(domain['start_max']),
        peak_min=unpack_tension(domain['peak_min']),
        end_min=unpack_tension(domain['end_min']),
    )
    return validate_completion(certificate)
