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


def patch_transport(fn):
    """http.get 은 리다이렉트 안전 opener 를 쓰므로 그 지점에서 가로챈다."""
    return mock.patch.object(http._opener, "open", lambda req, timeout=None: fn(req, timeout=timeout))


class RedirectTests(unittest.TestCase):
    def handler(self):
        return http.SafeRedirectHandler()

    def make_request(self, url):
        import urllib.request as ur
        return ur.Request(url, headers={"Authorization": "Bearer secret", "Accept": "application/json"})

    def test_https_to_http_downgrade_is_refused(self):
        req = self.make_request("https://huggingface.co/a/b/raw/main/README.md")
        new = self.handler().redirect_request(req, None, 302, "Found", {}, "http://cdn.example/x")
        self.assertIsNone(new, "https 에서 http 로 내려가는 리다이렉트는 따라가지 않는다")

    def test_cross_host_redirect_drops_the_token(self):
        req = self.make_request("https://huggingface.co/a/b/raw/main/README.md")
        new = self.handler().redirect_request(req, None, 302, "Found", {}, "https://cdn-lfs.hf.co/x")
        self.assertIsNotNone(new)
        self.assertNotIn("Authorization", new.headers)
        self.assertIn("Accept", new.headers, "민감하지 않은 헤더는 남는다")

    def test_same_host_redirect_keeps_the_token(self):
        req = self.make_request("https://huggingface.co/a/b")
        new = self.handler().redirect_request(req, None, 302, "Found", {}, "https://huggingface.co/a/b/resolve/main")
        self.assertIn("Authorization", new.headers)


class HttpTests(unittest.TestCase):
    def test_params_drop_empty_values(self):
        seen = {}

        def fake_urlopen(req, timeout=None):
            seen["url"] = req.full_url
            return FakeResponse(b"[]")

        with patch_transport(fake_urlopen):
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
        with patch_transport(lambda req, timeout=None: huge):
            text = http.get_text("https://x/readme", max_bytes=100)
        self.assertEqual(len(text), 100, "README 는 일부만 읽어도 쓸모가 있으므로 잘라서 돌려준다")
        self.assertEqual(huge.asked, 101, "읽는 양 자체를 제한하되 초과 여부를 알 만큼만 더 읽는다")

    def test_oversized_json_response_is_an_error_not_broken_json(self):
        class Huge(FakeResponse):
            def __init__(self):
                super().__init__(b'{"items": [' + b'0,' * 5000 + b']}')

        with patch_transport(lambda req, timeout=None: Huge()):
            with self.assertRaises(http.HttpError) as ctx:
                http.get_json("https://x/api", max_bytes=100)
        self.assertIn("exceeded", ctx.exception.body)

    def test_4xx_is_not_retried_and_carries_body(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(1)
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(b"API rate limit exceeded"))

        with patch_transport(fake_urlopen):
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

        with patch_transport(fake_urlopen), mock.patch("time.sleep"):
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

        with patch_transport(fake_urlopen), mock.patch("time.sleep"):
            self.assertEqual(http.get_json("https://x/api"), {"ok": True})
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
