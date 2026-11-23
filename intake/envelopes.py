from dataclasses import dataclass
from hashlib import sha256

from analysis.certificates import Certificate, decode_certificate
from analysis.certificates import Envelope as Envelope
from analysis.completions import CompletionCertificate, decode_completion


@dataclass(frozen=True)
class VerifiedEnvelope:
    envelope: Envelope
    certificate: Certificate


@dataclass(frozen=True)
class VerifiedCompletion:
    envelope: Envelope
    certificate: CompletionCertificate


def _check_outer(envelope: Envelope, expected_version: int, kind: str) -> Envelope:
    if not isinstance(envelope, Envelope):
        raise ValueError(f'a {kind} exchange envelope is required')
    if type(envelope.version) is not int or envelope.version != expected_version:
        raise ValueError('unsupported exchange version')
    if type(envelope.revision_id) is not int or type(envelope.body) is not bytes:
        raise ValueError('invalid exchange origin or body type')
    if sha256(envelope.body).hexdigest() != envelope.body_sha256:
        raise ValueError('exchange body digest mismatch')
    return envelope


def verify_envelope(envelope: Envelope) -> VerifiedEnvelope:
    checked = _check_outer(envelope, 1, 'V1')
    certificate = decode_certificate(checked.body)
    declared = checked.certificate_id, checked.run_id, checked.revision_id
    actual = certificate.certificate_id, certificate.run_id, certificate.revision_id
    if declared != actual:
        raise ValueError('exchange origin and certificate body disagree')
    return VerifiedEnvelope(checked, certificate)


def verify_completion_envelope(envelope: Envelope) -> VerifiedCompletion:
    checked = _check_outer(envelope, 2, 'V2 completion')
    certificate = decode_completion(checked.body)
    declared = checked.certificate_id, checked.run_id, checked.revision_id
    actual = certificate.certificate_id, certificate.run_id, certificate.revision_id
    if declared != actual:
        raise ValueError('exchange origin and completion body disagree')
    return VerifiedCompletion(checked, certificate)
