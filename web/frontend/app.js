const API = "/api";
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const state = {
  blocks: null,
  scenes: [],
  metadata: {},
  jobs: new Map(),
  drawerTab: "active",
  yamlText: "",
  yamlFilename: "",
  missingAssets: new Set(),
  knownAssets: new Set(),
  activeMode: null,
  generator: {
    mode: "live",
    task: "",
    url: "",
    voice: "jane",
    subtitles: "on",
    language: "ru",
    resolution: "1920x1080",
    fps: 30,
    browser: "chrome",
    selectedAssets: [],
    assetDescriptions: {},
    yaml: "",
    meta: null,
    abortController: null,
  },
};

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("aavb-theme", theme); } catch {}
  document.cookie = `aavb-theme=${theme}; path=/; max-age=31536000; samesite=lax`;
}
function readCookie(name) {
  const m = document.cookie.match(new RegExp("(?:^|;\\s*)" + name + "=([^;]+)"));
  return m ? m[1] : null;
}
function initTheme() {
  let saved;
  try { saved = localStorage.getItem("aavb-theme"); } catch {}
  if (!saved) saved = readCookie("aavb-theme");
  if (!saved) saved = matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  setTheme(saved);
}

function toast(message, kind = "info", timeout = 6000) {
  const stack = $("#toast-stack");
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  const body = document.createElement("div");
  body.className = "toast-body";
  body.textContent = message;
  const close = document.createElement("button");
  close.className = "toast-close";
  close.setAttribute("aria-label", "Закрыть");
  close.innerHTML = "&times;";
  close.onclick = () => el.remove();
  el.append(body, close);
  stack.append(el);
  if (timeout > 0) setTimeout(() => el.remove(), timeout);
}

function showMode(mode) {
  state.activeMode = mode === "entry" ? null : mode;
  $("#entry-mode").hidden = false;
  $("#editor-mode").hidden = mode !== "editor";
  $("#builder-mode").hidden = mode !== "builder";
  $("#generator-mode").hidden = mode !== "generator";

  $$(".choice-card").forEach(card => {
    card.classList.toggle("active", card.dataset.mode === state.activeMode);
  });

  syncAssetsCardVisibility();
}

function toggleMode(mode) {
  if (state.activeMode === mode) showMode("entry");
  else showMode(mode);
}

function escapeHtml(s) {
  return s.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}
