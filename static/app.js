/* LoRA 뉴스 프론트엔드 (의존성 없음) — 한/영 전환 지원 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);

  // 저장된 선택이 없으면 브라우저 언어를 따른다. 영어권 방문자가 한국어 화면을 보고 돌아서지 않도록.
  function defaultLang() {
    try {
      return String(navigator.language || "").toLowerCase().startsWith("ko") ? "ko" : "en";
    } catch (e) { return "ko"; }
  }
  const state = {
    items: [],
    byKey: new Map(),
    labelsEn: { base_models: {}, categories: {} },
    status: {},
    filters: loadPrefs({
      lang: defaultLang(), kind: "lora", q: "", source: "all", base: null, cat: null,
      onlyNew: false, onlyChanged: false, since: "all", hideNsfw: true, sort: "new", group: "none",
      thumbs: true,
    }),
    pollTimer: null,
  };

  // ---------------------------------------------------------------- i18n
  const STR = {
    title: { ko: "LoRA 뉴스", en: "LoRA News" },
    subtitle: { ko: "ComfyUI용 LoRA · 워크플로우 — Hugging Face + GitHub + Civitai 신규/기존 모아보기",
                en: "LoRAs and workflows for ComfyUI — new and existing, from Hugging Face + GitHub + Civitai" },
    refresh: { ko: "새로고침", en: "Refresh" },
    skip: { ko: "본문으로 건너뛰기", en: "Skip to content" },
    facets_summary: { ko: "상세 필터", en: "More filters" },
    clear_filters: { ko: "필터 초기화", en: "Clear filters" },
    sort_label: { ko: "정렬", en: "Sort" },
    group_label: { ko: "묶기", en: "Group" },
    tab_label: { ko: "종류 선택", en: "Item type" },
    preview_of: { ko: "{name} 미리보기", en: "Preview of {name}" },
    lang_switch: { ko: "EN", en: "한국어" },
    loading: { ko: "불러오는 중…", en: "Loading…" },
    refreshing: { ko: "새로고침 중…", en: "Refreshing…" },
    demo: { ko: "데모 데이터", en: "Demo data" },
    demo_hint: { ko: "데모 데이터입니다. 새로고침은 꺼져 있습니다.", en: "Demo data. Refresh is disabled." },
    last_update: { ko: "마지막 업데이트", en: "Last update" },
    no_data_yet: { ko: "아직 데이터 없음", en: "No data yet" },
    claude_on: { ko: "Claude 요약 켜짐", en: "Claude summaries on" },
    error_prefix: { ko: "오류: ", en: "Error: " },
    claude_unavailable: { ko: "Claude 요약 사용 불가: ", en: "Claude summaries unavailable: " },
    server_unreachable: { ko: "서버에 연결할 수 없습니다: ", en: "Cannot reach the server: " },
    refresh_failed: { ko: "서버에 연결할 수 없습니다. 앱이 아직 실행 중인지 확인하세요.",
                      en: "Could not reach the server. Check that the app is still running." },
    search_ph: { ko: "검색: 이름, 태그, 설명, 트리거 워드…", en: "Search: name, tags, description, trigger words…" },
    sort_new: { ko: "신규 우선", en: "New first" },
    sort_created: { ko: "등록일 최신순", en: "Newest added" },
    sort_updated: { ko: "수정일 최신순", en: "Recently updated" },
    sort_downloads: { ko: "다운로드 많은순", en: "Most downloads" },
    sort_likes: { ko: "좋아요/스타 많은순", en: "Most likes / stars" },
    sort_name: { ko: "이름순", en: "Name" },
    sort_found: { ko: "발견일 최신순", en: "Recently found" },
    sort_changed: { ko: "변경된 것 먼저", en: "Changed first" },
    since_all: { ko: "발견: 전체", en: "Found: any time" },
    since_1: { ko: "발견: 오늘", en: "Found: today" },
    since_3: { ko: "발견: 최근 3일", en: "Found: last 3 days" },
    since_7: { ko: "발견: 최근 7일", en: "Found: last 7 days" },
    since_30: { ko: "발견: 최근 30일", en: "Found: last 30 days" },
    since_label: { ko: "발견 시점", en: "Found within" },
    only_changed: { ko: "변경된 것만", en: "Changed only" },
    stat_found_today: { ko: "오늘 발견", en: "Found today" },
    stat_changed: { ko: "변경됨", en: "Changed" },
    badge_changed: { ko: "변경", en: "Updated" },
    change_version: { ko: "새 버전 {v}", en: "new version {v}" },
    change_updated: { ko: "업스트림 갱신", en: "updated upstream" },
    change_downloads: { ko: "다운로드 급증", en: "downloads jumped" },
    version: { ko: "버전", en: "Version" },
    readme: { ko: "모델 카드", en: "Model card" },
    show_thumbs: { ko: "썸네일", en: "Thumbnails" },
    enlarge: { ko: "크게 보기", en: "Enlarge" },
    prev_image: { ko: "이전 이미지", en: "Previous image" },
    next_image: { ko: "다음 이미지", en: "Next image" },
    image_pos: { ko: "{i}/{n}", en: "{i}/{n}" },
    close: { ko: "닫기", en: "Close" },
    open_source: { ko: "원본 페이지 열기", en: "Open source page" },
    group_none: { ko: "묶기: 없음", en: "Group: none" },
    group_category: { ko: "묶기: 용도별", en: "Group: by purpose" },
    group_base: { ko: "묶기: 베이스 모델별", en: "Group: by base model" },
    group_source: { ko: "묶기: 소스별", en: "Group: by source" },
    src_all: { ko: "전체", en: "All" },
    only_new: { ko: "신규만", en: "New only" },

    hide_nsfw: { ko: "NSFW 숨기기", en: "Hide NSFW" },
    facet_base: { ko: "베이스 모델", en: "Base model" },
    facet_cat: { ko: "용도", en: "Purpose" },
    all: { ko: "전체", en: "All" },
    tab_lora: { ko: "LoRA", en: "LoRA" },
    tab_workflow: { ko: "워크플로우", en: "Workflows" },
    stat_total: { ko: "전체", en: "Total" },
    stat_new: { ko: "신규 (최근 발견)", en: "New (recently found)" },
    stat_found: { ko: "이번 실행에서 발견", en: "Found this run" },
    stat_claude: { ko: "Claude 한글 요약", en: "Claude summaries" },
    count_of: { ko: "{n}개 표시 ({kind} {total}개 중)", en: "Showing {n} of {total} {kind}" },
    kind_lora: { ko: "LoRA", en: "LoRAs" },
    kind_workflow: { ko: "워크플로우", en: "workflows" },
    empty_filtered: { ko: "조건에 맞는 항목이 없습니다.", en: "No items match the current filters." },
    empty_loading: { ko: "데이터를 가져오는 중입니다…", en: "Fetching data…" },
    empty_none: { ko: "데이터가 없습니다. 새로고침을 눌러 주세요.", en: "No data. Press Refresh." },
    badge_new: { ko: "NEW", en: "NEW" },
    badge_found: { ko: "이번 실행 발견", en: "Found this run" },
    badge_ai: { ko: "AI 요약", en: "AI summary" },
    badge_ai_title: { ko: "Claude가 작성한 요약", en: "Summary written by Claude" },
    trigger: { ko: "트리거", en: "Trigger" },
    copy_hint: { ko: "클릭하면 복사", en: "Click to copy" },
    details: { ko: "원문 설명", en: "Original description" },
    files: { ko: "파일 {n}개", en: "{n} files" },
    files_one: { ko: "파일 1개", en: "1 file" },
    json_files: { ko: "JSON {n}개", en: "{n} JSON files" },
    json_one: { ko: "JSON 1개", en: "1 JSON file" },
    added: { ko: "등록", en: "Added" },
    updated: { ko: "수정", en: "Updated" },
    found: { ko: "발견", en: "Found" },
    downloads: { ko: "다운로드", en: "Downloads" },
    likes: { ko: "좋아요", en: "Likes" },
    stars: { ko: "스타", en: "Stars" },
    forks: { ko: "포크", en: "Forks" },
    other: { ko: "기타", en: "Other" },
    footer: { ko: "데이터: {hf} · {gh} · {cv} · 한글 요약은 규칙 기반이며 <code>ANTHROPIC_API_KEY</code> 설정 시 Claude가 더 자연스럽게 작성합니다.",
              en: "Data: {hf} · {gh} · {cv} · Summaries are rule-based; set <code>ANTHROPIC_API_KEY</code> to let Claude write better ones." },
    r_now: { ko: "방금", en: "just now" },
    r_min: { ko: "{n}분 전", en: "{n} min ago" },
    r_hour: { ko: "{n}시간 전", en: "{n} h ago" },
    r_day: { ko: "{n}일 전", en: "{n} d ago" },
    r_month: { ko: "{n}개월 전", en: "{n} mo ago" },
    r_year: { ko: "{n}년 전", en: "{n} y ago" },
  };
  function lang() { return state.filters.lang === "en" ? "en" : "ko"; }
  function t(key, vars) {
    const entry = STR[key];
    let s = entry ? (entry[lang()] || entry.ko) : key;
    if (vars) Object.keys(vars).forEach((k) => { s = s.replace(new RegExp("\\{" + k + "\\}", "g"), String(vars[k])); });
    return s;
  }
  function tm(m) {  // 백엔드 메시지 dict {ko,en} 또는 문자열
    if (m && typeof m === "object") return m[lang()] || m.ko || "";
    return m == null ? "" : String(m);
  }
  const IMAGE_HOSTS = ["image.civitai.com", "huggingface.co", "cdn-uploads.huggingface.co", "cdn-lfs.huggingface.co",
    "cdn-lfs-us-1.huggingface.co", "cdn-lfs.hf.co", "raw.githubusercontent.com", "user-images.githubusercontent.com", "github.com"];
  function safeImage(url) {
    if (typeof url !== "string" || !url.startsWith("https://")) return "";
    let host = "";
    try { host = new URL(url).hostname.toLowerCase(); } catch (e) { return ""; }
    return IMAGE_HOSTS.some((h) => host === h || host.endsWith("." + h)) ? url : "";
  }
  function safeLink(url) {
    return (typeof url === "string" && /^https?:\/\//i.test(url)) ? url : "#";
  }
  // 항목의 이미지 목록. 서버가 준 갤러리를 그릴 때 한 번 더 호스트 검사한다.
  // 이미지가 깨지면 목록에서 빼므로(onerror) 항목 객체에 붙여 두고 재사용한다.
  function galleryOf(it) {
    if (!it._gallery) {
      const raw = (Array.isArray(it.images) && it.images.length) ? it.images
        : (it.thumb ? [{ thumb: it.thumb, large: it.thumb_large }] : []);
      const seen = new Set();
      it._gallery = [];
      raw.forEach((p) => {
        const small = safeImage(p && p.thumb);
        if (!small || seen.has(small)) return;
        seen.add(small);
        it._gallery.push({ thumb: small, large: safeImage(p.large) || small });
      });
    }
    return it._gallery;
  }
  function itemOf(el) {
    const wrap = el && el.closest ? el.closest(".thumb-wrap") : null;
    return wrap ? { wrap, it: state.byKey.get(wrap.dataset.key) } : { wrap: null, it: null };
  }
  function baseLabel(v) { return lang() === "en" ? (state.labelsEn.base_models[v] || v) : v; }
  function catLabel(v) { return lang() === "en" ? (state.labelsEn.categories[v] || v) : v; }
  function summaryOf(it) { return (lang() === "en" && it.summary_en) ? it.summary_en : it.summary_ko; }

  const KINDS = [["lora", "tab_lora"], ["workflow", "tab_workflow"]];
  const SOURCES = [["all", null], ["huggingface", "Hugging Face"], ["github", "GitHub"], ["civitai", "Civitai"]];
  const SOURCE_LABEL = { huggingface: "Hugging Face", github: "GitHub", civitai: "Civitai" };
  const CAT_ORDER = ["가속 (저스텝)", "이미지 편집", "디테일 향상", "영상 모션/카메라", "캐릭터", "실사/포토",
    "의상/포즈/컨셉", "스타일/화풍", "기타", "학습 도구", "커스텀 노드", "로더/관리", "병합/변환", "자료 모음", "모델/가중치",
    "WF 이미지 생성", "WF 영상 생성", "WF 편집/인페인팅", "WF 업스케일/보정", "WF 컨트롤넷/포즈", "WF 캐릭터 일관성", "WF 학습/도구", "WF 모음/템플릿"];

  function loadPrefs(defaults) {
    try {
      const raw = localStorage.getItem("lora-news-prefs");
      if (raw) return Object.assign({}, defaults, JSON.parse(raw), { q: "" });
    } catch (e) { /* ignore */ }
    return defaults;
  }
  function savePrefs() {
    try { localStorage.setItem("lora-news-prefs", JSON.stringify(state.filters)); } catch (e) { /* ignore */ }
  }

  // ---------------------------------------------------------------- utils
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function fmtNum(n) {
    n = Number(n || 0);
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e4 ? 0 : 1) + "k";
    return String(n);
  }
  function parseDate(s) {
    if (!s) return null;
    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }
  function fmtDate(s) {
    const d = parseDate(s);
    if (!d) return "-";
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function rel(s) {
    const d = parseDate(s);
    if (!d) return "";
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return t("r_now");
    if (diff < 3600) return t("r_min", { n: Math.floor(diff / 60) });
    if (diff < 86400) return t("r_hour", { n: Math.floor(diff / 3600) });
    if (diff < 86400 * 30) return t("r_day", { n: Math.floor(diff / 86400) });
    if (diff < 86400 * 365) return t("r_month", { n: Math.floor(diff / (86400 * 30)) });
    return t("r_year", { n: Math.floor(diff / (86400 * 365)) });
  }
  function daysAgo(s, n) {
    const d = parseDate(s);
    return d && (Date.now() - d.getTime()) <= n * 86400 * 1000;
  }
  function cmpDate(a, b) { return (parseDate(a)?.getTime() || 0) - (parseDate(b)?.getTime() || 0); }
  function kindItems() { return state.items.filter((it) => (it.kind || "lora") === state.filters.kind); }

  // ---------------------------------------------------------------- data
  async function load() {
    try {
      const res = await fetch("/api/items", { cache: "no-store" });
      const data = await res.json();
      state.items = data.items || [];
      state.byKey = new Map(state.items.map((it) => [it.key, it]));
      state.labelsEn = data.labels_en || state.labelsEn;
      // demo 플래그는 응답 최상위에 온다. status 안으로 넣어 renderStatus 가 한 곳만 보게 한다.
      state.status = { ...(data.status || {}), demo: !!data.demo };
    } catch (e) {
      state.status = { last_error: t("server_unreachable") + e };
    }
    renderAll();
    schedulePoll();
  }

  async function pollStatus() {
    try {
      const res = await fetch("/api/status", { cache: "no-store" });
      const st = await res.json();
      const wasRefreshing = state.status.refreshing;
      state.status = st;
      renderStatus();
      if (wasRefreshing && !st.refreshing) { await load(); return; }
    } catch (e) { /* ignore */ }
    schedulePoll();
  }

  function schedulePoll() {
    clearTimeout(state.pollTimer);
    if (state.status.refreshing) state.pollTimer = setTimeout(pollStatus, 1500);
  }

  async function refresh() {
    const btn = $("#refresh-btn");
    btn.disabled = true;
    try {
      const res = await fetch("/api/refresh", { method: "POST" });
      const data = await res.json();
      state.status = data.status || state.status;
      state.status.refreshing = true;
      renderStatus();
      schedulePoll();
    } catch (e) {
      state.status.last_error = t("refresh_failed") + " (" + e + ")";
      renderStatus();
    } finally {
      setTimeout(() => { btn.disabled = false; }, 1500);
    }
  }

  // ---------------------------------------------------------------- filtering
  function applyFilters(except) {
    const f = state.filters;
    const q = f.q.trim().toLowerCase();
    return kindItems().filter((it) => {
      if (except !== "source" && f.source !== "all" && it.source !== f.source) return false;
      if (except !== "base" && f.base && it.base_model !== f.base) return false;
      if (except !== "cat" && f.cat && it.category !== f.cat) return false;
      if (f.onlyNew && !it.is_new) return false;
      if (f.onlyChanged && !(it.changes || []).length) return false;
      if (f.since !== "all" && !daysAgo(it.first_seen, Number(f.since))) return false;
      if (f.hideNsfw && it.nsfw) return false;
      if (q) {
        const hay = [it.name, it.author, it.summary_ko, it.summary_en, it.description, (it.tags || []).join(" "),
          (it.trigger_words || []).join(" "), it.base_model, baseLabel(it.base_model), it.category, catLabel(it.category),
          (it.hints || []).join(" ")].join(" ").toLowerCase();
        if (!q.split(/\s+/).every((w) => hay.includes(w))) return false;
      }
      return true;
    });
  }

  function hasActiveFilters() {
    const f = state.filters;
    return !!(f.q.trim() || f.source !== "all" || f.base || f.cat || f.onlyNew || f.onlyChanged || f.since !== "all");
  }

  function visibleItems() {
    const list = applyFilters(null);
    const by = {
      new: (a, b) => (b.found_this_run - a.found_this_run) || (b.is_new - a.is_new) || cmpDate(b.first_seen, a.first_seen),
      found: (a, b) => cmpDate(b.first_seen, a.first_seen),
      changed: (a, b) => ((b.changes || []).length > 0) - ((a.changes || []).length > 0) || cmpDate(b.last_change_at, a.last_change_at),
      created: (a, b) => cmpDate(b.created_at, a.created_at),
      updated: (a, b) => cmpDate(b.updated_at, a.updated_at),
      downloads: (a, b) => (b.downloads || 0) - (a.downloads || 0) || (b.likes || 0) - (a.likes || 0),
      likes: (a, b) => (b.likes || 0) - (a.likes || 0) || (b.downloads || 0) - (a.downloads || 0),
      name: (a, b) => a.name.localeCompare(b.name),
    };
    list.sort(by[state.filters.sort] || by.new);
    return list;
  }

  // ---------------------------------------------------------------- render
  function renderAll() {
    applyStatic();
    renderStatus();
    renderTabs();
    renderStats();
    renderFacets();
    renderList();
  }

  function applyStatic() {
    document.documentElement.lang = lang();
    document.title = t("title");
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    $("#lang-btn").textContent = t("lang_switch");
    $("#search").placeholder = t("search_ph");
    $("#search").setAttribute("aria-label", t("search_ph"));
    $("#sort").setAttribute("aria-label", t("sort_label"));
    $("#group").setAttribute("aria-label", t("group_label"));
    $("#tabs").setAttribute("aria-label", t("tab_label"));
    const opts = (pairs, current) => pairs.map(([v, k]) => `<option value="${v}"${v === current ? " selected" : ""}>${esc(t(k))}</option>`).join("");
    $("#sort").innerHTML = opts([["new", "sort_new"], ["found", "sort_found"], ["changed", "sort_changed"],
      ["created", "sort_created"], ["updated", "sort_updated"], ["downloads", "sort_downloads"],
      ["likes", "sort_likes"], ["name", "sort_name"]], state.filters.sort);
    $("#group").innerHTML = opts([["none", "group_none"], ["category", "group_category"], ["base_model", "group_base"],
      ["source", "group_source"]], state.filters.group);
    $("#since").innerHTML = opts([["all", "since_all"], ["1", "since_1"], ["3", "since_3"], ["7", "since_7"],
      ["30", "since_30"]], state.filters.since);
    $("#since").setAttribute("aria-label", t("since_label"));
    const link = (url, label) => `<a href="${url}" target="_blank" rel="noopener">${label}</a>`;
    $("#footer").innerHTML = t("footer", {
      hf: link("https://huggingface.co/models?other=lora", "Hugging Face"),
      gh: link("https://github.com/search?q=comfyui+lora", "GitHub"),
      cv: link("https://civitai.com/models?types=LORA", "Civitai"),
    });
  }

  function renderStatus() {
    const st = state.status || {};
    const el = $("#status-text");
    if (st.refreshing) {
      el.textContent = tm(st.progress) || t("refreshing");
      el.classList.add("busy");
    } else {
      el.classList.remove("busy");
      let text;
      if (st.last_refresh === "demo") text = t("demo");
      else if (st.last_refresh) text = t("last_update") + " " + rel(st.last_refresh) + " (" + new Date(st.last_refresh).toLocaleString(lang() === "en" ? "en-US" : "ko-KR") + ")";
      else text = t("no_data_yet");
      const c = st.claude || {};
      el.textContent = text + (c.enabled ? " · " + t("claude_on") : "");
    }
    const errs = [];
    if (st.last_error) errs.push(t("error_prefix") + tm(st.last_error));
    (st.errors || []).forEach((e) => errs.push("· " + tm(e)));
    if (st.claude && st.claude.enabled && st.claude.reason) errs.push("· " + t("claude_unavailable") + tm(st.claude.reason));
    const box = $("#errors");
    box.hidden = errs.length === 0;
    box.textContent = errs.join("\n");
    const btn = $("#refresh-btn");
    btn.disabled = !!st.refreshing || !!st.demo;
    btn.title = st.demo ? t("demo_hint") : "";
    btn.textContent = st.refreshing ? t("refreshing") : t("refresh");
  }

  function renderTabs() {
    const counts = {};
    state.items.forEach((it) => { const k = it.kind || "lora"; counts[k] = (counts[k] || 0) + 1; });
    $("#tabs").innerHTML = KINDS.map(([k, key]) =>
      `<button type="button" role="tab" class="tab" aria-selected="${state.filters.kind === k ? "true" : "false"}" ` +
      `data-kind="${k}">${esc(t(key))}<small>${counts[k] || 0}</small></button>`
    ).join("");
  }

  function renderStats() {
    const items = kindItems();
    const n = (fn) => items.filter(fn).length;
    const cells = [
      [t("stat_total"), items.length, ""],
      [t("stat_new"), n((it) => it.is_new), "new"],
      // "이번 실행 발견"은 cron 이 대신 실행하면 0이 된다. 시각 기준이라야 언제 열어도 맞다.
      [t("stat_found_today"), n((it) => daysAgo(it.first_seen, 1)), "found"],
      [t("stat_changed"), n((it) => (it.changes || []).length), "changed"],
    ];
    const claude = n((it) => it.summary_source === "claude");
    if (claude) cells.push([t("stat_claude"), claude, ""]);
    $("#stats").innerHTML = cells.map(([l, v, cls]) => `<div class="stat ${cls}"><b>${esc(v)}</b><span>${esc(l)}</span></div>`).join("");
  }

  function chip(label, count, active, attr) {
    const empty = count === 0 ? " empty" : "";
    return `<button type="button" class="chip${empty}" aria-pressed="${active ? "true" : "false"}" ${attr}>` +
      `${esc(label)}${count != null ? `<small>${esc(count)}</small>` : ""}</button>`;
  }

  function facetCounts(items, field) {
    const m = new Map();
    items.forEach((it) => { const k = it[field] || "기타"; m.set(k, (m.get(k) || 0) + 1); });
    return Array.from(m.entries());
  }

  function renderFacets() {
    const f = state.filters;
    // 각 필터의 개수는 "그 필터를 뺀 나머지 조건"을 적용한 결과에서 센다.
    // 그래야 칩에 적힌 숫자가 실제로 눌렀을 때 나오는 개수와 같다.
    const forSource = applyFilters("source");
    const counts = { all: forSource.length };
    forSource.forEach((it) => { counts[it.source] = (counts[it.source] || 0) + 1; });
    $("#source-chips").innerHTML = SOURCES.map(([k, l]) => chip(l || t("src_all"), counts[k] || 0, f.source === k, `data-source="${k}"`)).join("");

    const forBase = applyFilters("base");
    const bases = facetCounts(forBase, "base_model").sort((a, b) => b[1] - a[1]);
    $("#base-chips").innerHTML = chip(t("all"), forBase.length, !f.base, `data-base=""`) +
      bases.map(([b, n]) => chip(baseLabel(b), n, f.base === b, `data-base="${esc(b)}"`)).join("");

    const forCat = applyFilters("cat");
    const cats = facetCounts(forCat, "category").sort((a, b) => CAT_ORDER.indexOf(a[0]) - CAT_ORDER.indexOf(b[0]));
    $("#cat-chips").innerHTML = chip(t("all"), forCat.length, !f.cat, `data-cat=""`) +
      cats.map(([c, n]) => chip(catLabel(c), n, f.cat === c, `data-cat="${esc(c)}"`)).join("");

    $("#clear-btn").hidden = !hasActiveFilters();

    $("#search").value = f.q;
    $("#only-new").checked = f.onlyNew;
    $("#only-changed").checked = f.onlyChanged;
    $("#show-thumbs").checked = f.thumbs;
    $("#since").value = f.since;
    $("#hide-nsfw").checked = f.hideNsfw;
    $("#sort").value = f.sort;
    $("#group").value = f.group;
  }

  function sourceBadge(it) {
    if (it.source === "huggingface") return `<span class="badge hf">HF</span>`;
    if (it.source === "civitai") return `<span class="badge cv">Civitai</span>`;
    return `<span class="badge gh">GitHub</span>`;
  }

  function metric(icon, label, value) {
    return `<span aria-label="${esc(label)}: ${esc(fmtNum(value))}" title="${esc(label)}">` +
      `<span aria-hidden="true">${icon}</span> ${esc(fmtNum(value))}</span>`;
  }

  function metrics(it) {
    if (it.source === "github") return metric("★", t("stars"), it.likes) + metric("⑂", t("forks"), it.downloads);
    return metric("⬇", t("downloads"), it.downloads) + metric("♥", t("likes"), it.likes);
  }

  // 썸네일 블록. 여러 장이면 좌우 버튼과 장수 표시가 붙고, 방향키·스와이프로도 넘길 수 있다.
  // <img> 는 한 개뿐이라 현재 장만 내려받는다. 나머지는 넘길 때 받는다.
  function thumbBlock(it, g) {
    const p = g[0];
    const multi = g.length > 1;
    const nav = multi
      ? `<button type="button" class="thumb-nav prev" data-dir="-1" aria-label="${t("prev_image")}" title="${t("prev_image")}">‹</button>` +
        `<button type="button" class="thumb-nav next" data-dir="1" aria-label="${t("next_image")}" title="${t("next_image")}">›</button>` +
        `<span class="thumb-count" aria-live="polite">${t("image_pos", { i: 1, n: g.length })}</span>`
      : "";
    return `<div class="thumb-wrap${multi ? " multi" : ""}" data-key="${esc(it.key)}" data-index="0">` +
      `<button type="button" class="thumb-btn" data-large="${esc(p.large)}" title="${t("enlarge")}">` +
      `<img class="thumb" src="${esc(p.thumb)}" alt="${esc(t("preview_of", { name: it.name }))}" loading="lazy" decoding="async" fetchpriority="low" referrerpolicy="no-referrer" draggable="false"></button>${nav}</div>`;
  }
  // 카드의 썸네일을 index 번째 장으로 바꾼다. 범위를 넘으면 반대쪽으로 이어진다.
  function showImage(wrap, index) {
    const it = state.byKey.get(wrap.dataset.key);
    const g = it ? galleryOf(it) : [];
    if (!g.length) { wrap.remove(); return -1; }
    const i = ((index % g.length) + g.length) % g.length;
    wrap.dataset.index = String(i);
    const img = wrap.querySelector(".thumb");
    const btn = wrap.querySelector(".thumb-btn");
    if (img && img.getAttribute("src") !== g[i].thumb) img.src = g[i].thumb;
    if (btn) btn.dataset.large = g[i].large;
    const count = wrap.querySelector(".thumb-count");
    if (count) count.textContent = t("image_pos", { i: i + 1, n: g.length });
    if (g.length < 2) {
      wrap.classList.remove("multi");
      wrap.querySelectorAll(".thumb-nav, .thumb-count").forEach((n) => n.remove());
    }
    return i;
  }
  // 깨진 이미지는 갤러리에서 빼고 다음 장을 보인다. 전부 깨지면 블록을 없앤다.
  function dropBrokenImage(img) {
    const { wrap, it } = itemOf(img);
    if (!wrap) return;
    if (!it) { wrap.remove(); return; }
    const g = galleryOf(it);
    const bad = img.getAttribute("src");
    const idx = g.findIndex((p) => p.thumb === bad);
    if (idx >= 0) g.splice(idx, 1);
    if (!g.length) { wrap.remove(); if (lb.key === it.key) closeLightbox(); return; }
    showImage(wrap, idx >= 0 ? idx : 0);
  }
  // 가로 스와이프(터치·마우스 드래그). 세로 스크롤은 브라우저에 맡긴다(touch-action: pan-y).
  function attachSwipe(root, selector, onSwipe) {
    let start = null;
    root.addEventListener("pointerdown", (e) => {
      if (e.pointerType === "mouse" && e.button !== 0) return;
      const target = e.target.closest(selector);
      if (!target) return;
      start = { x: e.clientX, y: e.clientY, target, at: Date.now() };
    });
    root.addEventListener("pointerup", (e) => {
      if (!start) return;
      const s0 = start;
      start = null;
      const dx = e.clientX - s0.x, dy = e.clientY - s0.y;
      if (Math.abs(dx) < 40 || Math.abs(dx) < Math.abs(dy) * 1.5 || Date.now() - s0.at > 1000) return;
      s0.target.dataset.swiped = "1";           // 곧 따라오는 click 으로 확대창이 열리지 않게
      setTimeout(() => { delete s0.target.dataset.swiped; }, 400);
      onSwipe(s0.target, dx < 0 ? 1 : -1);
    });
    root.addEventListener("pointercancel", () => { start = null; });
  }

  function card(it) {
    const isWf = (it.kind || "lora") === "workflow";
    const triggers = (it.trigger_words || []).length
      ? `<div class="triggers">${t("trigger")} ${it.trigger_words.map((w) => `<button type="button" class="trigger" data-copy="${esc(w)}" title="${t("copy_hint")}">${esc(w)}</button>`).join("")}</div>`
      : "";
    const files = (it.files || []).length
      ? `<div class="files">${it.files.map((f) => `<code>${esc(f)}</code>`).join("")}</div>` : "";
    const desc = (it.description || "").trim();
    const readme = (it.readme_excerpt || "").trim();
    const changes = it.changes || [];
    const changeText = changes.map((c) => t({ version: "change_version", updated: "change_updated",
                                              downloads: "change_downloads" }[c] || "change_updated",
                                             { v: it.version || "?" })).join(", ");
    const nFiles = (it.files || []).length;
    const fileKey = isWf ? (nFiles === 1 ? "json_one" : "json_files") : (nFiles === 1 ? "files_one" : "files");
    const fileLabel = nFiles ? " · " + t(fileKey, { n: nFiles }) : "";
    const details = (desc || readme || files)
      ? `<details><summary>${t("details")}${fileLabel}</summary>` +
        `${readme ? `<p><b>${t("readme")}</b><br>${esc(readme)}</p>` : ""}` +
        `${desc ? `<p>${esc(desc)}</p>` : ""}${files}</details>`
      : "";
    const gallery = state.filters.thumbs ? galleryOf(it) : [];
    const thumb = gallery.length ? thumbBlock(it, gallery) : "";
    return `<article class="card${it.is_new ? " new" : ""}">
      ${thumb}
      <div class="card-top">
        <div class="badges">
          ${sourceBadge(it)}
          ${isWf ? `<span class="badge wf">WF</span>` : ""}
          ${it.found_this_run ? `<span class="badge found">${t("badge_found")}</span>` : (it.is_new ? `<span class="badge new">${t("badge_new")}</span>` : "")}
          ${changes.length ? `<span class="badge changed" title="${esc(changeText)}">${t("badge_changed")}</span>` : ""}
          ${it.nsfw ? `<span class="badge nsfw">NSFW</span>` : ""}
          ${it.summary_source === "claude" ? `<span class="badge claude" title="${t("badge_ai_title")}">${t("badge_ai")}</span>` : ""}
        </div>
        <div class="metrics">${metrics(it)}</div>
      </div>
      <div class="title"><a href="${esc(safeLink(it.url))}" target="_blank" rel="noopener">${esc(it.name)}</a></div>
      <div class="author">${esc(it.author)}${it.pipeline && !isWf ? " · " + esc(it.pipeline) : ""}</div>
      <div class="tags"><span class="tag base">${esc(baseLabel(it.base_model))}</span><span class="tag cat">${esc(catLabel(it.category))}</span>${it.version ? `<span class="tag ver">${esc(it.version)}</span>` : ""}${(it.tags || []).slice(0, 4).map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>
      <div class="summary">${esc(summaryOf(it))}</div>
      ${triggers}
      ${details}
      <div class="dates"><span>${t("added")} ${fmtDate(it.created_at)}</span><span>${t("updated")} ${fmtDate(it.updated_at)} (${rel(it.updated_at)})</span>${it.first_seen && it.first_seen !== it.created_at ? `<span>${t("found")} ${fmtDate(it.first_seen)}</span>` : ""}</div>
    </article>`;
  }

  function renderList() {
    const list = visibleItems();
    const f = state.filters;
    const total = kindItems().length;
    $("#result-count").textContent = t("count_of", { n: list.length, total, kind: t(f.kind === "workflow" ? "kind_workflow" : "kind_lora") });
    if (!list.length) {
      const rescue = hasActiveFilters() ? `<button type="button" class="btn ghost" data-clear>${esc(t("clear_filters"))}</button>` : "";
      $("#list").className = "list";
      $("#list").innerHTML = `<div class="empty-state"><span>${total ? t("empty_filtered") : (state.status.refreshing ? t("empty_loading") : t("empty_none"))}</span>${rescue}</div>`;
      return;
    }
    if (f.group === "none") {
      $("#list").className = "list";
      $("#list").innerHTML = list.map(card).join("");
      return;
    }
    const groups = new Map();
    list.forEach((it) => {
      let k;
      if (f.group === "source") k = SOURCE_LABEL[it.source] || it.source;
      else if (f.group === "category") k = it.category || "기타";
      else k = it.base_model || "기타";
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(it);
    });
    const keys = Array.from(groups.keys());
    if (f.group === "category") keys.sort((a, b) => CAT_ORDER.indexOf(a) - CAT_ORDER.indexOf(b));
    else keys.sort((a, b) => groups.get(b).length - groups.get(a).length);
    const labelOf = (k) => f.group === "category" ? catLabel(k) : (f.group === "base_model" ? baseLabel(k) : k);
    $("#list").className = "list grouped";
    $("#list").innerHTML = keys.map((k) =>
      `<section class="group"><h2 class="group-title">${esc(labelOf(k))}<small>${groups.get(k).length}</small></h2>` +
      `<div class="group-grid">${groups.get(k).map(card).join("")}</div></section>`
    ).join("");
  }

  // ---------------------------------------------------------------- events
  // ---------------------------------------------------------------- lightbox
  let lastFocus = null;
  const lb = { key: null, index: 0, wrap: null };
  function openLightbox(wrap) {
    const it = state.byKey.get(wrap.dataset.key);
    if (!it || !galleryOf(it).length) return;
    lastFocus = document.activeElement;
    lb.key = it.key;
    lb.wrap = wrap;
    $("#lightbox-name").textContent = it.name;
    const url = safeLink(it.url);
    $("#lightbox-link").href = url;
    $("#lightbox-link").hidden = url === "#";
    $("#lightbox-prev").setAttribute("aria-label", t("prev_image"));
    $("#lightbox-next").setAttribute("aria-label", t("next_image"));
    $("#lightbox").hidden = false;
    document.body.classList.add("no-scroll");
    lightboxShow(parseInt(wrap.dataset.index, 10) || 0);
    $("#lightbox-close").focus();
  }
  function lightboxShow(index) {
    const it = state.byKey.get(lb.key);
    const g = it ? galleryOf(it) : [];
    if (!g.length) { closeLightbox(); return; }
    const i = ((index % g.length) + g.length) % g.length;
    lb.index = i;
    const img = $("#lightbox-img");
    img.src = "";
    img.alt = t("preview_of", { name: it.name });
    img.src = g[i].large;            // 큰 이미지는 보는 장만 받는다. 옆 장은 미리 받지 않는다.
    const multi = g.length > 1;
    $("#lightbox-count").textContent = multi ? t("image_pos", { i: i + 1, n: g.length }) : "";
    $("#lightbox-prev").hidden = !multi;
    $("#lightbox-next").hidden = !multi;
    if (lb.wrap && lb.wrap.isConnected) showImage(lb.wrap, i);   // 닫았을 때 카드도 같은 장을 보이게
  }
  function lightboxStep(dir) {
    if ($("#lightbox").hidden) return;
    lightboxShow(lb.index + dir);
  }
  function closeLightbox() {
    const box = $("#lightbox");
    if (box.hidden) return;
    box.hidden = true;
    $("#lightbox-img").src = "";
    lb.key = null;
    lb.wrap = null;
    document.body.classList.remove("no-scroll");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function clearFilters() {
    Object.assign(state.filters, { q: "", source: "all", base: null, cat: null, onlyNew: false,
                                   onlyChanged: false, since: "all" });
    savePrefs();
    renderFacets();
    renderList();
    $("#search").focus();
  }

  function bind() {
    $("#refresh-btn").addEventListener("click", refresh);
    $("#clear-btn").addEventListener("click", clearFilters);
    $("#lang-btn").addEventListener("click", () => {
      state.filters.lang = lang() === "ko" ? "en" : "ko";
      savePrefs(); renderAll();
    });
    $("#tabs").addEventListener("click", (e) => {
      const el = e.target.closest("[data-kind]"); if (!el) return;
      if (state.filters.kind === el.dataset.kind) return;
      state.filters.kind = el.dataset.kind;
      state.filters.base = null; state.filters.cat = null;   // 종류별로 다른 분류이므로 초기화
      savePrefs(); renderAll();
    });
    let timer = null;
    $("#search").addEventListener("input", (e) => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.filters.q = e.target.value; renderFacets(); renderList(); }, 120);
    });
    $("#sort").addEventListener("change", (e) => { state.filters.sort = e.target.value; savePrefs(); renderList(); });
    $("#group").addEventListener("change", (e) => { state.filters.group = e.target.value; savePrefs(); renderList(); });
    $("#only-new").addEventListener("change", (e) => { state.filters.onlyNew = e.target.checked; savePrefs(); renderFacets(); renderList(); });
    $("#only-changed").addEventListener("change", (e) => { state.filters.onlyChanged = e.target.checked; savePrefs(); renderFacets(); renderList(); });
    $("#since").addEventListener("change", (e) => { state.filters.since = e.target.value; savePrefs(); renderFacets(); renderList(); });
    $("#hide-nsfw").addEventListener("change", (e) => { state.filters.hideNsfw = e.target.checked; savePrefs(); renderList(); });
    $("#source-chips").addEventListener("click", (e) => {
      const el = e.target.closest("[data-source]"); if (!el) return;
      state.filters.source = el.dataset.source; savePrefs(); renderFacets(); renderList();
    });
    $("#base-chips").addEventListener("click", (e) => {
      const el = e.target.closest("[data-base]"); if (!el) return;
      state.filters.base = el.dataset.base || null; savePrefs(); renderFacets(); renderList();
    });
    $("#cat-chips").addEventListener("click", (e) => {
      const el = e.target.closest("[data-cat]"); if (!el) return;
      state.filters.cat = el.dataset.cat || null; savePrefs(); renderFacets(); renderList();
    });
    $("#show-thumbs").addEventListener("change", (e) => { state.filters.thumbs = e.target.checked; savePrefs(); renderList(); });
    $("#lightbox").addEventListener("click", (e) => {
      const nav = e.target.closest(".lightbox-nav");
      if (nav) { lightboxStep(parseInt(nav.dataset.dir, 10) || 1); return; }
      if (e.target.closest("[data-swiped]")) return;
      if (e.target === e.currentTarget || e.target.closest("[data-close]")) closeLightbox();
    });
    $("#lightbox-img").addEventListener("error", () => {
      const it = state.byKey.get(lb.key);
      if (!it) return;
      const g = galleryOf(it);
      const bad = $("#lightbox-img").getAttribute("src");
      const idx = g.findIndex((p) => p.large === bad);
      if (idx >= 0) g.splice(idx, 1);
      if (!g.length) { closeLightbox(); if (lb.wrap) lb.wrap.remove(); return; }
      lightboxShow(idx >= 0 ? idx : 0);
    });
    attachSwipe($("#lightbox"), ".lightbox-stage", (_, dir) => lightboxStep(dir));
    attachSwipe($("#list"), ".thumb-wrap", (wrap, dir) => showImage(wrap, (parseInt(wrap.dataset.index, 10) || 0) + dir));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { closeLightbox(); return; }
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      const dir = e.key === "ArrowLeft" ? -1 : 1;
      if (!$("#lightbox").hidden) { e.preventDefault(); lightboxStep(dir); return; }
      const { wrap } = itemOf(e.target);
      if (wrap && wrap.classList.contains("multi")) {
        e.preventDefault();
        showImage(wrap, (parseInt(wrap.dataset.index, 10) || 0) + dir);
      }
    });
    // <img> 의 error 는 버블링하지 않으므로 캡처 단계에서 받는다
    $("#list").addEventListener("error", (e) => {
      if (e.target && e.target.classList && e.target.classList.contains("thumb")) dropBrokenImage(e.target);
    }, true);
    $("#list").addEventListener("click", async (e) => {
      if (e.target.closest("[data-clear]")) { clearFilters(); return; }
      const nav = e.target.closest(".thumb-nav");
      if (nav) {
        const { wrap } = itemOf(nav);
        if (wrap) showImage(wrap, (parseInt(wrap.dataset.index, 10) || 0) + (parseInt(nav.dataset.dir, 10) || 1));
        return;
      }
      const tb = e.target.closest(".thumb-btn");
      if (tb) {
        const { wrap } = itemOf(tb);
        if (wrap && !wrap.dataset.swiped) openLightbox(wrap);
        return;
      }
      const el = e.target.closest("[data-copy]"); if (!el) return;
      try {
        await navigator.clipboard.writeText(el.dataset.copy);
        el.classList.add("copied");
        setTimeout(() => el.classList.remove("copied"), 900);
      } catch (err) { /* clipboard unavailable */ }
    });
  }

  if (window.matchMedia("(max-width: 720px)").matches) $("#facets").open = false;
  bind();
  applyStatic();
  $("#status-text").textContent = t("loading");
  load();
})();
