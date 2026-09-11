"""모델 카드(README) 보강: 발췌, 트리거 워드, 대표 이미지. Hugging Face 와 GitHub 공용."""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import http
from .classify import extract_trigger_words
from .images import add_images, gallery_from_markdown, normalize_repo_base
from .models import LoraItem

log = logging.getLogger(__name__)

_FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)


def clean_readme(text: str, max_chars: int = 1200) -> str:
    text = _FRONT_MATTER.sub("", text or "", count=1)
    text = _CODE_FENCE.sub(" ", text)
    text = _MD_IMAGE.sub(" ", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _HTML_TAG.sub(" ", text)
    text = re.sub(r"[#>*`|]+", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text[:max_chars]


def readme_location(item: LoraItem) -> tuple[str, str] | None:
    """(README 원문 URL, 상대 이미지 기준 URL). 지원하지 않는 소스면 None."""
    if item.source == "huggingface":
        mid = item.key.split(":", 1)[1]                  # "author/name" 또는 "datasets/author/name"
        return (f"https://huggingface.co/{mid}/raw/main/README.md",
                f"https://huggingface.co/{mid}/resolve/main/")
    if item.source == "github":
        full = item.key.split(":", 1)[1]
        return (f"https://raw.githubusercontent.com/{full}/HEAD/README.md",
                f"https://raw.githubusercontent.com/{full}/HEAD/")
    return None


def fetch_readme(item: LoraItem, hf_token: str = "", gh_token: str = "", timeout: int = 20) -> dict:
    """{"excerpt", "triggers", "images"}. 실패하면 빈 값들."""
    empty = {"excerpt": "", "triggers": [], "images": []}
    loc = readme_location(item)
    if not loc:
        return empty
    url, base = loc
    headers = {"Accept": "text/plain"}
    token = hf_token if item.source == "huggingface" else gh_token
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        raw = http.get_text(url, headers=headers, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        log.debug("README 실패 %s: %s", item.key, e)
        return empty
    return {
        "excerpt": clean_readme(raw),
        "triggers": extract_trigger_words(raw) if item.kind == "lora" else [],
        "images": gallery_from_markdown(raw, normalize_repo_base(base)),
    }


def enrich(items: list[LoraItem], hf_token: str = "", gh_token: str = "", timeout: int = 20,
           workers: int = 6, now: str = "") -> int:
    """여러 항목의 README 를 병렬로 읽어 발췌/트리거/이미지를 채운다. 발췌를 얻은 개수 반환."""
    ok = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fetch_readme, it, hf_token, gh_token, timeout): it for it in items}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                got = fut.result()
            except Exception:  # noqa: BLE001
                continue
            it.readme_fetched_at = now or it.readme_fetched_at or "fetched"
            if got["excerpt"]:
                it.readme_excerpt = got["excerpt"]       # 덧붙이지 않고 대체한다
                ok += 1
            for t in got["triggers"]:
                if t not in it.trigger_words:
                    it.trigger_words.append(t)
            it.trigger_words = it.trigger_words[:5]
            if got["images"] and not it.nsfw:
                add_images(it, got["images"])   # 위젯 이미지 뒤에 모델 카드 이미지를 이어 붙인다
    return ok
