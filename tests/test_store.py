import json
import tempfile
import unittest
from pathlib import Path

from lora_news.store import Store


class StoreTests(unittest.TestCase):
    def test_round_trip_and_no_temp_files_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            store.save_cache({"items": [{"key": "hf:a/b"}], "updated_at": "now"})
            self.assertEqual(store.load_cache()["updated_at"], "now")
            leftovers = [p.name for p in Path(tmp).iterdir() if p.name.endswith(".tmp")]
            self.assertEqual(leftovers, [], "임시 파일이 남으면 안 된다")

    def test_corrupt_file_recovers_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            store.cache_path.write_text("{ this is not json", encoding="utf-8")
            self.assertEqual(store.load_cache(), {}, "손상된 캐시는 빈 값으로 되돌린다")
            store.seen_path.write_text("[1, 2, 3]", encoding="utf-8")
            self.assertEqual(store.load_seen(), {}, "형식이 다르면 빈 값")

    def test_missing_files_are_fine(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "nested")
            self.assertEqual(store.load_cache(), {})
            self.assertEqual(store.load_summaries(), {})

    def test_save_is_atomic_across_a_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            store.save_seen({"hf:a/b": "2026-01-01T00:00:00+00:00"})

            class Unserialisable:
                pass

            with self.assertRaises(TypeError):
                store.save_seen({"bad": Unserialisable()})
            self.assertEqual(json.loads(store.seen_path.read_text(encoding="utf-8")),
                             {"hf:a/b": "2026-01-01T00:00:00+00:00"}, "실패한 쓰기가 기존 파일을 망가뜨리면 안 된다")


if __name__ == "__main__":
    unittest.main()
