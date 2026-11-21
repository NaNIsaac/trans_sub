"""Upload a new video with its titles, descriptions, thumbnail and subtitles of every language.

The upload is planned first, like a push: nothing is sent without ``apply``. The video goes up with
``videos.insert`` (resumable), then the thumbnail with ``thumbnails.set``, then the subtitles as new
caption tracks through the push's own ``apply``.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from trans_sub.youtube.plan import UNITS, Meta, Plan, PushError, Step, apply, check_meta

UPLOAD_UNITS = {"videos.insert": 1600, "thumbnails.set": 50}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".wmv", ".flv", ".mpg", ".mpeg"}
THUMB_SUFFIXES = {".png", ".jpg", ".jpeg"}
THUMB_MAX_BYTES = 2 * 1024 * 1024
PRIVACY = ("private", "unlisted", "public")
# YouTube keeps a video uploaded by an API project that has not passed its audit private, whatever
# the request asks: https://developers.google.com/youtube/v3/docs/videos/insert
UNAUDITED_NOTE = (
    "an API project that has not passed YouTube's audit can only upload private videos; "
    "change the privacy in YouTube Studio afterwards"
)


@dataclass
class Upload:
    file: Path
    default_lang: str
    meta: dict[str, Meta]
    privacy: str = "private"
    publish_at: str | None = None
    category: str | None = None
    made_for_kids: bool = False
    synthetic: bool | None = None
    thumbnail: Path | None = None
    subtitles: dict[str, Path] = field(default_factory=dict)
    read_units: int = 0
    unknown_langs: list[str] = field(default_factory=list)

    @property
    def write_units(self) -> int:
        thumb = UPLOAD_UNITS["thumbnails.set"] if self.thumbnail else 0
        return (
            UPLOAD_UNITS["videos.insert"] + thumb + UNITS["captions.insert"] * len(self.subtitles)
        )

    @property
    def total_units(self) -> int:
        return self.read_units + self.write_units


def parse_publish_at(text: str, now: datetime | None = None) -> str:
    """An ISO 8601 time with its offset, in the future, as the UTC string YouTube takes."""
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        raise PushError(f"--publish-at {text!r} is not an ISO 8601 time") from None
    if when.tzinfo is None:
        raise PushError(f"--publish-at {text!r} needs an offset, such as +09:00 or Z")
    when = when.astimezone(UTC)
    if when <= (now or datetime.now(UTC)):
        raise PushError(f"--publish-at {text!r} is not in the future")
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def check_files(file: Path, thumbnail: Path | None) -> None:
    if not file.is_file():
        raise PushError(f"no video file {file}")
    if file.suffix.lower() not in VIDEO_SUFFIXES:
        raise PushError(
            f"{file.name}: not a video file YouTube takes ({file.suffix or 'no suffix'})"
        )
    if thumbnail is None:
        return
    if not thumbnail.is_file():
        raise PushError(f"no thumbnail file {thumbnail}")
    if thumbnail.suffix.lower() not in THUMB_SUFFIXES:
        raise PushError(f"{thumbnail.name}: the thumbnail must be PNG or JPEG")
    size = thumbnail.stat().st_size
    if size > THUMB_MAX_BYTES:
        raise PushError(f"{thumbnail.name}: {size} bytes, the thumbnail limit is 2 MB")


def make_upload(
    service: Any,
    file: Path,
    meta: dict[str, Meta],
    default_lang: str,
    *,
    subtitles: dict[str, Path] | None = None,
    thumbnail: Path | None = None,
    privacy: str = "private",
    publish_at: str | None = None,
    category: str | None = None,
    made_for_kids: bool = False,
    synthetic: bool | None = None,
    check_langs: bool = True,
) -> Upload:
    """Check the input and list what an upload would send. Reads only YouTube's language list."""
    check_files(file, thumbnail)
    if default_lang not in meta:
        langs = ", ".join(sorted(meta)) or "none"
        raise PushError(f"--meta has no {default_lang!r}, the default language (it has {langs})")
    for lang, item in meta.items():
        check_meta(lang, item)
    if privacy not in PRIVACY:
        raise PushError(f"privacy {privacy!r} is not one of {', '.join(PRIVACY)}")
    if publish_at and privacy != "private":
        raise PushError(
            "--publish-at needs --privacy private; YouTube makes it public at that time"
        )
    up = Upload(
        file=file,
        default_lang=default_lang,
        meta=meta,
        privacy=privacy,
        publish_at=publish_at,
        category=category,
        made_for_kids=made_for_kids,
        synthetic=synthetic,
        thumbnail=thumbnail,
        subtitles=dict(subtitles or {}),
    )
    if check_langs:
        listed = service.i18nLanguages().list(part="snippet").execute()
        up.read_units += UNITS["i18nLanguages.list"]
        known = {item["id"] for item in listed.get("items", [])}
        known |= {item["snippet"]["hl"] for item in listed.get("items", []) if "snippet" in item}
        up.unknown_langs = sorted((set(meta) | set(up.subtitles) | {default_lang}) - known)
    return up


