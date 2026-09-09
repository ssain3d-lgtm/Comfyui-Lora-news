import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lora_news.config import Config
from lora_news.models import LoraItem
from lora_news.service import NewsService
from lora_news.store import Store

from lora_news.i18n import msg

FIXTURES = Path(__file__).parent / "fixtures" / "sample_items.json"


def msg_partial():
    return msg("hf_failed", err="flaky query")


def fixture_items():
    return [LoraItem.from_dict(d) for d in json.loads(FIXTURES.read_text(encoding="utf-8"))]


class FakeSummarizer:
    available = True
    reason = ""

    def apply_cached(self, items):
        return 0

    def summarize(self, items, progress=None):
        for it in items[:2]:
            it.summary_ko = "AI 요약: " + it.name
            it.summary_source = "claude"
        return 2, []


def make_service(tmp, hf, gh, cv=lambda: ([], []), summarizer=None):
    cfg = Config()
    cfg.data_dir = Path(tmp)
    cfg.claude_enabled = summarizer is not None
    return NewsService(
        cfg, store=Store(cfg.data_dir),
        hf_fetch=lambda: hf(), gh_fetch=lambda: gh(), cv_fetch=lambda: cv(),
        readme_enricher=lambda items: 0, summarizer=summarizer,
    )


class ServiceTests(unittest.TestCase):
    def test_first_run_baseline_then_new_detection(self):
        items = fixture_items()
        hf = [it for it in items if it.source == "huggingface"]
        gh = [it for it in items if it.source == "github"]
        cv = [it for it in items if it.source == "civitai"]
        with tempfile.TemporaryDirectory() as tmp:
            svc = make_service(tmp, lambda: (hf[:-1], []), lambda: (gh, []), lambda: (cv, []))
            counts = svc.refresh()
            self.assertEqual(counts["total"], len(items) - 1)
            self.assertEqual(counts["civitai"], len(cv))
            self.assertEqual(counts["workflow"]["total"], sum(1 for it in hf[:-1] + gh + cv if it.kind == "workflow"))
            self.assertEqual(counts["lora"]["total"] + counts["workflow"]["total"], counts["total"])
            self.assertEqual(counts["found_this_run"], 0, "첫 실행은 기준선: '이번 실행 발견' 없음")
            # 첫 실행에서는 소스 등록일이 최근(72h)인 것만 신규
            recent = [it for it in svc.items if it.is_new]
            self.assertTrue(all(datetime.now(timezone.utc) - datetime.fromisoformat(it.created_at.replace("Z", "+00:00")) <= timedelta(hours=72) for it in recent))

            # 두 번째 실행: 이전에 없던 항목 하나 추가 -> found_this_run
            svc2 = make_service(tmp, lambda: (hf, []), lambda: (gh, []), lambda: (cv, []))
            counts2 = svc2.refresh()
            self.assertEqual(counts2["total"], len(items))
            self.assertEqual(counts2["found_this_run"], 1)
            found = [it for it in svc2.items if it.found_this_run]
            self.assertEqual(found[0].key, hf[-1].key)
            self.assertTrue(found[0].is_new)
            self.assertEqual(svc2.items[0].key, hf[-1].key, "신규 발견 항목이 맨 앞")

            # 캐시 파일 존재 및 재로드
            svc3 = make_service(tmp, lambda: ([], []), lambda: ([], []))
            self.assertEqual(len(svc3.items), len(items))
            seen = json.loads((Path(tmp) / "seen.json").read_text(encoding="utf-8"))
            self.assertEqual(len(seen), len(items))

    def test_source_failure_keeps_previous_cache(self):
        items = fixture_items()
        hf = [it for it in items if it.source == "huggingface"]
        gh = [it for it in items if it.source == "github"]
        cv = [it for it in items if it.source == "civitai"]
        with tempfile.TemporaryDirectory() as tmp:
            make_service(tmp, lambda: (hf, []), lambda: (gh, []), lambda: (cv, [])).refresh()

            def boom():
                raise RuntimeError("network down")

            from lora_news.i18n import msg
            svc = make_service(tmp, boom, lambda: (gh, []), lambda: ([], [msg("cv_forbidden")]))
            counts = svc.refresh()
            self.assertEqual(counts["huggingface"], len(hf))
            self.assertEqual(counts["civitai"], len(cv))
            errs = svc.status["errors"]
            self.assertTrue(all(isinstance(e, dict) and e.get("ko") and e.get("en") for e in errs), errs)
            self.assertTrue(any(e["key"] == "source_failed" and "Hugging Face 수집 실패" in e["ko"] for e in errs))
            self.assertTrue(any(e["key"] == "kept_cache_failed" and e["ko"].startswith("Hugging Face ") for e in errs))
            self.assertTrue(any("Hugging Face fetch failed" in e["en"] for e in errs))
            self.assertTrue(any(e["key"] == "cv_forbidden" for e in errs))
            self.assertEqual(sum(1 for e in errs if e["key"] == "kept_cache_failed"), 2)
            self.assertIsNone(svc.status["progress"])

    def test_claude_summaries_applied_and_kept(self):
        items = fixture_items()
        hf = [it for it in items if it.source == "huggingface"]
        with tempfile.TemporaryDirectory() as tmp:
            svc = make_service(tmp, lambda: (hf, []), lambda: ([], []), summarizer=FakeSummarizer())
            counts = svc.refresh()
            self.assertEqual(counts["claude"], 2)
            snap = svc.snapshot()
            self.assertEqual(sum(1 for d in snap["items"] if d["summary_source"] == "claude"), 2)
            self.assertIn("base_models", snap["facets"]["lora"])
            self.assertIn("categories", snap["facets"]["workflow"])
            self.assertEqual(snap["labels_en"]["categories"]["스타일/화풍"], "Style/art style")
            self.assertTrue(all(d["summary_en"] for d in snap["items"]), "모든 항목에 영문 요약")
            # 다음 실행에서 Claude 요약이 규칙 요약으로 덮이지 않음
            svc2 = make_service(tmp, lambda: (hf, []), lambda: ([], []), summarizer=None)
            svc2.refresh()
            self.assertEqual(sum(1 for it in svc2.items if it.summary_source == "claude"), 2)


