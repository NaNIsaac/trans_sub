import json
import sys
from pathlib import Path

import pytest
from fake_youtube import FakeYouTube, track, video

from trans_sub.cli import main as trans_sub_main
from trans_sub.youtube import auth
from trans_sub.youtube.cli import main
from trans_sub.youtube.meta import MetaError, dump_json, load_json, load_markdown
from trans_sub.youtube.plan import (
    Meta,
    PushError,
    apply,
    check_meta,
    find_subtitles,
    make_plan,
    render,
    video_body,
)

META = {
    "en": Meta("Morning talk", "A talk."),
    "de": Meta("Morgenrede", "Eine Rede."),
    "fr": Meta("Discours du matin", "Un discours."),
}


@pytest.fixture
def subs(tmp_path: Path) -> dict[str, Path]:
    for lang in ("en", "fr", "ja"):
        (tmp_path / f"talk.{lang}.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n")
    (tmp_path / "talk_clip.en.srt").write_text("")
    (tmp_path / "other.en.srt").write_text("")
    return find_subtitles(tmp_path, "talk")


def test_find_subtitles(subs):
    assert sorted(subs) == ["en", "fr", "ja"]


def test_plan_per_language(subs):
    service = FakeYouTube(
        video(defaultLanguage="en"),
        [track("t-en", "en"), track("t-ja-asr", "ja", kind="ASR"), track("t-x", "ko")],
    )
    plan = make_plan(service, "vid123", META, subs)
    got = [(s.lang, s.part, s.action, s.units) for s in plan.steps]
    assert got == [
        ("de", "metadata", "equal", 0),
        ("en", "metadata", "equal", 0),
        ("fr", "metadata", "add", 0),
        ("en", "caption", "update", 450),
        ("fr", "caption", "insert", 400),
        ("ja", "caption", "insert", 400),
    ]
    assert plan.read_units == 1 + 1 + 50
    assert plan.write_units == 50 + 450 + 400 + 400
    assert service.called() == ["videos.list", "i18nLanguages.list", "captions.list"]


def test_changed_text_is_an_update_and_equal_needs_no_video_update(subs):
    changed = {"de": Meta("Morgenrede", "Neu.")}
    plan = make_plan(FakeYouTube(video(defaultLanguage="en")), "vid123", changed, {})
    assert [(s.lang, s.action) for s in plan.steps] == [("de", "update")]
    plan = make_plan(FakeYouTube(video(defaultLanguage="en")), "vid123", {"de": META["de"]}, {})
    assert not plan.video_update and plan.write_units == 0


def test_video_body_keeps_snippet_and_other_languages(subs):
    service = FakeYouTube(video(defaultLanguage="en", tags=["a"]))
    meta = {"en": Meta("New title", "New text."), "fr": META["fr"]}
    body = video_body(make_plan(service, "vid123", meta, {}), meta)
    assert body == {
        "id": "vid123",
        "snippet": {
            "title": "New title",
            "description": "New text.",
            "tags": ["a"],
            "categoryId": "10",
            "defaultLanguage": "en",
        },
        "localizations": {
            "de": {"title": "Morgenrede", "description": "Eine Rede."},
            "fr": {"title": "Discours du matin", "description": "Un discours."},
        },
    }


def test_default_language_from_the_flag_is_set_and_shown():
    plan = make_plan(FakeYouTube(video()), "vid123", META, {}, default_lang="en")
    assert plan.default_lang == "en" and plan.snippet["defaultLanguage"] == "en"
    assert "default language: en (from --default-lang; the push sets it on the video)" in render(
        plan, 9000
    )


@pytest.mark.parametrize(
    ("snippet", "flag", "message"),
    [
        ({}, None, "the video has no default language; pass --default-lang"),
        ({"defaultLanguage": "en"}, "ko", "--default-lang ko differs from the video's default"),
    ],
)
def test_default_language_errors(snippet, flag, message):
    with pytest.raises(PushError, match=message):
        make_plan(FakeYouTube(video(**snippet)), "vid123", META, {}, default_lang=flag)


def test_missing_video():
    with pytest.raises(PushError, match="no video 'nope' on this account"):
        make_plan(FakeYouTube(None), "nope", META, {})


def test_two_tracks_in_one_language_are_refused(subs):
    service = FakeYouTube(
        video(defaultLanguage="en"), [track("a", "en"), track("b", "en", name="x")]
    )
    with pytest.raises(PushError, match="en: the video has 2 caption tracks in this language"):
        make_plan(service, "vid123", {}, subs)


def test_caption_modes(subs):
    service = FakeYouTube(video(defaultLanguage="en"), [track("t-en", "en")])
    plan = make_plan(service, "vid123", {}, subs, captions="missing")
    assert [(s.lang, s.action) for s in plan.steps] == [
        ("en", "skip"),
        ("fr", "insert"),
        ("ja", "insert"),
    ]
    service = FakeYouTube(video(defaultLanguage="en"))
    plan = make_plan(service, "vid123", {}, subs, captions="none")
    assert plan.steps == [] and "captions.list" not in service.called()


