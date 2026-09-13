/* VeilShare Edge — local web UI logic.
 * All API calls are relative (same origin); no external services. */

"use strict";

const SEV_META = {
  critical: { color: "#ef4444", name: "Critical" },
  high: { color: "#f97316", name: "High" },
  medium: { color: "#facc15", name: "Medium" },
  low: { color: "#38bdf8", name: "Low" },
  none: { color: "#34d399", name: "Clean" },
};

const state = {
  demos: [],
  source: null,        // {type:'demo', id, name} | {type:'upload', file, name}
  imgEl: null,         // decoded HTMLImageElement of the current source
  scan: null,          // last scan API result
  redactedUrl: null,
  excluded: new Set(), // finding ids excluded from redaction
  selected: null,      // selected finding id
  view: "findings",
  split: 50,           // compare slider position (%)
};

const $ = (id) => document.getElementById(id);

/* ---------------- helpers ---------------- */

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) { /* keep */ }
    throw new Error(detail);
  }
  return res;
}

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 4200);
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("could not load image"));
    img.src = url;
  });
}

/* ---------------- init ---------------- */

async function init() {
  await loadRuntime();
  await loadDemos();
  wireEvents();
}

async function loadRuntime() {
  try {
    const rt = await (await api("/api/runtime")).json();
    const chip = $("chipRuntime");
    const qnn = rt.onnxruntime && rt.onnxruntime.qnn_execution_provider;
    chip.textContent = qnn ? "Snapdragon NPU (QNN)" : "CPU dev fallback";
    chip.classList.toggle("chip-ok", !!qnn);
    renderRuntime(rt);
  } catch (e) {
    $("chipRuntime").textContent = "runtime unavailable";
  }
}

async function loadDemos() {
  try {
    state.demos = await (await api("/api/demos")).json();
  } catch (e) {
    toast("Could not load demos: " + e.message);
    return;
  }
  const grid = $("demoGrid");
  grid.innerHTML = "";
  for (const d of state.demos) {
    const card = document.createElement("div");
    card.className = "demo-card";
    card.dataset.demo = d.id;
    card.innerHTML = `
      <img src="${d.image}" alt="${d.name}" loading="lazy" />
      <div class="demo-name" title="${d.description}">${d.name}</div>`;
    card.addEventListener("click", () => selectDemo(d.id));
    grid.appendChild(card);
  }
}

function wireEvents() {
  const dz = $("dropzone");
  const fi = $("fileInput");
  dz.addEventListener("click", () => fi.click());
  dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") fi.click(); });
  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("dragover"); }));
  dz.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) selectUpload(file);
  });
  fi.addEventListener("change", () => {
    if (fi.files && fi.files[0]) selectUpload(fi.files[0]);
    fi.value = "";
  });

  $("scanBtn").addEventListener("click", scan);
  $("safeShareBtn").addEventListener("click", createSafeShare);
  document.querySelectorAll('input[name="mode"]').forEach((r) =>
    r.addEventListener("change", () => {
      if (state.redactedUrl) createSafeShare(); // live re-render with new mode
    }));

  document.querySelectorAll(".vt-btn").forEach((btn) =>
    btn.addEventListener("click", () => switchView(btn.dataset.view)));

  // compare slider drag
  const cmp = $("compare");
  const drag = (e) => {
    const rect = cmp.getBoundingClientRect();
    state.split = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
    $("afterClip").style.clipPath = `inset(0 0 0 ${state.split}%)`;
    $("divider").style.left = state.split + "%";
  };
  cmp.addEventListener("pointerdown", (e) => { cmp.setPointerCapture(e.pointerId); drag(e); });
  cmp.addEventListener("pointermove", (e) => { if (e.buttons) drag(e); });

  $("canvas").addEventListener("click", onCanvasClick);
}

/* ---------------- source selection ---------------- */

function markSelectedDemo(id) {
  document.querySelectorAll(".demo-card").forEach((c) =>
    c.classList.toggle("selected", c.dataset.demo === id));
}

async function selectDemo(id) {
  const demo = state.demos.find((d) => d.id === id);
  if (!demo) return;
  try {
    state.imgEl = await loadImage(demo.image);
  } catch (e) { toast(e.message); return; }
  state.source = { type: "demo", id, name: demo.name };
  markSelectedDemo(id);
  resetScanUi();
  drawCanvas();
  setReady(`Loaded demo: ${demo.name}`);
}

