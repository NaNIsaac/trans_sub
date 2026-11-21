"""An empty translation table for a source file, and a prompt to have it filled by hand or by any chat."""

from trans_sub.check import DEFAULT_LIMITS, Limits
from trans_sub.subrip import Cue
from trans_sub.table import SPLIT, Table, distinct_lines


def table_text(cues: list[Cue], langs: list[str], known: Table | None = None) -> str:
    """Every distinct source line once, with a row per language; rows ``known`` has are filled in."""
    known = known or Table()
    blocks = [
        "# One block per distinct source line: '@<source>' then '<lang>=<text>'.\n"
        + f"# '{SPLIT}' splits a translation into two lines. Leave the '@' lines unchanged."
    ]
    for line in distinct_lines(cues):
        rows = [f"@{line}"]
        for lang in langs:
            value = known.entries.get(line, {}).get(lang, ())
            rows.append(f"{lang}={SPLIT.join(value)}")
        blocks.append("\n".join(rows))
    return "\n\n".join(blocks) + "\n"


def prompt_text(table: str, langs: list[str], limits: Limits = DEFAULT_LIMITS) -> str:
    return f"""\
Translate the subtitle lines in the table below into these languages: {", ".join(langs)}.

The table has one block per distinct line. A block starts with '@' and the source line; under it is
one row per language, '<lang>=' followed by the translation. Fill in every empty row and return the
whole table in the same format, as plain text, with nothing before or after it.

Rules:
- Keep every '@' line exactly as it is. Do not add, remove, merge or reorder blocks.
- Each translation is shown on screen for the time the source line is shown, so keep it as short
  as the meaning allows.
- A translation may be split into two lines with '{SPLIT}', never more than two. Each line holds
  at most {limits.width} characters, or {limits.dense_width} for Chinese, Japanese, Korean or Thai.
- Translate the meaning, not word by word, and keep the tone of the source (casual or polite).
- Names, sung syllables and exclamations with no meaning are transliterated, not translated.
- The same word gets the same translation every time it appears.

{table}"""
