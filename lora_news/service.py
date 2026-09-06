"""수집 → 분류 → 신규 판정 → (선택) Claude 요약 → 저장 을 묶는 서비스."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone

from .classify import BASE_MODEL_EN, CATEGORY_EN, classify
from .config import Config
from .i18n import msg
from .models import LoraItem
from .sources import civitai as cv_source
from .sources import github as gh_source
from .sources import huggingface as hf_source
from .store import Store

log = logging.getLogger(__name__)

SOURCE_NAMES = {"huggingface": "Hugging Face", "github": "GitHub", "civitai": "Civitai"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        v = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


class NewsService:
    def __init__(self, config: Config | None = None, store: Store | None = None,
                 hf_fetch=None, gh_fetch=None, cv_fetch=None, readme_enricher=None, summarizer=None):
        self.config = config or Config()
        self.store = store or Store(self.config.data_dir)
        self._hf_fetch = hf_fetch or (lambda: hf_source.fetch(
            limit=self.config.hf_limit, token=self.config.hf_token, timeout=self.config.http_timeout))
        self._gh_fetch = gh_fetch or (lambda: gh_source.fetch(
            per_page=self.config.gh_per_page, token=self.config.github_token, timeout=self.config.http_timeout))
        self._cv_fetch = cv_fetch or (lambda: cv_source.fetch(
            limit=self.config.civitai_limit, token=self.config.civitai_token, timeout=self.config.http_timeout,
            nsfw=self.config.civitai_nsfw))
        self._readme_enricher = readme_enricher or (lambda items: hf_source.enrich_with_readmes(
            items, token=self.config.hf_token, timeout=min(self.config.http_timeout, 20)))
        self._summarizer = summarizer
        self._lock = threading.Lock()
        self._refresh_thread: threading.Thread | None = None
        self.status: dict = {
            "refreshing": False,
            "progress": None,          # {"key","ko","en"} 또는 None
            "last_refresh": None,
            "last_error": None,
            "errors": [],              # [{"key","ko","en"}, ...]
            "claude": {"enabled": self.config.claude_enabled, "model": self.config.claude_model, "summarized": 0},
            "counts": {},
        }
        cache = self.store.load_cache()
        self.items: list[LoraItem] = self._load_items(cache.get("items"))
        self._refresh_new_flags(self.items, _now())
        self.status["last_refresh"] = cache.get("updated_at")
        self.status["counts"] = cache.get("counts", self._counts(self.items))
        if cache.get("claude"):
            self.status["claude"].update({k: v for k, v in cache["claude"].items() if k in ("summarized",)})

    # ------------------------------------------------------------------
    @staticmethod
    def _load_items(rows) -> list[LoraItem]:
        """캐시에서 항목을 복원한다. 망가진 항목 하나가 앱 전체를 막지 않도록 건너뛴다."""
        items: list[LoraItem] = []
        skipped = 0
        for row in rows or []:
            try:
                items.append(LoraItem.from_dict(row))
            except Exception:  # noqa: BLE001
                skipped += 1
        if skipped:
            log.warning("캐시에서 손상된 항목 %d개를 건너뛰었습니다", skipped)
        return items

    def _refresh_new_flags(self, items: list[LoraItem], now: datetime) -> None:
        """캐시에서 읽은 신규 배지를 현재 시각 기준으로 다시 계산한다."""
        window = timedelta(hours=self.config.new_window_hours)
        for it in items:
            first_dt = _parse_dt(it.first_seen)
            it.is_new = bool(first_dt and now - first_dt <= window)
            it.found_this_run = False   # 이전 실행의 흔적이지 이번 실행의 발견이 아니다

    def _set_progress(self, message, **kw) -> None:
        """message: i18n 키(+포맷 인자) 또는 이미 만들어진 메시지 dict, None 이면 지움."""
        if isinstance(message, str):
            message = msg(message, **kw)
        self.status["progress"] = message
        if message:
            log.info(message["ko"])

    def start_refresh(self) -> bool:
        """백그라운드 새로고침 시작. 이미 진행 중이면 False."""
        with self._lock:
            if self.status["refreshing"]:
                return False
            self.status["refreshing"] = True
            self.status["progress"] = msg("starting")
            self._refresh_thread = threading.Thread(target=self._refresh_safe, daemon=True)
            self._refresh_thread.start()
            return True

    def wait(self, timeout: float | None = None) -> None:
        t = self._refresh_thread
        if t:
            t.join(timeout)

    def _refresh_safe(self) -> None:
        try:
            self.refresh()
        except Exception as e:  # noqa: BLE001
            log.exception("새로고침 실패")
            self.status["last_error"] = str(e)
        finally:
            self.status["refreshing"] = False
            self.status["progress"] = None

    # ------------------------------------------------------------------
    def refresh(self) -> dict:
        """동기 새로고침. 반환: 요약 통계."""
        self.status["errors"] = []
        self.status["last_error"] = None
        started = _now()
        self._set_progress("fetching")

        enabled = self.config.sources
        plan = [("huggingface", "Hugging Face", self._hf_fetch),
                ("github", "GitHub", self._gh_fetch),
                ("civitai", "Civitai", self._cv_fetch)]
        plan = [row for row in plan if row[0] in enabled]
        deadline = self.config.refresh_deadline

        results: dict[str, list[LoraItem]] = {}
        errors: list[dict] = []
        with ThreadPoolExecutor(max_workers=max(1, len(plan))) as pool:
            futures = {pool.submit(fn): (key, label) for key, label, fn in plan}
            for fut, (key, label) in futures.items():
                got, errs = self._safe_result(fut, label, timeout=deadline)
                results[key] = got
                errors.extend(errs)
        hf_items = results.get("huggingface", [])
        gh_items = results.get("github", [])
        cv_items = results.get("civitai", [])
        if plan and not any(results.values()):
            errors.append(msg("all_failed"))

        previous = {it.key: it for it in self.items}
        fetched: dict[str, LoraItem] = {}
        for it in hf_items + gh_items + cv_items:
            fetched.setdefault(it.key, it)

        # 소스가 오류를 냈거나 아예 비활성이면 그 소스의 이전 캐시 항목을 유지한다.
        # (쿼리 일부만 실패해도 이미 알던 항목이 사라지면 안 된다)
        failed_sources = {e.get("source_key") for e in errors if isinstance(e, dict)}
        for source in ("huggingface", "github", "civitai"):
            got = results.get(source)
            source_failed = source not in enabled or not got or source in failed_sources
            if not source_failed:
                continue
            kept = [it for it in previous.values() if it.source == source]
            missing = [it for it in kept if it.key not in fetched]
            if missing and source in enabled:
                errors.append(msg("kept_cache", source=SOURCE_NAMES.get(source, source), n=len(missing)))
            for it in kept:
                fetched.setdefault(it.key, it)

        # 이전에 Claude 요약이 있던 항목은 유지
        for key, it in fetched.items():
            prev = previous.get(key)
            if prev and prev.summary_source == "claude" and prev.summary_ko:
                it.summary_ko, it.summary_en, it.summary_source = prev.summary_ko, prev.summary_en, "claude"
            if prev and prev.description and it.source == "huggingface":
                # 이미 받아둔 README 발췌를 재사용하되, 이번에 새로 온 태그/예시 블록은 남긴다
                excerpt = prev.description.split("\n예시 프롬프트:")[0].split("\n태그:")[0].strip()
                if excerpt and excerpt not in it.description:
                    it.description = (excerpt + "\n" + it.description).strip()
                for t in prev.trigger_words:
                    if t not in it.trigger_words:
                        it.trigger_words.append(t)
                it.trigger_words = it.trigger_words[:5]

        items = list(fetched.values())
        self._set_progress("marking_new", n=len(items))
        self._mark_new(items, started)

        # README 발췌 보강 (신규/미요약 항목 우선, 최대 N개)
        need = [it for it in items if it.source == "huggingface" and len(it.description) < 200]
        need.sort(key=lambda it: (not it.found_this_run, not it.is_new, -(it.downloads + it.likes * 10)))
        need = need[: self.config.readme_fetch_max]
        if need:
            self._set_progress("reading_cards", n=len(need))
            try:
                self._readme_enricher(need)
            except Exception as e:  # noqa: BLE001
                errors.append(msg("readme_failed", err=e))

        self._set_progress("classifying")
        for it in items:
            classify(it)

        summarized = 0
        summarizer = self._get_summarizer()
        if summarizer is not None:
            try:
                summarizer.apply_cached(items)
                summarized, s_errors = summarizer.summarize(items, progress=self._set_progress)
                errors.extend(s_errors)
            except Exception as e:  # noqa: BLE001
                errors.append(msg("claude_failed", err=e))
            self.status["claude"]["summarized"] = self.status["claude"].get("summarized", 0) + summarized

        items.sort(key=lambda it: (it.found_this_run, it.is_new, it.created_at or ""), reverse=True)

        self.items = items
        self.status["errors"] = errors
        self.status["last_refresh"] = _now().isoformat()
        self.status["counts"] = self._counts(items)
        self.store.save_cache({
            "updated_at": self.status["last_refresh"],
            "counts": self.status["counts"],
            "claude": {"summarized": self.status["claude"]["summarized"]},
            "items": [it.to_dict() for it in items],
        })
        self._set_progress(None)
        log.info("새로고침 완료: %s", self.status["counts"])
        return self.status["counts"]

    # ------------------------------------------------------------------
    def _get_summarizer(self):
        if self._summarizer is not None:
            return self._summarizer
        if not self.config.claude_enabled:
            return None
        from .summarize import ClaudeSummarizer
        self._summarizer = ClaudeSummarizer(
            self.store, model=self.config.claude_model, max_items=self.config.claude_max_items)
        if not self._summarizer.available:
            self.status["claude"]["reason"] = self._summarizer.reason
        return self._summarizer

    @staticmethod
    def _safe_result(fut, label: str, timeout: float | None = None) -> tuple[list[LoraItem], list[dict]]:
        key = {"Hugging Face": "huggingface", "GitHub": "github", "Civitai": "civitai"}.get(label, label)
        try:
            items, errors = fut.result(timeout=timeout)
            return list(items), [dict(e, source_key=key) if isinstance(e, dict) else e for e in errors]
        except FuturesTimeout:
            fut.cancel()
            log.warning("%s 수집이 제한 시간(%ss)을 넘겼습니다", label, timeout)
            return [], [dict(msg("deadline", source=label), source_key=key)]
        except Exception as e:  # noqa: BLE001
            log.warning("%s 수집 실패: %s", label, e)
            return [], [dict(msg("source_failed", source=label, err=e), source_key=key)]

    def _mark_new(self, items: list[LoraItem], now: datetime) -> None:
        seen = self.store.load_seen()
        # 기준선은 소스마다 따로 잡는다. 한 소스가 처음 성공한 날 그 소스의 기존 항목이
        # 전부 "신규"로 쏟아지지 않도록 하기 위해서다.
        prefixes = {"huggingface": "hf:", "github": "gh:", "civitai": "civitai:"}
        baselined = {src for src, pre in prefixes.items() if any(k.startswith(pre) for k in seen)}
        window = timedelta(hours=self.config.new_window_hours)
        now_iso = now.isoformat()
        for it in items:
            first = seen.get(it.key)
            baseline = it.source not in baselined
            if not first:
                if baseline:
                    created = _parse_dt(it.created_at)
                    first = (created.isoformat() if created and created < now else now_iso)
                    it.found_this_run = False
                else:
                    first = now_iso
                    it.found_this_run = True
                seen[it.key] = first
            else:
                it.found_this_run = False
            it.first_seen = first
            first_dt = _parse_dt(first)
            it.is_new = bool(first_dt and now - first_dt <= window)
        self.store.save_seen(seen)

    @staticmethod
    def _counts(items: list[LoraItem]) -> dict:
        def block(subset: list[LoraItem]) -> dict:
            return {
                "total": len(subset),
                "huggingface": sum(1 for it in subset if it.source == "huggingface"),
                "github": sum(1 for it in subset if it.source == "github"),
                "civitai": sum(1 for it in subset if it.source == "civitai"),
                "new": sum(1 for it in subset if it.is_new),
                "found_this_run": sum(1 for it in subset if it.found_this_run),
                "claude": sum(1 for it in subset if it.summary_source == "claude"),
            }

        counts = block(items)
        counts["lora"] = block([it for it in items if it.kind == "lora"])
        counts["workflow"] = block([it for it in items if it.kind == "workflow"])
        return counts

    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        facets = {}
        for kind in ("lora", "workflow"):
            base_models: dict[str, int] = {}
            categories: dict[str, int] = {}
            for it in self.items:
                if it.kind != kind:
                    continue
                base_models[it.base_model] = base_models.get(it.base_model, 0) + 1
                categories[it.category] = categories.get(it.category, 0) + 1
            facets[kind] = {
                "base_models": sorted(base_models.items(), key=lambda kv: -kv[1]),
                "categories": sorted(categories.items(), key=lambda kv: -kv[1]),
            }
        return {
            "status": self.status,
            "items": [it.to_dict() for it in self.items],
            "facets": facets,
            "labels_en": {"base_models": BASE_MODEL_EN, "categories": CATEGORY_EN},
        }
