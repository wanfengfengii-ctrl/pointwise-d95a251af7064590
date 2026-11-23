from fractions import Fraction


def require_same_trial(first: str, second: str) -> None:
    if first != second:
        raise ValueError('records belong to different trials')


def require_common_seam(prefix_seam: Fraction, rear_seam: Fraction) -> None:
    if prefix_seam != rear_seam:
        raise ValueError('prefix seam and rear seam differ')
