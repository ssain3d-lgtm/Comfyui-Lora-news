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


MAX_IMAGES = 8   # 항목당 갤러리 상한. 브라우저는 현재 장만 받으므로 개수는 전송량이 아니라 캐시 크기 문제다


def gallery_from_markdown(markdown: str, base: str, limit: int = MAX_IMAGES, scan: int = 40) -> list[str]:
    """모델 카드에서 미리보기로 쓸 만한 이미지들. 문서 순서대로, 중복 없이, 최대 limit 개."""
    if not markdown:
        return []
    found: list[str] = []
    candidates = _MD_IMG.findall(markdown) + _HTML_IMG.findall(markdown)
    for raw in candidates[:scan]:
        url = resolve_image(raw, base)
        if is_allowed_image(url) and looks_like_preview(url) and url not in found:
            found.append(url)
            if len(found) >= limit:
                break
    return found


def first_image(markdown: str, base: str, limit: int = 12) -> str:
    """모델 카드에서 미리보기로 쓸 만한 첫 이미지. 없으면 빈 문자열."""
    got = gallery_from_markdown(markdown, base, limit=1, scan=limit)
    return got[0] if got else ""


def image_pair(url: str) -> dict:
    """그리드용/확대용 URL 쌍. Civitai 는 CDN 크기 변형을 쓰고, 나머지는 원본 그대로다."""
    if host_of(url) == "image.civitai.com":
        return {"thumb": civitai_variant(url, 320), "large": civitai_variant(url, 1200)}
    return {"thumb": url, "large": url}


def sanitize_gallery(pairs) -> list[dict]:
    """캐시나 소스에서 온 갤러리를 허용 호스트, 중복, 개수 기준으로 정리한다."""
    out: list[dict] = []
    seen: set[str] = set()
    for p in pairs if isinstance(pairs, list) else []:
        if not isinstance(p, dict):
            continue
        thumb = p.get("thumb")
        if not isinstance(thumb, str) or not is_allowed_image(thumb):
            continue
        large = p.get("large")
        if not isinstance(large, str) or not is_allowed_image(large):
            large = thumb
        if large in seen:
            continue
        seen.add(large)
        out.append({"thumb": thumb, "large": large})
        if len(out) >= MAX_IMAGES:
            break
    return out


def set_gallery(item, urls) -> None:
    """항목의 갤러리를 URL 목록으로 다시 채운다. thumb/thumb_large 는 항상 첫 장을 가리킨다."""
    item.images = sanitize_gallery([image_pair(u) for u in urls if isinstance(u, str) and u])
    item.thumb = item.images[0]["thumb"] if item.images else ""
    item.thumb_large = item.images[0]["large"] if item.images else ""


def add_images(item, urls) -> int:
    """갤러리 뒤에 새 이미지를 붙인다(중복 제외, 상한 유지). 추가된 개수 반환."""
    before = len(item.images)
    have = [p["large"] for p in item.images]
    set_gallery(item, have + [u for u in urls if isinstance(u, str)])
    return len(item.images) - before


def normalize_repo_base(base: str) -> str:
    return base if base.endswith("/") else base + "/"


__all__ = ["ALLOWED_IMAGE_HOSTS", "MAX_IMAGES", "is_allowed_image", "civitai_variant", "first_image",
           "gallery_from_markdown", "image_pair", "sanitize_gallery", "set_gallery", "add_images",
           "resolve_image", "looks_like_preview", "normalize_repo_base", "posixpath"]
