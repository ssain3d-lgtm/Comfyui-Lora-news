/* LoRA 뉴스 프론트엔드 (의존성 없음) */
(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const state = {
    items: [],
    facets: { base_models: [], categories: [] },
    status: {},
    filters: loadPrefs({
      q: "", source: "all", base: null, cat: null,
      onlyNew: false, recent7: false, hideNsfw: true, sort: "new", group: "none",
    }),
    pollTimer: null,
  };

  const CAT_ORDER = ["가속 (저스텝)", "이미지 편집", "디테일 향상", "영상 모션/카메라", "캐릭터", "실사/포토",
    "의상/포즈/컨셉", "스타일/화풍", "기타", "학습 도구", "커스텀 노드", "로더/관리", "병합/변환", "워크플로우/모음", "모델/가중치"];

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
    if (diff < 60) return "방금";
    if (diff < 3600) return Math.floor(diff / 60) + "분 전";
    if (diff < 86400) return Math.floor(diff / 3600) + "시간 전";
    if (diff < 86400 * 30) return Math.floor(diff / 86400) + "일 전";
    if (diff < 86400 * 365) return Math.floor(diff / (86400 * 30)) + "개월 전";
    return Math.floor(diff / (86400 * 365)) + "년 전";
  }
  function daysAgo(s, n) {
    const d = parseDate(s);
    return d && (Date.now() - d.getTime()) <= n * 86400 * 1000;
  }

  // ---------------------------------------------------------------- data
  async function load() {
    try {
      const res = await fetch("/api/items", { cache: "no-store" });
      const data = await res.json();
      state.items = data.items || [];
      state.facets = data.facets || state.facets;
      state.status = data.status || {};
    } catch (e) {
      state.status = { last_error: "서버에 연결할 수 없습니다: " + e };
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
      state.status.last_error = "새로고침 요청 실패: " + e;
      renderStatus();
    } finally {
      setTimeout(() => { btn.disabled = false; }, 1500);
    }
  }

  // ---------------------------------------------------------------- filtering
  function visibleItems() {
    const f = state.filters;
    const q = f.q.trim().toLowerCase();
    let list = state.items.filter((it) => {
      if (f.source !== "all" && it.source !== f.source) return false;
      if (f.base && it.base_model !== f.base) return false;
      if (f.cat && it.category !== f.cat) return false;
      if (f.onlyNew && !it.is_new) return false;
      if (f.recent7 && !daysAgo(it.created_at, 7)) return false;
      if (f.hideNsfw && it.nsfw) return false;
      if (q) {
        const hay = [it.name, it.author, it.summary_ko, it.description, (it.tags || []).join(" "),
          (it.trigger_words || []).join(" "), it.base_model, it.category, (it.hints || []).join(" ")].join(" ").toLowerCase();
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
  function cmpDate(a, b) { return (parseDate(a)?.getTime() || 0) - (parseDate(b)?.getTime() || 0); }

  // ---------------------------------------------------------------- render
  function renderAll() {
    renderStatus();
    renderStats();
    renderFacets();
    renderList();
  }

  function renderStatus() {
    const st = state.status || {};
    const el = $("#status-text");
    if (st.refreshing) {
      el.textContent = st.progress || "새로고침 중…";
      el.classList.add("busy");
    } else {
      el.classList.remove("busy");
      const t = st.last_refresh === "demo" ? "데모 데이터" : (st.last_refresh ? "마지막 업데이트 " + rel(st.last_refresh) + " (" + new Date(st.last_refresh).toLocaleString("ko-KR") + ")" : "아직 데이터 없음");
      const c = st.claude || {};
      el.textContent = t + (c.enabled ? " · Claude 요약 켜짐" : "");
    }
    const errs = [];
    if (st.last_error) errs.push("오류: " + st.last_error);
    (st.errors || []).forEach((e) => errs.push("· " + e));
    if (st.claude && st.claude.enabled && st.claude.reason) errs.push("· Claude 요약 사용 불가: " + st.claude.reason);
    const box = $("#errors");
    box.hidden = errs.length === 0;
    box.textContent = errs.join("\n");
    $("#refresh-btn").disabled = !!st.refreshing;
  }

  function renderStats() {
    const c = (state.status && state.status.counts) || {};
    const cells = [
      ["전체", c.total || state.items.length, ""],
      ["신규 (최근 발견)", c.new || 0, "new"],
      ["이번 실행에서 발견", c.found_this_run || 0, "found"],
      ["Hugging Face", c.huggingface || 0, ""],
      ["GitHub", c.github || 0, ""],
    ];
    if (c.claude) cells.push(["Claude 한글 요약", c.claude, ""]);
    $("#stats").innerHTML = cells.map(([l, v, cls]) => `<div class="stat ${cls}"><b>${esc(v)}</b><span>${esc(l)}</span></div>`).join("");
  }

  function chip(label, count, active, attr) {
    return `<span class="chip${active ? " active" : ""}" ${attr}>${esc(label)}${count != null ? `<small>${esc(count)}</small>` : ""}</span>`;
  }

  function renderFacets() {
    const f = state.filters;
    const counts = { all: state.items.length, huggingface: 0, github: 0 };
    state.items.forEach((it) => { counts[it.source] = (counts[it.source] || 0) + 1; });
    $("#source-chips").innerHTML = [["all", "전체"], ["huggingface", "Hugging Face"], ["github", "GitHub"]]
      .map(([k, l]) => chip(l, counts[k] || 0, f.source === k, `data-source="${k}"`)).join("");

    const bases = state.facets.base_models || [];
    $("#base-chips").innerHTML = chip("전체", null, !f.base, `data-base=""`) +
      bases.map(([b, n]) => chip(b, n, f.base === b, `data-base="${esc(b)}"`)).join("");

    const cats = (state.facets.categories || []).slice().sort((a, b) => CAT_ORDER.indexOf(a[0]) - CAT_ORDER.indexOf(b[0]));
    $("#cat-chips").innerHTML = chip("전체", null, !f.cat, `data-cat=""`) +
      cats.map(([c, n]) => chip(c, n, f.cat === c, `data-cat="${esc(c)}"`)).join("");

    $("#search").value = f.q;
    $("#only-new").checked = f.onlyNew;
    $("#recent7").checked = f.recent7;
    $("#hide-nsfw").checked = f.hideNsfw;
    $("#sort").value = f.sort;
    $("#group").value = f.group;
  }

  function card(it) {
    const isHf = it.source === "huggingface";
    const metrics = isHf
      ? `<span title="다운로드">⬇ ${fmtNum(it.downloads)}</span><span title="좋아요">♥ ${fmtNum(it.likes)}</span>`
      : `<span title="스타">★ ${fmtNum(it.likes)}</span><span title="포크">⑂ ${fmtNum(it.downloads)}</span>`;
    const triggers = (it.trigger_words || []).length
      ? `<div class="triggers">트리거 ${it.trigger_words.map((t) => `<span class="trigger" data-copy="${esc(t)}" title="클릭하면 복사">${esc(t)}</span>`).join("")}</div>`
      : "";
    const files = (it.files || []).length
      ? `<div class="files">${it.files.map((f) => `<code>${esc(f)}</code>`).join("")}</div>` : "";
    const desc = (it.description || "").trim();
    const details = (desc || files)
      ? `<details><summary>원문 설명${(it.files || []).length ? " · 파일 " + it.files.length + "개" : ""}</summary>${desc ? `<p>${esc(desc)}</p>` : ""}${files}</details>`
      : "";
    return `<article class="card${it.is_new ? " new" : ""}">
      <div class="card-top">
        <div class="badges">
          <span class="badge ${isHf ? "hf" : "gh"}">${isHf ? "HF" : "GitHub"}</span>
          ${it.found_this_run ? `<span class="badge found">이번 실행 발견</span>` : (it.is_new ? `<span class="badge new">NEW</span>` : "")}
          ${it.nsfw ? `<span class="badge nsfw">NSFW</span>` : ""}
          ${it.summary_source === "claude" ? `<span class="badge claude" title="Claude가 작성한 요약">AI 요약</span>` : ""}
        </div>
        <div class="metrics">${metrics}</div>
      </div>
      <div class="title"><a href="${esc(it.url)}" target="_blank" rel="noopener">${esc(it.name)}</a></div>
      <div class="author">${esc(it.author)}${it.pipeline ? " · " + esc(it.pipeline) : ""}</div>
      <div class="tags"><span class="tag base">${esc(it.base_model)}</span><span class="tag cat">${esc(it.category)}</span>${(it.tags || []).slice(0, 4).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
      <div class="summary">${esc(it.summary_ko)}</div>
      ${triggers}
      ${details}
      <div class="dates"><span>등록 ${fmtDate(it.created_at)}</span><span>수정 ${fmtDate(it.updated_at)} (${rel(it.updated_at)})</span>${it.first_seen && it.first_seen !== it.created_at ? `<span>발견 ${fmtDate(it.first_seen)}</span>` : ""}</div>
    </article>`;
  }

  function renderList() {
    const list = visibleItems();
    const f = state.filters;
    $("#result-count").textContent = `${list.length}개 표시 (전체 ${state.items.length}개)`;
    if (!list.length) {
      $("#list").innerHTML = `<div class="empty">${state.items.length ? "조건에 맞는 항목이 없습니다." : (state.status.refreshing ? "데이터를 가져오는 중입니다…" : "데이터가 없습니다. 새로고침을 눌러 주세요.")}</div>`;
      return;
    }
    if (f.group === "none") {
      $("#list").innerHTML = list.map(card).join("");
      return;
    }
    const groups = new Map();
    list.forEach((it) => {
      const k = f.group === "source" ? (it.source === "huggingface" ? "Hugging Face" : "GitHub") : (it[f.group] || "기타");
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k).push(it);
    });
    let keys = Array.from(groups.keys());
    if (f.group === "category") keys.sort((a, b) => CAT_ORDER.indexOf(a) - CAT_ORDER.indexOf(b));
    else keys.sort((a, b) => groups.get(b).length - groups.get(a).length);
    $("#list").innerHTML = keys.map((k) =>
      `<h2 class="group-title">${esc(k)}<small>${groups.get(k).length}개</small></h2>` + groups.get(k).map(card).join("")
    ).join("");
  }

  // ---------------------------------------------------------------- events
  function bind() {
    $("#refresh-btn").addEventListener("click", refresh);
    let t = null;
    $("#search").addEventListener("input", (e) => {
      clearTimeout(t);
      t = setTimeout(() => { state.filters.q = e.target.value; renderList(); }, 120);
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
  load();
})();
