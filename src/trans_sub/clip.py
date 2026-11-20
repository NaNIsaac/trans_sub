"""Cut a subtitle file down to one or more time ranges, played one after another from zero.

A cue that crosses a range edge is cut at the edge. A piece shorter than the minimum is dropped,
since it would flash on screen. Ranges may repeat or go backwards in the source: a looping short
that ends on its own opening is two ranges, the body and then the lead-in.
"""

from trans_sub.subrip import Cue

MIN_PIECE_MS = 500


def parse_seconds(value: str) -> int:
    try:
        seconds = float(value)
    except ValueError:
        raise ValueError(f"not a time in seconds: {value!r}") from None
    if seconds < 0:
        raise ValueError(f"negative time: {value!r}")
    return round(seconds * 1000)


def parse_range(value: str) -> tuple[int, int]:
    """``"12.5:30"`` to milliseconds."""
    start, sep, end = value.partition(":")
    if not sep:
        raise ValueError(f"expected <from>:<to> in seconds, found {value!r}")
    return parse_seconds(start), parse_seconds(end)


def clip(
    cues: list[Cue], ranges: list[tuple[int, int]], min_piece: int = MIN_PIECE_MS
) -> list[Cue]:
    """The cues inside ``ranges`` (source milliseconds), shifted so the ranges play back to back."""
    out = []
    at = 0
    for start, end in ranges:
        if end <= start:
            raise ValueError(
                f"range ends at or before its start: {start / 1000:g}-{end / 1000:g} s"
            )
        for cue in cues:
            a, b = max(cue.start, start), min(cue.end, end)
            if b - a >= min_piece:
                out.append(Cue(a - start + at, b - start + at, cue.lines))
        at += end - start
    return sorted(out, key=lambda c: c.start)
