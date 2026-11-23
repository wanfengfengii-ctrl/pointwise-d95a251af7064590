from dataclasses import dataclass
from hashlib import sha256

from analysis.certificates import Certificate, decode_certificate
from analysis.certificates import Envelope as Envelope


@dataclass(frozen=True)
class VerifiedEnvelope:
    envelope: Envelope
    certificate: Certificate


def verify_envelope(envelope: Envelope) -> VerifiedEnvelope:
    if not isinstance(envelope, Envelope):
        raise ValueError('a V1 exchange envelope is required')
    if type(envelope.version) is not int or envelope.version != 1:
        raise ValueError('unsupported exchange version')
    if type(envelope.revision_id) is not int or type(envelope.body) is not bytes:
        raise ValueError('invalid exchange origin or body type')
    if sha256(envelope.body).hexdigest() != envelope.body_sha256:
        raise ValueError('exchange body digest mismatch')
    certificate = decode_certificate(envelope.body)
    declared = envelope.certificate_id, envelope.run_id, envelope.revision_id
    actual = certificate.certificate_id, certificate.run_id, certificate.revision_id
    if declared != actual:
        raise ValueError('exchange origin and certificate body disagree')
    return VerifiedEnvelope(envelope, certificate)
