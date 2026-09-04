"""규칙 기반 분류: 베이스 모델 / 용도 분류 / 한글 힌트 / 트리거 워드 / 한글 한 줄 요약.

LoRA(HF·Civitai), LoRA 관련 GitHub 저장소, ComfyUI 워크플로우(세 소스 모두) 를 다룬다.
"""
from __future__ import annotations

import re
from typing import Iterable

from .models import LoraItem

# ---------------------------------------------------------------------------
# 키워드 매칭 도우미
# ---------------------------------------------------------------------------

_PATTERN_CACHE: dict[str, re.Pattern] = {}


def _pattern(keyword: str) -> re.Pattern:
    """단어 경계를 고려한 패턴. 'flux'는 'flux.1-dev'에는 맞고 'influx'에는 안 맞음.
    끝에 s/es 복수형은 허용 (style -> styles)."""
    pat = _PATTERN_CACHE.get(keyword)
    if pat is None:
        kw = keyword.lower()
        lead = r"(?<![a-z0-9])" if kw[0].isalnum() else ""
        trail = r"(?:s|es)?(?![a-z0-9])" if kw[-1].isalnum() else ""
        pat = re.compile(lead + re.escape(kw) + trail)
        _PATTERN_CACHE[keyword] = pat
    return pat


def _count(text: str, keywords: Iterable[str]) -> int:
    return sum(1 for k in keywords if _pattern(k).search(text))


def _any(text: str, keywords: Iterable[str]) -> bool:
    return any(_pattern(k).search(text) for k in keywords)


# ---------------------------------------------------------------------------
# 베이스 모델 (순서 = 우선순위)
# ---------------------------------------------------------------------------

BASE_MODEL_RULES: list[tuple[str, list[str]]] = [
    ("FLUX Kontext", ["kontext"]),
    ("FLUX.2", ["flux.2", "flux2", "flux-2", "flux_2"]),
    ("FLUX.1", ["flux", "flux.1", "flux1", "flux-dev", "flux-schnell", "flux.1-dev", "flux.1-schnell", "flux-fill", "flux-krea"]),
    ("Wan 2.x (비디오)", ["wan2", "wan2.1", "wan2.2", "wan-2", "wan-2.1", "wan-2.2", "wan_2", "wan", "wanx", "wan-ai", "wanvideo", "wan-video", "wan video"]),
    ("HunyuanVideo", ["hunyuanvideo", "hunyuan-video", "hunyuan_video", "hunyuan video"]),
    ("Hunyuan (이미지)", ["hunyuanimage", "hunyuan-image", "hunyuan image", "hunyuandit", "hunyuan"]),
    ("LTX-Video", ["ltx", "ltx-video", "ltxv", "ltx2", "ltx-2", "ltx video"]),
    ("CogVideoX", ["cogvideo", "cogvideox"]),
    ("Mochi", ["mochi"]),
    ("AnimateDiff", ["animatediff"]),
    ("Stable Video Diffusion", ["stable-video-diffusion", "stable video diffusion", "svd"]),
    ("Qwen-Image", ["qwen-image", "qwen_image", "qwenimage", "qwen-image-edit", "qwen image", "qwen"]),
    ("Z-Image", ["z-image", "z_image", "zimage", "z image"]),
    ("Chroma", ["chroma"]),
    ("HiDream", ["hidream"]),
    ("Lumina", ["lumina", "lumina2"]),
    ("Kolors", ["kolors"]),
    ("AuraFlow", ["auraflow"]),
    ("PixArt", ["pixart"]),
    ("Stable Cascade", ["stable-cascade", "stablecascade", "stable cascade"]),
    ("Pony (SDXL 계열)", ["pony", "ponyxl", "pony-xl", "ponydiffusion"]),
    ("Illustrious (SDXL 계열)", ["illustrious", "illustriousxl", "noobai", "noob-ai", "noobai-xl"]),
    ("Animagine (SDXL 계열)", ["animagine"]),
    ("SD3 / 3.5", ["stable-diffusion-3", "stable-diffusion-3.5", "sd3", "sd3.5", "sd-3", "sd3-medium", "sd 3.5", "sd 3"]),
    ("SDXL", ["sdxl", "stable-diffusion-xl", "sd-xl", "xl-base", "juggernaut", "realvis", "sdxl-turbo", "sdxl-lightning", "sdxl 1.0"]),
    ("SD 2.x", ["stable-diffusion-2", "stable-diffusion-2-1", "sd2", "sd2.1", "sd-2", "sd 2.1"]),
    ("SD 1.5", ["stable-diffusion-v1-5", "stable-diffusion-v1", "sd1.5", "sd-1.5", "sd15", "sd-1-5", "runwayml", "dreamshaper", "v1-5", "sd1", "sd 1.5"]),
]

