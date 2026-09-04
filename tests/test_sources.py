import unittest

from lora_news.sources.civitai import parse_model as parse_civitai
from lora_news.sources.github import detect_kind, parse_repo
from lora_news.sources.huggingface import clean_readme, is_workflow_repo, parse_model


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


class HuggingFaceWorkflowTests(unittest.TestCase):
    def test_workflow_filter(self):
        self.assertTrue(is_workflow_repo("a/comfyui-flux-workflows", []))
        self.assertTrue(is_workflow_repo("a/my-workflows", ["comfyui"]))
        self.assertFalse(is_workflow_repo("a/flux-lora", ["comfyui"]))
        self.assertFalse(is_workflow_repo("a/github-workflows", []))
        self.assertIsNone(parse_model({"id": "a/flux-lora", "tags": []}, kind="workflow"))
        it = parse_model({"id": "a/comfy-workflows", "tags": [], "siblings": [{"rfilename": "x.json"}, {"rfilename": "y.safetensors"}]},
                         kind="workflow", dataset=True)
        self.assertEqual(it.key, "hf:datasets/a/comfy-workflows")
        self.assertEqual(it.url, "https://huggingface.co/datasets/a/comfy-workflows")
        self.assertEqual(it.files, ["x.json"])
        self.assertIsNone(parse_model({"id": "a/some-dataset", "tags": []}, kind="lora", dataset=True))


class CivitaiParseTests(unittest.TestCase):
    MODEL = {
        "id": 12345, "name": "Ghibli Style", "type": "LORA", "nsfw": False, "nsfwLevel": 1,
        "description": "<p>Studio <b>Ghibli</b> style.<br>Use weight 0.8&ndash;1.0</p>",
        "tags": ["style", "anime"],
        "stats": {"downloadCount": 900, "thumbsUpCount": 120, "favoriteCount": 5},
        "creator": {"username": "artist"},
        "modelVersions": [
            {"id": 2, "name": "v2", "baseModel": "Illustrious", "publishedAt": "2026-09-04T03:00:00.000Z",
             "updatedAt": "2026-09-04T05:00:00.000Z", "trainedWords": ["ghibli style", "ghibli style"],
             "description": "<p>v2 retrained</p>",
             "files": [{"name": "ghibli_v2.safetensors", "type": "Model"}, {"name": "ghibli_v2.yaml", "type": "Config"}]},
            {"id": 1, "name": "v1", "baseModel": "Pony", "publishedAt": "2026-08-01T00:00:00.000Z",
             "trainedWords": ["ghibli"], "files": [{"name": "ghibli_v1.safetensors"}]},
        ],
    }

    def test_parse_lora(self):
        it = parse_civitai(self.MODEL)
        self.assertEqual(it.key, "civitai:12345")
        self.assertEqual(it.source, "civitai")
        self.assertEqual(it.kind, "lora")
        self.assertEqual(it.url, "https://civitai.com/models/12345")
        self.assertEqual(it.author, "artist")
        self.assertEqual(it.trigger_words, ["ghibli style", "ghibli"])
        self.assertEqual(it.files, ["ghibli_v2.safetensors"])
        self.assertEqual(it.base_model_raw, "Illustrious Pony")
        self.assertEqual(it.created_at, "2026-08-01T00:00:00.000Z")
        self.assertEqual(it.updated_at, "2026-09-04T05:00:00.000Z")
        self.assertEqual(it.downloads, 900)
        self.assertEqual(it.likes, 120)
        self.assertFalse(it.nsfw)
        self.assertIn("최신 버전: v2 · 베이스: Illustrious", it.description)
        self.assertIn("Studio Ghibli style.", it.description)
        self.assertIn("Use weight 0.8–1.0", it.description)
        self.assertNotIn("<", it.description)

    def test_parse_workflow_and_nsfw(self):
        m = dict(self.MODEL, id=7, type="Workflows", nsfw=False, nsfwLevel=8, name="Kontext Inpaint WF")
        m["modelVersions"] = [{"name": "v1", "baseModel": "Flux.1 Kontext", "publishedAt": "2026-09-01T00:00:00.000Z",
                               "files": [{"name": "wf.json"}, {"name": "preview.png"}]}]
        it = parse_civitai(m)
        self.assertEqual(it.kind, "workflow")
        self.assertTrue(it.nsfw)
        self.assertEqual(it.files, ["wf.json"])
        self.assertEqual(it.pipeline, "text-to-image")
        self.assertIsNone(parse_civitai({"name": "no id"}))
        self.assertIsNone(parse_civitai({"id": 1}))


class GitHubParseTests(unittest.TestCase):
    def test_detect_kind(self):
        self.assertEqual(detect_kind("a/comfyui-workflows", []), "workflow")
        self.assertEqual(detect_kind("a/tool", ["comfyui-workflow"]), "workflow")
        self.assertEqual(detect_kind("a/tool", ["lora"]), "lora")
        self.assertEqual(detect_kind("a/tool", [], default="workflow"), "workflow")

    def test_parse_repo(self):
        r = {"full_name": "o/r", "html_url": "https://github.com/o/r", "description": "LoRA trainer", "owner": {"login": "o"},
             "topics": ["lora"], "language": "Python", "stargazers_count": 5, "forks_count": 1,
             "created_at": "2026-01-01T00:00:00Z", "pushed_at": "2026-09-01T00:00:00Z", "fork": False}
        it = parse_repo(r)
        self.assertEqual(it.key, "gh:o/r")
        self.assertEqual(it.kind, "lora")
        self.assertEqual(it.tags, ["lora", "Python"])
        self.assertEqual(it.likes, 5)
        self.assertEqual(it.updated_at, "2026-09-01T00:00:00Z")
        self.assertIsNone(parse_repo({**r, "fork": True}))


if __name__ == "__main__":
    unittest.main()
