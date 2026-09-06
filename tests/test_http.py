import io
import unittest
import urllib.error
from unittest import mock

from lora_news import http


class FakeResponse(io.BytesIO):
    status = 200
    headers: dict = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


class HttpTests(unittest.TestCase):
    def test_params_drop_empty_values(self):
        seen = {}

        def fake_urlopen(req, timeout=None):
            seen["url"] = req.full_url
            return FakeResponse(b"[]")

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            http.get_json("https://x/api", params={"a": 1, "b": None, "c": "", "d": "ok"})
        self.assertIn("a=1", seen["url"])
        self.assertIn("d=ok", seen["url"])
        self.assertNotIn("b=", seen["url"])
        self.assertNotIn("c=", seen["url"])

    def test_body_is_capped_while_reading(self):
        class Huge(FakeResponse):
            def __init__(self):
                super().__init__(b"x" * 10_000)
                self.asked = None

            def read(self, n=-1):
                self.asked = n
                return super().read(n)

        huge = Huge()
        with mock.patch("urllib.request.urlopen", lambda req, timeout=None: huge):
            text = http.get_text("https://x/readme", max_bytes=100)
        self.assertEqual(len(text), 100)
        self.assertEqual(huge.asked, 100, "읽는 양 자체가 제한되어야 한다 (읽고 나서 자르면 늦다)")

    def test_4xx_is_not_retried_and_carries_body(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(1)
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b"API rate limit exceeded"))

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            with self.assertRaises(http.HttpError) as ctx:
                http.get("https://x/api", retries=2)
        self.assertEqual(len(calls), 1, "4xx 는 재시도하지 않는다")
        self.assertEqual(ctx.exception.status, 403)
        self.assertIn("rate limit", ctx.exception.body)

    def test_5xx_is_retried_then_raises(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(1)
            raise urllib.error.HTTPError(req.full_url, 503, "Busy", {}, io.BytesIO(b""))

        with mock.patch("urllib.request.urlopen", fake_urlopen), mock.patch("time.sleep"):
            with self.assertRaises(http.HttpError):
                http.get("https://x/api", retries=2)
        self.assertEqual(len(calls), 3)

    def test_truncated_transfer_is_retried(self):
        import http.client as hc
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(1)
            if len(calls) == 1:
                raise hc.IncompleteRead(b"half")
            return FakeResponse(b'{"ok": true}')

        with mock.patch("urllib.request.urlopen", fake_urlopen), mock.patch("time.sleep"):
            self.assertEqual(http.get_json("https://x/api"), {"ok": True})
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
