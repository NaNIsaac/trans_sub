"""A stand-in for the googleapiclient YouTube v3 service: same call chain, records every call.
Nothing reaches YouTube."""

from copy import deepcopy

LANGS = [
    "ar",
    "de",
    "en",
    "es",
    "fil",
    "fr",
    "hi",
    "id",
    "ja",
    "ko",
    "pt-BR",
    "ru",
    "th",
    "tr",
    "vi",
]
LANGS += ["zh-Hans", "zh-Hant"]


class _Progress:
    def __init__(self, share):
        self.share = share

    def progress(self):
        return self.share


class _Request:
    def __init__(self, result=None, error=None, on_execute=None, chunks=2):
        self.result, self.error, self.on_execute = result, error, on_execute
        self.chunks, self.sent = chunks, 0

    def execute(self):
        if self.error:
            raise self.error
        if self.on_execute:
            self.on_execute()
        return deepcopy(self.result)

    def next_chunk(self):
        """A resumable upload: ``chunks`` progress reports, then the response."""
        if self.error:
            raise self.error
        self.sent += 1
        if self.sent <= self.chunks:
            return _Progress(self.sent / (self.chunks + 1)), None
        return None, self.execute()


class _Resource:
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def __getattr__(self, method):
        def call(**kwargs):
            key = f"{self.name}.{method}"
            self.owner.calls.append((key, kwargs))
            return self.owner.respond(key, kwargs)

        return call


class FakeYouTube:
    def __init__(self, video=None, tracks=(), langs=LANGS, fail=None):
        self.video = deepcopy(video)
        self.tracks = list(deepcopy(tracks))
        self.langs = langs
        self.fail = fail or {}
        self.calls = []

    def videos(self):
        return _Resource(self, "videos")

    def captions(self):
        return _Resource(self, "captions")

    def i18nLanguages(self):
        return _Resource(self, "i18nLanguages")

    def thumbnails(self):
        return _Resource(self, "thumbnails")

    def respond(self, key, kwargs):
        if key in self.fail:
            return _Request(error=self.fail[key])
        if key == "videos.list":
            return _Request({"items": [self.video] if self.video else []})
        if key == "captions.list":
            return _Request({"items": self.tracks})
        if key == "i18nLanguages.list":
            return _Request({"items": [{"id": x, "snippet": {"hl": x}} for x in self.langs]})
        if key == "videos.update":

            def store():
                self.video.update(deepcopy(kwargs["body"]))

            return _Request(kwargs["body"], on_execute=store)
        if key == "videos.insert":
            return _Request({"id": "up456", **deepcopy(kwargs["body"])})
        return _Request({"id": "new"})

    def called(self):
        return [key for key, _ in self.calls]


def video(**snippet):
    base = {"title": "Morning talk", "description": "A talk.", "categoryId": "10"}
    base.update(snippet)
    return {
        "id": "vid123",
        "snippet": {**base, "channelId": "chan", "publishedAt": "2026-01-01T00:00:00Z"},
        "localizations": {"de": {"title": "Morgenrede", "description": "Eine Rede."}},
    }


def track(track_id, lang, kind="standard", name=""):
    return {"id": track_id, "snippet": {"language": lang, "trackKind": kind, "name": name}}