function highlightYaml(text) {
  const lines = text.split("\n");
  return lines.map(line => {
    const m = line.match(/^(\s*)(#.*)$/);
    if (m) return `${m[1]}<span class="tok-comment">${escapeHtml(m[2])}</span>`;

    let html = "";
    const dashMatch = line.match(/^(\s*-\s)(.*)$/);
    let rest = line;
    let prefix = "";
    if (dashMatch) {
      prefix = dashMatch[1].replace(/-/, '<span class="tok-dash">-</span>');
      rest = dashMatch[2];
    }
    const kv = rest.match(/^(\s*)([A-Za-z0-9_\-]+)(\s*:)(.*)$/);
    if (kv) {
      const indent = kv[1];
      const key = `<span class="tok-key">${escapeHtml(kv[2])}</span>`;
      const colon = escapeHtml(kv[3]);
      const value = highlightValue(kv[4]);
      html = `${prefix}${indent}${key}${colon}${value}`;
    } else {
      html = `${prefix}${highlightValue(rest)}`;
    }
    return html;
  }).join("\n");
}
function highlightValue(v) {
  if (!v) return "";
  const trimmed = v.trim();
  if (!trimmed) return escapeHtml(v);
  if (/^(true|false|null|yes|no|on|off)$/i.test(trimmed)) {
    return v.replace(trimmed, `<span class="tok-bool">${escapeHtml(trimmed)}</span>`);
  }
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return v.replace(trimmed, `<span class="tok-num">${escapeHtml(trimmed)}</span>`);
  }
  if (/^['"].*['"]$/.test(trimmed)) {
    return v.replace(trimmed, `<span class="tok-str">${escapeHtml(trimmed)}</span>`);
  }
  return `<span class="tok-str">${escapeHtml(v)}</span>`;
}
function syncHighlight() {
  const text = $("#yaml-text").value;
  $("#yaml-highlight").innerHTML = highlightYaml(text) + "\n";
}

function isYamlFile(file) {
  return /\.(ya?ml)$/i.test(file.name);
}
async function handleYamlFile(file) {
  if (!isYamlFile(file)) {
    toast("Принимаются только .yml / .yaml файлы", "error");
    return;
  }
  const fd = new FormData();
  fd.append("file", file);
  let resp;
  try {
    resp = await fetch(`${API}/scripts/parse`, { method: "POST", body: fd });
  } catch (e) {
    toast(`Ошибка сети: ${e.message}`, "error");
    return;
  }
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    const detail = typeof data.detail === "string"
      ? data.detail
      : JSON.stringify(data.detail || resp.statusText);
    toast(`Не удалось разобрать YAML: ${detail}`, "error", 9000);
    return;
  }
  const data = await resp.json();
  state.yamlText = data.yaml;
  state.yamlFilename = file.name;
  state.missingAssets = new Set(data.missing_assets || []);
  if ($("#builder-mode").hidden === false) {
    applyPayloadToBuilder(data.payload);
    if (state.missingAssets.size) {
      toast(`Не хватает ассетов: ${[...state.missingAssets].join(", ")}`, "error");
    }
  } else {
    $("#yaml-text").value = data.yaml;
    $("#editor-filename").textContent = file.name;
    syncHighlight();
    showMode("editor");
  }
  renderAssets();
}

async function loadBlocks() {
  if (state.blocks) return state.blocks;
  const resp = await fetch(`${API}/blocks`);
  const data = await resp.json();
  const arr = Array.isArray(data) ? data : data.blocks || [];
  state.blocks = Object.fromEntries(arr.map(b => [b.id, b]));
  return state.blocks;
}
function renderField(field, value, onChange) {
  const wrap = document.createElement("div");
  const t = field.type;
  wrap.className = "field" + (t === "bool" ? " checkbox" : "");
  const label = document.createElement("label");
  label.textContent = field.label || field.name;
  let input;
  if (t === "enum") {
    input = document.createElement("select");
    (field.options || []).forEach(c => {
      const opt = document.createElement("option");
      opt.value = c; opt.textContent = c;
      input.append(opt);
    });
  } else if (t === "bool") {
    input = document.createElement("input"); input.type = "checkbox";
  } else if (t === "text") {
    input = document.createElement("textarea"); input.rows = 2;
  } else if (t === "int") {
    input = document.createElement("input"); input.type = "number"; input.step = "1";
  } else if (t === "float") {
    input = document.createElement("input"); input.type = "number"; input.step = "0.1";
  } else {
    input = document.createElement("input"); input.type = "text";
  }
  if (value !== undefined && value !== null) {
    if (t === "bool") input.checked = !!value;
    else input.value = value;
  } else if (field.default !== undefined && field.default !== null) {
    if (t === "bool") input.checked = !!field.default;
    else input.value = field.default;
  }
  input.addEventListener("input", () => {
    let v = t === "bool" ? input.checked
          : t === "int"  ? parseInt(input.value || "0", 10)
          : t === "float"? parseFloat(input.value || "0")
          : input.value;
    onChange(v);
  });
  if (t === "bool") { wrap.append(input, label); }
  else { wrap.append(label, input); }
  return wrap;
}
function renderMetadata() {
  const block = state.blocks.metadata;
  const root = $('[data-block="metadata"]');
  root.innerHTML = "";
  block.fields.forEach(f => {
    if (state.metadata[f.name] === undefined) state.metadata[f.name] = f.default;
    root.append(renderField(f, state.metadata[f.name], v => state.metadata[f.name] = v));
  });
}
function renderScenes() {
  const list = $("#scenes-list");
  list.innerHTML = "";
  state.scenes.forEach((scene, idx) => list.append(renderScene(scene, idx)));
}
function renderScene(scene, idx) {
  const block = state.blocks.scene;
  const wrap = document.createElement("div");
  wrap.className = "block-card scene-block";
  const head = document.createElement("div");
  head.className = "scene-head";
  const title = document.createElement("h4");
  title.textContent = `Сцена ${idx + 1}`;
  const remove = document.createElement("button");
  remove.className = "btn tiny danger"; remove.textContent = "Удалить";
  remove.onclick = () => { state.scenes.splice(idx, 1); renderScenes(); };
  head.append(title, remove);
  wrap.append(head);

  const fields = document.createElement("div");
  fields.className = "fields";
  block.fields.forEach(f => {
    if (scene.fields[f.name] === undefined) scene.fields[f.name] = f.default;
    fields.append(renderField(f, scene.fields[f.name], v => {
      scene.fields[f.name] = v;
      if (f.name === "path") renderAssets();
    }));
  });
  wrap.append(fields);

  const annTitle = document.createElement("div");
  annTitle.style.marginTop = "12px"; annTitle.style.fontSize = "12px"; annTitle.style.color = "var(--text-muted)";
  annTitle.textContent = "Аннотации";
  wrap.append(annTitle);

  const annList = document.createElement("div"); annList.className = "annotations-list";
  scene.annotations.forEach((ann, ai) => annList.append(renderAnnotation(ann, ai, scene)));
  wrap.append(annList);

  const addAnn = document.createElement("button");
  addAnn.className = "btn tiny"; addAnn.textContent = "+ Аннотация";
  addAnn.style.marginTop = "8px";
  addAnn.onclick = () => { scene.annotations.push(makeAnnotation()); renderScenes(); };
  wrap.append(addAnn);

  return wrap;
}
function renderAnnotation(ann, ai, scene) {
  const block = state.blocks.annotation;
  const wrap = document.createElement("div");
  wrap.className = "annotation-block";
  const head = document.createElement("div"); head.className = "annotation-head";
  const t = document.createElement("strong"); t.textContent = `Аннотация ${ai + 1}`;
  const rm = document.createElement("button");
  rm.className = "btn tiny danger"; rm.textContent = "✕";
  rm.onclick = () => { scene.annotations.splice(ai, 1); renderScenes(); };
  head.append(t, rm); wrap.append(head);
  const fields = document.createElement("div"); fields.className = "fields";
  block.fields.forEach(f => {
    if (ann[f.name] === undefined) ann[f.name] = f.default;
    fields.append(renderField(f, ann[f.name], v => ann[f.name] = v));
  });
  wrap.append(fields);
  return wrap;
}
function makeScene() {
  return { fields: {}, annotations: [] };
}
function makeAnnotation() { return {}; }

function applyPayloadToBuilder(payload) {
  state.metadata = { ...payload.metadata };
  state.scenes = (payload.scenes || []).map(s => {
    const { annotations = [], ...rest } = s;
    return { fields: { ...rest }, annotations: annotations.map(a => ({ ...a })) };
  });
  renderMetadata();
  renderScenes();
}
function buildPayload() {
  return {
    metadata: { ...state.metadata },
    scenes: state.scenes.map(s => ({ ...s.fields, annotations: s.annotations.map(a => ({ ...a })) })),
  };
}

async function fetchAssets() {
  const resp = await fetch(`${API}/assets`);
  const data = await resp.json();
  const assets = (data.assets || []).map(a => ({ name: a.filename || a.name, size: a.size }));
  state.knownAssets = new Set(assets.map(a => a.name));
  return assets;
}
async function renderAssets() {
  const list = $("#assets-list");
  const assets = await fetchAssets();
  list.innerHTML = "";
  const referenced = new Set();
  state.scenes.forEach(s => s.fields?.path && referenced.add(s.fields.path));
  state.missingAssets.forEach(p => referenced.add(p));

  const seen = new Set();
  assets.forEach(a => {
    seen.add(a.name);
    const li = document.createElement("li");
    li.innerHTML = `<span>${a.name}</span>`;
    const del = document.createElement("button");
    del.className = "btn tiny danger"; del.textContent = "удалить";
    del.onclick = async () => {
      await fetch(`${API}/assets/${encodeURIComponent(a.name)}`, { method: "DELETE" });
      renderAssets();
    };
    li.append(del);
    list.append(li);
  });
  const missing = [...referenced].filter(name => name && !seen.has(name));
  state.missingAssets = new Set(missing);
  missing.forEach(name => {
    const li = document.createElement("li");
    li.className = "missing";
    li.textContent = `${name} — не загружен`;
    list.append(li);
  });
}
async function uploadAssets(files) {
  const fd = new FormData();
  Array.from(files).forEach(f => fd.append("files", f));
  const resp = await fetch(`${API}/assets`, { method: "POST", body: fd });
  if (!resp.ok) {
    toast("Не удалось загрузить файлы", "error");
    return;
  }
  renderAssets();
}

async function runScript(payload) {
  if (state.missingAssets.size) {
    toast(`Нельзя запустить: не хватает ${[...state.missingAssets].join(", ")}`, "error");
    return;
  }
  const resp = await fetch(`${API}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    toast(`Ошибка: ${typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)}`, "error", 9000);
    return;
  }
  const { job_id } = await resp.json();
  toast(`Задача поставлена: ${job_id}`, "success", 4000);
  openDrawer();
  pollJob(job_id);
}
async function runFromYaml() {
  let parsed;
  try {
    const fd = new FormData();
    const blob = new Blob([$("#yaml-text").value], { type: "text/yaml" });
    fd.append("file", blob, state.yamlFilename || "script.yaml");
    const resp = await fetch(`${API}/scripts/parse`, { method: "POST", body: fd });
    if (!resp.ok) {
      const data = await resp.json().catch(() => ({}));
      const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      toast(`YAML невалиден: ${detail}`, "error", 9000);
      return;
    }
    parsed = await resp.json();
  } catch (e) {
    toast(`Ошибка сети: ${e.message}`, "error");
    return;
  }
  state.missingAssets = new Set(parsed.missing_assets || []);
  await renderAssets();
  if (state.missingAssets.size) {
    toast(`Не хватает ассетов: ${[...state.missingAssets].join(", ")}`, "error");
    return;
  }
  await runScript(parsed.payload);
}

function openDrawer() {
  $("#drawer").classList.add("open");
  refreshAllJobs();
}
function closeDrawer() { $("#drawer").classList.remove("open"); }
function isActive(s) { return s === "queued" || s === "running"; }

async function refreshAllJobs() {
  await Promise.all([...state.jobs.keys()].map(pollJobOnce));
  renderJobs();
}
async function pollJobOnce(jobId) {
  try {
    const resp = await fetch(`${API}/jobs/${jobId}`);
    if (!resp.ok) return;
    const data = await resp.json();
    state.jobs.set(jobId, data);
  } catch {}
}
async function pollJob(jobId) {
  state.jobs.set(jobId, { job_id: jobId, status: "queued" });
  renderJobs();
  const tick = async () => {
    await pollJobOnce(jobId);
    renderJobs();
    const cur = state.jobs.get(jobId);
    if (cur && isActive(cur.status)) setTimeout(tick, 1500);
  };
  tick();
}
function renderJobs() {
  const list = $("#drawer-jobs");
  list.innerHTML = "";
  const all = [...state.jobs.values()].sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
  const filtered = all.filter(j => state.drawerTab === "active" ? isActive(j.status) : !isActive(j.status));
  if (!filtered.length) {
    const empty = document.createElement("li");
    empty.className = "empty";
    empty.textContent = state.drawerTab === "active" ? "Нет активных задач" : "Нет завершённых задач";
    list.append(empty);
    return;
  }
  filtered.forEach(j => list.append(renderJobItem(j)));
}
function renderJobItem(job) {
  const li = document.createElement("li");
  const head = document.createElement("div"); head.className = "job-head";
  const id = document.createElement("span"); id.className = "job-id"; id.textContent = job.job_id.slice(0, 8);
  const status = document.createElement("span");
  status.className = `job-status status-${job.status}`;
  status.textContent = job.status;
  head.append(id, status);
  li.append(head);

  if (job.error) {
    const err = document.createElement("div");
    err.style.color = "var(--danger)"; err.style.fontSize = "12px";
    err.textContent = job.error;
    li.append(err);
  }

  const actions = document.createElement("div"); actions.className = "job-actions";
  if (isActive(job.status)) {
    const cancel = document.createElement("button");
    cancel.className = "btn tiny danger"; cancel.textContent = "Отменить";
    cancel.onclick = async () => {
      await fetch(`${API}/jobs/${job.job_id}/cancel`, { method: "POST" });
      pollJobOnce(job.job_id).then(renderJobs);
    };
    actions.append(cancel);
  } else if (job.status === "done") {
    (job.output_files || []).forEach(name => {
      const a = document.createElement("a");
      a.className = "btn tiny";
      a.href = `${API}/jobs/${job.job_id}/files/${encodeURIComponent(name)}`;
      a.textContent = `↓ ${name}`;
      a.download = name;
      actions.append(a);
    });
  }
  if (actions.children.length) li.append(actions);
  return li;
}

function resetEditor() {
  state.yamlText = "";
  state.yamlFilename = "";
  state.missingAssets = new Set();
  $("#yaml-text").value = "";
  $("#editor-filename").textContent = "";
  syncHighlight();
  renderAssets();
}
function resetBuilder() {
  state.scenes = [];
  state.metadata = {};
  renderMetadata();
  renderScenes();
}

async function openGenerator() {
  showMode("generator");
  restoreGeneratorForm();
  syncGeneratorModeFields();
  await refreshGeneratorStatus();
  if (state.generator.yaml) {
    renderGeneratorResult(state.generator.meta || { valid: true, mode: state.generator.mode });
  } else {
    $("#generator-result").hidden = true;
    updateGeneratorActions();
  }
}

function persistGeneratorForm() {
  const g = state.generator;
  g.mode = document.querySelector('input[name="generator-mode-choice"]:checked')?.value || "live";
  g.task = $("#generator-task").value;
  g.url = $("#generator-url").value;
  g.voice = $("#generator-voice").value;
  g.subtitles = $("#generator-subtitles").value;
  g.language = $("#generator-language").value;
  g.resolution = $("#generator-resolution").value;
  g.fps = parseInt($("#generator-fps").value, 10) || 30;
  g.browser = $("#generator-browser").value;
  g.selectedAssets = [...document.querySelectorAll('#generator-assets-list input[type=checkbox]:checked')].map(c => c.value);
  const descs = {};
  document.querySelectorAll('#generator-assets-list input.asset-desc').forEach(inp => {
    const v = (inp.value || "").trim();
    if (v) descs[inp.dataset.filename] = v;
  });
  g.assetDescriptions = descs;
}

function restoreGeneratorForm() {
  const g = state.generator;
  const radio = document.querySelector(`input[name="generator-mode-choice"][value="${g.mode}"]`);
  if (radio) radio.checked = true;
  $("#generator-task").value = g.task || "";
  $("#generator-url").value = g.url || "";
  $("#generator-voice").value = g.voice || "jane";
  $("#generator-subtitles").value = g.subtitles || "on";
  $("#generator-language").value = g.language || "ru";
  $("#generator-resolution").value = g.resolution || "1920x1080";
  $("#generator-fps").value = g.fps || 30;
  $("#generator-browser").value = g.browser || "chrome";
  updateTaskPlaceholder();
}

const _TASK_PLACEHOLDERS = {
  live: "Например: открыть главную gitflic.ru, проскроллить вниз, нажать кнопку Войти",
  screenshot: "Например: покажи процесс логина — сначала экран входа, потом главная страница профиля",
};

function updateTaskPlaceholder() {
  const mode = document.querySelector('input[name="generator-mode-choice"]:checked')?.value || "live";
  $("#generator-task").placeholder = _TASK_PLACEHOLDERS[mode];
}

function clearGeneratorAll(options = {}) {
  const keepMode = options.keepMode === true;
  const silent = options.silent === true;
  const mode = keepMode ? state.generator.mode : "live";
  state.generator = {
    mode,
    task: "",
    url: "",
    voice: "jane",
    subtitles: "on",
    language: "ru",
    resolution: "1920x1080",
    fps: 30,
    browser: "chrome",
    selectedAssets: [],
    assetDescriptions: {},
    yaml: "",
    meta: null,
    abortController: null,
  };
  restoreGeneratorForm();
  syncGeneratorModeFields();
  $("#generator-result").hidden = true;
  $("#generator-yaml-text").value = "";
  $("#generator-yaml-highlight").innerHTML = "";
  $("#generator-meta").innerHTML = "";
  updateGeneratorActions();
  if (!silent) toast("Форма очищена", "info", 2000);
}

function resetGenerator() {
  clearGeneratorAll();
}

function syncGeneratorModeFields() {
  const mode = document.querySelector('input[name="generator-mode-choice"]:checked')?.value || "live";
  $("#generator-live-fields").hidden = mode !== "live";
  $("#generator-screenshot-fields").hidden = mode !== "screenshot";
  $("#generator-browser-wrap").hidden = mode !== "live";
  $("#generator-subtitles-wrap").hidden = mode !== "screenshot";
  syncAssetsCardVisibility();
  updateTaskPlaceholder();
  if (mode === "screenshot") refreshGeneratorAssets();
}

function syncAssetsCardVisibility() {
  const card = $("#assets-card");
  if (!card) return;
  const generatorActive = state.activeMode === "generator";
  const genMode = document.querySelector('input[name="generator-mode-choice"]:checked')?.value || "live";
  const hideForGeneratorLive = generatorActive && genMode === "live";
  card.hidden = hideForGeneratorLive;
}

async function refreshGeneratorStatus() {
  try {
    const r = await fetch(`${API}/generator/status`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const s = await r.json();
    const parts = [];
    if (s.llm_configured) parts.push(`model: ${s.llm_model}`); else parts.push("LLM не настроен");
    if (s.ocr_available) parts.push("OCR ok"); else parts.push("OCR недоступен");
    parts.push(`rate ${s.rate_limit}`);
    $("#generator-status").textContent = parts.join(" · ");
  } catch (e) {
    $("#generator-status").textContent = "не удалось получить статус";
  }
}

let _generatorAssetsRefreshInFlight = false;
async function refreshGeneratorAssets() {
  if (_generatorAssetsRefreshInFlight) return;
  _generatorAssetsRefreshInFlight = true;
  const list = $("#generator-assets-list");
  try {
    const r = await fetch(`${API}/assets`);
    const assets = (await r.json()).assets || [];
    list.innerHTML = "";
    if (!assets.length) {
      list.innerHTML = '<li class="muted">Сначала загрузите скриншоты в разделе справа</li>';
      return;
    }
    const selectedSet = new Set(state.generator.selectedAssets || []);
    const descriptions = state.generator.assetDescriptions || {};
    for (const a of assets) {
      const li = document.createElement("li");
      const checked = selectedSet.has(a.filename) ? " checked" : "";
      const desc = descriptions[a.filename] || "";
      li.innerHTML = `
        <label class="asset-pick">
          <input type="checkbox" value="${escapeHtml(a.filename)}"${checked} />
          <span class="asset-name">${escapeHtml(a.filename)}</span>
        </label>
        <input type="text" class="asset-desc" data-filename="${escapeHtml(a.filename)}"
          placeholder="описание (необязательно)" value="${escapeHtml(desc)}" />
      `;
      li.querySelector('input[type="checkbox"]').addEventListener("change", persistGeneratorForm);
      li.querySelector('input.asset-desc').addEventListener("input", persistGeneratorForm);
      list.appendChild(li);
    }
  } catch (e) {
    list.innerHTML = '<li class="muted">не удалось загрузить список</li>';
  } finally {
    _generatorAssetsRefreshInFlight = false;
  }
}

function buildGeneratorRequest() {
  const mode = document.querySelector('input[name="generator-mode-choice"]:checked')?.value || "live";
  const task = $("#generator-task").value.trim();
  if (!task) { toast("Опишите сценарий", "error"); return null; }

  const base = {
    mode,
    task,
    voice: $("#generator-voice").value,
    subtitles: $("#generator-subtitles").value,
    language: $("#generator-language").value,
    resolution: $("#generator-resolution").value.trim() || "1920x1080",
    fps: parseInt($("#generator-fps").value, 10) || 30,
  };

  if (mode === "live") {
    const url = $("#generator-url").value.trim();
    if (!url) { toast("Укажите стартовый URL", "error"); return null; }
    base.start_url = url;
    base.browser = $("#generator-browser").value;
  } else {
    const selected = [...document.querySelectorAll('#generator-assets-list input[type=checkbox]:checked')].map(c => c.value);
    if (!selected.length) { toast("Выберите хотя бы один скриншот", "error"); return null; }
    base.asset_filenames = selected;
    const descs = {};
    document.querySelectorAll('#generator-assets-list input.asset-desc').forEach(inp => {
      const v = (inp.value || "").trim();
      if (v && selected.includes(inp.dataset.filename)) descs[inp.dataset.filename] = v;
    });
    if (Object.keys(descs).length) base.asset_descriptions = descs;
  }

  return base;
}

async function runGenerator() {
  persistGeneratorForm();
  const req = buildGeneratorRequest();
  if (!req) return;

  setGeneratorLoading(true);
  const controller = new AbortController();
  state.generator.abortController = controller;

  try {
    const r = await fetch(`${API}/generator/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal: controller.signal,
    });
    const body = await r.json();
    if (!r.ok) {
      const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      toast(`Ошибка ${r.status}: ${detail}`, "error", 10000);
      return;
    }
    state.generator.yaml = body.yaml_script || "";
    state.generator.meta = body;
    renderGeneratorResult(body);
    setTimeout(() => {
      $("#generator-result")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  } catch (e) {
    if (e.name === "AbortError") {
      toast("Генерация отменена", "info", 3000);
    } else {
      toast(`Сетевая ошибка: ${e.message}`, "error", 10000);
    }
  } finally {
    setGeneratorLoading(false);
    state.generator.abortController = null;
  }
}

