"""Titles and descriptions per language: a JSON file, or a column pair of a Markdown table.

JSON: ``{"en": {"title": "...", "description": "..."}, "fr": {...}}``.

Markdown: the first table in the file whose first column holds the language code. The title and
description columns are chosen by header text or by number (1 is the language column).
"""

import json
import re
from pathlib import Path

from trans_sub.youtube.plan import Meta

_RULE = re.compile(r"\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*")


class MetaError(ValueError):
    """A metadata file that cannot be read as titles and descriptions."""


def load_json(path: Path) -> dict[str, Meta]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise MetaError(f"{path}: not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise MetaError(f"{path}: expected an object keyed by language")
    out = {}
    for lang, item in data.items():
        if not isinstance(item, dict) or not isinstance(item.get("title"), str):
            raise MetaError(f'{path}: {lang}: expected {{"title": ..., "description": ...}}')
        description = item.get("description", "")
        if not isinstance(description, str):
            raise MetaError(f"{path}: {lang}: description is not text")
        out[lang] = Meta(item["title"], description)
    return out


def _cells(row: str) -> list[str]:
    row = row.strip()
    row = row.removeprefix("|")
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    cells, cur, escaped = [], "", False
    for ch in row:
        if escaped:
            cur += ch
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "|":
            cells.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return [*cells, cur.strip()]


def _column(header: list[str], choice: str, path: Path) -> int:
    if choice.isdigit():
        index = int(choice) - 1
        if not 0 < index < len(header):
            raise MetaError(f"{path}: column {choice} is out of range 2..{len(header)}")
        return index
    if choice not in header:
        listed = ", ".join(repr(h) for h in header)
        raise MetaError(f"{path}: no column {choice!r}; the table has {listed}")
    return header.index(choice)


def load_markdown(path: Path, title_column: str, description_column: str) -> dict[str, Meta]:
    rows = path.read_text(encoding="utf-8-sig").splitlines()
    for i in range(len(rows) - 1):
        if rows[i].lstrip().startswith("|") and _RULE.fullmatch(rows[i + 1]):
            header = _cells(rows[i])
            t, d = _column(header, title_column, path), _column(header, description_column, path)
            out = {}
            for row in rows[i + 2 :]:
                if not row.lstrip().startswith("|"):
                    break
                cells = _cells(row)
                if len(cells) != len(header):
                    raise MetaError(
                        f"{path}: row {cells[0]!r} has {len(cells)} cells, the header {len(header)}"
                    )
                lang = cells[0]
                if lang in out:
                    raise MetaError(f"{path}: language {lang!r} appears twice")
                out[lang] = Meta(cells[t], cells[d])
            if not out:
                raise MetaError(f"{path}: the table has no rows")
            return out
    raise MetaError(f"{path}: no Markdown table found")


def dump_json(meta: dict[str, Meta]) -> str:
    data = {lang: {"title": m.title, "description": m.description} for lang, m in meta.items()}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
