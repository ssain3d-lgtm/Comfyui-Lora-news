import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import app as app_module
from lora_news.config import Config
from lora_news.service import NewsService
from lora_news.store import Store


def request(url, method="GET", headers=None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = Config()
        cfg.data_dir = Path(cls.tmp.name)
        cfg.claude_enabled = False
        # 같은 클래스의 다른 테스트가 진짜 새로고침을 실행하므로, 수집 결과가 비어 있으면 안 된다.
        # (예전에는 빈 성공을 실패로 오인해 캐시가 되살아나는 버그 덕분에 통과하고 있었다)
        from lora_news.models import LoraItem
        served = [LoraItem(key="hf:a/b", source="huggingface", name="a/b", author="a",
                           url="https://huggingface.co/a/b", base_model_raw="FLUX.1")]
        service = NewsService(cfg, store=Store(cfg.data_dir),
                              hf_fetch=lambda: (list(served), [], {"queries": 1, "failed": 0}),
                              gh_fetch=lambda: ([], [], {"queries": 1, "failed": 0}),
                              cv_fetch=lambda: ([], [], {"queries": 1, "failed": 0}),
                              readme_enricher=lambda items: 0)
        service.refresh()
        handler = app_module.make_handler(service, {"127.0.0.1", "localhost"})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.server.daemon_threads = True
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def test_serves_page_and_api(self):
        self.assertEqual(request(self.url("/"))[0], 200)
        status, body = request(self.url("/api/items"))
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["items"])
        self.assertIn("labels_en", data)

    def test_path_traversal_is_rejected(self):
        for path in ("/static/../app.py", "/static/..%2fapp.py", "/static/....//app.py", "/static/%2e%2e/app.py"):
            self.assertEqual(request(self.url(path))[0], 404, path)

    def test_unknown_host_is_rejected(self):
        # DNS 리바인딩 방어: 로컬 이름으로만 접근할 수 있어야 한다
        self.assertEqual(request(self.url("/api/items"), headers={"Host": "evil.example"})[0], 403)

    def test_cross_site_refresh_is_blocked(self):
        blocked = request(self.url("/api/refresh"), method="POST",
                          headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"})
        self.assertEqual(blocked[0], 403)
        allowed = request(self.url("/api/refresh"), method="POST",
                          headers={"Sec-Fetch-Site": "same-origin", "Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(allowed[0], 200)

    def test_unknown_route_is_404(self):
        self.assertEqual(request(self.url("/nope"))[0], 404)


class DemoServerTests(unittest.TestCase):
    """--demo 는 읽기 전용이어야 한다. 새로고침을 허용하면 샘플 항목이 진짜 캐시에 섞인다."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cfg = Config()
        cfg.data_dir = Path(cls.tmp.name)
        cfg.claude_enabled = False
        cls.service = NewsService(cfg, store=Store(cfg.data_dir),
                                  hf_fetch=lambda: ([], []), gh_fetch=lambda: ([], []), cv_fetch=lambda: ([], []),
                                  readme_enricher=lambda items: 0)
        app_module.load_demo(cls.service)
        handler = app_module.make_handler(cls.service, {"127.0.0.1", "localhost"}, demo=True)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.server.daemon_threads = True
        cls.port = cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def test_refresh_is_refused_and_flagged(self):
        status, body = request(f"http://127.0.0.1:{self.port}/api/refresh", method="POST",
                               headers={"Sec-Fetch-Site": "same-origin"})
        self.assertEqual(status, 409)
        self.assertTrue(json.loads(body)["demo"])
        self.assertFalse(self.service.status["refreshing"], "데모에서는 수집이 시작되지 않는다")
        self.assertTrue(json.loads(request(f"http://127.0.0.1:{self.port}/api/status")[1])["demo"])


class CliTests(unittest.TestCase):
    def test_parser_accepts_documented_options(self):
        args = app_module.build_parser().parse_args(
            ["--port", "0", "--host", "0.0.0.0", "--no-browser", "--no-refresh", "-v"])
        self.assertEqual(args.port, 0, "--port 0 도 값으로 인정되어야 한다")
        self.assertEqual(args.host, "0.0.0.0")
        self.assertTrue(args.verbose)

    def test_help_is_bilingual(self):
        text = app_module.build_parser().format_help()
        self.assertIn("포트", text)
        self.assertIn("Port", text)


if __name__ == "__main__":
    unittest.main()
