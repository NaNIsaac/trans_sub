"""The offline commands end to end: build, check, template."""

from pathlib import Path

import pytest

from trans_sub import subrip
from trans_sub.cli import main
from trans_sub.subrip import Cue
from trans_sub.table import Table

SOURCE = [
    Cue(1000, 2500, ("Good morning",)),
    Cue(3000, 4500, ("See", "you")),
    Cue(5000, 6000, ("Good morning",)),
]
TABLE = "@Good morning\nfr=Bonjour\nde=Guten|Morgen\n\n@See you\nfr=À plus\nde=Bis dann\n"


@pytest.fixture
def work(tmp_path: Path) -> Path:
    subrip.write(tmp_path / "talk.en.srt", SOURCE)
    (tmp_path / "talk.table.txt").write_text(TABLE, encoding="utf-8")
    return tmp_path


def test_build_writes_every_table_language(work, capsys):
    assert main(["build", str(work / "talk.en.srt"), "--table", str(work / "talk.table.txt")]) == 0
    assert subrip.read(work / "talk.fr.srt") == [
        Cue(1000, 2500, ("Bonjour",)),
        Cue(3000, 4500, ("À plus",)),
        Cue(5000, 6000, ("Bonjour",)),
    ]
    assert subrip.read(work / "talk.de.srt")[0].lines == ("Guten", "Morgen")
    assert capsys.readouterr().out.splitlines() == [
        str(work / "talk.de.srt"),
        str(work / "talk.fr.srt"),
    ]


def test_build_options(work):
    out = work / "out"
    args = ["build", str(work / "talk.en.srt"), "--table", str(work / "talk.table.txt")]
    args += ["--langs", "en", "fr", "--source-lang", "en", "--out", str(out), "--name", "clip"]
    assert main(args) == 0
    assert sorted(p.name for p in out.iterdir()) == ["clip.en.srt", "clip.fr.srt"]
    assert (out / "clip.en.srt").read_bytes() == (work / "talk.en.srt").read_bytes()


def test_build_missing_line_names_it_and_writes_nothing(work, capsys):
    (work / "talk.table.txt").write_text(TABLE + "@See you\nes=Hasta luego\n", encoding="utf-8")
    args = ["build", str(work / "talk.en.srt"), "--table", str(work / "talk.table.txt")]
    assert main([*args, "--langs", "fr", "es"]) == 1
    assert capsys.readouterr().err == "error: no es translation for 1 line(s):\n  @Good morning\n"
    assert not (work / "talk.fr.srt").exists()


def test_build_refuses_to_overwrite_the_source(work, capsys):
    args = ["build", str(work / "talk.en.srt"), "--table", str(work / "talk.table.txt")]
    assert main([*args, "--langs", "en", "--source-lang", "en"]) == 1
    assert "is the source; give another --out or --name" in capsys.readouterr().err


def test_build_empty_table(work, capsys):
    (work / "empty.txt").write_text("@Good morning\n", encoding="utf-8")
    assert main(["build", str(work / "talk.en.srt"), "--table", str(work / "empty.txt")]) == 1
    assert "the table has no translations and no --langs were given" in capsys.readouterr().err


def test_build_missing_file(work, capsys):
    assert main(["build", str(work / "nope.srt"), "--table", str(work / "talk.table.txt")]) == 1
    assert capsys.readouterr().err.startswith("error: ")


def test_check_passes_after_build(work, capsys):
    main(["build", str(work / "talk.en.srt"), "--table", str(work / "talk.table.txt")])
    capsys.readouterr()
    assert main(["check", str(work / "talk.en.srt"), str(work)]) == 0
    assert capsys.readouterr().out == "checked 2 files: 0 failures, 0 warnings\n"