function cancelGenerator() {
  if (state.generator.abortController) state.generator.abortController.abort();
}

function setGeneratorLoading(loading) {
  $("#generator-overlay").hidden = !loading;
  $("#generator-run").disabled = loading;
  $("#generator-clear").disabled = loading;
  $("#generator-back").disabled = loading;
}

function updateGeneratorActions() {
  const meta = state.generator.meta;
  const yaml = state.generator.yaml;
  const hasAny = !!yaml;
  const hasValid = hasAny && meta?.valid;
  const isLive = meta?.mode === "live";
  $("#generator-download").hidden = !hasAny;
  $("#generator-use-in-editor").hidden = !hasValid || isLive;
  $("#generator-render").hidden = !hasValid || isLive;
}

function extractYamlTitle(yaml) {
  if (!yaml) return null;
  const lines = yaml.split("\n");
  let inMeta = false;
  for (const raw of lines) {
    const line = raw.replace(/\r$/, "");
    if (/^metadata\s*:/i.test(line)) { inMeta = true; continue; }
    if (inMeta) {
      if (/^\S/.test(line)) break;
      const m = line.match(/^\s+title\s*:\s*['"]?([^'"\n]+?)['"]?\s*$/);
      if (m) return m[1].trim();
    }
  }
  return null;
}

