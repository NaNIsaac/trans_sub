import pytest

from trans_sub import subrip
from trans_sub.subrip import Cue, SubRipError

TEXT = (
    "1\n00:00:01,000 --> 00:00:02,500\nGood morning\n\n"
    "2\n01:02:03,004 --> 01:02:04,000\nTwo\nlines\n"
)


def test_parse_and_compose_round_trip():
    cues = subrip.parse(TEXT)
    assert cues == [
        Cue(1000, 2500, ("Good morning",)),
        Cue(3_723_004, 3_724_000, ("Two", "lines")),
    ]
    assert subrip.compose(cues) == TEXT


def test_crlf_and_trailing_blank_lines_are_accepted():
    assert subrip.parse(TEXT.replace("\n", "\r\n") + "\r\n\r\n") == subrip.parse(TEXT)


def test_cue_text_joins_lines_with_a_space():
    assert subrip.parse(TEXT)[1].text == "Two lines"


def test_empty_text_has_no_cues():
    assert subrip.parse("\n\n") == []


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("﻿" + TEXT, "x.srt: starts with a byte order mark"),
        (TEXT.replace("2\n01", "3\n01"), "x.srt: cue 2: expected number 2, found '3'"),
        ("1\n00:00:01,000 --> 00:00:02,000\n", "x.srt: cue 1: no text"),
        ("1\n00:00:01,000 -> 00:00:02,000\nx\n", "x.srt: cue 1: bad time line"),
        ("1\n00:00:01.000 --> 00:00:02,000\nx\n", "x.srt: cue 1: bad time '00:00:01.000'"),
        ("1\n00:61:01,000 --> 01:00:02,000\nx\n", "x.srt: cue 1: bad time '00:61:01,000'"),
        ("1\n00:00:02,000 --> 00:00:02,000\nx\n", "x.srt: cue 1: ends at or before its start"),
    ],
)
def test_malformed_input_names_file_and_cue(text, message):
    with pytest.raises(SubRipError, match=message.replace(".", r"\.")):
        subrip.parse(text, "x.srt")


def test_read_rejects_non_utf8(tmp_path):
    path = tmp_path / "latin.srt"
    path.write_bytes("1\n00:00:01,000 --> 00:00:02,000\ncaf\xe9\n".encode("latin-1"))
    with pytest.raises(SubRipError, match="not UTF-8"):
        subrip.read(path)


def test_write_is_utf8_with_lf(tmp_path):
    path = tmp_path / "out.srt"
    subrip.write(path, [Cue(0, 1000, ("café",))])
    assert path.read_bytes() == "1\n00:00:00,000 --> 00:00:01,000\ncafé\n".encode()
