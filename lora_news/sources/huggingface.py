"""Hugging Face Hub 에서 LoRA 목록 수집."""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from .. import http
from ..i18n import msg
from ..classify import extract_trigger_words
from ..models import LoraItem

log = logging.getLogger(__name__)

API_MODELS = "https://huggingface.co/api/models"
API_DATASETS = "https://huggingface.co/api/datasets"

# (kind, 엔드포인트, 추가 파라미터) - 신규 등록 / 인기(다운로드) / 최근 수정 순으로 여러 각도에서 가져와 합친다.
QUERIES: list[tuple[str, str, dict]] = [
    ("lora", API_MODELS, {"filter": "lora", "pipeline_tag": "text-to-image", "sort": "createdAt"}),
    ("lora", API_MODELS, {"filter": "lora", "pipeline_tag": "text-to-image", "sort": "lastModified"}),
    ("lora", API_MODELS, {"filter": "lora", "pipeline_tag": "text-to-image", "sort": "downloads"}),
    ("lora", API_MODELS, {"filter": "lora", "pipeline_tag": "text-to-image", "sort": "likes"}),
    ("lora", API_MODELS, {"filter": "lora", "pipeline_tag": "image-to-image", "sort": "createdAt"}),
    ("lora", API_MODELS, {"filter": "lora", "pipeline_tag": "image-to-image", "sort": "downloads"}),
    ("lora", API_MODELS, {"filter": "lora", "pipeline_tag": "text-to-video", "sort": "createdAt"}),
    ("lora", API_MODELS, {"filter": "lora", "pipeline_tag": "text-to-video", "sort": "downloads"}),
    ("lora", API_MODELS, {"filter": "lora", "pipeline_tag": "image-to-video", "sort": "createdAt"}),
    ("lora", API_MODELS, {"filter": "lora", "pipeline_tag": "image-to-video", "sort": "downloads"}),
    ("lora", API_MODELS, {"filter": "lora", "library": "diffusers", "sort": "createdAt"}),
    ("lora", API_MODELS, {"filter": "lora", "search": "comfyui", "sort": "createdAt"}),
    # 워크플로우: 이름에 comfy + workflow 가 함께 들어간 모델/데이터셋 저장소
    ("workflow", API_MODELS, {"search": "comfyui", "sort": "lastModified"}),
    ("workflow", API_MODELS, {"search": "workflow", "sort": "lastModified"}),
    ("workflow", API_DATASETS, {"search": "comfyui", "sort": "lastModified"}),
    ("workflow", API_DATASETS, {"search": "workflow", "sort": "lastModified"}),
]

_SKIP_TAG_PREFIXES = ("base_model:", "license:", "region:", "template:", "arxiv:", "doi:", "dataset:", "language:")
_SKIP_TAGS = {"diffusers", "safetensors", "lora", "text-to-image", "image-to-image", "text-to-video", "image-to-video",
              "diffusers-training", "template:sd-lora", "endpoints_compatible", "autotrain_compatible", "has_space", "peft"}
_WEIGHT_EXT = (".safetensors", ".pt", ".ckpt", ".bin")


def _headers(token: str = "") -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def is_workflow_repo(mid: str, tags: list[str]) -> bool:
    low = (mid or "").lower()
    tag_text = " ".join(tags).lower()
    return "workflow" in low and ("comfy" in low or "comfy" in tag_text)


