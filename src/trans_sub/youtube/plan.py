"""Work out what one push to a YouTube video changes, then apply it.

Everything here talks to a ``service`` object shaped like the one ``googleapiclient`` builds for
YouTube Data API v3 (``service.videos().list(...).execute()``), so tests can pass a fake one.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Quota units per call, from https://developers.google.com/youtube/v3/determine_quota_cost
UNITS = {
    "videos.list": 1,
    "videos.update": 50,
    "captions.list": 50,
    "captions.insert": 400,
    "captions.update": 450,
    "i18nLanguages.list": 1,
}
DAILY_QUOTA = 10_000
DONE = {"insert": "inserted", "update": "updated"}
DEFAULT_MAX_UNITS = 9_000

# Snippet fields a videos.update keeps only if they are sent back: an omitted one is deleted.
WRITABLE_SNIPPET = ("title", "description", "tags", "categoryId", "defaultLanguage")
TITLE_MAX = 100
DESCRIPTION_MAX_BYTES = 5000


class PushError(ValueError):
    """Input the push refuses before it writes anything."""


@dataclass(frozen=True, slots=True)
class Meta:
    title: str
    description: str


@dataclass
class Step:
    lang: str
    part: str  # "metadata" or "caption"
    action: str  # "add", "update", "insert", "equal", "skip"
    detail: str = ""
    units: int = 0
    track_id: str | None = None
    srt: Path | None = None


@dataclass
class Plan:
    video_id: str
    title: str
    default_lang: str
    default_lang_from_flag: bool
    snippet: dict[str, Any]
    localizations: dict[str, dict[str, str]]
    steps: list[Step] = field(default_factory=list)
    read_units: int = 0
    unknown_langs: list[str] = field(default_factory=list)

    @property
    def video_update(self) -> bool:
        return any(s.part == "metadata" and s.action in ("add", "update") for s in self.steps)

    @property
    def write_units(self) -> int:
        captions = sum(s.units for s in self.steps if s.part == "caption")
        return captions + (UNITS["videos.update"] if self.video_update else 0)

    @property
    def total_units(self) -> int:
        return self.read_units + self.write_units


def check_meta(lang: str, meta: Meta) -> None:
    if not meta.title.strip():
        raise PushError(f"{lang}: empty title")
    if len(meta.title) > TITLE_MAX:
        raise PushError(f"{lang}: title has {len(meta.title)} characters, the limit is {TITLE_MAX}")
    size = len(meta.description.encode())
    if size > DESCRIPTION_MAX_BYTES:
        raise PushError(
            f"{lang}: description is {size} bytes, the limit is {DESCRIPTION_MAX_BYTES}"
        )
    for name, text in (("title", meta.title), ("description", meta.description)):
        if "<" in text or ">" in text:
            raise PushError(f"{lang}: {name} contains '<' or '>', which YouTube does not accept")


def find_subtitles(directory: Path, stem: str) -> dict[str, Path]:
    """``{lang: path}`` for every ``<stem>.<lang>.srt`` in ``directory``."""
    found = {}
    for path in sorted(directory.glob("*.srt")):
        name = path.name
        if name.startswith(f"{stem}.") and name.count(".") >= 2:
            lang = name[len(stem) + 1 : -len(".srt")]
            if lang and "." not in lang:
                found[lang] = path
    return found


def make_plan(
    service: Any,
    video_id: str,
    meta: dict[str, Meta],
    subtitles: dict[str, Path],
    *,
    default_lang: str | None = None,
    captions: str = "all",
    check_langs: bool = True,
) -> Plan:
    """Read the video and its caption tracks and list the calls a push would make."""
    for lang, item in meta.items():
        check_meta(lang, item)

    found = service.videos().list(part="snippet,localizations", id=video_id).execute()
    items = found.get("items", [])
    if not items:
        raise PushError(f"no video {video_id!r} on this account (or no access to it)")
    video = items[0]
    snippet = video["snippet"]
    current_default = snippet.get("defaultLanguage")
    if current_default and default_lang and default_lang != current_default:
        raise PushError(
            f"--default-lang {default_lang} differs from the video's default language "
            f"{current_default}; leave the flag out or change the default in YouTube Studio"
        )
    if not current_default and not default_lang:
        raise PushError("the video has no default language; pass --default-lang")
    plan = Plan(
        video_id=video_id,
        title=snippet.get("title", ""),
        default_lang=current_default or default_lang,
        default_lang_from_flag=not current_default,
        snippet={k: snippet[k] for k in WRITABLE_SNIPPET if k in snippet},
        localizations={k: dict(v) for k, v in video.get("localizations", {}).items()},
        read_units=UNITS["videos.list"],
    )
    plan.snippet["defaultLanguage"] = plan.default_lang

    if check_langs:
        listed = service.i18nLanguages().list(part="snippet").execute()
        plan.read_units += UNITS["i18nLanguages.list"]
        known = {item["id"] for item in listed.get("items", [])}
        known |= {item["snippet"]["hl"] for item in listed.get("items", []) if "snippet" in item}
        plan.unknown_langs = sorted((set(meta) | set(subtitles)) - known)

    for lang in sorted(meta):
        want = meta[lang]
        if lang == plan.default_lang:
            have = Meta(snippet.get("title", ""), snippet.get("description", ""))
            where = "video title and description"
        elif lang in plan.localizations:
            loc = plan.localizations[lang]
            have = Meta(loc.get("title", ""), loc.get("description", ""))
            where = "localization"
        else:
            plan.steps.append(Step(lang, "metadata", "add", "localization"))
            continue
        action = "equal" if have == want else "update"
        plan.steps.append(Step(lang, "metadata", action, where))

    if captions == "none" or not subtitles:
        return plan
    tracks = service.captions().list(part="snippet", videoId=video_id).execute().get("items", [])
    plan.read_units += UNITS["captions.list"]
    by_lang: dict[str, list[dict]] = {}
    for track in tracks:
        if track["snippet"].get("trackKind", "standard").lower() != "asr":
            by_lang.setdefault(track["snippet"]["language"], []).append(track)
    for lang in sorted(subtitles):
        mine = by_lang.get(lang, [])
        if len(mine) > 1:
            names = ", ".join(repr(t["snippet"].get("name", "")) for t in mine)
            raise PushError(
                f"{lang}: the video has {len(mine)} caption tracks in this language ({names}); "
                "remove the extra ones in YouTube Studio first"
            )
        if not mine:
            units = UNITS["captions.insert"]
            plan.steps.append(
                Step(lang, "caption", "insert", "new track", units, srt=subtitles[lang])
            )
        elif captions == "missing":
            plan.steps.append(Step(lang, "caption", "skip", "track exists", track_id=mine[0]["id"]))
        else:
            units = UNITS["captions.update"]
            detail = "replace the file (the API cannot show the old text to compare)"
            track = mine[0]["id"]
            plan.steps.append(
                Step(lang, "caption", "update", detail, units, track_id=track, srt=subtitles[lang])
            )
    return plan


def video_body(plan: Plan, meta: dict[str, Meta]) -> dict[str, Any]:
    """The videos.update body: the whole writable snippet, every localization kept, ours merged in."""
    snippet = dict(plan.snippet)
    localizations = {k: dict(v) for k, v in plan.localizations.items()}
    for lang, item in meta.items():
        if lang == plan.default_lang:
            snippet["title"], snippet["description"] = item.title, item.description
        else:
            localizations[lang] = {"title": item.title, "description": item.description}
    return {"id": plan.video_id, "snippet": snippet, "localizations": localizations}


def apply(
    service: Any,
    plan: Plan,
    meta: dict[str, Meta],
    media: Callable[[Path], Any],
    track_name: str = "",
    log: Callable[[str], None] = print,
) -> None:
    """Make the plan's writes: the video's metadata first, then each caption track."""
    done: list[str] = []

    def failed(what: str, exc: Exception) -> PushError:
        before = ", ".join(done) or "nothing"
        return PushError(f"{what} failed: {exc}. Written before it: {before}")

    if plan.video_update:
        body = video_body(plan, meta)
        try:
            service.videos().update(part="snippet,localizations", body=body).execute()
        except Exception as exc:  # the API client raises HttpError and transport errors
            raise failed("videos.update", exc) from exc
        done.append("video metadata")
        log("video: title, description and localizations written")
    for step in plan.steps:
        if step.part != "caption" or step.action not in ("insert", "update"):
            continue
        try:
            if step.action == "insert":
                snippet = {"videoId": plan.video_id, "language": step.lang, "name": track_name}
                request = service.captions().insert(
                    part="snippet", body={"snippet": snippet}, media_body=media(step.srt)
                )
            else:
                request = service.captions().update(
                    part="id", body={"id": step.track_id}, media_body=media(step.srt)
                )
            request.execute()
        except Exception as exc:  # the API client raises HttpError and transport errors
            raise failed(f"{step.lang} caption {step.action}", exc) from exc
        done.append(f"{step.lang} caption")
        log(f"{step.lang}: caption {DONE[step.action]}")


def render(plan: Plan, max_units: int) -> list[str]:
    lines = [f"video {plan.video_id}: {plan.title}"]
    source = (
        "from --default-lang; the push sets it on the video"
        if plan.default_lang_from_flag
        else "set on the video"
    )
    lines.append(f"default language: {plan.default_lang} ({source})")
    width = max([len(s.lang) for s in plan.steps] + [4])
    for step in plan.steps:
        units = f" [{step.units} units]" if step.units else ""
        lines.append(
            f"  {step.lang:<{width}}  {step.part:<8}  {step.action:<6}  {step.detail}{units}"
        )
    if plan.video_update:
        lines.append(f"  one videos.update for all metadata [{UNITS['videos.update']} units]")
    if plan.unknown_langs:
        lines.append("languages YouTube does not list: " + ", ".join(plan.unknown_langs))
    lines.append(
        f"quota: {plan.read_units} units to read, {plan.write_units} to write, "
        f"{plan.total_units} in all (limit {max_units}, daily quota {DAILY_QUOTA})"
    )
    return lines