def test_unknown_language_codes_are_listed(subs):
    service = FakeYouTube(video(defaultLanguage="en"), langs=["en", "de"])
    plan = make_plan(service, "vid123", META, subs)
    assert plan.unknown_langs == ["fr", "ja"]
    plan = make_plan(
        FakeYouTube(video(defaultLanguage="en")), "vid123", META, subs, check_langs=False
    )
    assert plan.unknown_langs == [] and plan.read_units == 51


@pytest.mark.parametrize(
    ("meta", "message"),
    [
        (Meta(" ", ""), "xx: empty title"),
        (Meta("t" * 101, ""), "xx: title has 101 characters, the limit is 100"),
        (Meta("t", "é" * 2501), "xx: description is 5002 bytes, the limit is 5000"),
        (Meta("a <b>", ""), "xx: title contains '<' or '>'"),
        (Meta("t", "x > y"), "xx: description contains '<' or '>'"),
    ],
)
def test_meta_limits(meta, message):
    with pytest.raises(PushError, match=message):
        check_meta("xx", meta)


def test_apply_writes_video_then_captions(subs):
    service = FakeYouTube(video(defaultLanguage="en"), [track("t-en", "en")])
    plan = make_plan(service, "vid123", META, subs)
    log = []
    apply(service, plan, META, media=lambda p: f"media:{p.name}", track_name="", log=log.append)
    writes = [(k, kw) for k, kw in service.calls if k.endswith(("update", "insert"))]
    assert [k for k, _ in writes] == [
        "videos.update",
        "captions.update",
        "captions.insert",
        "captions.insert",
    ]
    assert writes[1][1] == {"part": "id", "body": {"id": "t-en"}, "media_body": "media:talk.en.srt"}
    assert writes[2][1]["body"] == {"snippet": {"videoId": "vid123", "language": "fr", "name": ""}}
    assert log[0] == "video: title, description and localizations written"
    assert log[1:] == ["en: caption updated", "fr: caption inserted", "ja: caption inserted"]


def test_apply_failure_says_what_was_written(subs):
    service = FakeYouTube(
        video(defaultLanguage="en"), fail={"captions.insert": RuntimeError("quotaExceeded")}
    )
    plan = make_plan(service, "vid123", META, subs)
    with pytest.raises(
        PushError,
        match="en caption insert failed: quotaExceeded. Written before it: video metadata",
    ):
        apply(service, plan, META, media=str, log=lambda _: None)


def write_meta(tmp_path: Path) -> Path:
    path = tmp_path / "meta.json"
    path.write_text(dump_json(META), encoding="utf-8")
    return path


def push_args(tmp_path: Path, *extra: str) -> list[str]:
    for lang in ("en", "fr"):
        (tmp_path / f"talk.{lang}.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n")
    meta = write_meta(tmp_path)
    return [
        "push",
        "--video",
        "vid123",
        "--meta",
        str(meta),
        "--subs",
        str(tmp_path),
        "--stem",
        "talk",
        *extra,
    ]


def test_cli_dry_run_writes_nothing(tmp_path, capsys):
    service = FakeYouTube(video(defaultLanguage="en"), [track("t-en", "en")])
    assert main(push_args(tmp_path), service_factory=lambda: service) == 0
    assert capsys.readouterr().out == (
        "video vid123: Morning talk\n"
        "default language: en (set on the video)\n"
        "  de    metadata  equal   localization\n"
        "  en    metadata  equal   video title and description\n"
        "  fr    metadata  add     localization\n"
        "  en    caption   update  replace the file (the API cannot show the old text to compare) [450 units]\n"
        "  fr    caption   insert  new track [400 units]\n"
        "  one videos.update for all metadata [50 units]\n"
        "quota: 52 units to read, 900 to write, 952 in all (limit 9000, daily quota 10000)\n"
        "dry run: nothing written; pass --apply to write\n"
    )
    assert not [k for k in service.called() if k.endswith(("update", "insert"))]


def test_cli_apply(tmp_path, capsys):
    service = FakeYouTube(video(defaultLanguage="en"))
    assert main(push_args(tmp_path, "--apply"), service_factory=lambda: service, media=str) == 0
    assert capsys.readouterr().out.endswith("en: caption inserted\nfr: caption inserted\ndone\n")
    assert service.video["localizations"]["fr"]["title"] == "Discours du matin"
    assert service.video["localizations"]["de"]["title"] == "Morgenrede"


def test_cli_refuses_over_the_unit_limit(tmp_path, capsys):
    service = FakeYouTube(video(defaultLanguage="en"))
    assert main(push_args(tmp_path, "--max-units", "100"), service_factory=lambda: service) == 1
    assert "would refuse: the push costs 902 units, over --max-units 100" in capsys.readouterr().out
    args = push_args(tmp_path, "--max-units", "100", "--apply")
    assert main(args, service_factory=lambda: service, media=str) == 1
    assert "error: the push costs 902 units, over --max-units 100" in capsys.readouterr().err
    assert not [k for k in service.called() if k.endswith(("update", "insert"))]


