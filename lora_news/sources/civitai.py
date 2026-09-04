"""Civitai 공개 API 에서 LoRA / 워크플로우 수집.

문서: https://github.com/civitai/civitai/wiki/REST-API-Reference
- GET https://civitai.com/api/v1/models?types=LORA&sort=Newest&limit=100
- 키 없이 동작하지만 CIVITAI_API_KEY 가 있으면 Bearer 로 보낸다.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from .. import http
from ..models import LoraItem
from ..text import strip_html

log = logging.getLogger(__name__)

API_MODELS = "https://civitai.com/api/v1/models"

LORA_TYPES = ["LORA", "LoCon", "DoRA"]
WORKFLOW_TYPES = ["Workflows"]

# (kind, 추가 파라미터)
QUERIES: list[tuple[str, dict]] = [
    ("lora", {"types": LORA_TYPES, "sort": "Newest"}),
    ("lora", {"types": LORA_TYPES, "sort": "Most Downloaded", "period": "Week"}),
    ("lora", {"types": LORA_TYPES, "sort": "Most Downloaded", "period": "Month"}),
    ("lora", {"types": LORA_TYPES, "sort": "Highest Rated", "period": "Month"}),
    ("workflow", {"types": WORKFLOW_TYPES, "sort": "Newest"}),
    ("workflow", {"types": WORKFLOW_TYPES, "sort": "Most Downloaded", "period": "Month"}),
]

_WEIGHT_EXT = (".safetensors", ".pt", ".ckpt", ".bin", ".json", ".zip")


def _headers(token: str = "") -> dict:
    h = {"Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _dt(v) -> str:
    return v if isinstance(v, str) else ""


def parse_model(m: dict) -> LoraItem | None:
    mid = m.get("id")
    name = m.get("name")
    if mid is None or not name:
        return None
    mtype = m.get("type") or ""
    kind = "workflow" if mtype == "Workflows" else "lora"
    versions = [v for v in (m.get("modelVersions") or []) if isinstance(v, dict)]
    latest = versions[0] if versions else {}

    base_raw = " ".join(str(v.get("baseModel") or "") for v in versions[:3]).strip()

    triggers: list[str] = []
    for v in versions[:2]:
        for w in v.get("trainedWords") or []:
            if isinstance(w, str) and w.strip() and w.strip() not in triggers:
                triggers.append(w.strip()[:80])
    triggers = triggers[:5]

    files: list[str] = []
    for f in latest.get("files") or []:
        fn = f.get("name") if isinstance(f, dict) else None
        if fn and fn.lower().endswith(_WEIGHT_EXT) and fn not in files:
            files.append(fn)
    files = files[:8]

    published = [_dt(v.get("publishedAt") or v.get("createdAt")) for v in versions]
    published = [p for p in published if p]
    created_at = min(published) if published else ""
    updated_candidates = published + [_dt(latest.get("updatedAt"))]
    updated_at = max(p for p in updated_candidates if p) if any(updated_candidates) else created_at

    stats = m.get("stats") or {}
    tags = [t for t in (m.get("tags") or []) if isinstance(t, str)]
    creator = (m.get("creator") or {}).get("username") or ""

    nsfw_level = m.get("nsfwLevel") or 0
    try:
        nsfw_level = int(nsfw_level)
    except (TypeError, ValueError):
        nsfw_level = 0
    nsfw = bool(m.get("nsfw")) or nsfw_level >= 4

    desc_parts = []
    meta = []
    if latest.get("name"):
        meta.append(f"최신 버전: {latest['name']}")
    if latest.get("baseModel"):
        meta.append(f"베이스: {latest['baseModel']}")
    if meta:
        desc_parts.append(" · ".join(meta))
    body = strip_html(m.get("description") or "", max_chars=1000)
    if body:
        desc_parts.append(body)
    vdesc = strip_html(latest.get("description") or "", max_chars=300)
    if vdesc and vdesc not in body:
        desc_parts.append(vdesc)

    base_lower = base_raw.lower()
    pipeline = "text-to-video" if "video" in base_lower else "text-to-image"

    return LoraItem(
        key=f"civitai:{mid}",
        source="civitai",
        kind=kind,
        name=str(name).strip(),
        author=creator,
        url=f"https://civitai.com/models/{mid}",
        description="\n".join(desc_parts),
        tags=tags[:30],
        pipeline=pipeline,
        base_model_raw=base_raw,
        trigger_words=triggers,
        created_at=created_at,
        updated_at=updated_at,
        downloads=int(stats.get("downloadCount") or 0),
        likes=int(stats.get("thumbsUpCount") or stats.get("favoriteCount") or 0),
        nsfw=nsfw,
        files=files,
    )


def fetch(limit: int = 100, token: str = "", timeout: int = 30, nsfw: bool = False,
          workers: int = 3) -> tuple[list[LoraItem], list[str]]:
    items: dict[str, LoraItem] = {}
    errors: list[str] = []

    def run(kind: str, q: dict):
        params = dict(q)
        params["limit"] = max(1, min(limit, 100))
        if not nsfw:
            params["nsfw"] = "false"
        return kind, http.get_json(API_MODELS, params=params, headers=_headers(token), timeout=timeout)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, k, q) for k, q in QUERIES]
        for fut in as_completed(futures):
            try:
                kind, data = fut.result()
            except http.HttpError as e:
                if e.status == 403:
                    msg = "Civitai 접근 거부(403): Cloudflare 차단이거나 API 키가 필요할 수 있습니다 (CIVITAI_API_KEY 설정 시도)"
                elif e.status == 429:
                    msg = "Civitai 요청 한도 초과(429): 잠시 후 다시 시도하세요"
                else:
                    msg = f"Civitai 요청 실패: {e}"
                log.warning(msg)
                if msg not in errors:
                    errors.append(msg)
                continue
            except Exception as e:  # noqa: BLE001
                msg = f"Civitai 요청 실패: {e}"
                log.warning(msg)
                errors.append(msg)
                continue
            rows = (data or {}).get("items") if isinstance(data, dict) else None
            if not isinstance(rows, list):
                errors.append(f"Civitai 응답 형식 오류: {str(data)[:120]}")
                continue
            for m in rows:
                try:
                    item = parse_model(m)
                except Exception as e:  # noqa: BLE001
                    log.debug("civitai parse error: %s", e)
                    continue
                if item and item.key not in items:
                    items[item.key] = item
    log.info("Civitai: %d개 수집 (오류 %d)", len(items), len(errors))
    return list(items.values()), errors
