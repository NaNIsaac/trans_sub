import pytest

from trans_sub.subrip import Cue
from trans_sub.table import Table, TableError, distinct_lines

TABLE = """\
# comment
@Good morning
fr=Bonjour
de=Guten|Morgen

@See you
fr=À plus
de=
"""

CUES = [
    Cue(0, 1000, ("Good morning",)),
    Cue(1000, 2000, ("See", "you")),
    Cue(2000, 3000, ("Good morning",)),
]


def table(text=TABLE):
    t = Table()
    t.merge(text, "t.txt")
    return t


def test_translate_keeps_times_and_splits_on_bar():
    out = table().translate(CUES, "fr")
    assert out == [
        Cue(0, 1000, ("Bonjour",)),
        Cue(1000, 2000, ("À plus",)),
        Cue(2000, 3000, ("Bonjour",)),
    ]
    assert table().translate(CUES[:1], "de") == [Cue(0, 1000, ("Guten", "Morgen"))]


def test_empty_value_is_missing_and_the_error_names_the_line():
    with pytest.raises(TableError, match=r"no de translation for 1 line\(s\):\n  @See you"):
        table().translate(CUES, "de")


def test_languages():
    assert table().languages() == ["de", "fr"]


def test_load_reads_several_files_and_a_bom(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("@See you\nfr=À plus\n", encoding="utf-8")
    b.write_text("﻿@See you\nes=Hasta luego\n", encoding="utf-8")
    assert Table.load(a, b).entries == {"See you": {"fr": ("À plus",), "es": ("Hasta luego",)}}


def test_same_translation_twice_is_fine():
    t = table()
    t.merge("@Good morning\nfr=Bonjour\n", "u.txt")
    assert t.entries["Good morning"]["fr"] == ("Bonjour",)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        (
            "@Good morning\nfr=Salut\n",
            "u.txt:2: fr has two different translations of 'Good morning'",
        ),
        ("fr=Bonjour\n", "u.txt:1: a translation before the first '@' line"),
        ("@\n", r"u.txt:1: empty source line after '@'"),
        ("@x\nBonjour\n", "u.txt:2: expected '<lang>=<text>', found 'Bonjour'"),
        ("@x\n=Bonjour\n", "u.txt:2: expected '<lang>=<text>'"),
        ("@x\nf r=Bonjour\n", "u.txt:2: expected '<lang>=<text>'"),
    ],
)
def test_malformed_table_names_file_and_line(text, message):
    with pytest.raises(TableError, match=message):
        table().merge(text, "u.txt")


def test_distinct_lines_in_first_order():
    assert distinct_lines(CUES) == ["Good morning", "See you"]
