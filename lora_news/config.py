from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Config:
    """환경변수로 조정 가능한 설정값."""

    def __init__(self) -> None:
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
