from datetime import UTC, datetime
from pathlib import Path

import pytest
from fake_youtube import FakeYouTube

from trans_sub.youtube.cli import main
from trans_sub.youtube.meta import dump_json
from trans_sub.youtube.plan import Meta, PushError
from trans_sub.youtube.upload import (
    apply_upload,
    insert_body,
    make_upload,
    parse_publish_at,
    render_upload,
)

META = {
    "ko": Meta("신의 부재중 통화", "부재중 전화 한 통."),
    "en": Meta("A Missed Call from God", "One missed call."),
    "ja": Meta("神様からの不在着信", "不在着信が一件。"),
}
NOW = datetime(2026, 11, 22, tzinfo=UTC)


@pytest.fixture
def files(tmp_path: Path) -> dict[str, Path]:
    video = tmp_path / "song.mp4"
    video.write_bytes(b"\0" * 2_000_000)
    thumb = tmp_path / "cover.png"
    thumb.write_bytes(b"\x89PNG")
    for lang in ("ko", "en"):
        (tmp_path / f"song.{lang}.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n")
    meta = tmp_path / "meta.json"
    meta.write_text(dump_json(META), encoding="utf-8")
    return {"video": video, "thumb": thumb, "meta": meta, "dir": tmp_path}


def subs_of(files):
    return {lang: files["dir"] / f"song.{lang}.srt" for lang in ("en", "ko")}


def test_plan_costs_and_reads_only_the_language_list(files):
    service = FakeYouTube()
    up = make_upload(
        service, files["video"], META, "ko", subtitles=subs_of(files), thumbnail=files["thumb"]
    )
    assert service.called() == ["i18nLanguages.list"]
    assert up.read_units == 1
    assert up.write_units == 1600 + 50 + 2 * 400
    assert up.total_units == 2451


def test_insert_body_default_language_is_the_videos_own(files):
    up = make_upload(
        FakeYouTube(),
        files["video"],
        META,
        "ko",
        publish_at="2026-11-25T09:00:00Z",
        category="10",
        synthetic=True,
    )
    assert insert_body(up) == {
        "snippet": {
            "title": "신의 부재중 통화",
            "description": "부재중 전화 한 통.",
            "defaultLanguage": "ko",
            "defaultAudioLanguage": "ko",
            "categoryId": "10",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
            "publishAt": "2026-11-25T09:00:00Z",
            "containsSyntheticMedia": True,
        },
        "localizations": {
            "en": {"title": "A Missed Call from God", "description": "One missed call."},
            "ja": {"title": "神様からの不在着信", "description": "不在着信が一件。"},
        },
    }


def test_unset_options_are_left_out_of_the_body(files):
    body = insert_body(make_upload(FakeYouTube(), files["video"], META, "ko", check_langs=False))
    assert "categoryId" not in body["snippet"]
    assert body["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": False}


def test_apply_uploads_video_then_thumbnail_then_captions(files):
    service = FakeYouTube()
    up = make_upload(
        service, files["video"], META, "ko", subtitles=subs_of(files), thumbnail=files["thumb"]
    )
    log = []
    video_id = apply_upload(
        service,
        up,
        video_media=lambda p: f"video:{p.name}",
        image_media=lambda p: f"image:{p.name}",
        caption_media=lambda p: f"srt:{p.name}",
        log=log.append,
    )
    assert video_id == "up456"
    writes = [(k, kw) for k, kw in service.calls if k != "i18nLanguages.list"]
    assert [k for k, _ in writes] == [
        "videos.insert",
        "thumbnails.set",
        "captions.insert",
        "captions.insert",
    ]
    assert writes[0][1]["part"] == "snippet,status,localizations"
    assert writes[0][1]["media_body"] == "video:song.mp4"
    assert writes[1][1] == {"videoId": "up456", "media_body": "image:cover.png"}
    assert writes[2][1]["body"]["snippet"] == {"videoId": "up456", "language": "en", "name": ""}
    assert writes[3][1]["media_body"] == "srt:song.ko.srt"
    assert log == [
        "uploading: 33%",
        "uploading: 66%",
        "video: uploaded as up456 (https://youtu.be/up456)",
        "thumbnail: set",
        "en: caption inserted",
        "ko: caption inserted",
    ]


def test_failed_insert_says_nothing_was_uploaded(files):
    service = FakeYouTube(fail={"videos.insert": RuntimeError("uploadLimitExceeded")})
    up = make_upload(service, files["video"], META, "ko")
    with pytest.raises(PushError, match="videos.insert failed: uploadLimitExceeded. Nothing"):
        apply_upload(service, up, str, str, str, log=lambda _: None)


