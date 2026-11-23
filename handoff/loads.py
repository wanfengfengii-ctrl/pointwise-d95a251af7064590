from dataclasses import dataclass
from fractions import Fraction


TensionInput = Fraction | int | str


def parse_tension(value: TensionInput) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if type(value) not in (int, str):
        raise ValueError('tension must be a Fraction, integer, or rational string')
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('invalid rational tension') from exc


def pack_tension(value: Fraction) -> str:
    # The base-16 pair is exact even for integers beyond decimal conversion limits.
    return f'{value.numerator:x}/{value.denominator:x}'


def unpack_tension(encoded: str) -> Fraction:
    if type(encoded) is not str:
        raise ValueError('encoded tension must be text')
    try:
        numerator, denominator = encoded.split('/')
        tension = Fraction(int(numerator, 16), int(denominator, 16))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('invalid encoded tension') from exc
    if pack_tension(tension) != encoded:
        raise ValueError('tension encoding is not canonical')
    return tension


@dataclass(frozen=True)
class PrefixLoad:
    start: Fraction
    seam: Fraction


def validate_prefix_load(start: TensionInput, seam: TensionInput) -> PrefixLoad:
    load = PrefixLoad(parse_tension(start), parse_tension(seam))
    if not 0 <= load.start < load.seam:
        raise ValueError('prefix must satisfy 0 <= start < seam')
    return load
