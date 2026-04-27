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
  $("#entry-mode").hidden = mode !== "entry";
  $("#editor-mode").hidden = mode !== "editor";
  $("#builder-mode").hidden = mode !== "builder";
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

  $("#btn-pick-yaml").onclick = () => $("#yaml-input").click();
  $("#choice-upload").addEventListener("click", e => {
    if (e.target.tagName !== "BUTTON") $("#yaml-input").click();
  });
  $("#yaml-input").onchange = e => { if (e.target.files[0]) handleYamlFile(e.target.files[0]); };

  $("#choice-builder").addEventListener("click", async e => {
    if (e.target.id === "btn-open-builder" || e.target.tagName !== "BUTTON") {
      await loadBlocks();
      if (!state.scenes.length) state.scenes.push(makeScene());
      renderMetadata();
      renderScenes();
      showMode("builder");
    }
  });

  $("#editor-back").onclick = () => { resetEditor(); showMode("entry"); };
  $("#builder-back").onclick = () => { resetBuilder(); showMode("entry"); };

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
