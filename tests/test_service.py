import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lora_news.config import Config
from lora_news.models import LoraItem
from lora_news.service import NewsService
from lora_news.store import Store

FIXTURES = Path(__file__).parent / "fixtures" / "sample_items.json"


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
            self.assertTrue(any(e["key"] == "kept_cache" and e["ko"].startswith("Hugging Face ") for e in errs))
            self.assertTrue(any("Hugging Face fetch failed" in e["en"] for e in errs))
            self.assertTrue(any(e["key"] == "cv_forbidden" for e in errs))
            self.assertEqual(sum(1 for e in errs if e["key"] == "kept_cache"), 2)
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


if __name__ == "__main__":
    unittest.main()