class NewDetectionTests(unittest.TestCase):
    """신규 판정은 이 앱의 핵심 기능이라 실패 조합까지 따로 확인한다."""

    def items_for(self, source, n=3):
        return [LoraItem(key=f"{source}:{i}", source=source, name=f"{source}/{i}", author="a", url="",
                         created_at="2020-01-01T00:00:00.000Z") for i in range(n)]

    def test_baseline_is_per_source(self):
        hf = self.items_for("huggingface")
        cv = self.items_for("civitai")
        with tempfile.TemporaryDirectory() as tmp:
            # 1회차: Civitai 실패
            first = make_service(tmp, lambda: (hf, []), lambda: ([], []), lambda: ([], []))
            first.refresh()
            self.assertEqual(first.status["counts"]["found_this_run"], 0)

            # 2회차: Civitai 성공. 오래된 Civitai 항목이 "신규"로 쏟아지면 안 된다.
            second = make_service(tmp, lambda: (hf, []), lambda: ([], []), lambda: (cv, []))
            counts = second.refresh()
            self.assertEqual(counts["civitai"], len(cv))
            self.assertEqual(counts["found_this_run"], 0, "소스마다 기준선을 따로 잡아야 한다")
            self.assertEqual(counts["new"], 0)

            # 3회차: 진짜 신규 한 건
            fresh = LoraItem(key="civitai:new", source="civitai", name="new", author="a", url="",
                             created_at=datetime.now(timezone.utc).isoformat())
            third = make_service(tmp, lambda: (hf, []), lambda: ([], []), lambda: (cv + [fresh], []))
            self.assertEqual(third.refresh()["found_this_run"], 1)

    def test_cached_new_badges_expire(self):
        old = datetime.now(timezone.utc) - timedelta(days=30)
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            store.save_cache({"updated_at": "x", "items": [{
                "key": "hf:a/b", "source": "huggingface", "name": "a/b", "author": "a", "url": "",
                "first_seen": old.isoformat(), "is_new": True, "found_this_run": True}]})
            svc = make_service(tmp, lambda: ([], []), lambda: ([], []))
            it = svc.items[0]
            self.assertFalse(it.is_new, "30일 전 항목에 NEW 배지가 남으면 안 된다")
            self.assertFalse(it.found_this_run, "이전 실행의 발견은 이번 실행의 발견이 아니다")

    def test_partial_source_failure_keeps_known_items(self):
        hf = self.items_for("huggingface", 5)
        with tempfile.TemporaryDirectory() as tmp:
            make_service(tmp, lambda: (hf, []), lambda: ([], [])).refresh()
            # 16개 쿼리 중 15개 실패, 1개만 성공한 상태
            from lora_news.i18n import msg
            svc = make_service(tmp, lambda: (hf[:1], [msg("hf_failed", err="boom")], {"queries": 16, "failed": 15}),
                               lambda: ([], []))
            counts = svc.refresh()
            self.assertEqual(counts["huggingface"], 5, "일부 실패해도 알던 항목이 사라지면 안 된다")
            kept = [e for e in svc.status["errors"] if e["key"] == "kept_cache_partial"]
            self.assertEqual(len(kept), 1)
            self.assertIn("15/16", kept[0]["ko"])

    def test_a_successful_source_does_not_resurrect_its_cache(self):
        hf = self.items_for("huggingface", 5)
        with tempfile.TemporaryDirectory() as tmp:
            make_service(tmp, lambda: (hf, [], {"queries": 16, "failed": 0}), lambda: ([], [])).refresh()
            # 업스트림에서 두 개가 사라진, 완전히 성공한 실행
            svc = make_service(tmp, lambda: (hf[:3], [], {"queries": 16, "failed": 0}), lambda: ([], []))
            counts = svc.refresh()
            self.assertEqual(counts["huggingface"], 3, "성공한 소스는 사라진 항목을 되살리지 않는다")
            self.assertEqual([e for e in svc.status["errors"] if e["key"].startswith("kept_cache")], [])

    def test_an_empty_but_successful_run_is_not_reported_as_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = make_service(tmp,
                               lambda: ([], [], {"queries": 16, "failed": 0}),
                               lambda: ([], [], {"queries": 8, "failed": 0}),
                               lambda: ([], [], {"queries": 6, "failed": 0}))
            svc.refresh()
            self.assertEqual(svc.status["errors"], [], "결과가 0개인 것과 실패한 것은 다르다")

    def test_retained_cache_is_bounded_by_age(self):
        hf = self.items_for("huggingface", 4)
        with tempfile.TemporaryDirectory() as tmp:
            make_service(tmp, lambda: (hf, [], {"queries": 16, "failed": 0}), lambda: ([], [])).refresh()
            # 두 항목의 last_seen 을 오래 전으로 되돌린 뒤 소스를 실패시킨다
            store = Store(Path(tmp))
            cache = store.load_cache()
            old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
            for row in cache["items"][:2]:
                row["last_seen"] = old
            store.save_cache(cache)

            def boom():
                raise RuntimeError("down")

            svc = make_service(tmp, boom, lambda: ([], []))
            counts = svc.refresh()
            self.assertEqual(counts["huggingface"], 2, "오래 안 보인 항목은 캐시에서 정리된다")

    def test_repeated_partial_failure_converges_instead_of_growing(self):
        """쿼리 하나가 계속 실패해도 캐시가 무한정 불어나면 안 된다."""
        def batch(run):
            steady = [LoraItem(key=f"hf:{i}", source="huggingface", name=f"a/{i}", author="a", url="",
                               created_at="2020-01-01T00:00:00Z") for i in range(5)]
            gone = [LoraItem(key=f"hf:gone{run}", source="huggingface", name=f"a/g{run}", author="a", url="",
                             created_at="2020-01-01T00:00:00Z")]
            return steady + gone

        with tempfile.TemporaryDirectory() as tmp:
            totals = []
            for run in range(1, 11):
                svc = make_service(tmp,
                                   lambda r=run: (batch(r), [msg_partial()], {"queries": 16, "failed": 1}),
                                   lambda: ([], [], {"queries": 1, "failed": 0}))
                totals.append(svc.refresh()["total"])
            self.assertEqual(totals[-1], totals[-4], f"수렴해야 한다: {totals}")
            self.assertLessEqual(totals[-1], 12, f"업스트림 6개인데 캐시가 너무 크다: {totals}")

    def test_changes_between_runs_are_recorded(self):
        def cv_item(**kw):
            d = dict(key="civitai:1", source="civitai", name="Ghibli", author="a", url="",
                     created_at="2026-01-01T00:00:00Z")
            d.update(kw)
            return LoraItem(**d)

        with tempfile.TemporaryDirectory() as tmp:
            def run(items):
                return make_service(tmp, lambda: ([], [], {"queries": 1, "failed": 0}),
                                    lambda: ([], [], {"queries": 1, "failed": 0}),
                                    lambda: (items, [], {"queries": 6, "failed": 0}))

            run([cv_item(version="v1.0", updated_at="2026-01-01T00:00:00Z", downloads=1000)]).refresh()

            svc = run([cv_item(version="v3.0", updated_at="2026-09-01T00:00:00Z", downloads=41000)])
            counts = svc.refresh()
            it = svc.items[0]
            self.assertEqual(sorted(it.changes), ["downloads", "updated", "version"])
            self.assertTrue(it.last_change_at)
            self.assertEqual(counts["changed"], 1)

            # 아무것도 안 바뀐 실행에서는 새 변화를 만들지 않는다
            svc2 = run([cv_item(version="v3.0", updated_at="2026-09-01T00:00:00Z", downloads=41000)])
            svc2.refresh()
            self.assertEqual(svc2.items[0].last_change_at, it.last_change_at, "변화가 없으면 시각도 그대로")

    def test_readme_excerpts_are_replaced_not_stacked(self):
        def hf_item():
            return LoraItem(key="hf:a/b", source="huggingface", name="a/b", author="a", url="",
                            created_at="2026-01-01T00:00:00Z")

        calls = []

        def enrich(items):
            calls.append(len(items))
            for it in items:
                it.readme_excerpt = "A watercolour style LoRA."
            return len(items)

        with tempfile.TemporaryDirectory() as tmp:
            for _ in range(3):
                cfg = Config()
                cfg.data_dir = Path(tmp)
                cfg.claude_enabled = False
                svc = NewsService(cfg, store=Store(cfg.data_dir),
                                  hf_fetch=lambda: ([hf_item()], [], {"queries": 16, "failed": 0}),
                                  gh_fetch=lambda: ([], [], {"queries": 1, "failed": 0}),
                                  cv_fetch=lambda: ([], [], {"queries": 1, "failed": 0}),
                                  readme_enricher=enrich)
                svc.refresh()
            self.assertEqual(svc.items[0].readme_excerpt, "A watercolour style LoRA.",
                             "매 실행 앞에 덧붙어 불어나면 안 된다")
            self.assertEqual(calls, [1], "한 번 읽은 모델 카드는 다시 읽지 않는다")

    def test_old_entries_are_pruned_from_seen_and_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
            store.save_seen({"hf:gone": old, "hf:recent": datetime.now(timezone.utc).isoformat()})
            store.save_summaries({"hf:gone": {"summary_ko": "x"}, "hf:live": {"summary_ko": "y"}})
            live = LoraItem(key="hf:live", source="huggingface", name="a/b", author="a", url="")
            svc = make_service(tmp, lambda: ([live], [], {"queries": 16, "failed": 0}), lambda: ([], []))
            svc.refresh()
            self.assertNotIn("hf:gone", store.load_seen(), "오래되고 목록에도 없는 기록은 정리한다")
            self.assertIn("hf:live", store.load_summaries())
            self.assertNotIn("hf:gone", store.load_summaries())

    def test_unknown_source_name_warns_instead_of_disabling_everything(self):
        hf = self.items_for("huggingface", 2)
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config()
            cfg.data_dir = Path(tmp)
            cfg.claude_enabled = False
            cfg.unknown_sources = ("hugginface",)
            svc = NewsService(cfg, store=Store(cfg.data_dir),
                              hf_fetch=lambda: (hf, [], {"queries": 16, "failed": 0}),
                              gh_fetch=lambda: ([], []), cv_fetch=lambda: ([], []),
                              readme_enricher=lambda items: 0)
            counts = svc.refresh()
            self.assertEqual(counts["total"], 2, "오타가 있어도 전체 소스로 계속 동작한다")
            self.assertTrue(any(e["key"] == "sources_unknown" for e in svc.status["errors"]))

    def test_corrupt_cache_entries_are_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            Store(Path(tmp)).save_cache({"updated_at": "x", "items": [
                {"key": "hf:ok", "source": "huggingface", "name": "ok", "author": "a", "url": "", "description": None},
                {"key": "hf:bad", "source": "huggingface", "name": None, "tags": [1, 2]},
                {"no_key": True},
            ]})
            svc = make_service(tmp, lambda: ([], []), lambda: ([], []))
            self.assertEqual({it.key for it in svc.items}, {"hf:ok", "hf:bad"})
            self.assertEqual(svc.items[0].description, "", "None 은 빈 문자열로 정리된다")
            svc.refresh()   # 예외 없이 끝나야 한다

    def test_disabled_source_is_not_fetched(self):
        called = []
        hf = self.items_for("huggingface")
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config()
            cfg.data_dir = Path(tmp)
            cfg.claude_enabled = False
            cfg.sources = ("huggingface",)
            svc = NewsService(cfg, store=Store(cfg.data_dir),
                              hf_fetch=lambda: (hf, []),
                              gh_fetch=lambda: (called.append("gh"), ([], []))[1],
                              cv_fetch=lambda: (called.append("cv"), ([], []))[1],
                              readme_enricher=lambda items: 0)
            counts = svc.refresh()
            self.assertEqual(called, [], "꺼둔 소스는 호출하지 않는다")
            self.assertEqual(counts["total"], len(hf))


if __name__ == "__main__":
    unittest.main()
