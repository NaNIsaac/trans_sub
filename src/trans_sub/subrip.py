"""Strict SubRip (.srt) reading and writing.

Times are whole milliseconds. The reader rejects what a lenient player would quietly fix (a byte
order mark, out-of-order numbers, a cue that ends before it starts), because a translated file
that differs from its source in any of these ways is a broken translation.
"""

import re
from dataclasses import dataclass
from pathlib import Path

_TIME = re.compile(r"(\d+):(\d{2}):(\d{2}),(\d{3})")
_TIME_LINE = re.compile(r"(\S+) --> (\S+)")
_BLOCK_GAP = re.compile(r"\n[ \t]*\n")


class SubRipError(ValueError):
    """A file that is not well-formed SubRip."""


@dataclass(frozen=True, slots=True)
class Cue:
    start: int
    end: int
    lines: tuple[str, ...]

    @property
    def text(self) -> str:
        """The cue's lines joined by one space: the key a translation table uses."""
        return " ".join(self.lines)

    @property
    def seconds(self) -> float:
        return (self.end - self.start) / 1000


def parse_time(value: str) -> int:
    m = _TIME.fullmatch(value)
    if not m:
        raise SubRipError(f"bad time {value!r}")
    h, mi, s, ms = map(int, m.groups())
    if mi > 59 or s > 59:
        raise SubRipError(f"bad time {value!r}")
    return ((h * 60 + mi) * 60 + s) * 1000 + ms


def format_time(ms: int) -> str:
    return f"{ms // 3_600_000:02d}:{ms // 60_000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def parse(text: str, name: str = "<text>") -> list[Cue]:
    """Parse SubRip text. Raise SubRipError naming the file and cue on anything malformed."""
    if text.startswith("﻿"):
        raise SubRipError(f"{name}: starts with a byte order mark")
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    cues = []
    for n, block in enumerate(_BLOCK_GAP.split(text), 1):
        rows = block.split("\n")
        if rows[0].strip() != str(n):
            raise SubRipError(f"{name}: cue {n}: expected number {n}, found {rows[0].strip()!r}")
        if len(rows) < 3:
            raise SubRipError(f"{name}: cue {n}: no text")
        m = _TIME_LINE.fullmatch(rows[1].strip())
        if not m:
            raise SubRipError(f"{name}: cue {n}: bad time line {rows[1].strip()!r}")
        try:
            start, end = parse_time(m[1]), parse_time(m[2])
        except SubRipError as exc:
            raise SubRipError(f"{name}: cue {n}: {exc}") from None
        if end <= start:
            raise SubRipError(f"{name}: cue {n}: ends at or before its start")
        cues.append(Cue(start, end, tuple(rows[2:])))
    return cues


def compose(cues: list[Cue]) -> str:
    return "\n".join(
        f"{i}\n{format_time(c.start)} --> {format_time(c.end)}\n" + "\n".join(c.lines) + "\n"
        for i, c in enumerate(cues, 1)
    )


def read(path: str | Path) -> list[Cue]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise SubRipError(f"{path}: not UTF-8") from None
    return parse(text, str(path))


def write(path: str | Path, cues: list[Cue]) -> None:
    """Write UTF-8 without a byte order mark, LF line ends."""
    Path(path).write_text(compose(cues), encoding="utf-8", newline="\n")
