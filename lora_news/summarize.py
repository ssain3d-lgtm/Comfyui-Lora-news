"""선택 기능: Claude API로 자연스러운 한글 한 줄 요약 생성.

- `anthropic` 패키지가 설치되어 있고 자격 증명(ANTHROPIC_API_KEY 등)이 있을 때만 동작.
- 결과는 data/summaries.json 에 캐시되어 같은 항목은 다시 호출하지 않는다.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone

from .classify import CATEGORIES
from .models import LoraItem
from .store import Store

log = logging.getLogger(__name__)

HF_CATEGORIES = [c for c in CATEGORIES if c not in ("학습 도구", "커스텀 노드", "로더/관리", "병합/변환", "워크플로우/모음", "모델/가중치")]
GH_CATEGORIES = ["학습 도구", "커스텀 노드", "로더/관리", "병합/변환", "워크플로우/모음", "모델/가중치"]

SYSTEM_PROMPT = (
    "당신은 ComfyUI 사용자를 위해 LoRA 모델과 관련 GitHub 저장소를 한국어로 짧게 소개하는 도우미입니다. "
    "각 항목에 대해 (1) 어떤 용도인지, (2) 어떤 베이스 모델에서 쓰는지, (3) 트리거 워드나 사용 팁이 있으면 그것까지 "
    "한두 문장(최대 100자)으로 자연스럽게 요약하세요. 정보가 부족하면 아는 범위에서만 쓰고 지어내지 마세요. "
    "category 는 주어진 목록 중 하나를 고르세요."
)

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
                    "category": {"type": "string", "enum": CATEGORIES},
                },
                "required": ["key", "summary_ko", "category"],
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
        "name": item.name,
        "base_model": item.base_model,
        "rule_category": item.category,
        "allowed_categories": GH_CATEGORIES if item.source == "github" else HF_CATEGORIES,
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
        self.reason = ""
        try:
            import anthropic  # noqa: F401
        except ImportError:
            self.reason = "anthropic 패키지가 없습니다 (pip install anthropic)"
            return
        try:
            self.client = anthropic.Anthropic()
            self.available = True
        except Exception as e:  # noqa: BLE001
            self.reason = f"Claude 클라이언트 초기화 실패: {e}"

    # ------------------------------------------------------------------
    def apply_cached(self, items: list[LoraItem]) -> int:
        cache = self.store.load_summaries()
        n = 0
        for it in items:
            hit = cache.get(it.key)
            if isinstance(hit, dict) and hit.get("summary_ko"):
                it.summary_ko = hit["summary_ko"]
                it.summary_source = "claude"
                if hit.get("category") in CATEGORIES:
                    it.category = hit["category"]
                n += 1
        return n

    def summarize(self, items: list[LoraItem], progress=None) -> tuple[int, list[str]]:
        """캐시에 없는 항목을 신규 우선으로 최대 max_items 개 요약. (요약 개수, 오류) 반환."""
        errors: list[str] = []
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
                progress(f"Claude 한글 요약 생성 중… ({done}/{len(todo)})")
            try:
                results = self._call(batch)
            except Exception as e:  # noqa: BLE001
                msg = f"Claude 요약 실패: {e}"
                log.warning(msg)
                errors.append(msg)
                if "인증" in msg or "AuthenticationError" in msg:
                    break
                continue
            by_key = {it.key: it for it in batch}
            now = datetime.now(timezone.utc).isoformat()
            for r in results:
                it = by_key.get(r.get("key"))
                summary = (r.get("summary_ko") or "").strip()
                if not it or not summary:
                    continue
                it.summary_ko = summary
                it.summary_source = "claude"
                if r.get("category") in CATEGORIES:
                    it.category = r["category"]
                cache[it.key] = {"summary_ko": summary, "category": it.category, "model": self.model, "ts": now}
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
                raise RuntimeError(f"인증 실패 (API 키 확인): {e}") from None
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
                raise RuntimeError("요청 한도 초과") from None
            except anthropic.APIStatusError as e:
                raise RuntimeError(f"API 오류 {e.status_code}: {getattr(e, 'message', e)}") from None
            except anthropic.APIConnectionError as e:
                raise RuntimeError(f"네트워크 오류: {e}") from None

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise RuntimeError(f"모델이 응답을 거절했습니다: {getattr(details, 'category', '')}")
        text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
        data = json.loads(text) if text else {}
        items = data.get("items") if isinstance(data, dict) else None
        return items if isinstance(items, list) else []
