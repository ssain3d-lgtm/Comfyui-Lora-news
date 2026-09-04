import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from lora_news.models import LoraItem
from lora_news.store import Store

try:
    import anthropic  # noqa: F401
    HAS_SDK = True
except ImportError:
    HAS_SDK = False


class StubMessages:
    def __init__(self, reply, stop_reason="end_turn"):
        self.reply = reply
        self.stop_reason = stop_reason
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            stop_details=None,
            content=[SimpleNamespace(type="text", text=json.dumps(self.reply, ensure_ascii=False))],
        )


@unittest.skipUnless(HAS_SDK, "anthropic 패키지 없음")
class SummarizerTests(unittest.TestCase):
    def make(self, tmp, reply, stop_reason="end_turn"):
        from lora_news.summarize import ClaudeSummarizer
        s = ClaudeSummarizer(Store(Path(tmp)), model="claude-opus-5", max_items=10, batch_size=2)
        stub = StubMessages(reply, stop_reason)
        s.client = SimpleNamespace(beta=SimpleNamespace(messages=stub), messages=stub)
        s.available = True
        return s, stub

    def items(self):
        return [
            LoraItem(key="hf:a/b", source="huggingface", name="a/b", author="a", url="", base_model="FLUX.1",
                     category="기타", description="style lora", is_new=True, found_this_run=True),
            LoraItem(key="hf:c/d", source="huggingface", name="c/d", author="c", url="", base_model="SDXL",
                     category="기타", description="character"),
            LoraItem(key="gh:e/f", source="github", name="e/f", author="e", url="", base_model="범용/도구",
                     category="모델/가중치", description="trainer"),
            LoraItem(key="civitai:9", source="civitai", kind="workflow", name="WF", author="w", url="", base_model="FLUX.1",
                     category="WF 이미지 생성", description="basic flux workflow"),
        ]

    def test_summarize_applies_and_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            reply = {"items": [
                {"key": "hf:a/b", "summary_ko": "FLUX용 스타일 LoRA", "summary_en": "Style LoRA for FLUX", "category": "스타일/화풍"},
                {"key": "hf:c/d", "summary_ko": "SDXL 캐릭터 LoRA", "summary_en": "SDXL character LoRA", "category": "캐릭터"},
                {"key": "gh:e/f", "summary_ko": "학습 스크립트", "summary_en": "Training scripts", "category": "학습 도구"},
                {"key": "civitai:9", "summary_ko": "기본 FLUX 워크플로우", "summary_en": "Basic FLUX workflow", "category": "WF 이미지 생성"},
                {"key": "hf:zzz", "summary_ko": "무시됨", "summary_en": "ignored", "category": "기타"},
            ]}
            s, stub = self.make(tmp, reply)
            its = self.items()
            n, errors = s.summarize(its)
            self.assertEqual(errors, [])
            self.assertEqual(n, 4)
            self.assertEqual(len(stub.calls), 2, "batch_size=2 -> 2회 호출")
            payload_items = json.loads(stub.calls[1]["messages"][0]["content"].split("\n\n", 1)[1])["items"]
            wf = next(i for i in payload_items if i["key"] == "civitai:9")
            self.assertEqual(wf["kind"], "workflow")
            self.assertIn("WF 이미지 생성", wf["allowed_categories"])
            self.assertNotIn("캐릭터", wf["allowed_categories"])
            call = stub.calls[0]
            self.assertEqual(call["model"], "claude-opus-5")
            self.assertEqual(call["fallbacks"], "default")
            self.assertIn("server-side-fallback-2026-07-01", call["betas"])
            self.assertEqual(call["output_config"]["format"]["type"], "json_schema")
            self.assertIn("summary_en", call["output_config"]["format"]["schema"]["properties"]["items"]["items"]["required"])
            # 신규 항목이 먼저 요약됨
            first_keys = [i["key"] for i in json.loads(call["messages"][0]["content"].split("\n\n", 1)[1])["items"]]
            self.assertEqual(first_keys[0], "hf:a/b")
            by = {i.key: i for i in its}
            self.assertEqual(by["hf:a/b"].summary_ko, "FLUX용 스타일 LoRA")
            self.assertEqual(by["hf:a/b"].summary_en, "Style LoRA for FLUX")
            self.assertEqual(by["hf:a/b"].category, "스타일/화풍")
            self.assertEqual(by["gh:e/f"].summary_source, "claude")
            cache = json.loads((Path(tmp) / "summaries.json").read_text(encoding="utf-8"))
            self.assertEqual(set(cache), {"hf:a/b", "hf:c/d", "gh:e/f", "civitai:9"})

            # 두 번째 실행: 캐시 적용, 추가 호출 없음
            s2, stub2 = self.make(tmp, {"items": []})
            fresh = self.items()
            self.assertEqual(s2.apply_cached(fresh), 4)
            self.assertEqual(next(i for i in fresh if i.key == "gh:e/f").summary_en, "Training scripts")
            n2, _ = s2.summarize(fresh)
            self.assertEqual(n2, 0)
            self.assertEqual(stub2.calls, [])

    def test_refusal_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, _ = self.make(tmp, {"items": []}, stop_reason="refusal")
            n, errors = s.summarize(self.items())
            self.assertEqual(n, 0)
            self.assertTrue(errors and "거절" in errors[0]["ko"], errors)
            self.assertIn("declined", errors[0]["en"])
            self.assertEqual(errors[0]["key"], "claude_failed")


if __name__ == "__main__":
    unittest.main()
