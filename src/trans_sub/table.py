"""Translation tables: one block per distinct source line.

    # a comment
    @Source line
    fr=Ligne source
    de=Erste Zeile|zweite Zeile

A block starts with ``@`` and the source cue's text (a two-line cue written as its lines joined by
one space). Each following ``<lang>=<text>`` row gives that line in one language; ``|`` breaks the
translation into two lines of the cue. An empty value counts as missing. Blank lines and lines
starting with ``#`` are ignored.
"""

from dataclasses import dataclass, field
from pathlib import Path

from trans_sub.subrip import Cue

SPLIT = "|"


class TableError(ValueError):
    """A malformed table, or a table that lacks a line the source needs."""


@dataclass
class Table:
    entries: dict[str, dict[str, tuple[str, ...]]] = field(default_factory=dict)

    def languages(self) -> list[str]:
        return sorted({lang for row in self.entries.values() for lang in row})

    def add(self, source: str, lang: str, lines: tuple[str, ...], where: str) -> None:
        row = self.entries.setdefault(source, {})
        if lang in row and row[lang] != lines:
            raise TableError(
                f"{where}: {lang} has two different translations of {source!r}: "
                f"{SPLIT.join(row[lang])!r} and {SPLIT.join(lines)!r}"
            )
        row[lang] = lines

    def merge(self, text: str, name: str = "<table>") -> None:
        source = None
        for n, raw in enumerate(text.splitlines(), 1):
            row = raw.strip()
            where = f"{name}:{n}"
            if not row or row.startswith("#"):
                continue
            if row.startswith("@"):
                source = row[1:].strip()
                if not source:
                    raise TableError(f"{where}: empty source line after '@'")
                self.entries.setdefault(source, {})
                continue
            if source is None:
                raise TableError(f"{where}: a translation before the first '@' line")
            lang, sep, value = row.partition("=")
            lang = lang.strip()
            if not sep or not lang or " " in lang:
                raise TableError(f"{where}: expected '<lang>=<text>', found {row!r}")
            parts = tuple(part.strip() for part in value.split(SPLIT))
            if any(parts):
                self.add(source, lang, parts, where)

    @classmethod
    def load(cls, *paths: str | Path) -> "Table":
        table = cls()
        for path in paths:
            table.merge(Path(path).read_text(encoding="utf-8-sig"), str(path))
        return table

    def translate(self, cues: list[Cue], lang: str) -> list[Cue]:
        """The cues with each text replaced by its translation; times are kept as they are."""
        missing = sorted({c.text for c in cues if lang not in self.entries.get(c.text, {})})
        if missing:
            listed = "\n".join(f"  @{line}" for line in missing)
            raise TableError(f"no {lang} translation for {len(missing)} line(s):\n{listed}")
        return [Cue(c.start, c.end, self.entries[c.text][lang]) for c in cues]


def distinct_lines(cues: list[Cue]) -> list[str]:
    """Each source text once, in the order it first appears."""
    return list(dict.fromkeys(c.text for c in cues))