function downloadYaml() {
  const yaml = state.generator.yaml;
  if (!yaml) return;
  const rawTitle = extractYamlTitle(yaml) || "generated";
  const slug = rawTitle.replace(/[^a-zA-Z0-9._-]+/g, "_").slice(0, 80) || "generated";
  const blob = new Blob([yaml], { type: "application/x-yaml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${slug}.yaml`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function openGeneratedInBuilder() {
  const yaml = state.generator.yaml;
  if (!yaml) return;
  parseYamlToBuilder(yaml);
}

async function parseYamlToBuilder(yaml) {
  const blob = new Blob([yaml], { type: "application/x-yaml" });
  const fd = new FormData();
  fd.append("file", blob, "generated.yaml");
  let resp;
  try {
    resp = await fetch(`${API}/scripts/parse`, { method: "POST", body: fd });
  } catch (e) {
    toast(`Ошибка сети: ${e.message}`, "error");
    return;
  }
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}));
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || resp.statusText);
    toast(`Не удалось распарсить YAML: ${detail}`, "error", 9000);
    return;
  }
  const data = await resp.json();
  state.yamlText = data.yaml;
  state.yamlFilename = "generated.yaml";
  state.missingAssets = new Set(data.missing_assets || []);
  await loadBlocks();
  applyPayloadToBuilder(data.payload);
  showMode("builder");
  if (state.missingAssets.size) {
    toast(`Не хватает ассетов: ${[...state.missingAssets].join(", ")}`, "warn");
  }
}

