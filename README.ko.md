# trans_sub

[English](README.md)

cue 순서와 타이밍을 유지한 채 `.srt` 자막 파일을 번역하는 [pysubtrans](https://github.com/machinewrapped/llm-subtrans)(`MIT`) 기반 CLI 및 Python 래퍼이고, 모든 언어의 제목·설명·자막을 YouTube 영상에 넣는 명령도 있습니다([YouTube에 올리기](#youtube에-올리기)).

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

## YouTube에 올리기

`trans-sub youtube push`는 내 영상 하나에 모든 언어의 제목, 설명, 자막을 넣습니다. 먼저 영상을 읽고, 언어마다 무엇을 추가·갱신·유지할지와 드는 quota를 보여 줍니다. `--apply`를 붙이기 전에는 아무것도 바꾸지 않습니다. 영상에 이미 있고 입력에 없는 언어는 그대로 둡니다.

선택 설치인 Google 패키지를 설치합니다:

```sh
uv sync --extra youtube
```

<!-- test -->
```sh
uv run trans-sub youtube push --help
```

### 준비 (한 번)

1. [Google Cloud console](https://console.cloud.google.com/)에서 프로젝트를 만듭니다.
2. API 라이브러리에서 **YouTube Data API v3**를 열고 **Enable**을 누릅니다.
3. **Google Auth Platform**에서 **Branding**(앱 이름, 지원 이메일)을 채웁니다. **Audience**에서 **External**을 고르고 게시 상태는 **Testing**으로 두며, 채널 주인 Google 계정을 테스트 사용자로 추가합니다.
4. **Clients**에서 **Create client**를 누르고 **Desktop app**을 골라 만듭니다. 클라이언트를 JSON 파일로 저장합니다. 클라이언트 secret 전체는 만들 때 한 번만 보입니다.
5. 그 파일을 아래 기본 경로에 두거나, `--client-secret <file>`로 주거나, `TRANS_SUB_YOUTUBE_CLIENT_SECRET`을 설정합니다. 어떤 저장소에도 넣지 않습니다.

| 파일 | 기본 경로 | 플래그 | 환경 변수 |
|---|---|---|---|
| OAuth 클라이언트 | `<config>/trans-sub/youtube-client.json` | `--client-secret` | `TRANS_SUB_YOUTUBE_CLIENT_SECRET` |
| 토큰 | `<config>/trans-sub/youtube-token.json` | `--token` | `TRANS_SUB_YOUTUBE_TOKEN` |

`<config>`는 Windows에서 `%APPDATA%`, macOS에서 `~/Library/Application Support`, 그 밖에서는 `$XDG_CONFIG_HOME`(없으면 `~/.config`)입니다.

첫 push는 로그인할 브라우저를 엽니다. 채널 계정을 고릅니다. 앱이 Testing 상태이고 Google 검증을 받지 않았으므로 브라우저가 확인되지 않은 앱이라고 경고합니다. 내 클라이언트이니 계속합니다. 도구는 자막 업로드에 필요한 범위 `youtube.force-ssl` 하나만 요청하고, 토큰 파일을 직접 씁니다(본인만 읽을 수 있음).

앱이 **Testing**인 동안 로그인은 7일간 유지되고, 그 뒤 push는 다시 브라우저를 엽니다. 앱을 **In production**으로 게시하면 이 제한이 없어지고, 경고를 없애려면 Google이 앱 검증을 요구할 수 있습니다. 출처: [설치형 앱 OAuth](https://developers.google.com/youtube/v3/guides/auth/installed-apps), [refresh token 만료](https://developers.google.com/identity/protocols/oauth2#expiration), [대상과 테스트 사용자](https://support.google.com/cloud/answer/15549945).

### 영상마다

제목과 설명은 언어를 키로 한 JSON 파일에서 읽습니다:

```json
{"en": {"title": "Morning talk", "description": "A talk."},
 "fr": {"title": "Discours du matin", "description": "Un discours."}}
```

`youtube meta`는 첫 열이 언어인 Markdown 표에서 이 파일을 씁니다. 제목·설명 열은 머리글이나 번호로 고릅니다:

```sh
uv run trans-sub youtube meta titles.md --title-column Title --description-column Description -o meta.json
```

계획을 보고, 적용합니다:

```sh
uv run trans-sub youtube push --video <id> --meta meta.json --subs subs --stem talk
uv run trans-sub youtube push --video <id> --meta meta.json --subs subs --stem talk --apply
```

`--subs subs --stem talk`는 모든 `subs/talk.<lang>.srt`를 씁니다. 언어마다:

- 기본 언어의 제목과 설명은 영상 자체의 것이고, 다른 언어는 현지화(localization)입니다. 같은 글은 건드리지 않습니다. 모두 `videos.update` 한 번으로 보내며, 이때 영상의 제목, 설명, 태그, 카테고리, 기본 언어를 그대로 돌려보냅니다.
- 그 언어의 자막 트랙이 있으면 바꾸고, 없으면 추가합니다. `--captions missing`은 추가만, `--captions none`은 자막을 건너뜁니다. 한 언어에 트랙이 둘이면 push가 멈춥니다(YouTube Studio에서 하나를 지웁니다). 자동 자막은 무시합니다.
- 기본 언어가 없는 영상은 `--default-lang`이 필요하고, push가 그 값을 설정합니다.
- 언어 코드는 먼저 YouTube 목록과 대조합니다(`--skip-lang-check`로 건너뜀).

제목은 100자, 설명은 5000바이트까지이고 둘 다 `<`, `>`를 쓸 수 없습니다. push는 쓰기 전에 이를 검사합니다.

### Quota

호출마다 프로젝트의 하루 quota 10,000 단위(태평양 시간 자정에 초기화)에서 빠집니다. `--max-units`(기본 9000)를 넘는 push는 적용을 거부합니다.

| 호출 | 단위 | 용도 |
|---|---|---|
| `videos.list` | 1 | 영상 읽기 |
| `i18nLanguages.list` | 1 | 언어 확인 |
| `captions.list` | 50 | 자막 트랙 읽기 |
| `videos.update` | 50 | 모든 제목과 설명, 한 번 |
| `captions.insert` | 400 | 새 트랙마다 |
| `captions.update` | 450 | 바꾸는 트랙마다 |

출처: [quota 비용](https://developers.google.com/youtube/v3/determine_quota_cost). 새 트랙 17개와 메타데이터는 52 + 50 + 17 × 400 = 6902단위, 트랙 17개를 바꾸면 7752단위이므로 하루에 영상 하나의 전체 push는 들어가고 둘은 들어가지 않습니다.

## 라이선스

`trans_sub`는 [MIT](LICENSE) 라이선스를 따르며 `pysubtrans`(`MIT`)와 `srt`(`MIT`)에 의존합니다.
