from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


@dataclass
class LoraItem:
    """하나의 LoRA / ComfyUI 워크플로우 / 관련 GitHub 저장소 항목."""

    key: str                      # "hf:author/name", "gh:owner/repo", "civitai:12345"
    source: str                   # "huggingface" | "github" | "civitai"
    name: str
    author: str
    url: str
    kind: str = "lora"            # "lora" | "workflow"
    description: str = ""         # 원문(영문) 설명 / 모델 카드 발췌
    tags: list = field(default_factory=list)
    pipeline: str = ""            # text-to-image, image-to-video ...
    base_model_raw: str = ""      # 태그에서 읽은 베이스 모델 원문
    base_model: str = ""          # 분류된 베이스 모델 라벨
    category: str = ""            # 분류된 용도 라벨
    hints: list = field(default_factory=list)   # 한글 힌트 (예: 수채화 느낌)
    summary_ko: str = ""
    summary_source: str = "rule"  # "rule" | "claude"
    trigger_words: list = field(default_factory=list)
    example_prompt: str = ""
    created_at: str = ""          # ISO8601
    updated_at: str = ""          # ISO8601
    downloads: int = 0
    likes: int = 0                # HF likes 또는 GitHub stars
    nsfw: bool = False
    files: list = field(default_factory=list)   # safetensors 파일명
    first_seen: str = ""          # 이 앱이 처음 발견한 시각
    is_new: bool = False          # 최근 발견 창(기본 72시간) 안에 처음 발견됨
    found_this_run: bool = False  # 이번 실행에서 처음 발견됨

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LoraItem":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def is_video(self) -> bool:
        return "video" in (self.pipeline or "") or any(
            k in (self.base_model or "").lower() for k in ("wan", "video", "ltx", "mochi", "cogvideo", "animatediff")
        )
