# trans_sub

[한국어](README.ko.md)

CLI and Python wrapper around [pysubtrans](https://github.com/machinewrapped/llm-subtrans) (`MIT`) for translating `.srt` subtitle files while preserving cue order and timing.

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

No default provider is built in, so `--provider` is always required. Keys come from each provider's environment variable; nothing accepts `--api-key`.

### Hosted provider

```sh
export OPENROUTER_API_KEY="your-key"
uv run trans-sub movie.srt --to ko --provider OpenRouter
```

Optional extras (`openai`, `gemini`, `claude`, `mistral`, `azure`, `bedrock`, `litellm`) read `OPENAI_API_KEY`, `GEMINI_API_KEY`, `CLAUDE_API_KEY`, `MISTRAL_API_KEY`, `AZURE_API_KEY`, `AWS_ACCESS_KEY_ID`, or `LITELLM_API_KEY` from the environment (and `DEEPSEEK_API_KEY` for `DeepSeek`).

### Local OpenAI-compatible server

```sh
export CUSTOM_SERVER_ADDRESS="http://<host>:<port>"
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

## License

`trans_sub` is [MIT](LICENSE) licensed and depends on `pysubtrans` (`MIT`) and `srt` (`MIT`).
