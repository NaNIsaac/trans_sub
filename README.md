# trans_sub

[한국어](README.ko.md)

CLI and Python wrapper around [pysubtrans](https://github.com/machinewrapped/llm-subtrans) (`MIT`) for translating `.srt` subtitle files while preserving cue order and timing, and a command that puts titles, descriptions and subtitles of every language on a YouTube video ([Publishing to YouTube](#publishing-to-youtube)).

## Install

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

Core install (`OpenRouter`, `DeepSeek`, and `Custom Server` work without extra SDKs):

<!-- test -->
```sh
uv sync
```

<!-- test -->
```sh
uv run trans-sub --help
```

SDK-backed providers install as optional extras (`openai`, `azure`, `gemini`, `claude`, `mistral`, `bedrock`, `litellm`), for example:

```sh
uv sync --extra gemini
```

## Usage

No default provider is built in, so `--provider` is always required. Credentials come from each provider's environment variable.

### Hosted provider

Shell:

```sh
export OPENROUTER_API_KEY="your-key"
uv run trans-sub movie.srt --to ko --provider OpenRouter
```

PowerShell:

```powershell
$env:OPENROUTER_API_KEY = "your-key"
uv run trans-sub movie.srt --to ko --provider OpenRouter
```

Optional extras (`openai`, `gemini`, `claude`, `mistral`, `azure`, `bedrock`, `litellm`) read `OPENAI_API_KEY`, `GEMINI_API_KEY`, `CLAUDE_API_KEY`, `MISTRAL_API_KEY`, `AZURE_API_KEY`, `AWS_ACCESS_KEY_ID`, or `LITELLM_API_KEY` from the environment (and `DEEPSEEK_API_KEY` for `DeepSeek`).

### Local OpenAI-compatible server

Shell:

```sh
export CUSTOM_SERVER_ADDRESS="http://<host>:<port>"
uv run trans-sub movie.srt --to ko --provider "Custom Server" --model "<model-name>"
```

PowerShell:

```powershell
$env:CUSTOM_SERVER_ADDRESS = "http://<host>:<port>"
uv run trans-sub movie.srt --to ko --provider "Custom Server" --model "<model-name>"
```

### Dry run, resume, and Python API

- `--dry-run`: parses and batches the input with `pysubtrans` without reading credentials or making API calls.
- `--resume`: keeps a `.subtrans` project file next to the source `.srt` so interrupted runs can continue.
- `-o PATH`: overrides the default `<stem>.<to>.srt` output path.

```python
from trans_sub import translate_srt

summary = translate_srt("movie.srt", to="ko", provider="OpenRouter")
```

## Publishing to YouTube

`trans-sub youtube push` puts the title, description and subtitles of every language on one video you own. It reads the video first and shows, per language, what it would add, update or leave alone, with the quota it costs. Nothing changes until you add `--apply`. Languages already on the video that are not in your input are kept.

Install the optional Google packages:

```sh
uv sync --extra youtube
```

<!-- test -->
```sh
uv run trans-sub youtube push --help
```

### Setup (once)

1. In the [Google Cloud console](https://console.cloud.google.com/), create a project.
2. In the API Library, open **YouTube Data API v3** and click **Enable**.
3. In **Google Auth Platform**, fill in **Branding** (app name, support email). Under **Audience**, choose **External**, leave the publishing status at **Testing**, and add the Google account that owns the channel as a test user.
4. Under **Clients**, click **Create client**, choose **Desktop app**, and create it. Save the client as a JSON file; the full client secret is shown only at creation.
5. Put that file at the default path below, or pass `--client-secret <file>`, or set `TRANS_SUB_YOUTUBE_CLIENT_SECRET`. Keep it out of any repository.

| File | Default path | Flag | Environment variable |
|---|---|---|---|
| OAuth client | `<config>/trans-sub/youtube-client.json` | `--client-secret` | `TRANS_SUB_YOUTUBE_CLIENT_SECRET` |
| Token | `<config>/trans-sub/youtube-token.json` | `--token` | `TRANS_SUB_YOUTUBE_TOKEN` |

`<config>` is `%APPDATA%` on Windows, `~/Library/Application Support` on macOS and `$XDG_CONFIG_HOME` (or `~/.config`) elsewhere.

The first push opens a browser to log in. Pick the channel's account. Because the app is in Testing and not verified by Google, the browser warns that Google has not verified the app; continue, since it is your own client. The tool asks for one scope, `youtube.force-ssl`, which caption uploads require, and writes the token file itself (readable by you only).

While the app is in **Testing**, Google lets the login last 7 days; after that the next push opens the browser again. Publishing the app to **In production** removes that limit; Google may then ask for app verification before it drops the warning. Sources: [OAuth for installed apps](https://developers.google.com/youtube/v3/guides/auth/installed-apps), [refresh token expiration](https://developers.google.com/identity/protocols/oauth2#expiration), [audience and test users](https://support.google.com/cloud/answer/15549945).

### Each video

Titles and descriptions come from a JSON file keyed by language:

```json
{"en": {"title": "Morning talk", "description": "A talk."},
 "fr": {"title": "Discours du matin", "description": "Un discours."}}
```

`youtube meta` writes that file from a Markdown table whose first column is the language, choosing the title and description columns by header or by number:

```sh
uv run trans-sub youtube meta titles.md --title-column Title --description-column Description -o meta.json
```

Then look at the plan, and apply it:

```sh
uv run trans-sub youtube push --video <id> --meta meta.json --subs subs --stem talk
uv run trans-sub youtube push --video <id> --meta meta.json --subs subs --stem talk --apply
```

`--subs subs --stem talk` takes every `subs/talk.<lang>.srt`. For each language:

- The default language's title and description are the video's own; the others are localizations. Equal text is left alone. All of them go in one `videos.update`, which sends back the video's title, description, tags, category and default language as they are.
- A caption track in that language is replaced; with none, one is added. `--captions missing` only adds, `--captions none` skips subtitles. Two tracks in one language stop the push (remove one in YouTube Studio). Automatic captions are ignored.
- A video without a default language needs `--default-lang`, which the push then sets.
- Language codes are checked against YouTube's list first (`--skip-lang-check` to skip).

Titles are limited to 100 characters, descriptions to 5000 bytes, and neither may contain `<` or `>`; the push checks this before it writes.

### Quota

Each call costs units from the project's daily quota of 10,000 (reset at midnight Pacific time). A push refuses to apply above `--max-units` (default 9000).

| Call | Units | Used for |
|---|---|---|
| `videos.list` | 1 | reading the video |
| `i18nLanguages.list` | 1 | the language check |
| `captions.list` | 50 | reading the caption tracks |
| `videos.update` | 50 | all titles and descriptions, once |
| `captions.insert` | 400 | each new track |
| `captions.update` | 450 | each replaced track |

Source: [quota costs](https://developers.google.com/youtube/v3/determine_quota_cost). Seventeen new tracks with metadata cost 52 + 50 + 17 × 400 = 6902 units; replacing seventeen tracks costs 7752, so one video's full push fits in a day, two do not.

## License

`trans_sub` is [MIT](LICENSE) licensed and depends on `pysubtrans` (`MIT`) and `srt` (`MIT`).