VIDEO_BASES = {"Wan 2.x (비디오)", "HunyuanVideo", "LTX-Video", "CogVideoX", "Mochi", "AnimateDiff", "Stable Video Diffusion"}


def detect_base_model(item: LoraItem) -> str:
    raw = (item.base_model_raw or "").lower()
    name = (item.name or "").lower()
    rest = " ".join([" ".join(item.tags or []), item.description or ""]).lower()
    for text in (raw, name, rest):
        if not text:
            continue
        for label, keywords in BASE_MODEL_RULES:
            if _any(text, keywords):
                return label
    if "video" in (item.pipeline or ""):
        return "비디오 모델 (미상)"
    return "미상/기타"


# ---------------------------------------------------------------------------
# 용도 분류
# ---------------------------------------------------------------------------

LORA_CATEGORIES = ["가속 (저스텝)", "이미지 편집", "디테일 향상", "영상 모션/카메라", "캐릭터", "실사/포토", "의상/포즈/컨셉", "스타일/화풍", "기타"]
GH_CATEGORIES = ["학습 도구", "커스텀 노드", "로더/관리", "병합/변환", "자료 모음", "모델/가중치"]
WF_CATEGORIES = ["WF 이미지 생성", "WF 영상 생성", "WF 편집/인페인팅", "WF 업스케일/보정", "WF 컨트롤넷/포즈", "WF 캐릭터 일관성", "WF 학습/도구", "WF 모음/템플릿"]
CATEGORIES = LORA_CATEGORIES + GH_CATEGORIES + WF_CATEGORIES

HF_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("가속 (저스텝)", ["lightning", "lcm", "turbo", "hyper-sd", "hyper sd", "hypersd", "hyper", "dmd", "dmd2", "distill", "distilled",
                    "causvid", "self-forcing", "self forcing", "accvid", "fusionx", "4-step", "4 step", "4step", "8-step", "8 step",
                    "8step", "few-step", "fewstep", "fast", "speed", "acceleration", "pcm", "tcd", "lightx2v"]),
    ("이미지 편집", ["kontext", "edit", "editing", "inpaint", "inpainting", "outpaint", "remove", "removal", "relight", "relighting",
                  "try-on", "tryon", "try on", "virtual try", "outfit swap", "face swap", "restore", "restoration", "colorize",
                  "colorization", "upscale", "upscaler", "super-resolution", "super resolution", "instruct", "transform"]),
    ("디테일 향상", ["detail", "detailer", "add-detail", "add detail", "enhancer", "enhance", "sharp", "sharpen", "skin texture",
                  "hands fix", "hand fix", "hand", "eye", "quality", "hd", "high-res", "realism boost", "texture", "improver", "fix"]),
    ("영상 모션/카메라", ["motion", "camera", "i2v", "t2v", "orbit", "dolly", "zoom", "rotate", "rotation", "pan", "tilt", "walk",
                      "dance", "dancing", "physics", "explosion", "transition", "loop", "animation", "animate", "movement", "fly",
                      "drone", "fpv", "timelapse"]),
    ("캐릭터", ["character", "chara", "characters", "person", "celebrity", "likeness", "girl", "boy", "woman", "man", "waifu", "idol",
              "actress", "actor", "face", "cosplay", "persona", "identity", "portrait", "selfie", "influencer", "model", "vtuber",
              "mascot", "hero", "heroine", "protagonist", "figure"]),
    ("실사/포토", ["realistic", "photorealistic", "photo", "photograph", "photography", "photographic", "realism", "amateur", "dslr",
                "raw photo", "hyperreal", "hyperrealistic", "lifelike", "real", "iphone", "candid", "35mm", "analog", "polaroid"]),
    ("의상/포즈/컨셉", ["outfit", "clothing", "clothes", "dress", "costume", "uniform", "lingerie", "swimsuit", "bikini", "armor",
                     "pose", "posing", "concept", "expression", "hairstyle", "hair", "background", "environment", "scene",
                     "architecture", "interior", "building", "vehicle", "car", "weapon", "props", "product", "logo", "tattoo",
                     "font", "typography", "text", "sticker", "emoji", "icon", "pattern", "fabric", "jewelry", "food", "landscape",
                     "nature", "animal", "creature", "monster", "mecha", "robot"]),
    ("스타일/화풍", ["style", "aesthetic", "painting", "painterly", "watercolor", "oil painting", "oil", "pixel", "pixel art", "ghibli",
                  "anime", "illustration", "illustrated", "sketch", "lineart", "line art", "manga", "comic", "cartoon", "3d", "render",
                  "clay", "claymation", "pixar", "disney", "cinematic", "film", "vintage", "retro", "cyberpunk", "fantasy", "art",
                  "artstyle", "art style", "flat", "vector", "minimal", "minimalist", "ink", "pastel", "neon", "graffiti", "chibi",
                  "lofi", "gothic", "steampunk", "surreal", "abstract", "impressionism", "impressionist", "ukiyo", "gouache",
                  "crayon", "pencil", "charcoal", "poster", "cover", "aesthetics", "vibe", "look", "filter", "toon", "papercut",
                  "origami", "lego", "voxel", "isometric", "low poly", "lowpoly", "stained glass", "mosaic", "embroidery", "knit"]),
]

