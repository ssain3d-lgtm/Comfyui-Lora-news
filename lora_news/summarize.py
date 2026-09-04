"""선택 기능: Claude API로 자연스러운 한글 한 줄 요약 생성.

- `anthropic` 패키지가 설치되어 있고 자격 증명(ANTHROPIC_API_KEY 등)이 있을 때만 동작.
- 결과는 data/summaries.json 에 캐시되어 같은 항목은 다시 호출하지 않는다.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from .classify import CATEGORIES, GH_CATEGORIES, LORA_CATEGORIES, WF_CATEGORIES
from .i18n import msg
from .models import LoraItem
from .store import Store


class SummarizeError(RuntimeError):
    def __init__(self, message: dict):
        super().__init__(message["ko"])
        self.message = message

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "당신은 ComfyUI 사용자를 위해 LoRA 모델, ComfyUI 워크플로우, 관련 GitHub 저장소를 짧게 소개하는 도우미입니다. "
    "각 항목에 대해 (1) 어떤 용도인지, (2) 어떤 베이스 모델에서 쓰는지, (3) 트리거 워드나 사용 팁이 있으면 그것까지 "
    "한두 문장으로 자연스럽게 요약하세요. summary_ko 는 한국어(최대 100자), summary_en 은 같은 내용의 영어(최대 160자)입니다. "
    "워크플로우는 무엇을 만드는 흐름인지와 필요한 모델/노드를 적으세요. "
    "정보가 부족하면 아는 범위에서만 쓰고 지어내지 마세요. category 는 각 항목의 allowed_categories 중 하나를 고르세요."
)


def allowed_categories(item: LoraItem) -> list[str]:
    if item.kind == "workflow":
        return WF_CATEGORIES
    if item.source == "github":
        return GH_CATEGORIES
    return LORA_CATEGORIES

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "summary_ko": {"type": "string"},
                    "summary_en": {"type": "string"},
                    "category": {"type": "string", "enum": CATEGORIES},
                },
                "required": ["key", "summary_ko", "summary_en", "category"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def _item_payload(item: LoraItem) -> dict:
    return {
        "key": item.key,
        "source": item.source,
        "kind": item.kind,
        "name": item.name,
        "base_model": item.base_model,
        "rule_category": item.category,
        "allowed_categories": allowed_categories(item),
        "tags": item.tags[:15],
        "trigger_words": item.trigger_words,
        "description": (item.description or "")[:900],
    }


class ClaudeSummarizer:
    def __init__(self, store: Store, model: str = "claude-opus-5", max_items: int = 60, batch_size: int = 12):
        self.store = store
        self.model = model
        self.max_items = max_items
        self.batch_size = batch_size
        self.client = None
        self.available = False
        self.reason: dict | None = None
        try:
            import anthropic  # noqa: F401
        except ImportError:
            self.reason = msg("claude_no_sdk")
            return
        try:
            self.client = anthropic.Anthropic()
            self.available = True
        except Exception as e:  # noqa: BLE001
            self.reason = msg("claude_init_failed", err=e)

    # ------------------------------------------------------------------
    def apply_cached(self, items: list[LoraItem]) -> int:
        cache = self.store.load_summaries()
        n = 0
        for it in items:
            hit = cache.get(it.key)
            if isinstance(hit, dict) and hit.get("summary_ko"):
                it.summary_ko = hit["summary_ko"]
                it.summary_en = hit.get("summary_en") or ""
                it.summary_source = "claude"
                if hit.get("category") in CATEGORIES:
                    it.category = hit["category"]
                n += 1
        return n

    def summarize(self, items: list[LoraItem], progress=None) -> tuple[int, list[dict]]:
        """캐시에 없는 항목을 신규 우선으로 최대 max_items 개 요약. (요약 개수, 오류 메시지 목록) 반환."""
        errors: list[dict] = []
        if not self.available:
            return 0, [self.reason] if self.reason else []
        cache = self.store.load_summaries()
        todo = [it for it in items if it.key not in cache]
        todo.sort(key=lambda it: (not it.found_this_run, not it.is_new, -(it.downloads + it.likes * 10)))
        todo = todo[: self.max_items]
        done = 0
        for start in range(0, len(todo), self.batch_size):
            batch = todo[start:start + self.batch_size]
            if progress:
                progress(msg("claude_progress", done=done, total=len(todo)))
            try:
                results = self._call(batch)
            except SummarizeError as e:
                log.warning(e.message["ko"])
                errors.append(msg("claude_failed", err=e.message["ko"]) | {"en": msg("claude_failed", err=e.message["en"])["en"]})
                if e.message.get("key") == "claude_auth":
                    break
                continue
            except Exception as e:  # noqa: BLE001
                log.warning("Claude 요약 실패: %s", e)
                errors.append(msg("claude_failed", err=e))
                continue
            by_key = {it.key: it for it in batch}
            now = datetime.now(timezone.utc).isoformat()
            for r in results:
                it = by_key.get(r.get("key"))
                summary = (r.get("summary_ko") or "").strip()
                summary_en = (r.get("summary_en") or "").strip()
                if not it or not summary:
                    continue
                it.summary_ko = summary
                it.summary_en = summary_en
                it.summary_source = "claude"
                if r.get("category") in CATEGORIES:
                    it.category = r["category"]
                cache[it.key] = {"summary_ko": summary, "summary_en": summary_en, "category": it.category,
                                 "model": self.model, "ts": now}
                done += 1
            self.store.save_summaries(cache)
        return done, errors

    # ------------------------------------------------------------------
    def _call(self, batch: list[LoraItem]) -> list[dict]:
        import anthropic

        payload = json.dumps({"items": [_item_payload(it) for it in batch]}, ensure_ascii=False)
        user_msg = (
            "다음 LoRA/저장소 목록을 각각 한국어로 요약해 주세요. 입력 key 를 그대로 돌려주세요.\n\n" + payload
        )
        kwargs = dict(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}, "effort": "low"},
        )
        for attempt in range(2):
            try:
                try:
                    # 안전 분류기 거절 시 서버가 다른 모델로 자동 재시도하도록 기본 폴백 사용
                    response = self.client.beta.messages.create(
                        betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                    )
                except TypeError:
                    # 구버전 SDK 는 fallbacks 파라미터를 모름
                    response = self.client.messages.create(**kwargs)
                break
            except anthropic.AuthenticationError as e:
                self.available = False
                raise SummarizeError(msg("claude_auth", err=e)) from None
            except anthropic.RateLimitError as e:
                if attempt == 0:
                    wait = 20
                    try:
                        wait = int(e.response.headers.get("retry-after", "20"))
                    except Exception:  # noqa: BLE001
                        pass
                    log.info("Claude 요청 한도, %ds 후 재시도", wait)
                    time.sleep(min(wait, 60))
                    continue
                raise SummarizeError(msg("claude_rate")) from None
            except anthropic.APIStatusError as e:
                raise SummarizeError(msg("claude_api", status=e.status_code, err=getattr(e, "message", e))) from None
            except anthropic.APIConnectionError as e:
                raise SummarizeError(msg("claude_network", err=e)) from None

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise SummarizeError(msg("claude_refusal", category=getattr(details, "category", "") or ""))
        text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
        data = json.loads(text) if text else {}
        items = data.get("items") if isinstance(data, dict) else None
        return items if isinstance(items, list) else []
