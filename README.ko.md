# trans_sub

[English](README.md)

cue 순서와 타이밍을 유지한 채 `.srt` 자막 파일을 번역하는 [pysubtrans](https://github.com/machinewrapped/llm-subtrans)(`MIT`) 기반 CLI 및 Python 래퍼입니다.

## 설치

Python 3.13과 [uv](https://docs.astral.sh/uv/)가 필요합니다.

기본 설치(`OpenRouter`, `DeepSeek`, `Custom Server`는 별도 SDK 없이 동작):

<!-- test -->
```sh
uv sync
```

<!-- test -->
```sh
uv run trans-sub --help
```

전용 SDK가 필요한 provider는 optional extra(`openai`, `azure`, `gemini`, `claude`, `mistral`, `bedrock`, `litellm`)로 설치합니다:

```sh
uv sync --extra gemini
```

## 사용법

기본 provider를 내장하지 않으므로 `--provider`는 항상 필수입니다. API 키는 각 provider의 환경 변수에서 읽습니다.

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

`OpenAI`, `Gemini`, `Claude`, `DeepSeek`, `Mistral`, `Azure`, `Bedrock`, `LiteLLM`은 각각 `OPENAI_API_KEY`, `GEMINI_API_KEY`, `CLAUDE_API_KEY`, `DEEPSEEK_API_KEY`, `MISTRAL_API_KEY`, `AZURE_API_KEY`, `AWS_ACCESS_KEY_ID`, `LITELLM_API_KEY` 환경 변수를 사용합니다.

### 로컬 OpenAI-compatible 서버

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
