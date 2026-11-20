# trans_sub

[English](README.md)

`.srt` 자막 파일을 여러 언어로 옮기고, 결과를 원본과 대조해 검사합니다.

번역 파일은 원본의 cue와 시간을 그대로 두고 글만 바꿉니다. 글을 얻는 길은 두 가지입니다.

- **번역표로** (`template`, `build`, `check`): 원본의 서로 다른 줄마다, 언어마다 한 행씩인 텍스트 표를 직접, 번역가가, 또는 아무 AI 채팅이 채웁니다. `trans-sub`가 그 표로 언어마다 `.srt`를 하나씩 쓰고 모든 파일을 검사합니다. 이 명령들은 네트워크를 쓰지 않습니다.
- **LLM provider로** (`translate`): [pysubtrans](https://github.com/machinewrapped/llm-subtrans)(`MIT`)를 거쳐 OpenRouter, Gemini 같은 provider에 파일을 보냅니다. API 키가 필요합니다.

## 설치

Python 3.13과 [uv](https://docs.astral.sh/uv/)가 필요합니다.

<!-- test -->
```sh
uv sync
```

<!-- test -->
```sh
uv run trans-sub --help
```

## 빠른 시작

저장소에 작은 예제가 있습니다: `examples/talk.en.srt`와 그 번역표 `examples/talk.table.txt`.

프랑스어와 독일어용 빈 번역표, 그리고 AI 채팅에 표를 채워 달라고 할 프롬프트를 씁니다:

<!-- test -->
```sh
uv run trans-sub template examples/talk.en.srt --langs fr de --out out
```

`out/talk.table.txt`와 `out/talk.prompt.txt`가 생깁니다. 프롬프트를 채팅에 붙여 넣거나 표를 직접 채웁니다. 예제 표는 이미 채워져 있으니 바로 만듭니다:

<!-- test -->
```sh
uv run trans-sub build examples/talk.en.srt --table examples/talk.table.txt --out out
```

`out/talk.fr.srt`와 `out/talk.de.srt`가 생깁니다. 원본과 대조해 검사합니다:

<!-- test -->
```sh
uv run trans-sub check examples/talk.en.srt out
```

## 번역표

원본의 서로 다른 줄마다 블록 하나. 블록은 `@`와 그 줄로 시작하고, 아래의 `<lang>=<text>` 행이 한 언어의 번역입니다.

```text
# 주석
@Good morning, everyone.
fr=Bonjour à tous.
de=Guten Morgen zusammen.

@The train is late again, so we start without it.
fr=Le train est encore en retard,|on commence sans lui.
```

- 두 줄짜리 원본 cue는 두 줄을 공백 하나로 이어 씁니다.
- `|`는 번역을 cue의 두 줄로 나눕니다.
- 원본 글이 같은 cue는 모두 같은 번역을 받습니다. 한 언어에서 한 줄에 서로 다른 번역 둘을 준 표는 오류입니다.
- 빈 행은 없는 것으로 봅니다. `build`는 빠진 줄 목록을 보여 주고 아무것도 쓰지 않은 채 멈춥니다.
- `--table`은 여러 번 줄 수 있습니다(예: 언어 묶음마다 표 하나). 표끼리 어긋나면 안 됩니다.

## 명령

### `template`

`trans-sub template <source.srt> --langs <lang>... [--table <file>] [--out <dir>] [--force]`

원본의 서로 다른 줄을 한 번씩, 언어마다 한 행씩 담은 `<name>.table.txt`와, 지시문과 표를 담아 아무 채팅에나 붙여 넣을 `<name>.prompt.txt`를 씁니다. `<name>`은 원본 파일 이름에서 `.srt`와 언어 태그를 뗀 것입니다(`talk.en.srt`는 `talk`). `--table` 파일에 있는 행은 채워 두므로, 언어를 더해도 앞의 번역이 남습니다. 표 파일이 이미 있으면 `--force` 없이는 덮어쓰지 않습니다.

### `build`

`trans-sub build <source.srt> --table <file> [--langs <lang>...] [--out <dir>] [--name <name>] [--source-lang <lang>]`

언어마다 `<name>.<lang>.srt`를 씁니다: 원본의 cue와 시간에 표의 글. `--langs`가 없으면 표의 모든 언어를 씁니다. `--source-lang`을 주면 `--langs`의 그 언어는 원본의 사본이 됩니다. 출력은 BOM 없는 UTF-8, LF 줄바꿈입니다.

### `check`

`trans-sub check <source.srt> <file or dir>...`

디렉터리는 그 안의 `<name>.<lang>.srt` 파일들을 뜻합니다. 파일마다 다음이면 실패입니다.

- 올바른 SubRip이 아님(차례대로 번호 붙은 블록, 올바른 시간, UTF-8, BOM 없음);
- cue 개수나 어느 cue의 시간이 원본과 다름;
- 빈 cue, 또는 `--max-lines`(기본 2)보다 줄이 많은 cue;
- `--width`(기본 42)자보다 긴 줄. 중국어·일본어·한국어·태국어 글자가 든 줄은 `--dense-width`(기본 20). 태국어 모음·성조 부호처럼 글자 위아래에 붙는 부호는 세지 않습니다.

초당 `--cps`자(기본 20, `--dense-cps` 15)보다 빨리 읽어야 하는 cue는 실패가 아니라 경고입니다. 시간은 원본이 정하므로 고칠 길은 번역을 줄이는 것뿐입니다. 원본 글 그대로인 cue는 세지 않습니다. `--cps 0`이면 경고를 끕니다. 실패가 하나라도 있거나 파일을 하나도 찾지 못하면 종료 코드는 1입니다.

## LLM provider로 번역

`trans-sub translate <file> --to <lang> --provider <name>`은 파일을 provider에 보내 `<stem>.<to>.srt`를 씁니다. `translate`라는 말 없이 불러도 같습니다. 이 명령은 네트워크와 provider의 API 키가 필요하고, provider가 요금을 매길 수 있습니다.

기본 설치로 `OpenRouter`, `DeepSeek`, `Custom Server`를 씁니다. 전용 SDK가 필요한 provider는 optional extra(`openai`, `azure`, `gemini`, `claude`, `mistral`, `bedrock`, `litellm`)로 설치합니다. 예:

```sh
uv sync --extra gemini
```


기본 provider를 내장하지 않으므로 `--provider`는 항상 필수입니다. API 키는 각 provider의 환경 변수에서 읽습니다.

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

`OpenAI`, `Gemini`, `Claude`, `DeepSeek`, `Mistral`, `Azure`, `Bedrock`, `LiteLLM`은 각각 `OPENAI_API_KEY`, `GEMINI_API_KEY`, `CLAUDE_API_KEY`, `DEEPSEEK_API_KEY`, `MISTRAL_API_KEY`, `AZURE_API_KEY`, `AWS_ACCESS_KEY_ID`, `LITELLM_API_KEY` 환경 변수를 사용합니다.

### 로컬 OpenAI-compatible 서버

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

### Dry run, 이어하기, Python API

- `--dry-run`: API 키나 네트워크 호출 없이 `pysubtrans`로 입력 `.srt`를 파싱하고 배치 수만 확인합니다.
- `--resume`: 원본 `.srt` 옆에 `.subtrans` 프로젝트 파일을 저장해 중단된 작업을 이어서 실행합니다.
- `-o PATH`: 기본 출력 경로(`<stem>.<to>.srt`)를 지정한 경로로 바꿉니다.

```python
from trans_sub import translate_srt

summary = translate_srt("movie.srt", to="ko", provider="OpenRouter")
```

## 라이선스

`trans_sub`는 [MIT](LICENSE) 라이선스를 따르며 `pysubtrans`(`MIT`)와 `srt`(`MIT`)에 의존합니다.
