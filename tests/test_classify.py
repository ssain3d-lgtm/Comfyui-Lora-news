import json
import unittest
from pathlib import Path

from lora_news.classify import classify, extract_trigger_words
from lora_news.models import LoraItem

FIXTURES = Path(__file__).parent / "fixtures" / "sample_items.json"


def load():
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return {d["key"]: classify(LoraItem.from_dict(d)) for d in data}


class ClassifyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = load()

    def test_base_models(self):
        expect = {
            "hf:XLabs-AI/flux-RealismLora": "FLUX.1",
            "hf:ByteDance/SDXL-Lightning": "SDXL",
            "hf:Kijai/WanVideo_comfy": "Wan 2.x (비디오)",
            "hf:someone/pony-anime-character-akira": "Pony (SDXL 계열)",
            "hf:fal/flux-kontext-lora-relight": "FLUX Kontext",
            "hf:someone/illustrious-detailer-xl": "Illustrious (SDXL 계열)",
            "hf:someone/qwen-image-pixelart": "Qwen-Image",
            "hf:someone/hunyuanvideo-orbit-camera": "HunyuanVideo",
            "hf:someone/sd15-watercolor-dreams": "SD 1.5",
            "gh:ltdrdata/ComfyUI-Manager": "범용/도구",
        }
        for key, base in expect.items():
            self.assertEqual(self.items[key].base_model, base, key)

    def test_categories(self):
        expect = {
            "hf:XLabs-AI/flux-RealismLora": "실사/포토",
            "hf:ByteDance/SDXL-Lightning": "가속 (저스텝)",
            "hf:Kijai/WanVideo_comfy": "가속 (저스텝)",
            "hf:alvdansen/frosting_lane_flux": "스타일/화풍",
            "hf:someone/pony-anime-character-akira": "캐릭터",
            "hf:fal/flux-kontext-lora-relight": "이미지 편집",
            "hf:someone/illustrious-detailer-xl": "디테일 향상",
            "hf:someone/qwen-image-pixelart": "스타일/화풍",
            "hf:someone/hunyuanvideo-orbit-camera": "영상 모션/카메라",
            "hf:someone/sd15-watercolor-dreams": "스타일/화풍",
            "gh:kohya-ss/sd-scripts": "학습 도구",
            "gh:someone/ComfyUI-Lora-Manager": "로더/관리",
            "gh:someone/lora-merge-tool": "병합/변환",
            "gh:someone/awesome-wan-loras": "워크플로우/모음",
        }
        for key, cat in expect.items():
            self.assertEqual(self.items[key].category, cat, key)

    def test_trigger_words_from_description(self):
        self.assertEqual(self.items["hf:alvdansen/frosting_lane_flux"].trigger_words, ["frstingln illustration"])
        self.assertEqual(self.items["hf:someone/pony-anime-character-akira"].trigger_words, ["akira_chr", "red jacket"])
        self.assertEqual(self.items["hf:someone/qwen-image-pixelart"].trigger_words, ["pxl style"])

    def test_trigger_parser_edge_cases(self):
        self.assertEqual(extract_trigger_words("Trigger words: none"), [])
        self.assertEqual(extract_trigger_words("Trigger Words\n`ohwx man`, `sks`"), ["ohwx man", "sks"])
        self.assertEqual(extract_trigger_words("no mention here"), [])
        self.assertEqual(extract_trigger_words("fetch metadata/trigger words from Civitai"), [])
        self.assertEqual(extract_trigger_words("instance_prompt: TOK person"), ["TOK person"])
        self.assertEqual(extract_trigger_words('Use the trigger word "ghibli style" at the start. Then more.'), ["ghibli style"])
        self.assertEqual(extract_trigger_words("Trigger words: xyz (weight 0.8) - optional"), ["xyz"])

    def test_summary_and_flags(self):
        it = self.items["hf:someone/pony-anime-character-akira"]
        self.assertTrue(it.nsfw)
        self.assertIn("Pony (SDXL 계열) 기반 캐릭터 LoRA", it.summary_ko)
        self.assertIn("트리거: akira_chr", it.summary_ko)
        self.assertIn("성인(NSFW)", it.summary_ko)
        self.assertEqual(it.summary_source, "rule")

        lite = self.items["hf:ByteDance/SDXL-Lightning"]
        self.assertIn("적은 스텝(4~8)으로 빠르게 생성", lite.hints)

        gh = self.items["gh:kohya-ss/sd-scripts"]
        self.assertTrue(gh.summary_ko.startswith("GitHub · 학습 도구"))
        self.assertEqual(self.items["gh:someone/ComfyUI-Lora-Manager"].trigger_words, [], "GitHub 저장소는 트리거 추출 안 함")

    def test_claude_summary_not_overwritten(self):
        it = LoraItem(key="hf:x/y", source="huggingface", name="x/y-flux-style", author="x", url="",
                      summary_ko="Claude 요약", summary_source="claude")
        classify(it)
        self.assertEqual(it.summary_ko, "Claude 요약")
        self.assertEqual(it.summary_source, "claude")

    def test_word_boundaries(self):
        it = LoraItem(key="hf:a/b", source="huggingface", name="a/influx-startle", author="a", url="",
                      description="a lora about cartoons")
        classify(it)
        self.assertEqual(it.base_model, "미상/기타")  # 'influx' 는 flux 로 잡히면 안 됨


if __name__ == "__main__":
    unittest.main()
