import unittest

from lora_news.images import (MAX_IMAGES, add_images, civitai_variant, first_image, gallery_from_markdown,
                              image_pair, is_allowed_image, resolve_image, sanitize_gallery)
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


class GalleryTests(unittest.TestCase):
    def test_gallery_from_markdown_keeps_order_dedupes_and_caps(self):
        md = "![badge](https://img.shields.io/x.svg)\n" + "".join(
            f"![s{i}](images/s{i % 5}.png)\n" for i in range(20))
        got = gallery_from_markdown(md, "https://huggingface.co/a/b/resolve/main/")
        self.assertEqual(got, [f"https://huggingface.co/a/b/resolve/main/images/s{i}.png" for i in range(5)])
        many = "".join(f"![s{i}](images/s{i}.png)\n" for i in range(20))
        self.assertEqual(len(gallery_from_markdown(many, "https://huggingface.co/a/b/resolve/main/")), MAX_IMAGES)
        self.assertEqual(first_image(many, "https://huggingface.co/a/b/resolve/main/"),
                         "https://huggingface.co/a/b/resolve/main/images/s0.png")

    def test_image_pair_only_resizes_civitai(self):
        self.assertEqual(image_pair("https://image.civitai.com/T/u/width=450/1.jpeg"),
                         {"thumb": "https://image.civitai.com/T/u/width=320/1.jpeg",
                          "large": "https://image.civitai.com/T/u/width=1200/1.jpeg"})
        hf = "https://huggingface.co/a/b/resolve/main/i.png"
        self.assertEqual(image_pair(hf), {"thumb": hf, "large": hf}, "크기를 줄일 수 없는 곳은 원본 그대로")

    def test_sanitize_gallery_drops_bad_hosts_and_duplicates(self):
        ok = "https://image.civitai.com/T/u/width=320/1.jpeg"
        pairs = [{"thumb": "https://evil.example/t.gif", "large": "https://evil.example/t.gif"},
                 {"thumb": ok, "large": "https://evil.example/big.gif"},
                 {"thumb": ok, "large": ok}, "junk", {"large": ok}]
        got = sanitize_gallery(pairs)
        self.assertEqual(got, [{"thumb": ok, "large": ok}], "허용되지 않는 확대 URL 은 썸네일로 대체하고, 같은 장은 한 번만")
        self.assertEqual(len(sanitize_gallery([{"thumb": f"https://huggingface.co/a/b/resolve/main/{i}.png"}
                                               for i in range(20)])), MAX_IMAGES)

    def test_add_images_appends_without_duplicates(self):
        it = LoraItem(key="hf:a/b", source="huggingface", name="a/b", author="a", url="")
        base = "https://huggingface.co/a/b/resolve/main/"
        self.assertEqual(add_images(it, [base + "w.png"]), 1)
        self.assertEqual(add_images(it, [base + "w.png", base + "r1.png", "https://evil.example/x.png"]), 1)
        self.assertEqual([p["large"] for p in it.images], [base + "w.png", base + "r1.png"])
        self.assertEqual(it.thumb, base + "w.png", "첫 장이 썸네일이다")

    def test_civitai_collects_every_all_ages_image_in_order(self):
        imgs = [{"url": "https://image.civitai.com/T/u/width=450/a.jpeg", "nsfwLevel": 1},
                {"url": "https://image.civitai.com/T/u/width=450/x.jpeg", "nsfwLevel": 8},
                {"url": "https://image.civitai.com/T/u/width=450/b.jpeg", "nsfwLevel": 1},
                {"url": "https://image.civitai.com/T/u/width=450/a.jpeg", "nsfwLevel": 1},
                {"url": "https://image.civitai.com/T/u/width=450/c.jpeg"}]
        m = {"id": 7, "name": "X", "type": "LORA", "stats": {}, "creator": {"username": "u"},
             "modelVersions": [{"name": "v1", "baseModel": "SDXL", "publishedAt": "2026-01-01T00:00:00Z", "files": [],
                                "images": imgs}]}
        it = parse_civitai(m)
        self.assertEqual([p["thumb"] for p in it.images],
                         ["https://image.civitai.com/T/u/width=320/a.jpeg", "https://image.civitai.com/T/u/width=320/b.jpeg"],
                         "등급이 높거나 등급이 없거나 중복인 이미지는 빠진다")
        self.assertEqual(it.images[1]["large"], "https://image.civitai.com/T/u/width=1200/b.jpeg")
        self.assertEqual(it.thumb, it.images[0]["thumb"])
        self.assertEqual(parse_civitai(dict(m, nsfw=True)).images, [])

    def test_huggingface_collects_every_widget_output(self):
        m = {"id": "a/flux-style", "tags": ["lora"],
             "cardData": {"widget": [{"text": "a cat", "output": {"url": "images/1.png"}},
                                     {"text": "a dog", "output": {"url": "images/2.png"}},
                                     {"text": "again", "output": {"url": "images/1.png"}}]}}
        it = parse_hf(m)
        self.assertEqual([p["thumb"] for p in it.images],
                         ["https://huggingface.co/a/flux-style/resolve/main/images/1.png",
                          "https://huggingface.co/a/flux-style/resolve/main/images/2.png"])

    def test_from_dict_sanitises_gallery_shape(self):
        it = LoraItem.from_dict({"key": "hf:a/b", "source": "huggingface",
                                 "images": [{"thumb": "https://huggingface.co/a/b/resolve/main/1.png"},
                                            {"thumb": "https://huggingface.co/a/b/resolve/main/2.png", "large": None},
                                            {"large": "x"}, "junk", 3]})
        self.assertEqual(it.images, [{"thumb": "https://huggingface.co/a/b/resolve/main/1.png", "large": "https://huggingface.co/a/b/resolve/main/1.png"},
                                     {"thumb": "https://huggingface.co/a/b/resolve/main/2.png", "large": "https://huggingface.co/a/b/resolve/main/2.png"}])
        self.assertEqual(LoraItem.from_dict({"key": "hf:a/b", "source": "huggingface", "images": "nope"}).images, [])


if __name__ == "__main__":
    unittest.main()