GH_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("학습 도구", ["train", "trainer", "training", "kohya", "kohya_ss", "kohya-ss", "fine-tune", "fine-tuning", "finetune", "finetuning",
                "dreambooth", "ai-toolkit", "diffusion-pipe", "musubi", "onetrainer", "simpletuner", "dataset", "captioning", "caption",
                "tagger", "trainable", "lora-scripts"]),
    ("커스텀 노드", ["node", "nodes", "custom node", "custom nodes", "custom_node", "custom_nodes", "comfyui-", "comfy-", "extension",
                  "plugin", "comfyui node"]),
    ("병합/변환", ["merge", "merger", "merging", "convert", "converter", "extract", "extraction", "resize", "quantize", "quantization",
                "gguf", "format", "conversion", "diff"]),
    ("로더/관리", ["loader", "manager", "management", "organizer", "organize", "browser", "gallery", "civitai", "download", "downloader",
                "metadata", "info", "preview", "sidebar", "library", "catalog", "viewer", "search"]),
    ("자료 모음", ["awesome", "collection", "list", "curated", "examples", "example", "guide", "tutorial", "notebook", "colab", "resources"]),
    ("모델/가중치", ["weights", "checkpoint", "release", "model card", "safetensors", "lora for", "-lora", "lora-", "pretrained"]),
]

WF_CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("WF 영상 생성", ["video", "wan", "wan2", "wan2.1", "wan2.2", "hunyuanvideo", "hunyuan video", "ltx", "ltxv", "animatediff", "i2v",
                   "t2v", "animate", "animation", "svd", "cogvideo", "mochi", "framepack", "img2vid", "image-to-video", "text-to-video",
                   "vace", "motion", "frame interpolation", "rife"]),
    ("WF 편집/인페인팅", ["inpaint", "inpainting", "outpaint", "outpainting", "edit", "editing", "kontext", "qwen-image-edit", "qwen image edit",
                      "remove", "replace", "relight", "try-on", "tryon", "swap", "background removal", "mask", "masking", "fill", "eraser",
                      "object removal", "img2img", "image-to-image"]),
    ("WF 업스케일/보정", ["upscale", "upscaler", "upscaling", "hires", "hires fix", "hi-res", "detailer", "face detailer", "facedetailer",
                       "restore", "restoration", "enhance", "enhancer", "supir", "tile", "tiled", "refiner", "refine", "sharpen",
                       "ultimate sd upscale", "denoise"]),
    ("WF 컨트롤넷/포즈", ["controlnet", "control net", "openpose", "pose", "depth", "canny", "lineart", "scribble", "ipadapter",
                       "ip-adapter", "ip adapter", "reference", "redux", "union", "sketch to image", "style transfer"]),
    ("WF 캐릭터 일관성", ["character", "consistent", "consistency", "pulid", "instantid", "instant id", "faceid", "face id", "reactor",
                       "portrait", "identity", "face swap", "photomaker", "same character", "character sheet"]),
    ("WF 학습/도구", ["train", "training", "lora training", "dataset", "caption", "captioning", "tool", "utility", "batch", "automation",
                    "api", "pipeline", "script", "benchmark", "test", "compare", "xy plot", "grid"]),
    ("WF 모음/템플릿", ["collection", "awesome", "templates", "template", "examples", "example", "pack", "library", "list", "workflows",
                     "starter", "beginner", "tutorial", "guide", "curated", "all-in-one", "all in one"]),
    ("WF 이미지 생성", ["txt2img", "text-to-image", "text to image", "t2i", "generation", "generate", "flux", "sdxl", "sd1.5", "sd 1.5",
                     "basic", "simple", "illustrious", "pony", "chroma", "qwen", "hidream", "z-image", "portrait", "anime", "realistic"]),
]


