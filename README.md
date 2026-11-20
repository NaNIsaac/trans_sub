# trans_sub

[한국어](README.ko.md)

Translate `.srt` subtitle files into many languages and check the result against the source.

A translated file keeps the source's cues and times; only the text changes. There are two ways to get the text:

- **From a translation table** (`template`, `build`, `check`, `clip`): you, a translator or any AI chat fill a plain-text table with one row per distinct source line and language. `trans-sub` writes one `.srt` per language from it and checks every file. These commands make no network calls.
- **From an LLM provider** (`translate`): sends the file through [pysubtrans](https://github.com/machinewrapped/llm-subtrans) (`MIT`) to a provider such as OpenRouter or Gemini, with your API key.

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

Cut the second half out of every language for a short; it starts at zero:

<!-- test -->
```sh
uv run trans-sub clip out/talk.fr.srt out/talk.de.srt --from 3.5 --to 8
```

This writes `out/talk_clip.fr.srt` and `out/talk_clip.de.srt`.

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
- `--table` takes one or more files (`--table a.txt b.txt`), and the flag may also be repeated; for example, one table per batch of languages. The tables must agree.

## Commands

### `template`

`trans-sub template <source.srt> --langs <lang>... [--table <file>...] [--out <dir>] [--force]`

Writes `<name>.table.txt` with every distinct source line once and a row per language, and `<name>.prompt.txt`: instructions and the table, to paste into any chat. `<name>` is the source file name without `.srt` and without a language tag (`talk.en.srt` gives `talk`). Rows found in `--table` files are filled in, so adding a language keeps the earlier ones. An existing table file is not overwritten unless `--force` is given.

### `build`

`trans-sub build <source.srt> --table <file>... [--langs <lang>...] [--out <dir>] [--name <name>] [--source-lang <lang>]`

Writes `<name>.<lang>.srt` for each language: the source's cues and times with the table's text. Without `--langs`, every language in the table is written. With `--source-lang`, that language in `--langs` writes a copy of the source. Output is UTF-8 without a byte order mark, with LF line ends.

### `check`

`trans-sub check <source.srt> <file or dir>...`

A directory stands for its `<name>.<lang>.srt` files. Each file fails if:

- it is not well-formed SubRip (numbered blocks in order, valid times, UTF-8, no byte order mark);
- its cue count or any cue time differs from the source;
- a cue is empty or has more than `--max-lines` lines (default 2);
- a line is longer than `--width` characters (default 42), or `--dense-width` (default 20) for a line with Chinese, Japanese, Korean or Thai characters. Marks above or below a letter, such as Thai vowels and tone marks, are not counted.

A cue read faster than `--cps` characters a second (default 20; `--dense-cps` 15) is a warning, not a failure: the source fixes the time, so the fix is a shorter translation. A cue left in the source text is not counted. `--cps 0` turns the warning off. The exit code is 1 on any failure, or when no file was found.

### `clip`

`trans-sub clip <file.srt>... --from <s> --to <s> [--then <from>:<to>]... [--suffix _clip] [--out <dir>] [--min-piece 0.5]`

Keeps the cues between `--from` and `--to` (seconds), shifted to start at zero. Each `--then` range plays after the one before, so a looping short that ends on its own opening is `--from <body start> --to <body end> --then <lead start>:<body start>`. A cue that crosses a range edge is cut at the edge; a piece shorter than `--min-piece` seconds is dropped. `talk.fr.srt` is written as `talk_clip.fr.srt`.

Cut the source and every translation with the same ranges, so all of them keep the same cues and times. `check` on the clipped files then compares against the clipped source.

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

## License

`trans_sub` is [MIT](LICENSE) licensed and depends on `pysubtrans` (`MIT`) and `srt` (`MIT`).
