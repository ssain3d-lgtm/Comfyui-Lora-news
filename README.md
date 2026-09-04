# LoRA 뉴스 (ComfyUI용 LoRA · 워크플로우 모아보기)

실행할 때마다 **Hugging Face**, **GitHub**, **Civitai**에서 LoRA와 ComfyUI 워크플로우의 최신 목록을 받아와,
**신규 항목**과 **기존 항목**을 베이스 모델(FLUX / SDXL / Pony / Illustrious / Wan / …)과
용도(스타일 · 캐릭터 · 실사 · 가속 · 이미지 편집 · 영상 모션 · 학습 도구 …)별로 나누고,
각 항목에 **한글 한 줄 요약**과 **트리거 워드**를 붙여 브라우저에서 보여주는 로컬 웹앱입니다.
화면 상단 탭으로 **LoRA** / **워크플로우**를 전환합니다.

```
python app.py
```

이게 전부입니다. Python 3.10 이상만 있으면 되고 추가 설치 패키지는 없습니다.

## 기능

- **세 가지 소스**: Hugging Face(`lora` 태그 모델), GitHub(저장소 검색), Civitai(LORA/LoCon/DoRA + Workflows 타입)
- **LoRA / 워크플로우 탭**: Civitai 워크플로우, GitHub `comfyui workflow` 저장소, HF에 올라온 워크플로우 JSON 모음을 따로 모아 봄
- **신규 감지**: 처음 발견한 항목은 `NEW`, 이번 실행에서 처음 본 항목은 `이번 실행 발견` 배지 (기본 72시간 동안 신규로 표시)
- **분류**: 베이스 모델 / 용도별 칩 필터, 용도별·베이스 모델별·소스별 묶어보기.
  워크플로우는 이미지 생성 · 영상 생성 · 편집/인페인팅 · 업스케일/보정 · 컨트롤넷/포즈 · 캐릭터 일관성 · 학습/도구 · 모음/템플릿으로 분류
- **한글 요약**: 이름·태그·모델 카드에서 규칙으로 뽑은 요약(예: `FLUX.1 기반 스타일/화풍 LoRA · 수채화 느낌 · 트리거: xyz`)
- **트리거 워드**: HF 모델 카드의 `instance_prompt` / "Trigger words:" 문구, Civitai의 `trainedWords` 자동 추출, 클릭하면 복사
- **정렬/검색**: 신규 우선, 등록일, 수정일, 다운로드, 좋아요/스타, 이름 · 텍스트 검색 · NSFW 숨기기(기본)
- **캐시**: 결과는 `data/` 폴더에 저장되어 네트워크가 안 되어도 마지막 결과를 볼 수 있음
- **(선택) Claude 한글 요약**: API 키가 있으면 더 자연스러운 한글 요약을 생성 (신규 항목만 호출, 캐시됨)

## 실행 방법

```bash
# Windows
run.bat
# macOS / Linux
./run.sh
# 또는
python app.py
```

브라우저가 자동으로 `http://127.0.0.1:8765/` 를 엽니다. 시작하자마자 백그라운드에서 최신 목록을 받아오고,
끝나면 화면이 자동으로 갱신됩니다. 화면 오른쪽 위 **새로고침** 버튼으로 언제든 다시 받아올 수 있습니다.

| 옵션 | 설명 |
| --- | --- |
| `--no-browser` | 브라우저 자동 열기 안 함 |
| `--no-refresh` | 시작 시 수집하지 않고 캐시만 표시 |
| `--refresh-only` | 서버 없이 수집만 하고 종료 (작업 스케줄러/cron 용) |
| `--demo` | 네트워크 없이 샘플 데이터로 UI 확인 |
| `--port 9000` | 포트 변경 (기본 8765) |

## 환경변수 (모두 선택)

| 변수 | 설명 |
| --- | --- |
| `GITHUB_TOKEN` | GitHub 검색 API 한도 확대 (비로그인은 분당 10회라 가끔 한도 오류가 날 수 있음) |
| `HF_TOKEN` | Hugging Face 토큰 (한도 확대, 비공개 모델은 대상 아님) |
| `CIVITAI_API_KEY` | Civitai API 키 (선택. 403/한도 오류가 나면 설정해 보세요) |
| `LORA_NEWS_CIVITAI_NSFW` | `1` 이면 Civitai에서 NSFW 항목도 받아옴 (기본은 제외, 받아온 뒤에도 화면에서 NSFW 숨기기 가능) |
| `LORA_NEWS_CIVITAI_LIMIT` | Civitai 쿼리당 개수 (기본 100, 최대 100) |
| `ANTHROPIC_API_KEY` | 설정하면 Claude로 한글 요약 생성. `pip install anthropic` 필요 |
| `LORA_NEWS_CLAUDE` | `0` 으로 두면 키가 있어도 Claude 요약 끔, `1` 이면 `ant auth login` 프로필로도 사용 |
| `LORA_NEWS_CLAUDE_MODEL` | 기본 `claude-opus-5` |
| `LORA_NEWS_CLAUDE_MAX_ITEMS` | 한 번 실행에 요약할 최대 개수 (기본 60) |
| `LORA_NEWS_NEW_WINDOW_HOURS` | 처음 발견 후 신규로 표시할 시간 (기본 72) |
| `LORA_NEWS_HF_LIMIT` | Hugging Face 쿼리당 개수 (기본 100) |
| `LORA_NEWS_README_MAX` | 모델 카드(README)를 읽어올 최대 개수 (기본 40) |
| `LORA_NEWS_PORT` / `LORA_NEWS_HOST` | 포트 / 바인드 주소 |
| `LORA_NEWS_DATA_DIR` | 캐시 폴더 (기본 `./data`) |