def _score_rules(item: LoraItem, rules: list[tuple[str, list[str]]]) -> list[tuple[int, str]]:
    name = (item.name or "").lower().replace("_", " ").replace("-", " ") + " " + (item.name or "").lower()
    tags = " ".join(item.tags or []).lower()
    desc = (item.description or "").lower()
    scored = []
    for idx, (label, keywords) in enumerate(rules):
        score = 3 * _count(name, keywords) + 2 * _count(tags, keywords) + _count(desc, keywords)
        scored.append((score, label, idx))
    scored.sort(key=lambda t: (-t[0], t[2]))
    return [(s, l) for s, l, _ in scored]


def detect_category(item: LoraItem) -> str:
    if item.kind == "workflow":
        scored = _score_rules(item, WF_CATEGORY_RULES)
        if scored and scored[0][0] > 0:
            return scored[0][1]
        return "WF 영상 생성" if item.base_model in VIDEO_BASES else "WF 이미지 생성"

    if item.source == "github":
        scored = _score_rules(item, GH_CATEGORY_RULES)
        return scored[0][1] if scored and scored[0][0] > 0 else "모델/가중치"

    video = item.base_model in VIDEO_BASES or "video" in (item.pipeline or "")
    rules = HF_CATEGORY_RULES if video else [r for r in HF_CATEGORY_RULES if r[0] != "영상 모션/카메라"]
    scored = _score_rules(item, rules)
    if scored and scored[0][0] > 0:
        return scored[0][1]
    return "영상 모션/카메라" if video else "기타"


# ---------------------------------------------------------------------------
# 한글 힌트 (키워드 -> 짧은 한글 설명). 순서 = 우선순위
# ---------------------------------------------------------------------------

