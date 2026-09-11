import unittest

from lora_news.images import civitai_variant, first_image, is_allowed_image, resolve_image
from lora_news.models import LoraItem
from lora_news.readme import readme_location
from lora_news.sources.civitai import parse_model as parse_civitai
from lora_news.sources.huggingface import parse_model as parse_hf


class ImageUrlTests(unittest.TestCase):
    def test_civitai_size_variants(self):
        url = "https://image.civitai.com/TOKEN/uuid-1/width=450/123.jpeg"
        self.assertEqual(civitai_variant(url, 320), "https://image.civitai.com/TOKEN/uuid-1/width=320/123.jpeg")
        self.assertEqual(civitai_variant("https://image.civitai.com/TOKEN/uuid-1/original=true/123.jpeg", 1200),
                         "https://image.civitai.com/TOKEN/uuid-1/width=1200/123.jpeg")
        self.assertEqual(civitai_variant("https://image.civitai.com/TOKEN/uuid-1/123.jpeg", 320),
                         "https://image.civitai.com/TOKEN/uuid-1/width=320/123.jpeg", "크기 조각이 없으면 끼워 넣는다")
        self.assertEqual(civitai_variant("https://huggingface.co/a/b/resolve/main/x.png", 320),
                         "https://huggingface.co/a/b/resolve/main/x.png", "다른 호스트는 손대지 않는다")

    def test_host_allowlist(self):
        self.assertTrue(is_allowed_image("https://image.civitai.com/x/y/width=320/1.jpeg"))
        self.assertTrue(is_allowed_image("https://huggingface.co/a/b/resolve/main/i.png"))
        self.assertTrue(is_allowed_image("https://raw.githubusercontent.com/o/r/HEAD/wf.png"))
        self.assertFalse(is_allowed_image("https://evil.example/tracker.gif"))
        self.assertFalse(is_allowed_image("http://image.civitai.com/x/y/1.jpeg"), "https 만")
        self.assertFalse(is_allowed_image("javascript:alert(1)"))

    def test_first_image_skips_badges_and_unknown_hosts(self):
        md = ("[![CI](https://img.shields.io/badge/ci-passing-green.svg)](x)\n"
              "<img src='https://evil.example/a.png'>\n"
              "![sample](./images/sample_1.png)\n")
        self.assertEqual(first_image(md, "https://huggingface.co/a/b/resolve/main/"),
                         "https://huggingface.co/a/b/resolve/main/images/sample_1.png")
        self.assertEqual(first_image("no images here", "https://huggingface.co/a/b/resolve/main/"), "")

    def test_github_blob_links_become_raw(self):
        self.assertEqual(resolve_image("https://github.com/o/r/blob/main/docs/wf.png?raw=true", ""),
                         "https://raw.githubusercontent.com/o/r/main/docs/wf.png")
        self.assertEqual(resolve_image("docs/wf.png", "https://raw.githubusercontent.com/o/r/HEAD/"),
                         "https://raw.githubusercontent.com/o/r/HEAD/docs/wf.png")

    def test_readme_locations(self):
        hf = LoraItem(key="hf:a/b", source="huggingface", name="a/b", author="a", url="")
        gh = LoraItem(key="gh:o/r", source="github", name="o/r", author="o", url="")
        cv = LoraItem(key="civitai:1", source="civitai", name="x", author="a", url="")
        self.assertEqual(readme_location(hf)[0], "https://huggingface.co/a/b/raw/main/README.md")
        self.assertEqual(readme_location(gh)[0], "https://raw.githubusercontent.com/o/r/HEAD/README.md")
        self.assertIsNone(readme_location(cv), "Civitai 는 API 가 이미지를 직접 준다")


class ThumbnailParsingTests(unittest.TestCase):
    def test_huggingface_widget_output_is_a_free_thumbnail(self):
        m = {"id": "a/flux-style", "tags": ["lora"],
             "cardData": {"widget": [{"text": "a cat", "output": {"url": "images/example_1.png"}}]}}
        it = parse_hf(m)
        self.assertEqual(it.thumb, "https://huggingface.co/a/flux-style/resolve/main/images/example_1.png")
        self.assertEqual(it.thumb_large, it.thumb)
        nsfw = parse_hf(dict(m, tags=["lora", "not-for-all-audiences"]))
        self.assertEqual(nsfw.thumb, "", "NSFW 태그 항목은 미리보기를 붙이지 않는다")

    def test_civitai_grid_and_lightbox_variants(self):
        m = {"id": 5, "name": "X", "type": "LORA", "stats": {}, "creator": {"username": "u"},
             "modelVersions": [{"name": "v1", "baseModel": "SDXL", "publishedAt": "2026-01-01T00:00:00Z", "files": [],
                                "images": [{"url": "https://image.civitai.com/T/u1/width=450/1.jpeg", "nsfwLevel": 1}]}]}
        it = parse_civitai(m)
        self.assertEqual(it.thumb, "https://image.civitai.com/T/u1/width=320/1.jpeg")
        self.assertEqual(it.thumb_large, "https://image.civitai.com/T/u1/width=1200/1.jpeg")

    def test_civitai_missing_rating_fails_closed(self):
        m = {"id": 6, "name": "X", "type": "LORA", "stats": {}, "creator": {"username": "u"},
             "modelVersions": [{"name": "v1", "baseModel": "SDXL", "publishedAt": "2026-01-01T00:00:00Z", "files": [],
                                "images": [{"url": "https://image.civitai.com/T/u2/width=450/2.jpeg"}]}]}
        self.assertEqual(parse_civitai(m).thumb, "", "등급 필드가 없으면 표시하지 않는다")


if __name__ == "__main__":
    unittest.main()
