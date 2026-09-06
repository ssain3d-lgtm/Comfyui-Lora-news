"""백엔드가 만드는 사용자 메시지(진행 상태·오류)의 한/영 문구. 프론트엔드가 언어에 맞춰 골라 보여준다."""
from __future__ import annotations

MESSAGES: dict[str, tuple[str, str]] = {
    # 진행 상태
    "starting": ("시작 중…", "Starting…"),
    "fetching": ("Hugging Face / GitHub / Civitai 에서 목록 가져오는 중…", "Fetching listings from Hugging Face / GitHub / Civitai…"),
    "marking_new": ("{n}개 항목 신규 판정 중…", "Checking {n} items for new arrivals…"),
    "reading_cards": ("모델 카드 {n}개 읽는 중…", "Reading {n} model cards…"),
    "classifying": ("분류 및 요약 생성 중…", "Classifying and writing summaries…"),
    "claude_progress": ("Claude 요약 생성 중… ({done}/{total})", "Generating Claude summaries… ({done}/{total})"),
    # 수집 오류
    "hf_failed": ("HuggingFace 요청 실패: {err}", "Hugging Face request failed: {err}"),
    "hf_bad_response": ("HuggingFace 응답 형식 오류: {body}", "Unexpected Hugging Face response: {body}"),
    "gh_rate_limited": ("GitHub API 요청 한도 초과 (GITHUB_TOKEN 설정 시 한도가 늘어납니다)",
                        "GitHub API rate limit exceeded (set GITHUB_TOKEN for a higher limit)"),
    "gh_failed": ("GitHub 요청 실패: {err}", "GitHub request failed: {err}"),
    "gh_forbidden": ("GitHub 접근 거부(403): 네트워크/프록시 차단이거나 토큰이 유효하지 않습니다",
                     "GitHub returned 403: a network/proxy block, or an invalid token"),
    "cv_forbidden": ("Civitai 접근 거부(403): Cloudflare 차단이거나 API 키가 필요할 수 있습니다 (CIVITAI_API_KEY 설정 시도)",
                     "Civitai returned 403: Cloudflare block or an API key may be required (try setting CIVITAI_API_KEY)"),
    "cv_rate_limited": ("Civitai 요청 한도 초과(429): 잠시 후 다시 시도하세요", "Civitai rate limit exceeded (429): try again later"),
    "cv_failed": ("Civitai 요청 실패: {err}", "Civitai request failed: {err}"),
    "cv_bad_response": ("Civitai 응답 형식 오류: {body}", "Unexpected Civitai response: {body}"),
    "source_failed": ("{source} 수집 실패: {err}", "{source} fetch failed: {err}"),
    "kept_cache": ("{source} 수집 결과가 비어 있어 이전 캐시 {n}개를 유지합니다", "{source} returned nothing; keeping {n} cached items"),
    "readme_failed": ("모델 카드 읽기 실패: {err}", "Failed to read model cards: {err}"),
    "deadline": ("{source} 수집이 제한 시간을 넘겨 중단했습니다", "{source} fetch exceeded its time limit and was stopped"),
    "all_failed": ("세 소스 모두 실패했습니다. 네트워크나 프록시 설정을 확인하세요 (--demo 로 화면만 확인 가능)",
                   "All three sources failed. Check your network or proxy (use --demo to view the UI offline)"),
    # Claude 요약
    "claude_failed": ("Claude 요약 실패: {err}", "Claude summary failed: {err}"),
    "claude_no_sdk": ("anthropic 패키지가 없습니다 (pip install anthropic)", "The anthropic package is not installed (pip install anthropic)"),
    "claude_init_failed": ("Claude 클라이언트 초기화 실패: {err}", "Failed to initialise the Claude client: {err}"),
    "claude_auth": ("인증 실패 (API 키 확인): {err}", "Authentication failed (check the API key): {err}"),
    "claude_rate": ("요청 한도 초과", "Rate limit exceeded"),
    "claude_api": ("API 오류 {status}: {err}", "API error {status}: {err}"),
    "claude_network": ("네트워크 오류: {err}", "Network error: {err}"),
    "claude_bad_json": ("Claude 응답을 JSON 으로 읽지 못했습니다", "Could not read the Claude response as JSON"),
    "claude_refusal": ("모델이 응답을 거절했습니다: {category}", "The model declined the request: {category}"),
}


def msg(key: str, **kw) -> dict:
    """{"key": ..., "ko": ..., "en": ...} 형태의 메시지."""
    ko, en = MESSAGES[key]
    return {"key": key, "ko": ko.format(**kw), "en": en.format(**kw)}


def text(m, lang: str = "ko") -> str:
    """메시지 dict 또는 문자열에서 한 언어의 문구를 꺼낸다."""
    if isinstance(m, dict):
        return m.get(lang) or m.get("ko") or ""
    return str(m or "")