def insert_body(up: Upload) -> dict[str, Any]:
    """The videos.insert body: the default language's text is the video's own, the rest
    localizations."""
    main = up.meta[up.default_lang]
    snippet: dict[str, Any] = {
        "title": main.title,
        "description": main.description,
        "defaultLanguage": up.default_lang,
        "defaultAudioLanguage": up.default_lang,
    }
    if up.category:
        snippet["categoryId"] = up.category
    status: dict[str, Any] = {
        "privacyStatus": up.privacy,
        "selfDeclaredMadeForKids": up.made_for_kids,
    }
    if up.publish_at:
        status["publishAt"] = up.publish_at
    if up.synthetic is not None:
        status["containsSyntheticMedia"] = up.synthetic
    localizations = {
        lang: {"title": m.title, "description": m.description}
        for lang, m in sorted(up.meta.items())
        if lang != up.default_lang
    }
    return {"snippet": snippet, "status": status, "localizations": localizations}


def render_upload(up: Upload, max_units: int) -> list[str]:
    size = up.file.stat().st_size / 1_000_000
    lines = [f"upload {up.file.name} ({size:.1f} MB) as a new video"]
    lines.append(f"  title ({up.default_lang}): {up.meta[up.default_lang].title}")
    when = f", public at {up.publish_at}" if up.publish_at else ""
    lines.append(f"  privacy: {up.privacy}{when}")
    lines.append(f"  made for kids: {'yes' if up.made_for_kids else 'no'}")
    if up.synthetic is not None:
        lines.append(f"  altered or synthetic content: {'yes' if up.synthetic else 'no'}")
    if up.category:
        lines.append(f"  category: {up.category}")
    others = sorted(lang for lang in up.meta if lang != up.default_lang)
    if others:
        lines.append(f"  localizations: {', '.join(others)}")
    lines.append(f"  videos.insert, resumable [{UPLOAD_UNITS['videos.insert']} units]")
    if up.thumbnail:
        lines.append(f"  thumbnail {up.thumbnail.name} [{UPLOAD_UNITS['thumbnails.set']} units]")
    for lang in sorted(up.subtitles):
        lines.append(f"  {lang} caption insert new track [{UNITS['captions.insert']} units]")
    if up.privacy != "private" or up.publish_at:
        lines.append(f"note: {UNAUDITED_NOTE}")
    if up.unknown_langs:
        lines.append("languages YouTube does not list: " + ", ".join(up.unknown_langs))
    lines.append(
        f"quota: {up.read_units} units to read, {up.write_units} to write, "
        f"{up.total_units} in all (limit {max_units}, daily quota 10000)"
    )
    return lines


def send_video(service: Any, up: Upload, media: Any, log: Callable[[str], None]) -> str:
    request = service.videos().insert(
        part="snippet,status,localizations", body=insert_body(up), media_body=media
    )
    response = None
    shown = -1
    while response is None:
        status, response = request.next_chunk()
        if status:
            percent = int(status.progress() * 100)
            if percent // 10 > shown:
                shown = percent // 10
                log(f"uploading: {percent}%")
    return response["id"]


def apply_upload(
    service: Any,
    up: Upload,
    video_media: Callable[[Path], Any],
    image_media: Callable[[Path], Any],
    caption_media: Callable[[Path], Any],
    track_name: str = "",
    log: Callable[[str], None] = print,
) -> str:
    """Upload the video, then the thumbnail, then each caption track. Returns the new video's ID.

    A failure after the video is up names the video, so the rest can follow with ``push``."""
    try:
        video_id = send_video(service, up, video_media(up.file), log)
    except Exception as exc:  # the API client raises HttpError and transport errors
        raise PushError(f"videos.insert failed: {exc}. Nothing was uploaded") from exc
    log(f"video: uploaded as {video_id} (https://youtu.be/{video_id})")

    def failed(what: str, exc: Exception) -> PushError:
        return PushError(
            f"{what} failed: {exc}. The video is up as {video_id}; finish with "
            f"'trans-sub youtube push --video {video_id}'"
        )

    if up.thumbnail:
        try:
            service.thumbnails().set(
                videoId=video_id, media_body=image_media(up.thumbnail)
            ).execute()
        except Exception as exc:  # the API client raises HttpError and transport errors
            raise failed("thumbnails.set", exc) from exc
        log("thumbnail: set")
    if up.subtitles:
        plan = Plan(
            video_id=video_id,
            title=up.meta[up.default_lang].title,
            default_lang=up.default_lang,
            default_lang_from_flag=False,
            snippet={},
            localizations={},
            steps=[
                Step(lang, "caption", "insert", "new track", UNITS["captions.insert"], srt=path)
                for lang, path in sorted(up.subtitles.items())
            ],
        )
        try:
            apply(service, plan, {}, caption_media, track_name=track_name, log=log)
        except PushError as exc:
            raise failed("captions", exc) from exc
    return video_id
