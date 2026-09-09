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

# 리다이렉트를 따라갈 때 절대 넘겨서는 안 되는 헤더
_SENSITIVE_HEADERS = ("authorization", "cookie", "proxy-authorization")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """리다이렉트에 토큰을 딸려 보내지 않는 핸들러.

    urllib 기본 동작은 Authorization 헤더를 새 요청에 그대로 복사한다. Hugging Face 의 raw 경로처럼
    CDN 호스트로 302 를 보내는 곳에서는 토큰이 다른 호스트로 새어 나간다. https -> http 로 내려가는
    리다이렉트는 아예 따라가지 않는다 (이 앱은 https API 세 곳만 쓴다).
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            return None
        old = urllib.parse.urlsplit(req.full_url)
        dest = urllib.parse.urlsplit(newurl)
        if old.scheme == "https" and dest.scheme != "https":
            log.warning("https -> %s 리다이렉트를 거부했습니다: %s", dest.scheme or "?", newurl)
            return None
        if (old.hostname or "").lower() != (dest.hostname or "").lower():
            for store in (new.headers, getattr(new, "unredirected_hdrs", {})):
                for name in [h for h in store if h.lower() in _SENSITIVE_HEADERS]:
                    del store[name]
        return new


_opener = urllib.request.build_opener(SafeRedirectHandler)


def get(url: str, params: dict | None = None, headers: dict | None = None,
        timeout: int = 30, retries: int = 2, max_bytes: int = DEFAULT_MAX_BYTES,
        allow_truncation: bool = False) -> tuple[int, dict, bytes]:
    """GET 요청. (status, headers, body) 반환. 5xx/네트워크 오류는 재시도.

    본문은 max_bytes 까지만 읽는다. 그보다 크면 기본적으로 HttpError 를 낸다. 잘린 JSON 을 파싱하다
    엉뚱한 오류를 만나는 것보다 "응답이 너무 큽니다"가 낫기 때문이다. allow_truncation=True 면
    (README 처럼 일부만 읽어도 쓸모 있는 경우) 조용히 자른다.
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
            with _opener.open(req, timeout=timeout) as resp:
                body = resp.read(max_bytes + 1)
                if len(body) > max_bytes:
                    if not allow_truncation:
                        raise HttpError(resp.status, url, f"response exceeded {max_bytes} bytes")
                    body = body[:max_bytes]
                return resp.status, dict(resp.headers), body
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
    status, _, body = get(url, headers=headers, timeout=timeout, retries=0, max_bytes=max_bytes,
                          allow_truncation=True)
    return body.decode("utf-8", "replace")