def parse_model(m: dict, kind: str = "lora", dataset: bool = False) -> LoraItem | None:
    mid = m.get("id") or m.get("modelId")
    if not mid or m.get("private") or m.get("disabled"):
        return None
    tags = [t for t in (m.get("tags") or []) if isinstance(t, str)]
    if kind == "workflow" and not is_workflow_repo(mid, tags):
        return None
    if kind == "lora" and dataset:
        return None
    card = m.get("cardData") or {}
    if not isinstance(card, dict):
        card = {}

    base_raw: list[str] = []
    for t in tags:
        if t.startswith("base_model:"):
            base_raw.append(t.split(":")[-1])
    cb = card.get("base_model")
    if isinstance(cb, list):
        base_raw.extend(str(x) for x in cb)
    elif isinstance(cb, str):
        base_raw.append(cb)

    instance_prompt = card.get("instance_prompt")
    triggers: list[str] = []
    if isinstance(instance_prompt, str) and instance_prompt.strip():
        triggers = [instance_prompt.strip()[:80]]

    examples: list[str] = []
    for w in card.get("widget") or []:
        if isinstance(w, dict):
            p = w.get("text") or w.get("prompt") or (w.get("inputs") if isinstance(w.get("inputs"), str) else None)
            if isinstance(p, str) and p.strip():
                examples.append(p.strip()[:200])
        if len(examples) >= 2:
            break

    files = []
    exts = (".json",) if kind == "workflow" else _WEIGHT_EXT
    for s in m.get("siblings") or []:
        fn = s.get("rfilename") if isinstance(s, dict) else None
        if fn and fn.lower().endswith(exts):
            files.append(fn)
    files = files[:8]

    clean_tags = [t for t in tags if t not in _SKIP_TAGS and not t.startswith(_SKIP_TAG_PREFIXES)]
    card_tags = card.get("tags")
    if isinstance(card_tags, list):
        for t in card_tags:
            if isinstance(t, str) and t not in clean_tags and t not in _SKIP_TAGS:
                clean_tags.append(t)

    desc_parts = []
    if examples:
        desc_parts.append("예시 프롬프트: " + " | ".join(examples))
    if clean_tags:
        desc_parts.append("태그: " + ", ".join(clean_tags[:20]))

    author = m.get("author") or mid.split("/")[0]
    prefix = "datasets/" if dataset else ""
    return LoraItem(
        key=f"hf:{prefix}{mid}",
        source="huggingface",
        kind=kind,
        name=mid,
        author=author,
        url=f"https://huggingface.co/{prefix}{mid}",
        description="\n".join(desc_parts),
        tags=clean_tags[:30],
        pipeline=m.get("pipeline_tag") or "",
        base_model_raw=" ".join(base_raw),
        trigger_words=triggers,
        example_prompt=examples[0] if examples else "",
        created_at=m.get("createdAt") or "",
        updated_at=m.get("lastModified") or "",
        downloads=int(m.get("downloads") or 0),
        likes=int(m.get("likes") or 0),
        nsfw="not-for-all-audiences" in tags,
        files=files,
    )


def fetch(limit: int = 100, token: str = "", timeout: int = 30, workers: int = 4) -> tuple[list[LoraItem], list[dict]]:
    """여러 쿼리를 병렬로 호출해 중복 제거된 LoRA 목록을 반환. (items, errors)"""
    items: dict[str, LoraItem] = {}
    errors: list[dict] = []

    def run(kind: str, endpoint: str, q: dict):
        params = dict(q)
        params.update({"direction": -1, "limit": limit, "full": "true", "cardData": "true"})
        return kind, endpoint, http.get_json(endpoint, params=params, headers=_headers(token), timeout=timeout)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run, k, ep, q) for k, ep, q in QUERIES]
        for fut in as_completed(futures):
            try:
                kind, endpoint, data = fut.result()
            except Exception as e:  # noqa: BLE001
                log.warning("HuggingFace 요청 실패: %s", e)
                m = msg("hf_failed", err=e)
                if m not in errors:
                    errors.append(m)
                continue
            if not isinstance(data, list):
                m = msg("hf_bad_response", body=str(data)[:120])
                if m not in errors:
                    errors.append(m)
                continue
            for m in data:
                try:
                    item = parse_model(m, kind=kind, dataset=(endpoint == API_DATASETS))
                except Exception as e:  # noqa: BLE001
                    log.debug("parse error: %s", e)
                    continue
                if item and item.key not in items:
                    # 어느 쿼리가 먼저 끝나든 같은 결과가 되도록 kind 를 다시 판정한다
                    item.kind = "workflow" if is_workflow_repo(item.name, item.tags) else "lora"
                    items[item.key] = item
    log.info("HuggingFace: %d개 수집 (오류 %d)", len(items), len(errors))
    return list(items.values()), errors


# ---------------------------------------------------------------------------
# 모델 카드(README) 발췌
# ---------------------------------------------------------------------------

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


def fetch_readme(item: LoraItem, token: str = "", timeout: int = 20) -> tuple[str, list[str]]:
    """README 발췌와 트리거 워드를 반환. 실패하면 ('', [])."""
    mid = item.key.split(":", 1)[1]  # "author/name" 또는 "datasets/author/name"
    url = f"https://huggingface.co/{mid}/raw/main/README.md"
    try:
        raw = http.get_text(url, headers={**_headers(token), "Accept": "text/plain"}, timeout=timeout)
    except Exception as e:  # noqa: BLE001
        log.debug("README 실패 %s: %s", mid, e)
        return "", []
    return clean_readme(raw), extract_trigger_words(raw)


def enrich_with_readmes(items: list[LoraItem], token: str = "", timeout: int = 20, workers: int = 6) -> int:
    """여러 항목의 README를 병렬로 가져와 description/trigger_words 를 보강. 성공 개수 반환."""
    ok = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fetch_readme, it, token, timeout): it for it in items}
        for fut in as_completed(futs):
            it = futs[fut]
            try:
                excerpt, triggers = fut.result()
            except Exception:  # noqa: BLE001
                continue
            if excerpt:
                it.description = (excerpt + "\n" + it.description).strip()
                ok += 1
            for t in triggers:
                if t not in it.trigger_words:
                    it.trigger_words.append(t)
            it.trigger_words = it.trigger_words[:5]
    return ok
