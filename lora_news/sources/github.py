"""GitHub 저장소 검색으로 LoRA 관련 프로젝트 수집."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .. import http
from ..models import LoraItem

log = logging.getLogger(__name__)

API_SEARCH = "https://api.github.com/search/repositories"

# (검색어, 정렬). 비로그인 검색 API 는 분당 10회 제한이므로 쿼리 수를 적게 유지.
QUERIES: list[tuple[str, str]] = [
    ("comfyui lora in:name,description,topics", "updated"),
    ("comfyui lora in:name,description,topics", "stars"),
    ("topic:lora topic:comfyui", "updated"),
    ("lora flux in:name,description,topics", "updated"),
    ("lora sdxl in:name,description,topics", "updated"),
    ("lora wan video in:name,description,topics", "updated"),
    ("lora training diffusion in:name,description,topics", "updated"),
]


def _headers(token: str = "") -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def parse_repo(r: dict) -> LoraItem | None:
    full = r.get("full_name")
    if not full or r.get("fork"):
        return None
    owner = r.get("owner") or {}
    topics = [t for t in (r.get("topics") or []) if isinstance(t, str)]
    lang = r.get("language")
    tags = list(topics)
    if isinstance(lang, str):
        tags.append(lang)
    if r.get("archived"):
        tags.append("archived")
    return LoraItem(
        key=f"gh:{full}",
        source="github",
        name=full,
        author=owner.get("login") or full.split("/")[0],
        url=r.get("html_url") or f"https://github.com/{full}",
        description=(r.get("description") or "").strip(),
        tags=tags,
        created_at=r.get("created_at") or "",
        updated_at=r.get("pushed_at") or r.get("updated_at") or "",
        likes=int(r.get("stargazers_count") or 0),
        downloads=int(r.get("forks_count") or 0),
    )


def fetch(per_page: int = 50, token: str = "", timeout: int = 30, workers: int = 3) -> tuple[list[LoraItem], list[str]]:
    items: dict[str, LoraItem] = {}
    errors: list[str] = []

    def run(q: str, sort: str):
        params = {"q": q, "sort": sort, "order": "desc", "per_page": per_page}
        return http.get_json(API_SEARCH, params=params, headers=_headers(token), timeout=timeout)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, q, s) for q, s in QUERIES]
        for fut in as_completed(futures):
            try:
                data = fut.result()
            except http.HttpError as e:
                if e.status in (403, 429):
                    msg = "GitHub API 요청 한도 초과 (GITHUB_TOKEN 설정 시 한도가 늘어납니다)"
                else:
                    msg = f"GitHub 요청 실패: {e}"
                log.warning(msg)
                if msg not in errors:
                    errors.append(msg)
                continue
            except Exception as e:  # noqa: BLE001
                msg = f"GitHub 요청 실패: {e}"
                log.warning(msg)
                errors.append(msg)
                continue
            for r in (data or {}).get("items") or []:
                try:
                    item = parse_repo(r)
                except Exception:  # noqa: BLE001
                    continue
                if item and item.key not in items:
                    items[item.key] = item
    log.info("GitHub: %d개 수집 (오류 %d)", len(items), len(errors))
    return list(items.values()), errors
