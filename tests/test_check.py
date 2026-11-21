from pathlib import Path

from trans_sub import subrip
from trans_sub.check import (
    Limits,
    Report,
    base_name,
    check,
    check_cues,
    is_dense,
    translations_in,
    width,
)
from trans_sub.subrip import Cue

SOURCE = [Cue(0, 2000, ("Good morning",)), Cue(2000, 4000, ("See you",))]


def setup(tmp_path: Path, **files: list[Cue]) -> Path:
    src = tmp_path / "talk.en.srt"
    subrip.write(src, SOURCE)
    for lang, cues in files.items():
        subrip.write(tmp_path / f"talk.{lang.replace('_', '-')}.srt", cues)
    return src


def test_good_file_passes(tmp_path):
    src = setup(tmp_path, fr=[Cue(0, 2000, ("Bonjour",)), Cue(2000, 4000, ("À plus",))])
    report = check(src, [tmp_path])
    assert (report.files, report.failures, report.warnings) == (1, [], [])


def test_directory_finds_translations_but_not_the_source_or_other_names(tmp_path):
    src = setup(tmp_path, fr=SOURCE, zh_Hant=SOURCE)
    subrip.write(tmp_path / "talk_short.fr.srt", SOURCE)
    subrip.write(tmp_path / "talk.notes.srt", SOURCE)
    assert [p.name for p in translations_in(tmp_path, src)] == ["talk.fr.srt", "talk.zh-Hant.srt"]


def test_every_failure(tmp_path):
    src = setup(
        tmp_path,
        fr=[Cue(0, 2100, ("Salut",)), Cue(2000, 4000, ("ok",)), Cue(4000, 5000, ("extra",))],
        de=[Cue(0, 2000, ("a", "b", "c")), Cue(2000, 4000, ("x" * 43,))],
        ja=[Cue(0, 2000, ("あ" * 21,)), Cue(2000, 4000, ("ok",))],
    )
    (tmp_path / "talk.es.srt").write_text("1\nbroken\nx\n", encoding="utf-8")
    report = check(src, [tmp_path])
    assert report.failures == [
        "talk.de.srt #1: 3 lines, the limit is 2",
        f"talk.de.srt #2: line of 43 characters, the limit is 42: {'x' * 43}",
        f"{tmp_path / 'talk.es.srt'}: cue 1: bad time line 'broken'",
        "talk.fr.srt: 3 cues, the source has 2",
        (
            "talk.fr.srt #1: time 00:00:00,000 --> 00:00:02,100, "
            "the source has 00:00:00,000 --> 00:00:02,000"
        ),
        f"talk.ja.srt #1: line of 21 characters, the limit is 20: {'あ' * 21}",
    ]


def test_empty_cue():
    report = Report()
    check_cues("x.srt", [Cue(0, 2000, ("", " ")), SOURCE[1]], SOURCE, Limits(), report)
    assert report.failures == ["x.srt #1: empty"]


def test_limits_are_settable(tmp_path):
    src = setup(tmp_path, de=[Cue(0, 2000, ("a", "b", "c")), Cue(2000, 4000, ("x" * 43,))])
    assert check(src, [tmp_path], Limits(max_lines=3, width=50)).failures == []


def test_fast_cue_is_a_warning_and_untranslated_cues_are_not(tmp_path):
    src = setup(tmp_path, fr=[Cue(0, 2000, ("x" * 22, "y" * 22)), SOURCE[1]])
    report = check(src, [tmp_path / "talk.fr.srt"])
    assert report.failures == []
    assert report.warnings == [
        f"talk.fr.srt #1: 22.0 characters a second in 2.00 s: {'x' * 22} / {'y' * 22}"
    ]
    assert check(src, [tmp_path / "talk.fr.srt"], Limits(cps=0)).warnings == []


def test_dense_text_has_its_own_speed_limit(tmp_path):
    src = setup(tmp_path, ja=[Cue(0, 2000, ("あ" * 16,)), Cue(2000, 4000, ("あ" * 14,))])
    assert check(src, [tmp_path]).warnings == []
    assert check(src, [tmp_path], Limits(dense_cps=7)).warnings == [
        f"talk.ja.srt #1: 8.0 characters a second in 2.00 s: {'あ' * 16}"
    ]


def test_dense_scripts_and_width():
    assert is_dense("안녕") and is_dense("こんにちは") and is_dense("你好") and is_dense("สวัสดี")
    assert not is_dense("Привет") and not is_dense("مرحبا")
    assert width("ที่") == 1 and width("ปาฏิหาริย์") == 7
    assert width("é") == 1 and width("é") == 1


def test_base_name():
    assert base_name(Path("talk.en.srt")) == "talk"
    assert base_name(Path("talk.zh-Hant.srt")) == "talk"
    assert base_name(Path("talk.srt")) == "talk"
    assert base_name(Path("v1.2.final.srt")) == "v1.2.final"