HINT_RULES: list[tuple[str, list[str]]] = [
    ("적은 스텝(4~8)으로 빠르게 생성", ["lightning", "lcm", "turbo", "hyper", "dmd", "distill", "distilled", "4-step", "8-step", "few-step", "causvid", "self-forcing", "lightx2v", "accvid"]),
    ("이미지 편집·변형 지시용", ["kontext", "edit", "editing", "instruct"]),
    ("가상 피팅/의상 교체", ["try-on", "tryon", "virtual try", "outfit swap"]),
    ("배경/객체 제거", ["remove", "removal"]),
    ("조명 재설정", ["relight", "relighting"]),
    ("손상 복원/흑백 채색", ["restore", "restoration", "colorize", "colorization"]),
    ("업스케일/화질 개선", ["upscale", "upscaler", "super-resolution"]),
    ("디테일·선명도 향상", ["detail", "detailer", "add-detail", "enhancer", "sharpen", "sharp"]),
    ("손/눈 보정", ["hands fix", "hand fix", "eye fix", "better hands", "hand"]),
    ("피부 질감 강화", ["skin texture", "skin"]),
    ("사실적인 실사 표현", ["realistic", "photorealistic", "realism", "hyperreal", "lifelike"]),
    ("아마추어/스냅 사진 느낌", ["amateur", "candid", "iphone", "selfie", "snapshot"]),
    ("필름/아날로그 사진 감성", ["film", "analog", "35mm", "polaroid", "kodak", "fuji"]),
    ("영화 같은 색감·조명", ["cinematic", "movie"]),
    ("인물 초상/얼굴", ["portrait", "face", "headshot"]),
    ("특정 인물/캐릭터 재현", ["character", "chara", "likeness", "celebrity", "persona", "identity", "vtuber"]),
    ("애니메이션 화풍", ["anime", "animation style", "2d"]),
    ("지브리풍", ["ghibli"]),
    ("만화/코믹 스타일", ["manga", "comic", "webtoon"]),
    ("카툰/툰 렌더", ["cartoon", "toon", "pixar", "disney"]),
    ("수채화 느낌", ["watercolor", "watercolour"]),
    ("유화 느낌", ["oil painting", "oil"]),
    ("스케치·선화", ["sketch", "lineart", "line art", "pencil", "charcoal", "ink"]),
    ("픽셀아트", ["pixel", "pixel art", "8-bit", "16-bit"]),
    ("3D 렌더 느낌", ["3d", "render", "blender", "octane", "unreal", "clay", "claymation"]),
    ("치비 스타일", ["chibi"]),
    ("플랫/벡터 일러스트", ["flat", "vector", "minimal", "minimalist"]),
    ("빈티지·레트로", ["vintage", "retro", "80s", "90s", "y2k"]),
    ("사이버펑크/네온", ["cyberpunk", "neon", "synthwave"]),
    ("판타지/중세", ["fantasy", "medieval", "dnd", "rpg"]),
    ("고딕/다크", ["gothic", "dark", "horror"]),
    ("파스텔톤", ["pastel"]),
    ("스팀펑크", ["steampunk"]),
    ("초현실/추상", ["surreal", "abstract"]),
    ("아이소메트릭/로우폴리", ["isometric", "low poly", "lowpoly", "voxel"]),
    ("레고/블록 스타일", ["lego"]),
    ("종이공예/오리가미", ["papercut", "paper cut", "origami"]),
    ("자수/니트 질감", ["embroidery", "knit", "crochet"]),
    ("의상/코스튬", ["outfit", "clothing", "clothes", "dress", "costume", "uniform", "cosplay"]),
    ("헤어스타일", ["hairstyle", "hair"]),
    ("포즈/자세", ["pose", "posing"]),
    ("표정", ["expression", "expressions"]),
    ("배경/환경", ["background", "environment", "scenery", "scene"]),
    ("건축/인테리어", ["architecture", "interior", "building", "room"]),
    ("풍경", ["landscape"]),
    ("자동차/탈것", ["car", "vehicle", "motorcycle"]),
    ("로봇/메카", ["mecha", "robot"]),
    ("몬스터/크리처", ["monster", "creature"]),
    ("동물", ["animal", "cat", "dog"]),
    ("음식 사진", ["food"]),
    ("제품 사진", ["product", "packaging"]),
    ("로고 디자인", ["logo"]),
    ("타투 디자인", ["tattoo"]),
    ("글자/타이포그래피", ["typography", "font", "text rendering", "lettering"]),
    ("스티커/아이콘", ["sticker", "icon", "emoji"]),
    ("패턴/텍스처", ["pattern", "texture", "fabric", "seamless"]),
    ("포스터/커버 아트", ["poster", "cover art", "album cover"]),
    ("카메라 무빙(오빗/돌리/줌)", ["orbit", "dolly", "zoom", "camera", "crane", "pan"]),
    ("이미지→비디오(I2V)", ["i2v", "image-to-video", "image to video"]),
    ("텍스트→비디오(T2V)", ["t2v", "text-to-video", "text to video"]),
    ("춤/동작", ["dance", "dancing", "walk", "walking", "run", "running"]),
    ("폭발/파괴 효과", ["explosion", "destroy", "destruction"]),
    ("물리/변형 효과", ["physics", "melt", "inflate", "deflate", "squish"]),
    ("타임랩스/드론 샷", ["timelapse", "drone", "fpv", "aerial"]),
    ("루프 애니메이션", ["loop", "looping"]),
    ("성인(NSFW)", ["nsfw", "explicit", "not-for-all-audiences", "hentai", "nude"]),
]

