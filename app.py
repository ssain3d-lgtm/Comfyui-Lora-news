#!/usr/bin/env python3
"""LoRA News / LoRA 뉴스 - a local web app for ComfyUI LoRAs and workflows.

    python app.py                # serve + open browser + refresh in the background
    python app.py --refresh-only # fetch only, no server (for cron / Task Scheduler)
    python app.py --no-refresh   # serve the cached data only
    python app.py --demo         # sample data, no network needed
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

from lora_news import __version__  # noqa: E402
from lora_news.config import Config  # noqa: E402
from lora_news.service import NewsService  # noqa: E402

STATIC_DIR = ROOT / "static"
log = logging.getLogger("lora_news.app")


def make_handler(service: NewsService, allowed_hosts: set[str]):
    class Handler(BaseHTTPRequestHandler):
        server_version = f"LoraNews/{__version__}"

        def log_message(self, fmt, *args):  # quiet
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

        def _host_ok(self) -> bool:
            """Reject DNS-rebinding: only localhost names may address this server."""
            host = (self.headers.get("Host") or "").split(":")[0].strip("[]").lower()
            return host in allowed_hosts

        def _same_origin(self) -> bool:
            """Block cross-site writes. A browser always sends one of these on a cross-site POST."""
            site = (self.headers.get("Sec-Fetch-Site") or "").lower()
            if site and site not in ("same-origin", "same-site", "none"):
                return False
            origin = self.headers.get("Origin")
            if origin:
                netloc = urlparse(origin).hostname or ""
                return netloc.lower() in allowed_hosts
            return True

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
            if not self._host_ok():
                self.send_error(HTTPStatus.FORBIDDEN, "Unrecognised Host header")
                return
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
            if not self._host_ok():
                self.send_error(HTTPStatus.FORBIDDEN, "Unrecognised Host header")
                return
            if not self._same_origin():
                self.send_error(HTTPStatus.FORBIDDEN, "Cross-site request blocked")
                return
            path = urlparse(self.path).path
            if path == "/api/refresh":
                started = service.start_refresh()
                self._json({"started": started, "status": service.status})
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

    return Handler


def load_demo(service: NewsService) -> None:
    """Run on bundled sample data, no network. / 네트워크 없이 샘플 데이터로 동작."""
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="app.py",
        description="LoRA News - ComfyUI LoRAs and workflows from Hugging Face, GitHub and Civitai. "
                    "/ ComfyUI용 LoRA·워크플로우 모아보기.",
    )
    p.add_argument("--port", type=int, default=None, help="Port, default 8765 / 포트 (기본 8765)")
    p.add_argument("--host", default=None, help="Bind address, default 127.0.0.1 / 바인드 주소")
    p.add_argument("--no-browser", action="store_true", help="Do not open the browser / 브라우저 자동 열기 안 함")
    p.add_argument("--no-refresh", action="store_true", help="Serve cached data only / 캐시만 표시")
    p.add_argument("--refresh-only", action="store_true", help="Fetch and exit, no server / 수집만 하고 종료")
    p.add_argument("--demo", action="store_true", help="Sample data, no network / 샘플 데이터로 실행")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging / 상세 로그")
    p.add_argument("--version", action="version", version=f"LoRA News {__version__}")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S",
    )
    config = Config()
    if args.port is not None:
        config.port = args.port
    if args.host is not None:
        config.host = args.host
    service = NewsService(config)

    if args.refresh_only:
        counts = service.refresh()
        total = counts.get("total") or 0
        failed = [e for e in service.status["errors"] if isinstance(e, dict)]
        print(f"{total} items collected / {total}개 수집" + (f", {len(failed)} problem(s)" if failed else ""))
        print(json.dumps({"counts": counts, "errors": service.status["errors"]}, ensure_ascii=False, indent=1))
        return 0 if total else 1

    if args.demo:
        load_demo(service)
    elif not args.no_refresh:
        service.start_refresh()

    allowed_hosts = {"127.0.0.1", "localhost", "::1", "0.0.0.0", config.host.lower()}
    try:
        server = ThreadingHTTPServer((config.host, config.port), make_handler(service, allowed_hosts))
    except OSError as e:
        print(f"\n  Cannot listen on {config.host}:{config.port} - {e}")
        print(f"  {config.host}:{config.port} 에서 서버를 열 수 없습니다.")
        print("  Another program may be using the port. Try: python app.py --port 9000")
        print("  다른 프로그램이 포트를 쓰고 있을 수 있습니다. 예: python app.py --port 9000\n")
        return 2
    server.daemon_threads = True
    url = f"http://{config.host}:{server.server_port}/"
    print(f"\n  LoRA News running at / 실행 중: {url}")
    print("  Stop with Ctrl+C / 종료: Ctrl+C\n")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. / 종료합니다.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
