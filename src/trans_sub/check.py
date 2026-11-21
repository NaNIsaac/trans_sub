"""Check translated subtitle files against their source.

A failure is something a viewer would see as broken: a file that does not parse, a cue count or a
cue time that differs from the source, an empty cue, too many lines, a line too long for the
screen. A cue read faster than the speed limit is only a warning, because the source fixes the
times and a translation can only get shorter.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from trans_sub import subrip
from trans_sub.subrip import Cue

LANG_TAG = re.compile(r"[a-z]{2,3}(?:-[A-Za-z]{2,4})?")

# Scripts set in full-width or dense glyphs get the shorter line limit: Hangul, kana, Han, Thai,
# and CJK punctuation and full-width forms.
_DENSE = (
    (0x0E00, 0x0E7F),
    (0x1100, 0x11FF),
    (0x3000, 0x30FF),
    (0x3130, 0x318F),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xAC00, 0xD7AF),
    (0xF900, 0xFAFF),
    (0xFF00, 0xFFEF),
)


@dataclass(frozen=True, slots=True)
class Limits:
    max_lines: int = 2
    width: int = 42
    dense_width: int = 20
    cps: float = 20.0
    dense_cps: float = 15.0


@dataclass
class Report:
    files: int = 0
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


DEFAULT_LIMITS = Limits()
_ZERO_WIDTH = {"Mn", "Me", "Cf"}


def is_dense(text: str) -> bool:
    return any(lo <= ord(ch) <= hi for ch in text for lo, hi in _DENSE)


def width(text: str) -> int:
    """Characters as a reader counts them: marks set above or below a letter (Thai vowels and tone
    marks, accents) and invisible format characters add nothing."""
    return sum(1 for ch in text if unicodedata.category(ch) not in _ZERO_WIDTH)


def base_name(path: Path) -> str:
    """The file name without ``.srt`` and without a trailing language tag: ``song.ko.srt`` -> ``song``."""
    stem, dot, tag = path.stem.rpartition(".")
    return stem if dot and LANG_TAG.fullmatch(tag) else path.stem


def translations_in(directory: Path, source: Path) -> list[Path]:
    """``<base>.<lang>.srt`` files next to each other in ``directory``, the source itself left out."""
    base = base_name(source)
    found = []
    for path in sorted(directory.glob(f"{glob_escape(base)}.*.srt")):
        tag = path.name[len(base) + 1 : -len(".srt")]
        if LANG_TAG.fullmatch(tag) and path.resolve() != source.resolve():
            found.append(path)
    return found


def glob_escape(text: str) -> str:
    return re.sub(r"([*?\[])", r"[\1]", text)


def check_cues(name: str, cues: list[Cue], source: list[Cue], limits: Limits, report: Report):
    fail, warn = report.failures.append, report.warnings.append
    if len(cues) != len(source):
        fail(f"{name}: {len(cues)} cues, the source has {len(source)}")
    for i, (cue, ref) in enumerate(zip(cues, source, strict=False), 1):
        at = f"{name} #{i}"
        if (cue.start, cue.end) != (ref.start, ref.end):
            fail(
                f"{at}: time {subrip.format_time(cue.start)} --> {subrip.format_time(cue.end)}, "
                f"the source has {subrip.format_time(ref.start)} --> {subrip.format_time(ref.end)}"
            )
        if not any(line.strip() for line in cue.lines):
            fail(f"{at}: empty")
            continue
        if len(cue.lines) > limits.max_lines:
            fail(f"{at}: {len(cue.lines)} lines, the limit is {limits.max_lines}")
        for line in cue.lines:
            limit = limits.dense_width if is_dense(line) else limits.width
            if width(line) > limit:
                fail(f"{at}: line of {width(line)} characters, the limit is {limit}: {line}")
        if cue.text == ref.text:
            continue
        cps_limit = limits.dense_cps if is_dense(cue.text) else limits.cps
        cps = sum(width(line) for line in cue.lines) / cue.seconds
        if cps_limit and cps > cps_limit:
            warn(
                f"{at}: {cps:.1f} characters a second in {cue.seconds:.2f} s: {' / '.join(cue.lines)}"
            )


def check(source: Path, targets: list[Path], limits: Limits = DEFAULT_LIMITS) -> Report:
    """Check every target file against the source. Directories expand to their translations."""
    report = Report()
    ref = subrip.read(source)
    files = []
    for target in targets:
        files += translations_in(target, source) if target.is_dir() else [target]
    for path in files:
        report.files += 1
        try:
            cues = subrip.read(path)
        except (OSError, subrip.SubRipError) as exc:
            report.failures.append(str(exc))
            continue
        check_cues(path.name, cues, ref, limits, report)
    return report
