import os
import tempfile
import unittest
from pathlib import Path

from lora_news.config import Config, load_dotenv


class DotenvTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in ("LORA_NEWS_PORT", "GITHUB_TOKEN", "HF_TOKEN", "LORA_NEWS_TEST_X")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_parse_and_no_override(self):
        os.environ["GITHUB_TOKEN"] = "from-shell"
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / ".env"
            env.write_text(
                "# comment\n"
                "\n"
                "LORA_NEWS_PORT=9001\n"
                "GITHUB_TOKEN=from-file\n"
                "HF_TOKEN=\"quoted value\"\n"
                "export LORA_NEWS_TEST_X=abc # trailing comment\n"
                "BROKEN LINE WITHOUT EQUALS\n",
                encoding="utf-8",
            )
            loaded = load_dotenv(env)
            self.assertEqual(loaded["LORA_NEWS_PORT"], "9001")
            self.assertEqual(loaded["HF_TOKEN"], "quoted value")
            self.assertEqual(loaded["LORA_NEWS_TEST_X"], "abc")
            self.assertEqual(os.environ["GITHUB_TOKEN"], "from-shell", "쉘 환경변수가 우선")
            self.assertEqual(os.environ["HF_TOKEN"], "quoted value")
            cfg = Config(env_file=env)
            self.assertEqual(cfg.port, 9001)
            self.assertEqual(cfg.github_token, "from-shell")
            self.assertEqual(cfg.hf_token, "quoted value")

    def test_missing_file_is_fine(self):
        self.assertEqual(load_dotenv(Path("/nonexistent/.env")), {})
        cfg = Config(env_file=Path("/nonexistent/.env"))
        self.assertEqual(cfg.port, 8765)


if __name__ == "__main__":
    unittest.main()