# 워크플로우 전용 힌트 (먼저 적용)
WF_HINT_RULES: list[tuple[str, list[str]]] = [
    ("이미지→비디오(I2V)", ["i2v", "image-to-video", "image to video", "img2vid"]),
    ("텍스트→비디오(T2V)", ["t2v", "text-to-video", "text to video"]),
    ("ControlNet 사용", ["controlnet", "control net", "openpose", "canny", "depth"]),
    ("IPAdapter/Redux 스타일 참조", ["ipadapter", "ip-adapter", "ip adapter", "redux", "style transfer"]),
    ("얼굴 일관성(PuLID/InstantID/FaceID)", ["pulid", "instantid", "instant id", "faceid", "face id", "photomaker"]),
    ("얼굴 교체(ReActor)", ["reactor", "face swap", "faceswap"]),
    ("인페인팅/아웃페인팅", ["inpaint", "inpainting", "outpaint", "outpainting", "fill"]),
    ("배경 제거/교체", ["background removal", "remove background", "rembg", "background replace"]),
    ("업스케일 포함", ["upscale", "upscaler", "upscaling", "hires", "supir", "ultimate sd upscale"]),
    ("얼굴/디테일 보정(Detailer)", ["detailer", "face detailer", "facedetailer", "adetailer"]),
    ("프레임 보간", ["frame interpolation", "rife", "interpolation"]),
    ("LoRA 스택/여러 LoRA 사용", ["lora stack", "multiple lora", "lora loader", "power lora"]),
    ("GGUF/저사양(VRAM 절약)", ["gguf", "low vram", "lowvram", "8gb", "12gb", "fp8", "nf4"]),
    ("배치/자동화", ["batch", "automation", "automated", "queue"]),
    ("API/외부 연동", ["api", "webhook", "discord", "telegram"]),
    ("초보자용/기본 템플릿", ["basic", "simple", "starter", "beginner", "minimal", "template"]),
    ("고급/올인원", ["advanced", "all-in-one", "all in one", "ultimate", "complete"]),
]


def extract_hints(item: LoraItem, limit: int = 3) -> list[str]:
    text = " ".join([
        (item.name or "").replace("_", " ").replace("-", " "),
        item.name or "",
        " ".join(item.tags or []),
        item.description or "",
        item.example_prompt or "",
    ]).lower()
    found: list[str] = []
    rules = (WF_HINT_RULES + HINT_RULES) if item.kind == "workflow" else HINT_RULES
    for hint, keywords in rules:
        # 'character' 같은 흔한 단어는 캐릭터 분류일 때만 힌트로 쓴다
        if hint == "특정 인물/캐릭터 재현" and item.category != "캐릭터":
            continue
        if _any(text, keywords) and hint not in found:
            found.append(hint)
            if len(found) >= limit:
                break
    return found


# ---------------------------------------------------------------------------
# 트리거 워드 추출 (모델 카드 텍스트에서)
# ---------------------------------------------------------------------------

_TRIGGER_RE = re.compile(
    r"(?:trigger\s*(?:word|phrase|token|keyword)s?|activation\s*(?:word|token|tag)s?|instance[\s_]*prompt|trigger)"
    r"(?:\s*[:：\-]\s*|\s*\n\s*|\s+(?=[`\"]))"   # 콜론/대시, 줄바꿈, 또는 바로 뒤에 따옴표가 와야 함 (일반 문장 오인식 방지)
    r"([^\n]{2,160})",
    re.IGNORECASE,
)
_BAD_TRIGGERS = {"none", "n/a", "not needed", "no trigger", "no trigger word", "not required", "optional", "no"}


def extract_trigger_words(text: str) -> list[str]:
    words: list[str] = []
    for m in _TRIGGER_RE.finditer(text or ""):
        chunk = m.group(1).strip()
        # 문장 끝 / 괄호 설명 / 대시 설명에서 자른다
        chunk = re.split(r"(?<=\S)\.\s|\s{2,}|\s\(|\s-\s|\s—\s", chunk)[0].strip()
        quoted = re.findall(r"`([^`]+)`", chunk) or re.findall(r"\"([^\"]{2,60})\"", chunk)
        parts = quoted if quoted else re.split(r"\s*[,/|]\s*", chunk)
        for part in parts:
            part = part.strip(" `*_\"'.:;")
            if 1 < len(part) <= 60 and part.lower() not in _BAD_TRIGGERS and part not in words:
                words.append(part)
        if len(words) >= 5:
            break
    return words[:5]


# ---------------------------------------------------------------------------
# 한글 요약 (규칙 기반)
# ---------------------------------------------------------------------------

