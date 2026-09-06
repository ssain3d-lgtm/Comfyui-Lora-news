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
    summary_en: str = ""
    summary_source: str = "rule"  # "rule" | "claude"
    trigger_words: list = field(default_factory=list)
    example_prompt: str = ""
    created_at: str = ""          # ISO8601
    updated_at: str = ""          # ISO8601
    downloads: int = 0
    likes: int = 0                # HF likes 또는 GitHub stars
    nsfw: bool = False
    files: list = field(default_factory=list)   # safetensors 파일명
    thumb: str = ""               # 미리보기 이미지 URL (전체 이용가 등급만)
    first_seen: str = ""          # 이 앱이 처음 발견한 시각
    is_new: bool = False          # 최근 발견 창(기본 72시간) 안에 처음 발견됨
    found_this_run: bool = False  # 이번 실행에서 처음 발견됨

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LoraItem":
        """캐시 JSON 에서 복원. 손상된 값이 있어도 앱이 멈추지 않도록 타입을 강제한다."""
        if not isinstance(data, dict):
            raise ValueError("LoraItem 은 dict 에서만 복원할 수 있습니다")
        spec = {f.name: f for f in fields(cls)}
        clean: dict = {}
        for key, value in data.items():
            field_def = spec.get(key)
            if field_def is None:
                continue
            if field_def.type in ("str", str):
                clean[key] = value if isinstance(value, str) else ("" if value is None else str(value))
            elif field_def.type in ("int", int):
                try:
                    clean[key] = int(value)
                except (TypeError, ValueError):
                    clean[key] = 0
            elif field_def.type in ("bool", bool):
                clean[key] = bool(value)
            elif field_def.type in ("list", list):
                clean[key] = [v for v in value if isinstance(v, str)] if isinstance(value, list) else []
            else:
                clean[key] = value
        if not clean.get("key") or not clean.get("source"):
            raise ValueError("key/source 가 없는 항목")
        for required in ("name", "author", "url"):   # 기본값이 없는 필드
            clean.setdefault(required, "")
        return cls(**clean)

    @property
    def is_video(self) -> bool:
        return "video" in (self.pipeline or "") or any(
            k in (self.base_model or "").lower() for k in ("wan", "video", "ltx", "mochi", "cogvideo", "animatediff")
        )
