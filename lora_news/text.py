"""텍스트 정리 도우미."""
from __future__ import annotations

import html
import re

_TAG = re.compile(r"<[^>]+>")
_BR = re.compile(r"<\s*(br|/p|/div|/li|/h[1-6]|/tr)\s*/?>", re.IGNORECASE)


def strip_html(text: str, max_chars: int = 1200) -> str:
    """HTML 을 대략적인 평문으로. 블록 태그는 줄바꿈으로."""
    if not text:
        return ""
    text = _BR.sub("\n", text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text[:max_chars]
