"""Pin the behaviour of the `srt` package that the translation pipeline relies on.

trans_sub has no translation code yet. These tests record what the SRT layer guarantees and
what it does not, so the validation the pipeline must do itself (see README, "Validation") is
not assumed to come from the parser.
"""

from datetime import timedelta

import pytest
import srt

CANONICAL = (
    "1\n00:00:01,000 --> 00:00:02,500\nHello\nworld\n\n"
    "2\n00:01:03,123 --> 00:01:04,000\n<i>Hi</i>\n\n"
)


def test_canonical_round_trip_is_byte_stable():
    assert srt.compose(srt.parse(CANONICAL)) == CANONICAL


def test_crlf_input_is_normalised_to_lf_without_losing_content_or_times():
    crlf = CANONICAL.replace("\n", "\r\n")
    subs = list(srt.parse(crlf))
    assert [s.content for s in subs] == ["Hello\nworld", "<i>Hi</i>"]
    assert subs[1].start == timedelta(minutes=1, seconds=3, milliseconds=123)
    assert srt.compose(subs) == CANONICAL


def test_bom_in_text_is_tolerated():
    assert len(list(srt.parse("﻿" + CANONICAL))) == 2


def test_overlapping_cues_are_not_rejected():
    overlapping = "1\n00:00:01,000 --> 00:00:03,000\na\n\n2\n00:00:02,000 --> 00:00:04,000\nb\n\n"
    subs = list(srt.parse(overlapping))
    assert subs[0].end > subs[1].start


def test_non_contiguous_indices_are_kept_until_reindexed():
    text = "5\n00:00:03,000 --> 00:00:04,000\nx\n\n2\n00:00:01,000 --> 00:00:02,000\ny\n\n"
    subs = list(srt.parse(text))
    assert [s.index for s in subs] == [5, 2]
    assert [s.index for s in srt.sort_and_reindex(subs)] == [1, 2]


def test_malformed_block_raises_instead_of_being_dropped():
    broken = "1\n00:00:01,000 --> 00:00:02,000\nx\n\n2\n00:00:0X,000 --> 00:00:02,000\ny\n"
    with pytest.raises(srt.SRTParseError):
        list(srt.parse(broken))


def test_blank_lines_cannot_live_inside_cue_content():
    assert srt.make_legal_content("a\n\n\nb") == "a\nb"


def test_replacing_only_the_content_preserves_index_and_timing():
    source = list(srt.parse(CANONICAL))
    translated = [srt.Subtitle(s.index, s.start, s.end, f"[ko] {s.content}") for s in source]
    reparsed = list(srt.parse(srt.compose(translated)))
    assert [(s.index, s.start, s.end) for s in reparsed] == [
        (s.index, s.start, s.end) for s in source
    ]
    assert reparsed[0].content == "[ko] Hello\nworld"