def test_cli_refuses_unknown_languages_on_apply(tmp_path, capsys):
    service = FakeYouTube(video(defaultLanguage="en"), langs=["en"])
    assert main(push_args(tmp_path, "--apply"), service_factory=lambda: service, media=str) == 1
    err = capsys.readouterr()
    assert "languages YouTube does not list: de, fr" in err.out
    assert "fix the language codes YouTube does not list, or pass --skip-lang-check" in err.err


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["push", "--video", "v"], "nothing to push: give --meta, --subs or both"),
        (["push", "--video", "v", "--subs", "."], "--subs needs --stem"),
        (
            ["push", "--video", "v", "--subs", ".", "--stem", "none"],
            "no none.<lang>.srt files in .",
        ),
    ],
)
def test_cli_input_errors(args, message, capsys):
    assert main(args, service_factory=lambda: pytest.fail("no service needed")) == 1
    assert message in capsys.readouterr().err


def test_trans_sub_routes_youtube(capsys):
    with pytest.raises(SystemExit):
        trans_sub_main(["youtube", "--help"])
    assert "push" in capsys.readouterr().out


def test_missing_extra_says_how_to_install(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "googleapiclient.discovery", None)
    monkeypatch.setitem(sys.modules, "googleapiclient.http", None)
    with pytest.raises(auth.AuthError, match="uv sync --extra youtube"):
        auth.youtube_service()
    with pytest.raises(auth.AuthError, match="uv sync --extra youtube"):
        auth.media_upload(Path("x.srt"))


def test_missing_client_file(tmp_path):
    pytest.importorskip("google_auth_oauthlib")
    with pytest.raises(auth.AuthError, match="no OAuth client file: pass --client-secret"):
        auth.youtube_service(tmp_path / "none.json", tmp_path / "token.json")


def test_paths_come_from_flags_then_env_then_config_dir(tmp_path, monkeypatch):
    monkeypatch.delenv(auth.TOKEN_ENV, raising=False)
    assert auth.token_path(None) == auth.config_dir() / "youtube-token.json"
    monkeypatch.setenv(auth.TOKEN_ENV, str(tmp_path / "t.json"))
    assert auth.token_path(None) == tmp_path / "t.json"
    assert auth.token_path(tmp_path / "flag.json") == tmp_path / "flag.json"
    monkeypatch.setenv(auth.CLIENT_SECRET_ENV, str(tmp_path / "c.json"))
    assert auth.client_secret_path(None) == tmp_path / "c.json"
    assert auth.config_dir().name == "trans-sub"


MD = """\
# Titles

| lang | Title (with source) | Title | Description |
|---|---|---|---|
| en | Talk (Morning talk) | Morning talk | A talk. |
| fr | Talk (Discours) | Discours | Un \\| discours. |

Text after.
"""


def test_markdown_table_by_header_or_number(tmp_path):
    path = tmp_path / "t.md"
    path.write_text(MD, encoding="utf-8")
    assert load_markdown(path, "Title", "Description") == {
        "en": Meta("Morning talk", "A talk."),
        "fr": Meta("Discours", "Un | discours."),
    }
    assert load_markdown(path, "2", "4")["en"].title == "Talk (Morning talk)"


@pytest.mark.parametrize(
    ("text", "columns", "message"),
    [
        ("no table", ("2", "3"), "no Markdown table found"),
        (MD, ("Nope", "3"), "no column 'Nope'; the table has 'lang', "),
        (MD, ("1", "3"), "column 1 is out of range 2..4"),
        ("| a | b |\n|---|---|\n", ("2", "2"), "the table has no rows"),
        ("| a | b |\n|---|---|\n| x | y | z |\n", ("2", "2"), "row 'x' has 3 cells, the header 2"),
        ("| a | b |\n|---|---|\n| x | y |\n| x | z |\n", ("2", "2"), "language 'x' appears twice"),
    ],
)
def test_markdown_errors(tmp_path, text, columns, message):
    path = tmp_path / "t.md"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(MetaError, match=message):
        load_markdown(path, *columns)


def test_json_round_trip_and_errors(tmp_path):
    path = write_meta(tmp_path)
    assert load_json(path) == META
    for text, message in [
        ("{", "not valid JSON"),
        ("[]", "expected an object keyed by language"),
        ('{"en": {"description": "x"}}', "en: expected"),
        ('{"en": {"title": "x", "description": 3}}', "en: description is not text"),
    ]:
        path.write_text(text, encoding="utf-8")
        with pytest.raises(MetaError, match=message):
            load_json(path)


def test_meta_command(tmp_path, capsys):
    path = tmp_path / "t.md"
    path.write_text(MD, encoding="utf-8")
    out = tmp_path / "meta.json"
    args = ["meta", str(path), "--title-column", "Title", "--description-column", "Description"]
    assert main([*args, "-o", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["fr"]["description"] == "Un | discours."
    assert main(args) == 0
    assert '"title": "Morning talk"' in capsys.readouterr().out