async function selectUpload(file) {
  const url = URL.createObjectURL(file);
  try {
    state.imgEl = await loadImage(url);
  } catch (e) {
    URL.revokeObjectURL(url);
    toast("Not a readable image: " + file.name);
    return;
  }
  if (state.source && state.source.type === "upload" && state.source.url) {
    URL.revokeObjectURL(state.source.url);
  }
  state.source = { type: "upload", file, name: file.name, url };
  markSelectedDemo(null);
  resetScanUi();
  drawCanvas();
  setReady(`Loaded upload: ${file.name}`);
}

function setReady(msg) {
  $("scanBtn").disabled = false;
  $("scanHint").textContent = msg + " — click Scan Locally.";
}

/* ---------------- scan ---------------- */

async function scan() {
  if (!state.source) return;
  $("scanBtn").disabled = true;
  $("scanSpinner").hidden = false;

  const fd = new FormData();
  if (state.source.type === "demo") fd.append("demo", state.source.id);
  else fd.append("file", state.source.file);

  try {
    const res = await api("/api/scan", { method: "POST", body: fd });
    state.scan = await res.json();
    state.excluded = new Set();
    state.selected = null;
    renderScanResults();
  } catch (e) {
    toast("Scan failed: " + e.message);
  } finally {
    $("scanSpinner").hidden = true;
    $("scanBtn").disabled = false;
  }
}

function resetScanUi() {
  state.scan = null;
  state.redactedUrl = null;
  state.excluded = new Set();
  state.selected = null;
  if (state.source && state.source.type === "upload" && state.source.url) { /* keep url */ }
  $("viewToggle").hidden = true;
  $("safeShareBtn").disabled = true;
  $("downloadBtn").hidden = true;
  $("findingCount").textContent = "";
  $("findingsList").innerHTML = '<span class="muted">No findings yet.</span>';
  $("summaryBody").innerHTML = '<span class="muted">Run a scan to see the risk report.</span>';
  $("privacyPanel").innerHTML = '<span class="muted">Scan to measure network activity.</span>';
  $("statusbar").textContent = "No scan yet.";
  switchView("findings", /* force */ true);
}

function renderScanResults() {
  const r = state.scan;
  renderSummary(r.summary);
  renderFindings(r.findings);
  renderPrivacy(r);
  renderRuntime(r.runtime);
  const t = r.timings;
  $("statusbar").textContent =
    `${r.image_size[0]}×${r.image_size[1]} · OCR: ${r.ocr_engine} (${r.ocr_items} items) · ` +
    `semantic: ${r.semantic_engine} · scan ${t.total_ms} ms (ocr ${t.ocr_ms} + detect ${t.detect_ms})`;
  $("safeShareBtn").disabled = r.findings.length === 0;
  $("viewToggle").hidden = false;
  if (r.ocr_engine === "none") {
    toast("No OCR engine available for this image — " + r.ocr_note);
  }
  drawCanvas();
}

function renderSummary(s) {
  const meta = SEV_META[s.overall_severity] || SEV_META.none;
  const counts = s.by_severity;
  $("summaryBody").innerHTML = `
    <span class="sev-badge sev-${s.overall_severity}">${meta.name}</span>
    <div class="score-row">
      <div class="score-track"><div class="score-fill" style="width:${s.risk_score}%"></div></div>
      <div class="score-num">${s.risk_score}/100</div>
    </div>
    <div class="sev-counts">
      ${["critical", "high", "medium", "low"].map((sev) => `
        <div class="sev-count">
          <b style="color:${SEV_META[sev].color}">${counts[sev] || 0}</b>
          <span>${sev}</span>
        </div>`).join("")}
    </div>`;
}