async function renderGeneratedYaml() {
  const yaml = state.generator.yaml;
  if (!yaml) return;
  state.yamlText = yaml;
  state.yamlFilename = "generated.yaml";
  $("#yaml-text").value = yaml;
  await runFromYaml();
}

function renderGeneratorResult(body) {
  $("#generator-result").hidden = false;
  const yaml = state.generator.yaml || "";
  $("#generator-yaml-text").value = yaml;
  $("#generator-yaml-highlight").innerHTML = highlightYaml(yaml);

  const meta = $("#generator-meta");
  meta.innerHTML = "";
  const badge = (text, kind = "") => `<span class="badge ${kind}">${escapeHtml(text)}</span>`;

  if (body.valid) meta.innerHTML += badge("YAML валиден", "ok");
  else meta.innerHTML += badge(`YAML невалиден: ${body.parse_error || "?"}`, "error");

  if (body.mode === "live") {
    if (body.iterations != null) meta.innerHTML += badge(`iter ${body.iterations}`);
    if (body.verification_passed) meta.innerHTML += badge("verify ok", "ok");
    else if (body.verification_attempts) meta.innerHTML += badge(`verify failed (${body.verification_attempts} попыток)`, "warn");
    if (body.hit_iteration_limit) meta.innerHTML += badge("лимит итераций", "warn");
    if (body.timed_out) meta.innerHTML += badge("таймаут", "warn");
    if (body.exploration_incomplete) meta.innerHTML += badge("неполная разведка", "warn");
  } else if (body.mode === "screenshot") {
    if (body.ocr_used) meta.innerHTML += badge("OCR применён", "ok");
    if (body.self_correction_used) meta.innerHTML += badge("self-correction", "warn");
  }

  if (body.notes) {
    const note = document.createElement("div");
    note.className = "muted";
    note.style.fontSize = "13px";
    note.style.whiteSpace = "pre-wrap";
    note.textContent = body.notes;
    meta.appendChild(note);
  }

  updateGeneratorActions();
}

