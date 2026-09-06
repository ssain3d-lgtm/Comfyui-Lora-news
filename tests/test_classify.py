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
            "hf:Kijai/WanVideo_comfy": "Wan (비디오)",
            "hf:someone/pony-anime-character-akira": "Pony (SDXL 계열)",
            "hf:fal/flux-kontext-lora-relight": "FLUX Kontext",
            "hf:someone/illustrious-detailer-xl": "Illustrious (SDXL 계열)",
            "hf:someone/qwen-image-pixelart": "Qwen-Image",
            "hf:someone/hunyuanvideo-orbit-camera": "HunyuanVideo",
            "hf:someone/sd15-watercolor-dreams": "SD 1.5",
            "gh:ltdrdata/ComfyUI-Manager": "범용/도구",
            "civitai:1001": "SDXL",
            "civitai:1002": "Illustrious (SDXL 계열)",
            "civitai:1003": "Wan (비디오)",
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
        self.assertTrue(gh.summary_ko.startswith("GitHub · 학습 도구 · Training scripts"), gh.summary_ko)
        self.assertEqual(self.items["gh:someone/ComfyUI-Lora-Manager"].trigger_words, [], "GitHub 저장소는 트리거 추출 안 함")

    def test_workflows(self):
        expect = {
            "civitai:2001": ("FLUX Kontext", "WF 편집/인페인팅"),
            "civitai:2002": ("Wan (비디오)", "WF 영상 생성"),
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
        self.assertNotIn("카메라 무빙(오빗/돌리/줌)", self.items["hf:someone/illustrious-detailer-xl"].hints,
                         "정지 이미지 LoRA 에는 영상 힌트가 붙지 않는다")
        self.assertTrue(wf.summary_ko.startswith("Wan (비디오) 기반 영상 생성 ComfyUI 워크플로우"), wf.summary_ko)
        self.assertIn("JSON 1개", wf.summary_ko)
        generic = self.items["gh:comfyanonymous/ComfyUI_examples"]
        self.assertTrue(generic.summary_ko.startswith("ComfyUI 워크플로우 모음/템플릿"), generic.summary_ko)

    def test_civitai_summary(self):
        it = self.items["civitai:1002"]
        self.assertEqual(it.hints, ["지브리풍", "애니메이션 화풍", "배경/환경"], "이름에 있는 지브리가 먼저")
        self.assertTrue(it.summary_ko.startswith("Illustrious (SDXL 계열) 기반 스타일/화풍 LoRA · 지브리풍, 애니메이션 화풍"), it.summary_ko)
        self.assertTrue(it.summary_ko.endswith("트리거: ghibli style"), it.summary_ko)

    def test_english_summaries(self):
        self.assertEqual(self.items["hf:someone/sd15-watercolor-dreams"].summary_en, "Style/art style LoRA for SD 1.5 · watercolour look")
        self.assertEqual(self.items["hf:ByteDance/SDXL-Lightning"].summary_en, "Speed-up (few-step) LoRA for SDXL · fast 4-8 step generation")
        pony = self.items["hf:someone/pony-anime-character-akira"].summary_en
        self.assertTrue(pony.startswith("Character LoRA for Pony (SDXL family)"), pony)
        self.assertIn("Trigger: akira_chr, red jacket", pony)
        self.assertTrue(pony.endswith("NSFW tag"), pony)
        wf = self.items["civitai:2002"].summary_en
        self.assertTrue(wf.startswith("Wan (video) ComfyUI workflow for video generation ·"), wf)
        self.assertIn("image-to-video (I2V)", wf)
        self.assertIn("1 JSON file", wf)
        generic = self.items["gh:comfyanonymous/ComfyUI_examples"].summary_en
        self.assertTrue(generic.startswith("Collection of ComfyUI workflow templates"), generic)
        gh = self.items["gh:kohya-ss/sd-scripts"].summary_en
        self.assertTrue(gh.startswith("GitHub · Training tool · Training scripts"), gh)
        self.assertNotIn("LoRA training tool", gh, "설명이 있으면 분류를 되풀이하지 않는다")
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


class RegressionTests(unittest.TestCase):
    """리뷰에서 실제로 재현된 오분류들. 다시 생기면 여기서 잡힌다."""

    def make(self, name, source="huggingface", kind="lora", raw="", desc="", tags=None, pipeline=""):
        return classify(LoraItem(key=f"x:{name}", source=source, kind=kind, name=name, author="a", url="",
                                 base_model_raw=raw, description=desc, tags=tags or [], pipeline=pipeline))

    def test_github_names_are_not_all_model_weights(self):
        expect = {
            "a/ComfyUI-Lora-Manager": "로더/관리",
            "a/comfyui-lora-tag-loader": "로더/관리",
            "a/comfyui-lora-trainer": "학습 도구",
            "a/flux-lora-training": "학습 도구",
            "a/kohya-lora-gui": "학습 도구",
            "a/awesome-comfyui-loras": "자료 모음",
            "a/lora-merge-tool": "병합/변환",
            "a/comfyui-impact-pack-nodes": "커스텀 노드",
        }
        for name, category in expect.items():
            self.assertEqual(self.make(name, source="github").category, category, name)

    def test_unclassifiable_repo_is_other_not_a_confident_guess(self):
        it = self.make("comfyanonymous/ComfyUI", source="github",
                       desc="The most powerful and modular diffusion model GUI and backend.")
        self.assertEqual(it.category, "기타")
        self.assertNotIn("가중치", it.summary_ko)

    def test_tags_outrank_a_passing_mention_in_the_description(self):
        cases = [
            (dict(name="a/motion", tags=["wan", "video"],
                  desc="Wan 2.2 motion LoRA for I2V. A FLUX version is also available."), "Wan (비디오)"),
            (dict(name="a/detail", tags=["sdxl"],
                  desc="SDXL detail LoRA. Not compatible with Qwen-Image or Hunyuan."), "SDXL"),
            (dict(name="a/camera", tags=["hunyuanvideo"],
                  desc="Camera LoRA. Inspired by my FLUX Kontext edit LoRA."), "HunyuanVideo"),
        ]
        for kwargs, base in cases:
            self.assertEqual(self.make(**kwargs).base_model, base, kwargs["name"])

    def test_greedy_base_model_keywords_need_a_qualifier(self):
        expect = [
            (dict(name="Hailuo 02 Director Camera Motion LoRA", raw="Hailuo 02"), "MiniMax Hailuo (비디오)"),
            (dict(name="MiniMax Hailuo 2.3 orbit lora", raw="Hailuo 2.3"), "MiniMax Hailuo (비디오)"),
            (dict(name="Hailuo 3 slow orbit", raw="MiniMax H3"), "MiniMax H3"),
            (dict(name="Pony Diffusion V7 - Sharp Lineart", raw="Pony V7"), "Pony V7 (AuraFlow 계열)"),
            (dict(name="My Little Pony style LoRA"), "미상/기타"),
            (dict(name="a/qwen-vl-captioner-for-lora-training", source="github"), "범용/도구"),
            (dict(name="a/portrait", raw="black-forest-labs/FLUX.1-Krea-dev"), "FLUX.1"),
            (dict(name="a/krea2-oil-painting-lora", raw="krea/krea-2"), "Krea 2"),
            (dict(name="tencent/Hunyuan3D-2.1 texture lora"), "Hunyuan3D"),
            (dict(name="Seedream 4.0 product photo LoRA"), "Seedream"),
            (dict(name="Kling 2.5 camera control workflow", kind="workflow"), "Kling (비디오)"),
        ]
        for kwargs, base in expect:
            self.assertEqual(self.make(**kwargs).base_model, base, kwargs["name"])

    def test_chroma_key_is_not_the_chroma_model(self):
        it = self.make("Chroma Key Green Screen Removal Workflow", kind="workflow")
        self.assertNotEqual(it.base_model, "Chroma")
        self.assertEqual(it.category, "WF 편집/인페인팅")

    def test_the_word_model_does_not_make_it_a_character_lora(self):
        for desc in ["This model was trained on 40 images.",
                     "A LoRA model for ComfyUI.",
                     "Fine-tuned model weights, use with the standard workflow."]:
            self.assertEqual(self.make("a/mystery-lora", raw="FLUX.1", desc=desc).category, "기타", desc)

    def test_negated_trigger_phrases_are_dropped(self):
        for text in ["Trigger words: none needed, the style is always on.",
                     "Trigger word: not required for this LoRA.",
                     "Trigger words: You don't need any trigger word.",
                     "Trigger: no trigger words are necessary"]:
            self.assertEqual(extract_trigger_words(text), [], text)
        self.assertEqual(extract_trigger_words("Trigger words: akira_chr, red jacket"), ["akira_chr", "red jacket"])

    def test_hints_are_scored_and_context_gated(self):
        # 'Run FLUX...' 의 run 이 춤/동작으로 잡히면 안 된다
        self.assertEqual(self.make("a/nunchaku-svdquant-flux-loader", source="github",
                                   desc="Run FLUX in int4 with SVDQuant.").hints, [])
        # 정지 이미지 LoRA 에 카메라 무빙 힌트가 붙으면 안 된다
        self.assertNotIn("카메라 무빙(오빗/돌리/줌)", self.make("Zoom Lens Bokeh Portrait", raw="SDXL", tags=["photo"]).hints)
        self.assertNotIn("루프 애니메이션", self.make("Loop Knit Sweater Texture", raw="SDXL").hints)
        # 이름에 있는 신호가 설명보다 앞선다
        hints = self.make("a/watercolor-dreams-lora", raw="SD 1.5", tags=["watercolor", "style"],
                          desc="Adds detail to portrait shots.").hints
        self.assertEqual(hints[0], "수채화 느낌")

    def test_github_base_model_ignores_the_description(self):
        it = self.make("kohya-ss/sd-scripts", source="github",
                       desc="Training scripts for Stable Diffusion, SDXL, FLUX.1 and more.")
        self.assertEqual(it.base_model, "범용/도구", "범용 도구가 특정 모델 라벨을 달면 안 된다")


if __name__ == "__main__":
    unittest.main()