function renderFindings(findings) {
  const list = $("findingsList");
  $("findingCount").textContent = findings.length ? `${findings.length}` : "";
  if (!findings.length) {
    list.innerHTML = '<span class="muted">No sensitive content detected.</span>';
    return;
  }
  list.innerHTML = "";
  for (const f of findings) {
    const el = document.createElement("div");
    el.className = `finding f-${f.severity}` + (state.excluded.has(f.id) ? " excluded" : "");
    el.dataset.id = f.id;
    el.innerHTML = `
      <div class="finding-top">
        <span class="sev-dot"></span>
        <span class="finding-label">${f.label}</span>
        <span class="finding-conf">${Math.round(f.confidence * 100)}%</span>
      </div>
      <div class="finding-text">${escapeHtml(f.masked)}</div>
      <div class="finding-explain">${escapeHtml(f.explanation)}</div>
      <div class="finding-meta">
        <span class="mini">${f.category}</span>
        <span class="mini">src: ${f.source}</span>
      </div>
      <div class="finding-actions">
        <button class="reveal" type="button">show text</button>
        <label><input type="checkbox" class="include" ${state.excluded.has(f.id) ? "" : "checked"} /> include in redaction</label>
      </div>`;
    el.querySelector(".reveal").addEventListener("click", (e) => {
      e.stopPropagation();
      const t = el.querySelector(".finding-text");
      const showing = t.dataset.full === "1";
      t.textContent = showing ? f.masked : f.text;
      t.dataset.full = showing ? "" : "1";
      e.target.textContent = showing ? "show text" : "hide text";
    });
    el.querySelector(".include").addEventListener("change", (e) => {
      e.stopPropagation();
      if (e.target.checked) state.excluded.delete(f.id);
      else state.excluded.add(f.id);
      el.classList.toggle("excluded", !e.target.checked);
      drawCanvas();
    });
    el.addEventListener("click", () => {
      state.selected = state.selected === f.id ? null : f.id;
      renderSelection();
      drawCanvas();
    });
    list.appendChild(el);
  }
}

