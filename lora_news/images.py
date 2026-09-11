"""미리보기 이미지 URL 처리: 허용 호스트, Civitai 크기 변형, README 에서 첫 이미지 찾기.

이 앱은 이미지를 직접 받지 않고 브라우저가 CDN 에서 불러오게 한다. 그래서 여기서 하는 일은
(1) 아무 URL 이나 <img> 에 넣지 않도록 호스트를 제한하고, (2) 작은 변형이 있는 곳(Civitai)은
그것을 쓰고, (3) 모델 카드에서 대표 이미지를 고르는 것뿐이다.
"""
from __future__ import annotations

import posixpath
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

# 브라우저가 이미지를 불러올 수 있는 호스트. 여기 없는 호스트는 카드에 표시하지 않는다.
ALLOWED_IMAGE_HOSTS = (
    "image.civitai.com",
    "huggingface.co",
    "cdn-uploads.huggingface.co",
    "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.huggingface.co",
    "cdn-lfs.hf.co",
    "raw.githubusercontent.com",
    "user-images.githubusercontent.com",
    "github.com",
)
_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif")
# 뱃지·아이콘처럼 미리보기가 아닌 이미지가 흔히 있는 경로
_SKIP_HINTS = ("shields.io", "badge", "/badges/", "icon", "logo", "colab", "button", "star-history")


def host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def is_allowed_image(url: str) -> bool:
    if not isinstance(url, str) or not url.startswith("https://"):
        return False
    host = host_of(url)
    return any(host == h or host.endswith("." + h) for h in ALLOWED_IMAGE_HOSTS)


def looks_like_preview(url: str) -> bool:
    low = url.lower()
    path = urlsplit(low).path
    if not path.endswith(_IMAGE_EXT) and "civitai.com" not in low:
        return False
    return not any(h in low for h in _SKIP_HINTS)


_CIVITAI_SIZE = re.compile(r"^(width=\d+|height=\d+|original=true|anim=false|,)+$")


def civitai_variant(url: str, width: int) -> str:
    """Civitai 이미지 CDN 의 크기 변형. 경로에 width=NNN 조각이 있으면 바꾸고, 없으면 끼워 넣는다.

    예: https://image.civitai.com/TOKEN/uuid/width=450/123.jpeg -> .../width=320/123.jpeg
    """
    if host_of(url) != "image.civitai.com":
        return url
    parts = urlsplit(url)
    segs = parts.path.split("/")
    replaced = False
    for i, seg in enumerate(segs):
        if seg and _CIVITAI_SIZE.match(seg):
            segs[i] = f"width={width}"
            replaced = True
            break
    if not replaced and len(segs) >= 3:
        segs.insert(len(segs) - 1, f"width={width}")
    return urlunsplit((parts.scheme, parts.netloc, "/".join(segs), "", ""))


_MD_IMG = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_HTML_IMG = re.compile(r"<img[^>]+src\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_GITHUB_BLOB = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$")


def resolve_image(url: str, base: str) -> str:
    """상대 경로를 절대 URL 로. GitHub 의 blob 링크는 raw 로 바꾼다."""
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith(("http://", "https://")):
        url = urljoin(base, url.lstrip("./"))
    m = _GITHUB_BLOB.match(url)
    if m:
        owner, repo, ref, path = m.groups()
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path.split('?')[0]}"
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    return url


def first_image(markdown: str, base: str, limit: int = 12) -> str:
    """모델 카드에서 미리보기로 쓸 만한 첫 이미지. 없으면 빈 문자열."""
    if not markdown:
        return ""
    candidates = _MD_IMG.findall(markdown) + _HTML_IMG.findall(markdown)
    for raw in candidates[:limit]:
        url = resolve_image(raw, base)
        if is_allowed_image(url) and looks_like_preview(url):
            return url
    return ""


def normalize_repo_base(base: str) -> str:
    return base if base.endswith("/") else base + "/"


__all__ = ["ALLOWED_IMAGE_HOSTS", "is_allowed_image", "civitai_variant", "first_image", "resolve_image",
           "looks_like_preview", "normalize_repo_base", "posixpath"]
