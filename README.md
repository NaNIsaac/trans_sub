# trans_sub

[한국어](README.ko.md)

Translate `.srt` subtitle files into many languages and check the result against the source.

A translated file keeps the source's cues and times; only the text changes. There are two ways to get the text:

- **From a translation table** (`template`, `build`, `check`): you, a translator or any AI chat fill a plain-text table with one row per distinct source line and language. `trans-sub` writes one `.srt` per language from it and checks every file. These commands make no network calls.
- **From an LLM provider** (`translate`): sends the file through [pysubtrans](https://github.com/machinewrapped/llm-subtrans) (`MIT`) to a provider such as OpenRouter or Gemini, with your API key.

The `youtube` command puts the title, description and subtitles of every language on one YouTube video ([Publishing to YouTube](#publishing-to-youtube)).

## Install

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

<!-- test -->
```sh
uv sync
```

<!-- test -->
```sh
uv run trans-sub --help
```

## Quick start

The repository has a small example: `examples/talk.en.srt` and its table, `examples/talk.table.txt`.

Write an empty table for French and German, and a prompt that asks an AI chat to fill it:

<!-- test -->
```sh
uv run trans-sub template examples/talk.en.srt --langs fr de --out out
```

This writes `out/talk.table.txt` and `out/talk.prompt.txt`. Paste the prompt into a chat, or fill the table by hand. The example table is already filled, so build from it:

<!-- test -->
```sh
uv run trans-sub build examples/talk.en.srt --table examples/talk.table.txt --out out
```

This writes `out/talk.fr.srt` and `out/talk.de.srt`. Check them against the source:

<!-- test -->
```sh
uv run trans-sub check examples/talk.en.srt out
```

## Translation tables

One block per distinct source line. A block starts with `@` and the line; each `<lang>=<text>` row under it is that line in one language.

```text
# A comment
@Good morning, everyone.
fr=Bonjour à tous.
de=Guten Morgen zusammen.

@The train is late again, so we start without it.
fr=Le train est encore en retard,|on commence sans lui.
```

- A source cue of two lines is written as its lines joined by one space.
- `|` splits a translation into two lines of the cue.
- Every cue with the same source text gets the same translation. A table that gives one line two different translations in the same language is an error.
- An empty row counts as missing. `build` stops with the list of missing lines and writes nothing.
- `--table` can be repeated (for example, one table per batch of languages). The tables must agree.

## Commands

### `template`

`trans-sub template <source.srt> --langs <lang>... [--table <file>] [--out <dir>] [--force]`

Writes `<name>.table.txt` with every distinct source line once and a row per language, and `<name>.prompt.txt`: instructions and the table, to paste into any chat. `<name>` is the source file name without `.srt` and without a language tag (`talk.en.srt` gives `talk`). Rows found in `--table` files are filled in, so adding a language keeps the earlier ones. An existing table file is not overwritten unless `--force` is given.

### `build`

`trans-sub build <source.srt> --table <file> [--langs <lang>...] [--out <dir>] [--name <name>] [--source-lang <lang>]`

Writes `<name>.<lang>.srt` for each language: the source's cues and times with the table's text. Without `--langs`, every language in the table is written. With `--source-lang`, that language in `--langs` writes a copy of the source. Output is UTF-8 without a byte order mark, with LF line ends.

### `check`

`trans-sub check <source.srt> <file or dir>...`

A directory stands for its `<name>.<lang>.srt` files. Each file fails if:

- it is not well-formed SubRip (numbered blocks in order, valid times, UTF-8, no byte order mark);
- its cue count or any cue time differs from the source;
- a cue is empty or has more than `--max-lines` lines (default 2);
- a line is longer than `--width` characters (default 42), or `--dense-width` (default 20) for a line with Chinese, Japanese, Korean or Thai characters. Marks above or below a letter, such as Thai vowels and tone marks, are not counted.

A cue read faster than `--cps` characters a second (default 20; `--dense-cps` 15) is a warning, not a failure: the source fixes the time, so the fix is a shorter translation. A cue left in the source text is not counted. `--cps 0` turns the warning off. The exit code is 1 on any failure, or when no file was found.

## Translating with an LLM provider

`trans-sub translate <file> --to <lang> --provider <name>` sends the file to the provider and writes `<stem>.<to>.srt`. The same call without the word `translate` does the same. This command needs network access and the provider's API key, and the provider may charge for it.

The core install covers `OpenRouter`, `DeepSeek` and `Custom Server`. Providers with their own SDK install as optional extras (`openai`, `azure`, `gemini`, `claude`, `mistral`, `bedrock`, `litellm`), for example:

```sh
uv sync --extra gemini
```

No default provider is built in, so `--provider` is always required. Credentials come from each provider's environment variable.

### Hosted provider

Shell:

```sh
export OPENROUTER_API_KEY="your-key"
uv run trans-sub translate movie.srt --to ko --provider OpenRouter
```

PowerShell:

```powershell
$env:OPENROUTER_API_KEY = "your-key"
uv run trans-sub translate movie.srt --to ko --provider OpenRouter
```

Optional extras (`openai`, `gemini`, `claude`, `mistral`, `azure`, `bedrock`, `litellm`) read `OPENAI_API_KEY`, `GEMINI_API_KEY`, `CLAUDE_API_KEY`, `MISTRAL_API_KEY`, `AZURE_API_KEY`, `AWS_ACCESS_KEY_ID`, or `LITELLM_API_KEY` from the environment (and `DEEPSEEK_API_KEY` for `DeepSeek`).

### Local OpenAI-compatible server

Shell:

```sh
export CUSTOM_SERVER_ADDRESS="http://<host>:<port>"
uv run trans-sub translate movie.srt --to ko --provider "Custom Server" --model "<model-name>"
```

PowerShell:

```powershell
$env:CUSTOM_SERVER_ADDRESS = "http://<host>:<port>"
uv run trans-sub translate movie.srt --to ko --provider "Custom Server" --model "<model-name>"
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