function renderSelection() {
  document.querySelectorAll(".finding").forEach((el) =>
    el.classList.toggle("selected", el.dataset.id === state.selected));
  const sel = document.querySelector(`.finding[data-id="${state.selected}"]`);
  if (sel) sel.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function renderPrivacy(r) {
  const p = r.privacy;
  const zero = p.new_outbound_connections_during_scan === 0;
  const big = `
    <div class="proof-big${zero ? "" : " warn"}">
      ${zero ? "✔" : "⚠"} ${p.new_outbound_connections_during_scan === null
        ? "Monitor unavailable"
        : `${p.new_outbound_connections_during_scan} outbound connection(s) opened during scan`}
    </div>`;
  const rows = [
    ["Monitor", p.monitor],
    ["OCR engine", r.ocr_engine],
    ["Semantic engine", r.semantic_engine],
    ["Cloud calls", p.cloud_calls_during_scan ?? "n/a"],
  ];
  $("privacyPanel").innerHTML = big + `
    <dl class="kv">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(String(v))}</dd>`).join("")}</dl>
    <p class="hint">${escapeHtml(p.note || "")}</p>`;
}

function renderRuntime(rt) {
  const ort = rt.onnxruntime;
  let providers = "<span class='muted'>not installed</span>";
  if (ort) {
    providers = ort.available_providers
      .map((p) => `<span class="provider ${p.includes("QNN") ? "provider-qnn" : "provider-cpu"}">${escapeHtml(p)}</span>`)
      .join(" ");
  }
  $("runtimePanel").innerHTML = `
    <dl class="kv">
      <dt>Acceleration</dt><dd>${escapeHtml(rt.acceleration || "")}</dd>
      <dt>Platform</dt><dd>${escapeHtml(rt.platform)} ${escapeHtml(rt.machine)}</dd>
      <dt>Processor</dt><dd>${escapeHtml((rt.processor || "").slice(0, 40))}</dd>
      <dt>Python</dt><dd>${escapeHtml(rt.python)}</dd>
      <dt>ONNX Runtime</dt><dd>${ort ? escapeHtml(ort.version) : "—"}</dd>
    </dl>
    <div style="margin-top:8px">${providers}</div>`;
}

/* ---------------- canvas viewer ---------------- */

let viewTransform = { scale: 1, ox: 0, oy: 0 };

function drawCanvas() {
  if (!state.imgEl) return;
  const canvas = $("canvas");
  const empty = $("emptyState");
  const compare = $("compare");

  if (state.view === "compare") {
    canvas.hidden = true; empty.hidden = true; compare.hidden = false;
    return;
  }
  compare.hidden = true;
  empty.hidden = true;
  canvas.hidden = false;

  const img = state.imgEl;
  const maxW = $("viewer").clientWidth - 8;
  const maxH = Math.max(320, window.innerHeight * 0.68);
  const scale = Math.min(maxW / img.naturalWidth, maxH / img.naturalHeight, 1);
  const w = Math.round(img.naturalWidth * scale);
  const h = Math.round(img.naturalHeight * scale);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = w * dpr; canvas.height = h * dpr;
  canvas.style.width = w + "px"; canvas.style.height = h + "px";

  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  ctx.drawImage(img, 0, 0, w, h);
  viewTransform = { scale, ox: 0, oy: 0 };

  if (!state.scan) return;
  for (const f of state.scan.findings) {
    if (!f.bbox) continue;
    const excluded = state.excluded.has(f.id);
    const meta = SEV_META[f.severity];
    const [bx, by, bw, bh] = f.bbox;
    const x = bx * scale, y = by * scale, fw = bw * scale, fh = bh * scale;

    ctx.save();
    ctx.globalAlpha = excluded ? 0.25 : 1;
    ctx.fillStyle = meta.color + "22";
    ctx.fillRect(x, y, fw, fh);
    ctx.lineWidth = state.selected === f.id ? 3 : 1.6;
    ctx.setLineDash(excluded ? [5, 4] : []);
    ctx.strokeStyle = meta.color;
    ctx.strokeRect(x, y, fw, fh);
    ctx.setLineDash([]);

    // label chip
    const label = `${meta.name.toUpperCase()} · ${f.label}`;
    ctx.font = "600 11px system-ui, sans-serif";
    const tw = ctx.measureText(label).width + 12;
    const th = 18;
    let ly = y - th - 3; if (ly < 2) ly = y + fh + 3;
    ctx.fillStyle = meta.color;
    roundRect(ctx, x, ly, tw, th, 4);
    ctx.fill();
    ctx.fillStyle = "#0b0f16";
    ctx.fillText(label, x + 6, ly + 13);
    ctx.restore();
  }
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function onCanvasClick(e) {
  if (!state.scan) return;
  const rect = e.target.getBoundingClientRect();
  const px = (e.clientX - rect.left) / viewTransform.scale;
  const py = (e.clientY - rect.top) / viewTransform.scale;
  // topmost finding under the cursor (findings are sorted most-severe-first)
  const hit = [...state.scan.findings].reverse()
    .find((f) => f.bbox && px >= f.bbox[0] && px <= f.bbox[0] + f.bbox[2]
              && py >= f.bbox[1] && py <= f.bbox[1] + f.bbox[3]);
  state.selected = hit ? (state.selected === hit.id ? null : hit.id) : null;
  renderSelection();
  drawCanvas();
}

/* ---------------- safe share ---------------- */

async function createSafeShare() {
  if (!state.scan) return;
  const mode = document.querySelector('input[name="mode"]:checked').value;
  const ids = state.scan.findings.filter((f) => !state.excluded.has(f.id)).map((f) => f.id);
  if (!ids.length) { toast("All findings are excluded from redaction."); return; }

  $("safeShareBtn").disabled = true;
  try {
    const res = await api("/api/redact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scan_id: state.scan.scan_id, mode, finding_ids: ids }),
    });
    const blob = await res.blob();
    if (state.redactedUrl) URL.revokeObjectURL(state.redactedUrl);
    state.redactedUrl = URL.createObjectURL(blob);

    $("beforeImg").src = state.imgEl.src;
    $("afterImg").src = state.redactedUrl;
    const dl = $("downloadBtn");
    dl.href = state.redactedUrl;
    dl.download = `safe_share_${state.scan.scan_id}.png`;
    dl.hidden = false;
    switchView("compare");
  } catch (e) {
    toast("Redaction failed: " + e.message);
  } finally {
    $("safeShareBtn").disabled = false;
  }
}

function switchView(view, force) {
  if (!force && !state.scan) return;
  state.view = view;
  document.querySelectorAll(".vt-btn").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === view));
  drawCanvas();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

window.addEventListener("resize", () => drawCanvas());

init();
