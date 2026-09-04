import unittest

from lora_news.sources.github import parse_repo
from lora_news.sources.huggingface import clean_readme, parse_model


class HuggingFaceParseTests(unittest.TestCase):
    def test_parse_model_full(self):
        m = {
            "id": "author/flux-style-lora", "author": "author", "pipeline_tag": "text-to-image",
            "tags": ["diffusers", "lora", "text-to-image", "base_model:black-forest-labs/FLUX.1-dev",
                     "base_model:adapter:black-forest-labs/FLUX.1-dev", "license:apache-2.0", "style", "region:us"],
            "cardData": {"instance_prompt": "xyz style", "base_model": "black-forest-labs/FLUX.1-dev",
                         "widget": [{"text": "xyz style, a cat", "output": {"url": "a.png"}}]},
            "siblings": [{"rfilename": "README.md"}, {"rfilename": "lora.safetensors"}, {"rfilename": "samples/1.png"}],
            "createdAt": "2026-09-01T00:00:00.000Z", "lastModified": "2026-09-02T00:00:00.000Z",
            "downloads": 12, "likes": 3,
        }
        it = parse_model(m)
        self.assertEqual(it.key, "hf:author/flux-style-lora")
        self.assertEqual(it.trigger_words, ["xyz style"])
        self.assertEqual(it.example_prompt, "xyz style, a cat")
        self.assertEqual(it.files, ["lora.safetensors"])
        self.assertIn("FLUX.1-dev", it.base_model_raw)
        self.assertEqual(it.tags, ["style"])
        self.assertFalse(it.nsfw)

    def test_parse_model_minimal_and_private(self):
        self.assertIsNotNone(parse_model({"id": "a/b"}))
        self.assertIsNone(parse_model({"id": "a/b", "private": True}))
        self.assertIsNone(parse_model({}))

    def test_clean_readme(self):
        raw = "---\nlicense: mit\ntags:\n- lora\n---\n# Title\n![img](x.png)\nHello [link](http://x) <b>bold</b>\n```py\ncode\n```\nTrigger words: abc"
        txt = clean_readme(raw)
        self.assertNotIn("license", txt)
        self.assertNotIn("code", txt)
        self.assertIn("Hello link bold", txt)
        self.assertIn("Trigger words: abc", txt)


class GitHubParseTests(unittest.TestCase):
    def test_parse_repo(self):
        r = {"full_name": "o/r", "html_url": "https://github.com/o/r", "description": "LoRA trainer", "owner": {"login": "o"},
             "topics": ["lora"], "language": "Python", "stargazers_count": 5, "forks_count": 1,
             "created_at": "2026-01-01T00:00:00Z", "pushed_at": "2026-09-01T00:00:00Z", "fork": False}
        it = parse_repo(r)
        self.assertEqual(it.key, "gh:o/r")
        self.assertEqual(it.tags, ["lora", "Python"])
        self.assertEqual(it.likes, 5)
        self.assertEqual(it.updated_at, "2026-09-01T00:00:00Z")
        self.assertIsNone(parse_repo({**r, "fork": True}))


if __name__ == "__main__":
    unittest.main()
