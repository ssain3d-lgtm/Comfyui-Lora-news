#!/usr/bin/env python3
"""LoRA 뉴스 - 실행하면 최신 LoRA 목록을 받아와 브라우저로 보여주는 로컬 웹앱.

    python app.py                # 서버 실행 + 브라우저 열기 + 백그라운드 새로고침
    python app.py --refresh-only # 브라우저 없이 수집만 하고 종료 (스케줄러용)
    python app.py --no-refresh   # 캐시된 데이터만 표시
    python app.py --demo         # 네트워크 없이 샘플 데이터로 UI 확인
"""
from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lora_news.config import Config  # noqa: E402
from lora_news.service import NewsService  # noqa: E402

STATIC_DIR = ROOT / "static"
log = logging.getLogger("lora_news.app")


def make_handler(service: NewsService):
    class Handler(BaseHTTPRequestHandler):
        server_version = "LoraNews/0.1"

        def log_message(self, fmt, *args):  # 조용히
            log.debug("%s - %s", self.address_string(), fmt % args)

        # -- helpers ---------------------------------------------------
        def _json(self, obj, status: int = 200) -> None:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _static(self, rel: str) -> None:
            rel = rel.lstrip("/") or "index.html"
            path = (STATIC_DIR / rel).resolve()
            if STATIC_DIR.resolve() not in path.parents or not path.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
                ctype += "; charset=utf-8"
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)

        # -- routes ----------------------------------------------------
        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/items":
                self._json(service.snapshot())
            elif path == "/api/status":
                self._json(service.status)
            elif path in ("/", "/index.html"):
                self._static("index.html")
            elif path.startswith("/static/"):
                self._static(path[len("/static/"):])
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self):  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/refresh":
                started = service.start_refresh()
                self._json({"started": started, "status": service.status})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

    return Handler


def load_demo(service: NewsService) -> None:
    """네트워크 없이 샘플 데이터로 동작 (UI 점검용)."""
    from lora_news.classify import classify
    from lora_news.models import LoraItem

    sample = json.loads((ROOT / "tests" / "fixtures" / "sample_items.json").read_text(encoding="utf-8"))
    items = [classify(LoraItem.from_dict(d)) for d in sample]
    for i, it in enumerate(items):
        it.is_new = i % 3 == 0
        it.found_this_run = i % 6 == 0
    service.items = items
    service.status["last_refresh"] = "demo"
    service.status["counts"] = service._counts(items)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="LoRA 뉴스 웹앱")
    parser.add_argument("--port", type=int, default=None, help="포트 (기본 8765)")
    parser.add_argument("--host", default=None, help="바인드 주소 (기본 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="브라우저 자동 열기 안 함")
    parser.add_argument("--no-refresh", action="store_true", help="시작 시 새로고침 안 함 (캐시만 표시)")
    parser.add_argument("--refresh-only", action="store_true", help="수집만 하고 서버 없이 종료")
    parser.add_argument("--demo", action="store_true", help="샘플 데이터로 실행 (네트워크 불필요)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
    )
    config = Config()
    if args.port:
        config.port = args.port
    if args.host:
        config.host = args.host
    service = NewsService(config)

    if args.refresh_only:
        counts = service.refresh()
        print(json.dumps({"counts": counts, "errors": service.status["errors"]}, ensure_ascii=False, indent=1))
        return 0 if counts.get("total") else 1

    if args.demo:
        load_demo(service)
    elif not args.no_refresh:
        service.start_refresh()

    server = ThreadingHTTPServer((config.host, config.port), make_handler(service))
    server.daemon_threads = True
    url = f"http://{config.host}:{config.port}/"
    print(f"\n  LoRA 뉴스 실행 중: {url}\n  종료: Ctrl+C\n")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
