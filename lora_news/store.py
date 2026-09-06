"""로컬 JSON 저장소: 캐시된 항목, 처음 발견 시각(seen), Claude 요약 캐시."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


class Store:
    def __init__(self, data_dir: Path):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.dir / "cache.json"
        self.seen_path = self.dir / "seen.json"
        self.summaries_path = self.dir / "summaries.json"

    # -- generic -----------------------------------------------------------
    def load_json(self, path: Path, default):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return default
        except Exception as e:  # noqa: BLE001
            log.warning("%s 읽기 실패 (%s) - 초기화합니다", path.name, e)
            return default

    def save_json(self, path: Path, obj) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(self.dir), prefix=path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False, indent=1)
                f.flush()
                os.fsync(f.fileno())   # 이름 바꾸기 전에 내용이 디스크에 남도록
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    # -- typed accessors ---------------------------------------------------
    def load_cache(self) -> dict:
        data = self.load_json(self.cache_path, {})
        return data if isinstance(data, dict) else {}

    def save_cache(self, data: dict) -> None:
        self.save_json(self.cache_path, data)

    def load_seen(self) -> dict:
        data = self.load_json(self.seen_path, {})
        return data if isinstance(data, dict) else {}

    def save_seen(self, seen: dict) -> None:
        self.save_json(self.seen_path, seen)

    def load_summaries(self) -> dict:
        data = self.load_json(self.summaries_path, {})
        return data if isinstance(data, dict) else {}

    def save_summaries(self, data: dict) -> None:
        self.save_json(self.summaries_path, data)
