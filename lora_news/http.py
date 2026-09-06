"""표준 라이브러리(urllib)만 사용하는 작은 HTTP 도우미."""
from __future__ import annotations

import http.client
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

from . import __version__

USER_AGENT = f"comfyui-lora-news/{__version__} (+https://github.com/ssain3d-lgtm/Comfyui-Lora-news)"


class HttpError(Exception):
    def __init__(self, status: int, url: str, body: str = ""):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.url = url
        self.body = body


# 응답 본문 기본 상한. 악의적이거나 실수로 거대한 응답이 메모리를 삼키지 않도록 읽는 단계에서 자른다.
DEFAULT_MAX_BYTES = 8 * 1024 * 1024

# OSError 계열이 아니라서 따로 잡아야 하는 전송 중단 오류
_TRANSIENT = (http.client.IncompleteRead, http.client.BadStatusLine, http.client.RemoteDisconnected)


def get(url: str, params: dict | None = None, headers: dict | None = None,
        timeout: int = 30, retries: int = 2, max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[int, dict, bytes]:
    """GET 요청. (status, headers, body) 반환. 5xx/네트워크 오류는 재시도.

    본문은 max_bytes 까지만 읽는다 (읽은 뒤 자르는 것이 아니라 읽는 양 자체를 제한).
    """
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None and v != ""}, doseq=True)
        url = f"{url}?{query}"
    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, dict(resp.headers), resp.read(max_bytes)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:500]
            except Exception:
                pass
            if e.code >= 500 and attempt < retries:
                last_exc = e
                time.sleep(1.5 * (attempt + 1))
                continue
            raise HttpError(e.code, url, body) from None
        except (urllib.error.URLError, TimeoutError, OSError, *_TRANSIENT) as e:
            last_exc = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"request failed: {url}: {last_exc}")  # pragma: no cover - 루프가 항상 반환/예외


def get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 30,
             max_bytes: int = DEFAULT_MAX_BYTES):
    status, _, body = get(url, params=params, headers=headers, timeout=timeout, max_bytes=max_bytes)
    return json.loads(body.decode("utf-8"))


def get_text(url: str, headers: dict | None = None, timeout: int = 30, max_bytes: int = 200_000) -> str:
    status, _, body = get(url, headers=headers, timeout=timeout, retries=0, max_bytes=max_bytes)
    return body.decode("utf-8", "replace")