Claude 요약을 켜려면:

```bash
pip install anthropic
set ANTHROPIC_API_KEY=sk-ant-...      # Windows (PowerShell 은 $env:ANTHROPIC_API_KEY="...")
export ANTHROPIC_API_KEY=sk-ant-...   # macOS / Linux
python app.py
```

요약은 `data/summaries.json` 에 캐시되므로 같은 항목에 대해 다시 비용이 들지 않습니다.
안전 분류기가 요청을 거절하면 서버 쪽 기본 폴백 모델로 자동 재시도하도록 설정되어 있습니다.

## 동작 원리

1. Hugging Face `api/models` 를 `lora` 태그 + text-to-image / image-to-image / text-to-video / image-to-video 파이프라인으로
   등록순·다운로드순·수정순 등 여러 각도에서 조회해 합칩니다 (쿼리당 100개).
2. GitHub `search/repositories` 로 `comfyui lora`, `topic:lora topic:comfyui`, `lora flux/training`, `comfyui workflow`,
   `topic:comfyui-workflow` 를 검색합니다 (비로그인 한도 안에 들도록 8개 쿼리).
3. Civitai `api/v1/models` 를 `types=LORA,LoCon,DoRA` 와 `types=Workflows` 로 최신순·주간/월간 다운로드순·평점순 조회합니다.
   기본은 `nsfw=false` 로 받아오며, 베이스 모델(`baseModel`)과 트리거 워드(`trainedWords`)를 그대로 사용합니다.
4. 워크플로우는 Civitai Workflows 타입, 이름/토픽에 workflow 가 들어간 GitHub 저장소, 이름에 comfy+workflow 가 들어간 HF 모델/데이터셋을 모읍니다.
5. 항목마다 이름·태그·`base_model` 태그·모델 카드 발췌를 규칙으로 분석해 베이스 모델, 용도, 한글 힌트, 트리거 워드를 뽑습니다.
6. `data/seen.json` 에 "처음 본 시각"을 기록해 신규 여부를 판정합니다. 첫 실행은 기준선으로 삼아
   소스의 등록일이 최근인 것만 신규로 표시하고, 이후 실행부터 새로 나타난 항목을 `이번 실행 발견` 으로 표시합니다.
7. (선택) Claude 가 신규·미요약 항목의 한글 요약을 작성하고 캐시합니다.

## 한계

- Hugging Face 의 `lora` 태그가 없는 모델은 잡히지 않습니다.
- Civitai 는 Cloudflare 보호 때문에 환경에 따라 403 이 날 수 있습니다. 그 경우 `CIVITAI_API_KEY` 를 설정해 보고, 실패하면 이전 캐시를 유지합니다.
- 워크플로우는 저장소 이름/타입으로 판별하므로 이름에 workflow 가 없는 GitHub/HF 저장소는 놓칠 수 있습니다.
- 규칙 기반 분류는 이름/태그가 불친절하면 `기타`/`미상` 으로 빠질 수 있습니다. Claude 요약을 켜면 분류도 함께 보정됩니다.
- GitHub 비로그인 검색 한도(분당 10회)에 걸리면 해당 실행에서는 이전 캐시를 유지합니다.

## 테스트

```bash
python -m unittest discover -s tests -v
```

## 구조

```
app.py                  # 서버 + CLI 진입점
lora_news/
  config.py             # 환경변수 설정
  models.py             # LoraItem 데이터 모델
  http.py               # urllib 기반 HTTP 도우미
  sources/huggingface.py# HF 수집 (LoRA 모델 + 워크플로우 모델/데이터셋) + README 발췌
  sources/github.py     # GitHub 검색 수집 (LoRA 도구 + 워크플로우 저장소)
  sources/civitai.py    # Civitai 수집 (LoRA + Workflows)
  text.py               # HTML 제거 등 텍스트 정리
  classify.py           # 베이스 모델/용도/한글 힌트/트리거/규칙 요약
  summarize.py          # (선택) Claude 한글 요약
  store.py              # data/ JSON 저장
  service.py            # 수집→분류→신규 판정→요약→저장
static/                 # 프론트엔드 (의존성 없음)
tests/                  # 단위 테스트 + 샘플 데이터
```
