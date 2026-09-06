from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None, override: bool = False) -> dict:
    """프로젝트 루트의 .env 파일을 읽어 환경변수에 넣는다 (외부 패키지 없이).

    - `KEY=VALUE` 한 줄씩. `#` 으로 시작하는 줄과 빈 줄은 무시. 값의 따옴표는 벗긴다.
    - 이미 설정된 환경변수는 override=True 가 아니면 건드리지 않는다.
    - 읽어 들인 값들을 dict 로 반환 (테스트/디버그용).
    """
    path = Path(path) if path else ROOT / ".env"
    loaded: dict = {}
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return loaded
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        # 따옴표로 감싼 값은 그대로, 아니면 뒤따르는 주석을 떼어낸다
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        else:
            if " #" in value:
                value = value.split(" #", 1)[0].rstrip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
        loaded[key] = value
    return loaded


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Config:
    """환경변수로 조정 가능한 설정값."""

    def __init__(self, env_file: Path | None = None) -> None:
        load_dotenv(env_file)
        self.data_dir = Path(os.environ.get("LORA_NEWS_DATA_DIR", ROOT / "data"))
        self.host = os.environ.get("LORA_NEWS_HOST", "127.0.0.1")
        self.port = _int("LORA_NEWS_PORT", 8765)
        # 처음 발견 후 이 시간(시간 단위) 동안 "신규"로 표시
        self.new_window_hours = _int("LORA_NEWS_NEW_WINDOW_HOURS", 72)
        # 소스별 요청 개수
        self.hf_limit = _int("LORA_NEWS_HF_LIMIT", 100)
        self.gh_per_page = _int("LORA_NEWS_GH_PER_PAGE", 50)
        # 모델 카드(README) 발췌를 가져올 최대 개수 (신규/미요약 항목 우선)
        self.readme_fetch_max = _int("LORA_NEWS_README_MAX", 40)
        self.hf_token = os.environ.get("HF_TOKEN", "")
        self.github_token = os.environ.get("GITHUB_TOKEN", "")
        # Civitai (공개 API, 키는 선택)
        self.civitai_token = os.environ.get("CIVITAI_API_KEY", "")
        self.civitai_limit = _int("LORA_NEWS_CIVITAI_LIMIT", 100)
        self.civitai_nsfw = os.environ.get("LORA_NEWS_CIVITAI_NSFW", "").strip().lower() in ("1", "true", "on", "yes")
        # Claude 한글 요약 (선택)
        self.claude_model = os.environ.get("LORA_NEWS_CLAUDE_MODEL", "claude-opus-5")
        self.claude_max_items = _int("LORA_NEWS_CLAUDE_MAX_ITEMS", 60)
        flag = os.environ.get("LORA_NEWS_CLAUDE", "").strip().lower()
        if flag in ("0", "false", "off", "no"):
            self.claude_enabled = False
        elif flag in ("1", "true", "on", "yes"):
            self.claude_enabled = True
        else:
            self.claude_enabled = bool(
                os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            )
        self.http_timeout = _int("LORA_NEWS_HTTP_TIMEOUT", 30)
        # 한 번의 새로고침이 통째로 매달리지 않도록 하는 상한 (초)
        self.refresh_deadline = _int("LORA_NEWS_REFRESH_DEADLINE", 180)
        # 사용할 소스 선택: "huggingface,github,civitai" 중 일부
        raw_sources = os.environ.get("LORA_NEWS_SOURCES", "").strip().lower()
        known = ("huggingface", "github", "civitai")
        aliases = {"hf": "huggingface", "gh": "github", "cv": "civitai", "civit": "civitai"}
        chosen = [aliases.get(x.strip(), x.strip()) for x in raw_sources.split(",") if x.strip()]
        self.sources = tuple(s for s in known if s in chosen) if chosen else known
