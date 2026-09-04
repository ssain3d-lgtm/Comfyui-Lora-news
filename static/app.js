/* LoRA 뉴스 프론트엔드 (의존성 없음) — 한/영 전환 지원 */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const state = {
    items: [],
    labelsEn: { base_models: {}, categories: {} },
    status: {},
    filters: loadPrefs({
      lang: "ko", kind: "lora", q: "", source: "all", base: null, cat: null,
      onlyNew: false, recent7: false, hideNsfw: true, sort: "new", group: "none",
    }),
    pollTimer: null,
  };

  // ---------------------------------------------------------------- i18n
  const STR = {
    title: { ko: "LoRA 뉴스", en: "LoRA News" },
    subtitle: { ko: "ComfyUI용 LoRA · 워크플로우 — Hugging Face + GitHub + Civitai 신규/기존 모아보기",
                en: "LoRAs and workflows for ComfyUI — new and existing, from Hugging Face + GitHub + Civitai" },
    refresh: { ko: "새로고침", en: "Refresh" },
    lang_switch: { ko: "EN", en: "한국어" },
    loading: { ko: "불러오는 중…", en: "Loading…" },
    refreshing: { ko: "새로고침 중…", en: "Refreshing…" },
    demo: { ko: "데모 데이터", en: "Demo data" },
    last_update: { ko: "마지막 업데이트", en: "Last update" },
    no_data_yet: { ko: "아직 데이터 없음", en: "No data yet" },
    claude_on: { ko: "Claude 요약 켜짐", en: "Claude summaries on" },
    error_prefix: { ko: "오류: ", en: "Error: " },
    claude_unavailable: { ko: "Claude 요약 사용 불가: ", en: "Claude summaries unavailable: " },
    server_unreachable: { ko: "서버에 연결할 수 없습니다: ", en: "Cannot reach the server: " },
    refresh_failed: { ko: "새로고침 요청 실패: ", en: "Refresh request failed: " },
    search_ph: { ko: "검색: 이름, 태그, 설명, 트리거 워드…", en: "Search: name, tags, description, trigger words…" },
    sort_new: { ko: "신규 우선", en: "New first" },
    sort_created: { ko: "등록일 최신순", en: "Newest added" },
    sort_updated: { ko: "수정일 최신순", en: "Recently updated" },
    sort_downloads: { ko: "다운로드 많은순", en: "Most downloads" },
    sort_likes: { ko: "좋아요/스타 많은순", en: "Most likes / stars" },
    sort_name: { ko: "이름순", en: "Name" },
    group_none: { ko: "묶기: 없음", en: "Group: none" },
    group_category: { ko: "묶기: 용도별", en: "Group: by purpose" },
    group_base: { ko: "묶기: 베이스 모델별", en: "Group: by base model" },
    group_source: { ko: "묶기: 소스별", en: "Group: by source" },
    src_all: { ko: "전체", en: "All" },
    only_new: { ko: "신규만", en: "New only" },
    recent7: { ko: "최근 7일 등록", en: "Added in last 7 days" },
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
      state.labelsEn = data.labels_en || state.labelsEn;
      state.status = data.status || {};
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
      state.status.last_error = t("refresh_failed") + e;
      renderStatus();
    } finally {
      setTimeout(() => { btn.disabled = false; }, 1500);
    }
  }

  // ---------------------------------------------------------------- filtering
  function visibleItems() {
    const f = state.filters;
    const q = f.q.trim().toLowerCase();
    const list = kindItems().filter((it) => {
      if (f.source !== "all" && it.source !== f.source) return false;
      if (f.base && it.base_model !== f.base) return false;
      if (f.cat && it.category !== f.cat) return false;
      if (f.onlyNew && !it.is_new) return false;
      if (f.recent7 && !daysAgo(it.created_at, 7)) return false;
      if (f.hideNsfw && it.nsfw) return false;
      if (q) {
        const hay = [it.name, it.author, it.summary_ko, it.summary_en, it.description, (it.tags || []).join(" "),
          (it.trigger_words || []).join(" "), it.base_model, baseLabel(it.base_model), it.category, catLabel(it.category),
          (it.hints || []).join(" ")].join(" ").toLowerCase();
        if (!q.split(/\s+/).every((w) => hay.includes(w))) return false;
      }
      return true;
    });
    const by = {
      new: (a, b) => (b.found_this_run - a.found_this_run) || (b.is_new - a.is_new) || cmpDate(b.created_at, a.created_at),
      created: (a, b) => cmpDate(b.created_at, a.created_at),
      updated: (a, b) => cmpDate(b.updated_at, a.updated_at),
      downloads: (a, b) => (b.downloads || 0) - (a.downloads || 0) || (b.likes || 0) - (a.likes || 0),
      likes: (a, b) => (b.likes || 0) - (a.likes || 0) || (b.downloads || 0) - (a.downloads || 0),
      name: (a, b) => a.name.localeCompare(b.name),
    };
    list.sort(by[f.sort] || by.new);
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
    const opts = (pairs, current) => pairs.map(([v, k]) => `<option value="${v}"${v === current ? " selected" : ""}>${esc(t(k))}</option>`).join("");
    $("#sort").innerHTML = opts([["new", "sort_new"], ["created", "sort_created"], ["updated", "sort_updated"],
      ["downloads", "sort_downloads"], ["likes", "sort_likes"], ["name", "sort_name"]], state.filters.sort);
    $("#group").innerHTML = opts([["none", "group_none"], ["category", "group_category"], ["base_model", "group_base"],
      ["source", "group_source"]], state.filters.group);
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
    $("#refresh-btn").disabled = !!st.refreshing;
  }

  function renderTabs() {
    const counts = {};
    state.items.forEach((it) => { const k = it.kind || "lora"; counts[k] = (counts[k] || 0) + 1; });
    $("#tabs").innerHTML = KINDS.map(([k, key]) =>
      `<button class="tab${state.filters.kind === k ? " active" : ""}" data-kind="${k}">${esc(t(key))}<small>${counts[k] || 0}</small></button>`
    ).join("");
  }

  function renderStats() {
    const items = kindItems();
    const n = (fn) => items.filter(fn).length;
    const cells = [
      [t("stat_total"), items.length, ""],
      [t("stat_new"), n((it) => it.is_new), "new"],
      [t("stat_found"), n((it) => it.found_this_run), "found"],
      ["Hugging Face", n((it) => it.source === "huggingface"), ""],
      ["GitHub", n((it) => it.source === "github"), ""],
      ["Civitai", n((it) => it.source === "civitai"), ""],
    ];
    const claude = n((it) => it.summary_source === "claude");
    if (claude) cells.push([t("stat_claude"), claude, ""]);
    $("#stats").innerHTML = cells.map(([l, v, cls]) => `<div class="stat ${cls}"><b>${esc(v)}</b><span>${esc(l)}</span></div>`).join("");
  }

  function chip(label, count, active, attr) {
    return `<span class="chip${active ? " active" : ""}" ${attr}>${esc(label)}${count != null ? `<small>${esc(count)}</small>` : ""}</span>`;
  }

  function facetCounts(items, field) {
    const m = new Map();
    items.forEach((it) => { const k = it[field] || "기타"; m.set(k, (m.get(k) || 0) + 1); });
    return Array.from(m.entries());
  }

  function renderFacets() {
    const f = state.filters;
    const items = kindItems();
    const counts = { all: items.length };
    items.forEach((it) => { counts[it.source] = (counts[it.source] || 0) + 1; });
    $("#source-chips").innerHTML = SOURCES.map(([k, l]) => chip(l || t("src_all"), counts[k] || 0, f.source === k, `data-source="${k}"`)).join("");

    const bases = facetCounts(items, "base_model").sort((a, b) => b[1] - a[1]);
    $("#base-chips").innerHTML = chip(t("all"), null, !f.base, `data-base=""`) +
      bases.map(([b, n]) => chip(baseLabel(b), n, f.base === b, `data-base="${esc(b)}"`)).join("");

    const cats = facetCounts(items, "category").sort((a, b) => CAT_ORDER.indexOf(a[0]) - CAT_ORDER.indexOf(b[0]));
    $("#cat-chips").innerHTML = chip(t("all"), null, !f.cat, `data-cat=""`) +
      cats.map(([c, n]) => chip(catLabel(c), n, f.cat === c, `data-cat="${esc(c)}"`)).join("");

    $("#search").value = f.q;
    $("#only-new").checked = f.onlyNew;
    $("#recent7").checked = f.recent7;
    $("#hide-nsfw").checked = f.hideNsfw;
    $("#sort").value = f.sort;
    $("#group").value = f.group;
  }

  function sourceBadge(it) {
    if (it.source === "huggingface") return `<span class="badge hf">HF</span>`;
    if (it.source === "civitai") return `<span class="badge cv">Civitai</span>`;
    return `<span class="badge gh">GitHub</span>`;
  }

  function metrics(it) {
    if (it.source === "github") return `<span title="${t("stars")}">★ ${fmtNum(it.likes)}</span><span title="${t("forks")}">⑂ ${fmtNum(it.downloads)}</span>`;
    if (it.source === "civitai") return `<span title="${t("downloads")}">⬇ ${fmtNum(it.downloads)}</span><span title="${t("likes")}">👍 ${fmtNum(it.likes)}</span>`;
    return `<span title="${t("downloads")}">⬇ ${fmtNum(it.downloads)}</span><span title="${t("likes")}">♥ ${fmtNum(it.likes)}</span>`;
  }

  function card(it) {
    const isWf = (it.kind || "lora") === "workflow";
    const triggers = (it.trigger_words || []).length
      ? `<div class="triggers">${t("trigger")} ${it.trigger_words.map((w) => `<span class="trigger" data-copy="${esc(w)}" title="${t("copy_hint")}">${esc(w)}</span>`).join("")}</div>`
      : "";
    const files = (it.files || []).length
      ? `<div class="files">${it.files.map((f) => `<code>${esc(f)}</code>`).join("")}</div>` : "";
    const desc = (it.description || "").trim();
    const nFiles = (it.files || []).length;
    const fileKey = isWf ? (nFiles === 1 ? "json_one" : "json_files") : (nFiles === 1 ? "files_one" : "files");
    const fileLabel = nFiles ? " · " + t(fileKey, { n: nFiles }) : "";
    const details = (desc || files)
      ? `<details><summary>${t("details")}${fileLabel}</summary>${desc ? `<p>${esc(desc)}</p>` : ""}${files}</details>`
      : "";
    return `<article class="card${it.is_new ? " new" : ""}">
      <div class="card-top">
        <div class="badges">
          ${sourceBadge(it)}
          ${isWf ? `<span class="badge wf">WF</span>` : ""}
          ${it.found_this_run ? `<span class="badge found">${t("badge_found")}</span>` : (it.is_new ? `<span class="badge new">${t("badge_new")}</span>` : "")}
          ${it.nsfw ? `<span class="badge nsfw">NSFW</span>` : ""}
          ${it.summary_source === "claude" ? `<span class="badge claude" title="${t("badge_ai_title")}">${t("badge_ai")}</span>` : ""}
        </div>
        <div class="metrics">${metrics(it)}</div>
      </div>
      <div class="title"><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.name)}</a></div>
      <div class="author">${esc(it.author)}${it.pipeline && !isWf ? " · " + esc(it.pipeline) : ""}</div>
      <div class="tags"><span class="tag base">${esc(baseLabel(it.base_model))}</span><span class="tag cat">${esc(catLabel(it.category))}</span>${(it.tags || []).slice(0, 4).map((x) => `<span class="tag">${esc(x)}</span>`).join("")}</div>
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
      $("#list").innerHTML = `<div class="empty">${total ? t("empty_filtered") : (state.status.refreshing ? t("empty_loading") : t("empty_none"))}</div>`;
      return;
    }
    if (f.group === "none") {
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
    $("#list").innerHTML = keys.map((k) =>
      `<h2 class="group-title">${esc(labelOf(k))}<small>${groups.get(k).length}</small></h2>` + groups.get(k).map(card).join("")
    ).join("");
  }

  // ---------------------------------------------------------------- events
  function bind() {
    $("#refresh-btn").addEventListener("click", refresh);
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
      timer = setTimeout(() => { state.filters.q = e.target.value; renderList(); }, 120);
    });
    $("#sort").addEventListener("change", (e) => { state.filters.sort = e.target.value; savePrefs(); renderList(); });
    $("#group").addEventListener("change", (e) => { state.filters.group = e.target.value; savePrefs(); renderList(); });
    $("#only-new").addEventListener("change", (e) => { state.filters.onlyNew = e.target.checked; savePrefs(); renderList(); });
    $("#recent7").addEventListener("change", (e) => { state.filters.recent7 = e.target.checked; savePrefs(); renderList(); });
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
    $("#list").addEventListener("click", async (e) => {
      const el = e.target.closest("[data-copy]"); if (!el) return;
      try {
        await navigator.clipboard.writeText(el.dataset.copy);
        el.classList.add("copied");
        setTimeout(() => el.classList.remove("copied"), 900);
      } catch (err) { /* clipboard unavailable */ }
    });
  }

  bind();
  applyStatic();
  $("#status-text").textContent = t("loading");
  load();
})();
