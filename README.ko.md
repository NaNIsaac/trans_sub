# trans_sub

[English](README.md)

`.srt` 자막 파일을 여러 언어로 옮기고, 결과를 원본과 대조해 검사합니다.

번역 파일은 원본의 cue와 시간을 그대로 두고 글만 바꿉니다. 글을 얻는 길은 두 가지입니다.

- **번역표로** (`template`, `build`, `check`, `clip`): 원본의 서로 다른 줄마다, 언어마다 한 행씩인 텍스트 표를 직접, 번역가가, 또는 아무 AI 채팅이 채웁니다. `trans-sub`가 그 표로 언어마다 `.srt`를 하나씩 쓰고 모든 파일을 검사합니다. 이 명령들은 네트워크를 쓰지 않습니다.
- **LLM provider로** (`translate`): [pysubtrans](https://github.com/machinewrapped/llm-subtrans)(`MIT`)를 거쳐 OpenRouter, Gemini 같은 provider에 파일을 보냅니다. API 키가 필요합니다.

`youtube` 명령은 영상을 올리고 모든 언어의 제목·설명·자막을 넣습니다([YouTube에 올리기](#youtube에-올리기)).

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

모든 언어에서 뒤쪽 절반을 잘라 쇼츠용으로 만듭니다. 0초에서 시작합니다:

<!-- test -->
```sh
uv run trans-sub clip out/talk.fr.srt out/talk.de.srt --from 3.5 --to 8
```

`out/talk_clip.fr.srt`와 `out/talk_clip.de.srt`가 생깁니다.

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
- `--table`에는 파일을 여러 개 줄 수 있고(`--table a.txt b.txt`), 플래그를 되풀이해도 됩니다. 예: 언어 묶음마다 표 하나. 표끼리 어긋나면 안 됩니다.

## 명령

### `template`

`trans-sub template <source.srt> --langs <lang>... [--table <file>...] [--out <dir>] [--force]`

원본의 서로 다른 줄을 한 번씩, 언어마다 한 행씩 담은 `<name>.table.txt`와, 지시문과 표를 담아 아무 채팅에나 붙여 넣을 `<name>.prompt.txt`를 씁니다. `<name>`은 원본 파일 이름에서 `.srt`와 언어 태그를 뗀 것입니다(`talk.en.srt`는 `talk`). `--table` 파일에 있는 행은 채워 두므로, 언어를 더해도 앞의 번역이 남습니다. 표 파일이 이미 있으면 `--force` 없이는 덮어쓰지 않습니다.

### `build`

`trans-sub build <source.srt> --table <file>... [--langs <lang>...] [--out <dir>] [--name <name>] [--source-lang <lang>]`

언어마다 `<name>.<lang>.srt`를 씁니다: 원본의 cue와 시간에 표의 글. `--langs`가 없으면 표의 모든 언어를 씁니다. `--source-lang`을 주면 `--langs`의 그 언어는 원본의 사본이 됩니다. 출력은 BOM 없는 UTF-8, LF 줄바꿈입니다.

### `check`

`trans-sub check <source.srt> <file or dir>...`

디렉터리는 그 안의 `<name>.<lang>.srt` 파일들을 뜻합니다. 파일마다 다음이면 실패입니다.

- 올바른 SubRip이 아님(차례대로 번호 붙은 블록, 올바른 시간, UTF-8, BOM 없음);
- cue 개수나 어느 cue의 시간이 원본과 다름;
- 빈 cue, 또는 `--max-lines`(기본 2)보다 줄이 많은 cue;
- `--width`(기본 42)자보다 긴 줄. 중국어·일본어·한국어·태국어 글자가 든 줄은 `--dense-width`(기본 20). 태국어 모음·성조 부호처럼 글자 위아래에 붙는 부호는 세지 않습니다.

초당 `--cps`자(기본 20, `--dense-cps` 15)보다 빨리 읽어야 하는 cue는 실패가 아니라 경고입니다. 시간은 원본이 정하므로 고칠 길은 번역을 줄이는 것뿐입니다. 원본 글 그대로인 cue는 세지 않습니다. `--cps 0`이면 경고를 끕니다. 실패가 하나라도 있거나 파일을 하나도 찾지 못하면 종료 코드는 1입니다.

### `clip`

`trans-sub clip <file.srt>... --from <s> --to <s> [--then <from>:<to>]... [--suffix _clip] [--out <dir>] [--min-piece 0.5]`

`--from`과 `--to`(초) 사이의 cue만 남기고 0초에서 시작하도록 옮깁니다. `--then` 구간은 앞 구간 뒤에 이어 붙으므로, 첫머리로 되돌아가며 끝나는 반복 쇼츠는 `--from <본문 시작> --to <본문 끝> --then <도입 시작>:<본문 시작>`입니다. 구간 경계에 걸친 cue는 경계에서 자르고, `--min-piece`초보다 짧은 조각은 버립니다. `talk.fr.srt`는 `talk_clip.fr.srt`로 씁니다.

원본과 모든 번역을 같은 구간으로 자르면 모두 같은 cue와 시간을 유지합니다. 잘린 파일의 `check`는 잘린 원본과 대조합니다.

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

## YouTube에 올리기

`trans-sub youtube push`는 내 영상 하나에 모든 언어의 제목, 설명, 자막을 넣습니다. 먼저 영상을 읽고, 언어마다 무엇을 추가·갱신·유지할지와 드는 quota를 보여 줍니다. `--apply`를 붙이기 전에는 아무것도 바꾸지 않습니다. 영상에 이미 있고 입력에 없는 언어는 그대로 둡니다. `trans-sub youtube upload`는 새 영상에 같은 일을 합니다. 파일을 올리면서 이것들을 한 번에 넣습니다([새 영상](#새-영상)).

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

### 새 영상

`youtube upload`는 영상 파일을 제목, 설명, 썸네일, 자막과 함께 올립니다. push처럼 먼저 보낼 내용과 quota를 보여 주고, `--apply`가 있을 때만 올립니다:

```sh
uv run trans-sub youtube upload --file song.mp4 --meta meta.json --default-lang ko --subs subs --thumb cover.png
uv run trans-sub youtube upload --file song.mp4 --meta meta.json --default-lang ko --subs subs --thumb cover.png --apply
```

- `--default-lang`은 영상의 언어입니다. `--meta`에서 그 언어의 항목이 영상 자체의 제목과 설명이 되고, 다른 언어는 현지화가 됩니다. `--meta`에 그 언어가 있어야 합니다.
- `--subs subs`는 모든 `subs/<stem>.<lang>.srt`를 씁니다. stem은 `--stem`을 주지 않으면 영상 파일 이름(`song`)입니다. 영상이 올라간 뒤 각각 새 자막 트랙이 됩니다.
- `--thumb`는 썸네일을 정합니다(PNG 또는 JPEG, 2 MB까지). YouTube는 맞춤 썸네일 기능이 켜진 채널(YouTube Studio에서 전화번호 인증)에서만 받습니다.
- 영상은 **비공개**로 올라갑니다. `--privacy unlisted`나 `public`으로 요청할 수 있지만, YouTube는 감사를 통과하지 않은 API 프로젝트가 올린 영상을 요청과 상관없이 모두 비공개로 둡니다. YouTube Studio에서 바꿉니다. `--publish-at 2026-11-25T18:00:00+09:00`은 비공개로 올리고 그 시각에 YouTube가 공개합니다.
- `--made-for-kids`는 아동용으로 선언합니다(없으면 아동용이 아니라고 선언합니다). `--synthetic yes`는 AI 생성 음성 같은 변경되거나 합성된 콘텐츠를 선언합니다. `--category 10`은 카테고리를 정합니다(10은 음악).
- 파일은 8 MB씩 나눠 올리며 진행률을 보여 줍니다. 영상이 올라간 뒤 단계(썸네일이나 자막)가 실패하면 오류에 새 영상 ID가 나오므로, 나머지는 `youtube push --video <id>`로 이어 갑니다.

### Quota

호출마다 프로젝트의 하루 quota 10,000 단위(태평양 시간 자정에 초기화)에서 빠집니다. `--max-units`(기본 9000)를 넘는 push나 upload는 적용을 거부합니다.

| 호출 | 단위 | 용도 |
|---|---|---|
| `videos.list` | 1 | 영상 읽기 |
| `i18nLanguages.list` | 1 | 언어 확인 |
| `captions.list` | 50 | 자막 트랙 읽기 |
| `videos.update` | 50 | 모든 제목과 설명, 한 번 |
| `captions.insert` | 400 | 새 트랙마다 |
| `captions.update` | 450 | 바꾸는 트랙마다 |
| `videos.insert` | 1600 | 영상 올리기, 모든 제목과 설명 포함 |
| `thumbnails.set` | 50 | 썸네일 |

출처: [quota 비용](https://developers.google.com/youtube/v3/determine_quota_cost). 새 트랙 17개와 메타데이터는 52 + 50 + 17 × 400 = 6902단위, 트랙 17개를 바꾸면 7752단위이므로 하루에 영상 하나의 전체 push는 들어가고 둘은 들어가지 않습니다. 썸네일과 트랙 17개를 붙여 영상을 올리면 1 + 1600 + 50 + 17 × 400 = 8451단위입니다.

## 라이선스

`trans_sub`는 [MIT](LICENSE) 라이선스를 따르며 `pysubtrans`(`MIT`)와 `srt`(`MIT`)에 의존합니다.
