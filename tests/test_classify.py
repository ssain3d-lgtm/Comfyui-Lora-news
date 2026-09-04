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
            "civitai:1001": "SDXL",
            "civitai:1002": "Illustrious (SDXL 계열)",
            "civitai:1003": "Wan 2.x (비디오)",
            "civitai:1004": "MiniMax H3",
            "hf:someone/krea2-oil-painting-lora": "Krea 2",
        }
        for key, base in expect.items():
            self.assertEqual(self.items[key].base_model, base, key)

    def test_minimax_and_krea2_rules(self):
        def base(name, raw="", desc=""):
            it = LoraItem(key="hf:" + name, source="huggingface", name=name, author="a", url="", base_model_raw=raw, description=desc)
            return classify(it).base_model

        self.assertEqual(base("a/minimax-h3-dance"), "MiniMax H3")
        self.assertEqual(base("a/dance-lora", raw="MiniMax H3"), "MiniMax H3")
        self.assertEqual(base("a/dance-lora", desc="Trained on Hailuo 3 clips"), "MiniMax H3")
        self.assertEqual(base("a/krea2-style"), "Krea 2")
        self.assertEqual(base("a/style", raw="Krea 2.0"), "Krea 2")
        self.assertEqual(base("a/style", raw="krea/krea-2"), "Krea 2")
        # FLUX.1 Krea 는 여전히 FLUX.1
        self.assertEqual(base("a/style", raw="black-forest-labs/FLUX.1-Krea-dev"), "FLUX.1")
        self.assertEqual(base("a/flux-krea-portrait"), "FLUX.1")
        # MiniMax H3 는 비디오 베이스: 카메라 LoRA 는 영상 모션 분류
        self.assertEqual(self.items["civitai:1004"].category, "영상 모션/카메라")
        self.assertIn("카메라 무빙(오빗/돌리/줌)", self.items["civitai:1004"].hints)
        self.assertEqual(self.items["hf:someone/krea2-oil-painting-lora"].category, "스타일/화풍")
        self.assertEqual(self.items["hf:someone/krea2-oil-painting-lora"].trigger_words, ["kr2 oil"])

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
            "gh:someone/awesome-wan-loras": "자료 모음",
            "civitai:1001": "디테일 향상",
            "civitai:1002": "스타일/화풍",
            "civitai:1003": "가속 (저스텝)",
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

    def test_workflows(self):
        expect = {
            "civitai:2001": ("FLUX Kontext", "WF 편집/인페인팅"),
            "civitai:2002": ("Wan 2.x (비디오)", "WF 영상 생성"),
            "gh:comfyanonymous/ComfyUI_examples": ("범용/미상", "WF 모음/템플릿"),
            "gh:someone/comfyui-pulid-consistent-character-workflow": ("FLUX.1", "WF 캐릭터 일관성"),
            "hf:datasets/someone/comfyui-workflows-collection": ("FLUX.1", "WF 모음/템플릿"),
        }
        for key, (base, cat) in expect.items():
            it = self.items[key]
            self.assertEqual(it.kind, "workflow", key)
            self.assertEqual(it.base_model, base, key)
            self.assertEqual(it.category, cat, key)
            self.assertEqual(it.trigger_words, [], "워크플로우는 트리거 추출 안 함")
        wf = self.items["civitai:2002"]
        self.assertIn("이미지→비디오(I2V)", wf.hints)
        self.assertIn("GGUF/저사양(VRAM 절약)", wf.hints)
        self.assertTrue(wf.summary_ko.startswith("Wan 2.x (비디오) 기반 영상 생성 ComfyUI 워크플로우"), wf.summary_ko)
        self.assertIn("JSON 1개", wf.summary_ko)
        generic = self.items["gh:comfyanonymous/ComfyUI_examples"]
        self.assertTrue(generic.summary_ko.startswith("ComfyUI 워크플로우 모음/템플릿"), generic.summary_ko)

    def test_civitai_summary(self):
        it = self.items["civitai:1002"]
        self.assertEqual(it.hints, ["애니메이션 화풍", "지브리풍", "배경/환경"])
        self.assertTrue(it.summary_ko.startswith("Illustrious (SDXL 계열) 기반 스타일/화풍 LoRA · 애니메이션 화풍, 지브리풍"), it.summary_ko)
        self.assertTrue(it.summary_ko.endswith("트리거: ghibli style"), it.summary_ko)

    def test_english_summaries(self):
        self.assertEqual(self.items["hf:someone/sd15-watercolor-dreams"].summary_en, "Style/art style LoRA for SD 1.5 · watercolour look")
        self.assertEqual(self.items["hf:ByteDance/SDXL-Lightning"].summary_en, "Speed-up (few-step) LoRA for SDXL · fast 4-8 step generation")
        pony = self.items["hf:someone/pony-anime-character-akira"].summary_en
        self.assertTrue(pony.startswith("Character LoRA for Pony (SDXL family)"), pony)
        self.assertIn("Trigger: akira_chr, red jacket", pony)
        self.assertTrue(pony.endswith("NSFW tag"), pony)
        wf = self.items["civitai:2002"].summary_en
        self.assertTrue(wf.startswith("Wan 2.x (video) ComfyUI workflow for video generation · image-to-video (I2V)"), wf)
        self.assertIn("1 JSON file", wf)
        generic = self.items["gh:comfyanonymous/ComfyUI_examples"].summary_en
        self.assertTrue(generic.startswith("Collection of ComfyUI workflow templates"), generic)
        gh = self.items["gh:kohya-ss/sd-scripts"].summary_en
        self.assertTrue(gh.startswith("GitHub · Training tool · LoRA training tool"), gh)
        for it in self.items.values():
            self.assertTrue(it.summary_en, it.key)
            self.assertFalse(any("\uac00" <= ch <= "\ud7a3" for ch in it.summary_en), f"영문 요약에 한글 포함: {it.summary_en}")

    def test_claude_summary_not_overwritten(self):
        it = LoraItem(key="hf:x/y", source="huggingface", name="x/y-flux-style", author="x", url="",
                      summary_ko="Claude 요약", summary_en="Claude summary", summary_source="claude")
        classify(it)
        self.assertEqual(it.summary_ko, "Claude 요약")
        self.assertEqual(it.summary_en, "Claude summary")
        self.assertEqual(it.summary_source, "claude")
        # 영문 요약이 비어 있는 옛 캐시는 규칙 기반 영문으로 채움
        it2 = LoraItem(key="hf:x/z", source="huggingface", name="x/z-flux-style", author="x", url="",
                       summary_ko="Claude 요약", summary_source="claude")
        classify(it2)
        self.assertEqual(it2.summary_ko, "Claude 요약")
        self.assertTrue(it2.summary_en.startswith("Style/art style LoRA for FLUX.1"), it2.summary_en)

    def test_word_boundaries(self):
        it = LoraItem(key="hf:a/b", source="huggingface", name="a/influx-startle", author="a", url="",
                      description="a lora about cartoons")
        classify(it)
        self.assertEqual(it.base_model, "미상/기타")  # 'influx' 는 flux 로 잡히면 안 됨


if __name__ == "__main__":
    unittest.main()
