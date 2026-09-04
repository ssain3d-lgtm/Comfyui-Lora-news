"""표준 라이브러리(urllib)만 사용하는 작은 HTTP 도우미."""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

USER_AGENT = "comfyui-lora-news/0.1 (+https://github.com/ssain3d-lgtm/Comfyui-Lora-news)"


class HttpError(Exception):
    def __init__(self, status: int, url: str, body: str = ""):
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.url = url
        self.body = body


def get(url: str, params: dict | None = None, headers: dict | None = None,
        timeout: int = 30, retries: int = 2) -> tuple[int, dict, bytes]:
    """GET 요청. (status, headers, body) 반환. 5xx/네트워크 오류는 재시도."""
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
                return resp.status, dict(resp.headers), resp.read()
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
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_exc = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"request failed: {url}: {last_exc}")


def get_json(url: str, params: dict | None = None, headers: dict | None = None, timeout: int = 30):
    status, _, body = get(url, params=params, headers=headers, timeout=timeout)
    return json.loads(body.decode("utf-8"))


def get_text(url: str, headers: dict | None = None, timeout: int = 30, max_bytes: int = 200_000) -> str:
    status, _, body = get(url, headers=headers, timeout=timeout, retries=0)
    return body[:max_bytes].decode("utf-8", "replace")