def test_check_failure_exits_1_and_limits_are_options(work, capsys):
    subrip.write(work / "talk.fr.srt", [*SOURCE[:2], Cue(5000, 6000, ("x" * 43,))])
    assert main(["check", str(work / "talk.en.srt"), str(work / "talk.fr.srt")]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "checked 1 files: 1 failures, 1 warnings"
    assert out[1].startswith("FAIL talk.fr.srt #3: line of 43 characters, the limit is 42")
    assert out[2].startswith("warn talk.fr.srt #3: 43.0 characters a second")
    args = ["check", str(work / "talk.en.srt"), str(work / "talk.fr.srt"), "--width", "43"]
    assert main([*args, "--cps", "0"]) == 0


def test_check_with_nothing_to_check_fails(work, capsys):
    assert main(["check", str(work / "talk.en.srt"), str(work)]) == 1
    assert "FAIL no translated files found for talk.en.srt" in capsys.readouterr().out


def test_template_writes_table_and_prompt(work):
    assert main(["template", str(work / "talk.en.srt"), "--langs", "es", "ja", "--force"]) == 0
    table = (work / "talk.table.txt").read_text(encoding="utf-8")
    assert table.endswith("@Good morning\nes=\nja=\n\n@See you\nes=\nja=\n")
    prompt = (work / "talk.prompt.txt").read_text(encoding="utf-8")
    assert prompt.startswith(
        "Translate the subtitle lines in the table below into these languages: es, ja."
    )
    assert prompt.endswith(table)
    assert Table.load(work / "talk.table.txt").languages() == []


def test_template_fills_known_rows(work):
    known = work / "known.txt"
    known.write_text(TABLE, encoding="utf-8")
    args = ["template", str(work / "talk.en.srt"), "--langs", "de", "es", "--table", str(known)]
    assert main([*args, "--out", str(work / "t")]) == 0
    table = (work / "t" / "talk.table.txt").read_text(encoding="utf-8")
    assert "@Good morning\nde=Guten|Morgen\nes=\n" in table


def test_template_will_not_overwrite_a_table(work, capsys):
    assert main(["template", str(work / "talk.en.srt"), "--langs", "es"]) == 1
    assert "talk.table.txt exists; pass it as --table to keep its rows, or --force" in (
        capsys.readouterr().err
    )


def test_filled_template_builds(work):
    main(["template", str(work / "talk.en.srt"), "--langs", "es", "--force"])
    path = work / "talk.table.txt"
    text = path.read_text(encoding="utf-8")
    text = text.replace("@Good morning\nes=", "@Good morning\nes=Buenos días")
    path.write_text(text.replace("@See you\nes=", "@See you\nes=Hasta luego"), encoding="utf-8")
    assert main(["build", str(work / "talk.en.srt"), "--table", str(path)]) == 0
    assert subrip.read(work / "talk.es.srt")[1].lines == ("Hasta luego",)


def test_help_lists_the_commands(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    for command in ("translate", "build", "check", "template", "clip"):
        assert command in out


def test_translate_command_and_bare_form_take_the_same_arguments(work, capsys, monkeypatch):
    monkeypatch.setenv("LLM_SUBTRANS_CONFIG_PATH", str(work / "cfg"))
    src = str(work / "talk.en.srt")
    assert main(["translate", src, "--to", "ko", "--provider", "OpenRouter", "--dry-run"]) == 0
    first = capsys.readouterr().out
    assert main([src, "--to", "ko", "--provider", "OpenRouter", "--dry-run"]) == 0
    assert capsys.readouterr().out == first
    assert first.startswith("Dry run: 3 lines")


def test_table_takes_several_files_after_one_flag_or_a_repeated_flag(work):
    (work / "fr.txt").write_text(
        "@Good morning\nfr=Bonjour\n@See you\nfr=À plus\n", encoding="utf-8"
    )
    (work / "es.txt").write_text(
        "@Good morning\nes=Hola\n@See you\nes=Hasta luego\n", encoding="utf-8"
    )
    src = str(work / "talk.en.srt")
    out = work / "o"
    assert (
        main(
            ["build", src, "--table", str(work / "fr.txt"), str(work / "es.txt"), "--out", str(out)]
        )
        == 0
    )
    assert sorted(p.name for p in out.iterdir()) == ["talk.es.srt", "talk.fr.srt"]
    args = ["build", src, "--table", str(work / "fr.txt"), "--table", str(work / "es.txt")]
    assert main([*args, "--out", str(work / "p")]) == 0
    assert len(list((work / "p").iterdir())) == 2
