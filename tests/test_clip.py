import pytest

from trans_sub import subrip
from trans_sub.cli import main
from trans_sub.clip import clip, parse_range, parse_seconds
from trans_sub.subrip import Cue

CUES = [
    Cue(1000, 3000, ("one",)),
    Cue(3000, 5000, ("two",)),
    Cue(5000, 9000, ("three",)),
    Cue(9000, 9300, ("blink",)),
]


def test_one_range_shifts_to_zero_and_cuts_at_the_edges():
    assert clip(CUES, [(2000, 6000)]) == [
        Cue(0, 1000, ("one",)),
        Cue(1000, 3000, ("two",)),
        Cue(3000, 4000, ("three",)),
    ]


def test_pieces_under_the_minimum_are_dropped():
    assert clip(CUES, [(2600, 5400)]) == [Cue(400, 2400, ("two",))]
    assert clip(CUES, [(2600, 5400)], min_piece=0) == [
        Cue(0, 400, ("one",)),
        Cue(400, 2400, ("two",)),
        Cue(2400, 2800, ("three",)),
    ]
    assert clip(CUES, [(8000, 10000)]) == [Cue(0, 1000, ("three",))]


def test_ranges_play_in_order_and_may_go_back():
    assert clip(CUES, [(3000, 5000), (1000, 3000)]) == [
        Cue(0, 2000, ("two",)),
        Cue(2000, 4000, ("one",)),
    ]


def test_bad_ranges():
    with pytest.raises(ValueError, match="range ends at or before its start: 3-3 s"):
        clip(CUES, [(3000, 3000)])
    with pytest.raises(ValueError, match="expected <from>:<to> in seconds, found '3'"):
        parse_range("3")
    with pytest.raises(ValueError, match="not a time in seconds: 'x'"):
        parse_seconds("x")
    with pytest.raises(ValueError, match="negative time: '-1'"):
        parse_seconds("-1")
    assert parse_range("1.5:2.25") == (1500, 2250)


def test_cli_clips_several_files_and_keeps_the_language_tag(tmp_path, capsys):
    for lang in ("en", "fr"):
        subrip.write(tmp_path / f"talk.{lang}.srt", CUES)
    subrip.write(tmp_path / "plain.srt", CUES)
    files = [str(tmp_path / n) for n in ("talk.en.srt", "talk.fr.srt", "plain.srt")]
    assert main(["clip", *files, "--from", "3", "--to", "5", "--then", "1:3"]) == 0
    assert subrip.read(tmp_path / "talk_clip.fr.srt") == [
        Cue(0, 2000, ("two",)),
        Cue(2000, 4000, ("one",)),
    ]
    assert (tmp_path / "plain_clip.srt").exists()
    assert capsys.readouterr().out.splitlines()[0] == f"{tmp_path / 'talk_clip.en.srt'}: 2 cues"


def test_cli_options(tmp_path):
    subrip.write(tmp_path / "talk.en.srt", CUES)
    args = ["clip", str(tmp_path / "talk.en.srt"), "--from", "2.6", "--to", "5.4"]
    assert (
        main([*args, "--suffix", "_short", "--out", str(tmp_path / "o"), "--min-piece", "0"]) == 0
    )
    assert len(subrip.read(tmp_path / "o" / "talk_short.en.srt")) == 3


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        (["--suffix", ""], "--suffix must not be empty"),
        (["--then", "4"], "expected <from>:<to> in seconds"),
        (["--min-piece", "soon"], "not a time in seconds: 'soon'"),
    ],
)
def test_cli_errors(tmp_path, capsys, extra, message):
    subrip.write(tmp_path / "talk.en.srt", CUES)
    assert main(["clip", str(tmp_path / "talk.en.srt"), "--from", "1", "--to", "3", *extra]) == 1
    assert message in capsys.readouterr().err


def test_cli_reversed_range_writes_nothing(tmp_path, capsys):
    subrip.write(tmp_path / "talk.en.srt", CUES)
    assert main(["clip", str(tmp_path / "talk.en.srt"), "--from", "5", "--to", "3"]) == 1
    assert "range ends at or before its start: 5-3 s" in capsys.readouterr().err
    assert not (tmp_path / "talk_clip.en.srt").exists()