CATEGORY_PURPOSE = {
    "가속 (저스텝)": "적은 스텝으로 생성 속도를 높이는 용도",
    "이미지 편집": "기존 이미지를 지시대로 편집·변형하는 용도",
    "디테일 향상": "결과물의 디테일·화질을 끌어올리는 보조용",
    "영상 모션/카메라": "영상 생성 시 움직임·카메라 연출을 넣는 용도",
    "캐릭터": "특정 인물·캐릭터의 외형을 재현하는 용도",
    "실사/포토": "사진처럼 사실적인 결과를 내는 용도",
    "의상/포즈/컨셉": "특정 의상·포즈·소재·컨셉을 표현하는 용도",
    "스타일/화풍": "특정 화풍·분위기를 입히는 용도",
    "기타": "용도 미분류",
    "학습 도구": "LoRA 학습(트레이닝) 도구",
    "커스텀 노드": "ComfyUI 커스텀 노드",
    "로더/관리": "LoRA 로드·관리·미리보기 도구",
    "병합/변환": "LoRA 병합·추출·변환 도구",
    "자료 모음": "LoRA 관련 자료·목록 모음",
    "모델/가중치": "LoRA 가중치/모델 배포 저장소",
    "WF 이미지 생성": "텍스트→이미지 생성 워크플로우",
    "WF 영상 생성": "영상 생성 워크플로우",
    "WF 편집/인페인팅": "이미지 편집·인페인팅 워크플로우",
    "WF 업스케일/보정": "업스케일·디테일 보정 워크플로우",
    "WF 컨트롤넷/포즈": "ControlNet·포즈·참조 이미지 제어 워크플로우",
    "WF 캐릭터 일관성": "캐릭터/얼굴 일관성 유지 워크플로우",
    "WF 학습/도구": "학습·배치·유틸리티 워크플로우",
    "WF 모음/템플릿": "워크플로우 모음/템플릿",
}


def _short_desc(text: str, n: int = 140) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text[:n] + ("…" if len(text) > n else "")


def build_rule_summary(item: LoraItem) -> str:
    purpose = CATEGORY_PURPOSE.get(item.category, "")
    hints = [h for h in item.hints if h != "성인(NSFW)"]

    if item.kind == "workflow":
        head = purpose.replace("워크플로우", "ComfyUI 워크플로우") if purpose else "ComfyUI 워크플로우"
        if item.base_model not in ("미상/기타", "비디오 모델 (미상)", "범용/도구", "범용/미상"):
            head = f"{item.base_model} 기반 {head}"
        parts = [head]
        if hints:
            parts.append(", ".join(hints))
        if item.files:
            parts.append(f"JSON {len(item.files)}개")
        if item.description and item.source == "github":
            parts.append(_short_desc(item.description))
        if item.nsfw:
            parts.append("성인(NSFW) 태그")
        return " · ".join(parts)

    if item.source == "github":
        parts = [f"GitHub · {item.category}"]
        if purpose:
            parts.append(purpose)
        if hints:
            parts.append(", ".join(hints))
        if item.description:
            parts.append(_short_desc(item.description))
        return " · ".join(parts)

    parts = [f"{item.base_model} 기반 {item.category} LoRA"]
    if hints:
        parts.append(", ".join(hints))
    elif purpose:
        parts.append(purpose)
    if item.trigger_words:
        parts.append("트리거: " + ", ".join(item.trigger_words[:3]))
    if item.nsfw:
        parts.append("성인(NSFW) 태그")
    return " · ".join(parts)


def classify(item: LoraItem) -> LoraItem:
    """항목을 제자리에서 분류하고 규칙 기반 요약을 채운다 (Claude 요약이 있으면 덮어쓰지 않음)."""
    if item.kind not in ("lora", "workflow"):
        item.kind = "lora"
    if item.source == "github" and item.kind == "lora":
        item.base_model = _generic_base_model(item)
    elif item.kind == "workflow":
        item.base_model = _generic_base_model(item, fallback="범용/미상")
    else:
        item.base_model = detect_base_model(item)
    item.category = detect_category(item)
    item.hints = extract_hints(item)
    if not item.trigger_words and item.source != "github" and item.kind == "lora":
        item.trigger_words = extract_trigger_words(item.description)
    text = " ".join([item.name, " ".join(item.tags), item.description]).lower()
    if not item.nsfw and _any(text, ["nsfw", "not-for-all-audiences", "explicit", "hentai"]):
        item.nsfw = True
    if item.summary_source != "claude" or not item.summary_ko:
        item.summary_ko = build_rule_summary(item)
        item.summary_source = "rule"
    return item


def _generic_base_model(item: LoraItem, fallback: str = "범용/도구") -> str:
    """특정 베이스 모델 언급이 있으면 그것을, 없으면 범용 라벨."""
    label = detect_base_model(item)
    return label if label not in ("미상/기타", "비디오 모델 (미상)") else fallback