def test_failure_after_the_video_is_up_names_it(files):
    service = FakeYouTube(fail={"thumbnails.set": RuntimeError("forbidden")})
    up = make_upload(service, files["video"], META, "ko", thumbnail=files["thumb"])
    with pytest.raises(
        PushError, match="thumbnails.set failed: forbidden. The video is up as up456; finish with"
    ):
        apply_upload(service, up, str, str, str, log=lambda _: None)
    service = FakeYouTube(fail={"captions.insert": RuntimeError("quotaExceeded")})
    up = make_upload(service, files["video"], META, "ko", subtitles=subs_of(files))
    with pytest.raises(PushError, match="captions failed: en caption insert failed"):
        apply_upload(service, up, str, str, str, log=lambda _: None)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("tomorrow", "is not an ISO 8601 time"),
        ("2026-11-25T09:00:00", "needs an offset"),
        ("2026-11-21T09:00:00+09:00", "is not in the future"),
    ],
)
def test_publish_at_errors(text, message):
    with pytest.raises(PushError, match=message):
        parse_publish_at(text, NOW)


def test_publish_at_becomes_utc():
    assert parse_publish_at("2026-11-25T18:00:00+09:00", NOW) == "2026-11-25T09:00:00Z"


def test_input_errors(files, tmp_path):
    service = FakeYouTube()
    with pytest.raises(PushError, match="--meta has no 'fr', the default language"):
        make_upload(service, files["video"], META, "fr")
    with pytest.raises(PushError, match="--publish-at needs --privacy private"):
        make_upload(
            service, files["video"], META, "ko", privacy="public", publish_at="2026-12-01T00:00:00Z"
        )
    with pytest.raises(PushError, match="no video file"):
        make_upload(service, tmp_path / "none.mp4", META, "ko")
    text = tmp_path / "notes.txt"
    text.write_text("x")
    with pytest.raises(PushError, match="not a video file YouTube takes"):
        make_upload(service, text, META, "ko")
    big = tmp_path / "big.png"
    big.write_bytes(b"\0" * (2 * 1024 * 1024 + 1))
    with pytest.raises(PushError, match="the thumbnail limit is 2 MB"):
        make_upload(service, files["video"], META, "ko", thumbnail=big)
    with pytest.raises(PushError, match="must be PNG or JPEG"):
        make_upload(service, files["video"], META, "ko", thumbnail=text)
    assert service.calls == []


def test_render_shows_privacy_note_and_unknown_languages(files):
    service = FakeYouTube(langs=["ko", "en"])
    up = make_upload(service, files["video"], META, "ko", privacy="unlisted")
    lines = render_upload(up, 9000)
    assert lines[0] == "upload song.mp4 (2.0 MB) as a new video"
    assert "  privacy: unlisted" in lines
    assert any(line.startswith("note: an API project that has not passed") for line in lines)
    assert "languages YouTube does not list: ja" in lines
    assert (
        lines[-1]
        == "quota: 1 units to read, 1600 to write, 1601 in all (limit 9000, daily quota 10000)"
    )


def upload_args(files, *extra):
    return [
        "upload",
        "--file",
        str(files["video"]),
        "--meta",
        str(files["meta"]),
        "--default-lang",
        "ko",
        "--subs",
        str(files["dir"]),
        "--thumb",
        str(files["thumb"]),
        *extra,
    ]


def test_cli_dry_run_uploads_nothing(files, capsys):
    service = FakeYouTube()
    assert main(upload_args(files), service_factory=lambda: service) == 0
    out = capsys.readouterr().out
    assert "  en caption insert new track [400 units]" in out
    assert "quota: 1 units to read, 2450 to write, 2451 in all" in out
    assert out.endswith("dry run: nothing uploaded; pass --apply to upload\n")
    assert service.called() == ["i18nLanguages.list"]


def test_cli_apply(files, capsys):
    service = FakeYouTube()
    code = main(
        upload_args(files, "--apply", "--synthetic", "yes"),
        service_factory=lambda: service,
        media=str,
        video_media=str,
        image_media=str,
    )
    assert code == 0
    assert capsys.readouterr().out.endswith("ko: caption inserted\ndone\n")
    insert = next(kw for k, kw in service.calls if k == "videos.insert")
    assert insert["body"]["status"]["containsSyntheticMedia"] is True


def test_cli_stem_defaults_to_the_file_and_missing_subs_stop(files, capsys):
    args = upload_args(files, "--stem", "other")
    assert main(args, service_factory=lambda: pytest.fail("no service needed")) == 1
    assert "no other.<lang>.srt files in" in capsys.readouterr().err


def test_cli_refuses_over_the_unit_limit(files, capsys):
    service = FakeYouTube()
    args = upload_args(files, "--max-units", "2000", "--apply")
    assert main(args, service_factory=lambda: service, media=str, video_media=str) == 1
    assert "the upload costs 2451 units, over --max-units 2000" in capsys.readouterr().err
    assert "videos.insert" not in service.called()


def test_media_helpers_build_resumable_video_and_typed_image(files):
    pytest.importorskip("googleapiclient.http")
    from trans_sub.youtube import auth

    video = auth.video_upload(files["video"])
    assert video.resumable() and video.chunksize() == 8 * 1024 * 1024
    assert video.mimetype() == "video/*"
    image = auth.image_upload(files["thumb"])
    assert not image.resumable() and image.mimetype() == "image/png"