async function init() {
  initTheme();
  $("#theme-toggle").onclick = () => {
    const cur = document.documentElement.getAttribute("data-theme");
    setTheme(cur === "dark" ? "light" : "dark");
  };

  $("#drawer-toggle").onclick = openDrawer;
  $("#drawer-close").onclick = closeDrawer;
  $$(".drawer-tabs .tab").forEach(t => {
    t.onclick = () => {
      $$(".drawer-tabs .tab").forEach(x => x.classList.remove("active"));
      t.classList.add("active");
      state.drawerTab = t.dataset.tab;
      renderJobs();
    };
  });

  $("#btn-pick-yaml").onclick = e => { e.stopPropagation(); $("#yaml-input").click(); };
  $("#choice-upload").addEventListener("click", e => {
    if (e.target.tagName === "BUTTON") return;
    if (state.activeMode === "editor") { showMode("entry"); return; }
    if (state.yamlText) showMode("editor");
    else $("#yaml-input").click();
  });
  $("#yaml-input").onchange = e => { if (e.target.files[0]) handleYamlFile(e.target.files[0]); };

  $("#choice-builder").addEventListener("click", async e => {
    if (e.target.id === "btn-open-builder" || e.target.tagName !== "BUTTON") {
      if (state.activeMode === "builder") { showMode("entry"); return; }
      await loadBlocks();
      if (!state.scenes.length) state.scenes.push(makeScene());
      renderMetadata();
      renderScenes();
      showMode("builder");
    }
  });

  $("#choice-generator").addEventListener("click", async e => {
    if (e.target.id === "btn-open-generator" || e.target.tagName !== "BUTTON") {
      if (state.activeMode === "generator") { showMode("entry"); return; }
      await openGenerator();
    }
  });

  $("#editor-back").onclick = () => showMode("entry");
  $("#builder-back").onclick = () => showMode("entry");
  $("#generator-back").onclick = () => showMode("entry");

  document.querySelectorAll('input[name="generator-mode-choice"]').forEach(radio => {
    radio.addEventListener("change", () => {
      if (!radio.checked) return;
      if (state.generator.mode === radio.value) return;
      const previousMode = state.generator.mode;
      state.generator.mode = radio.value;
      clearGeneratorAll({ keepMode: true, silent: true });
      if (radio.value === "screenshot") refreshGeneratorAssets();
      toast(`Режим переключён на ${radio.value === "live" ? "Live" : "Screenshot"}, данные очищены`, "info", 3000);
    });
  });

  ["generator-task", "generator-url", "generator-resolution", "generator-fps"].forEach(id => {
    const el = $("#" + id);
    if (el) el.addEventListener("input", () => persistGeneratorForm());
  });
  ["generator-voice", "generator-language", "generator-browser"].forEach(id => {
    const el = $("#" + id);
    if (el) el.addEventListener("change", () => persistGeneratorForm());
  });

  $("#generator-yaml-text").addEventListener("input", () => {
    const t = $("#generator-yaml-text");
    state.generator.yaml = t.value;
    $("#generator-yaml-highlight").innerHTML = highlightYaml(t.value);
  });
  $("#generator-yaml-text").addEventListener("scroll", () => {
    const h = $("#generator-yaml-highlight"), t = $("#generator-yaml-text");
    h.scrollTop = t.scrollTop; h.scrollLeft = t.scrollLeft;
  });

  $("#generator-run").onclick = runGenerator;
  $("#generator-cancel").onclick = cancelGenerator;
  $("#generator-clear").onclick = clearGeneratorAll;
  $("#generator-use-in-editor").onclick = openGeneratedInBuilder;
  $("#generator-render").onclick = renderGeneratedYaml;
  $("#generator-download").onclick = downloadYaml;

  $("#editor-run").onclick = runFromYaml;
  $("#builder-run").onclick = () => runScript(buildPayload());

  $("#add-scene").onclick = () => { state.scenes.push(makeScene()); renderScenes(); };
  $("#preview-btn").onclick = async () => {
    const pre = $("#preview");
    const resp = await fetch(`${API}/scripts/preview`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload()),
    });
    const data = await resp.json();
    if (resp.ok) { pre.textContent = data.yaml; pre.hidden = false; }
    else { toast(`Ошибка: ${JSON.stringify(data.detail)}`, "error"); }
  };

  $("#yaml-text").addEventListener("input", syncHighlight);
  $("#yaml-text").addEventListener("scroll", () => {
    const h = $("#yaml-highlight"), t = $("#yaml-text");
    h.scrollTop = t.scrollTop; h.scrollLeft = t.scrollLeft;
  });

  $("#btn-pick-assets").onclick = () => $("#asset-input").click();
  $("#asset-input").onchange = e => uploadAssets(e.target.files);
  const drop = $("#asset-drop");
  ["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => {
    e.preventDefault(); e.stopPropagation(); drop.classList.add("dragover");
  }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => {
    e.preventDefault(); e.stopPropagation(); drop.classList.remove("dragover");
  }));
  drop.addEventListener("drop", e => {
    const files = [...e.dataTransfer.files].filter(f => f.type.startsWith("image/"));
    if (files.length) uploadAssets(files);
  });

  initGlobalDragDrop();
  await loadBlocks();
  renderAssets();
  showMode("entry");
}

function initGlobalDragDrop() {
  const overlay = $("#drop-overlay");
  let counter = 0;
  window.addEventListener("dragenter", e => {
    if (!hasYamlInDrag(e)) return;
    counter++; overlay.classList.add("visible");
  });
  window.addEventListener("dragleave", () => {
    counter--; if (counter <= 0) { counter = 0; overlay.classList.remove("visible"); }
  });
  window.addEventListener("dragover", e => { if (hasYamlInDrag(e)) e.preventDefault(); });
  window.addEventListener("drop", e => {
    counter = 0; overlay.classList.remove("visible");
    const files = [...(e.dataTransfer?.files || [])];
    const yaml = files.find(isYamlFile);
    if (yaml) { e.preventDefault(); handleYamlFile(yaml); }
  });
}
function hasYamlInDrag(e) {
  const items = e.dataTransfer?.items;
  if (!items) return false;
  for (const it of items) if (it.kind === "file") return true;
  return false;
}

document.addEventListener("DOMContentLoaded", init);
