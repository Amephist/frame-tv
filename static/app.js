const $ = (s) => document.querySelector(s);
const state = { page: 0, total: 0, item: null, matColor: "#000000", upload: null };
const TV_RATIO = 16 / 9;
const MAT_COLORS = { Black: "#000000", Charcoal: "#1e1d1b", "Warm gray": "#6f6a62", Antique: "#e4ddcd", White: "#f5f3ee" };

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return r.status === 204 ? null : r.json();
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (t.hidden = true), 3500);
}

function el(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (v != null) e.setAttribute(k, v);
  }
  e.append(...kids.filter((k) => k != null));
  return e;
}

/* ---------- tabs ---------- */
document.querySelectorAll("nav button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.toggle("active", x === b));
    $("#browse").hidden = b.dataset.tab !== "browse";
    $("#tv").hidden = b.dataset.tab !== "tv";
    if (b.dataset.tab === "tv") loadTv();
  })
);

/* ---------- browse ---------- */
function isPortrait(w, h) { return w && h && w < h; }

function card(item) {
  const img = el("img", { src: item.thumb, loading: "lazy", alt: "" });
  const c = el("button", { class: "card", type: "button", onclick: () => openDetail(item) },
    img,
    item.on_tv.length ? el("span", { class: "flag" }, "On TV") : null,
    el("span", { class: "cap" }, el("span", { class: "t" }, item.title), el("span", { class: "a" }, [item.artist, item.date].filter(Boolean).join(" · "))));
  const markPortrait = (w, h) => {
    c.dataset.portrait = isPortrait(w, h) ? "1" : "";
    c.hidden = $("#landscape").checked && c.dataset.portrait === "1";
  };
  markPortrait(item.width, item.height);
  img.addEventListener("load", () => item.width || markPortrait(img.naturalWidth, img.naturalHeight));
  return c;
}

async function search(reset) {
  if (reset) { state.page = 0; $("#results").replaceChildren(); }
  const params = new URLSearchParams({ source: $("#source").value, q: $("#q").value, page: state.page, paintings: $("#paintings").checked });
  $("#more").hidden = true;
  $("#count").textContent = "Searching…";
  try {
    const r = await api(`/api/search?${params}`);
    state.total = r.total;
    $("#results").append(...r.results.map(card));
    $("#count").textContent = `${r.total.toLocaleString()} works`;
    $("#more").hidden = (r.page + 1) * r.page_size >= r.total;
  } catch (e) {
    $("#count").textContent = `Search failed: ${e.message}`;
  }
}

$("#search").addEventListener("submit", (e) => { e.preventDefault(); search(true); });
$("#source").addEventListener("change", () => search(true));
$("#paintings").addEventListener("change", () => search(true));
$("#landscape").addEventListener("change", () => {
  document.querySelectorAll("#results .card").forEach((c) => (c.hidden = $("#landscape").checked && c.dataset.portrait === "1"));
});
$("#more").addEventListener("click", () => { state.page++; search(false); });

/* ---------- detail ---------- */
/* The crop (fractions of the work) applies in every mode. Passepartout is drawn into the image
   server-side; the TV matte is drawn by the TV. The preview mirrors both, the TV one roughly. */
const TV_MATTE_TYPES = { modernthin: "Modern thin", modern: "Modern", modernwide: "Modern wide", flexible: "Flexible", shadowbox: "Shadowbox" };
const TV_MATTE_BORDER = { modernthin: 0.05, modern: 0.1, modernwide: 0.16, flexible: 0.1, shadowbox: 0.1 };
Object.assign(state, { crop: { x: 0, y: 0, w: 1, h: 1 }, cropTouched: false, tvMattes: null, tvType: "modern", tvColor: "polar" });

$("#matte-colors").replaceChildren(...Object.entries(MAT_COLORS).map(([name, hex]) =>
  el("button", { type: "button", title: name, "data-color": hex, style: `background: ${hex}`,
    onclick: () => { state.matColor = hex; applyMat(); } })));
$("#border").addEventListener("input", applyMat);
function border() { return $("#border").value / 100; }
function applyMat() {
  $("#border-val").textContent = `${$("#border").value}%`;
  document.querySelectorAll("#matte-colors button").forEach((b) => b.classList.toggle("sel", b.dataset.color === state.matColor));
  renderPreview();
}

async function loadTvMattes() {
  if (state.tvMattes) return;
  $("#tv-matte-status").textContent = "Asking the TV for its mattes…";
  try {
    const r = await api("/api/tv/mattes");
    const types = r.matte_types.map((t) => t.matte_type).filter((t) => t in TV_MATTE_TYPES);
    state.tvMattes = { types, colors: r.matte_colors };
    $("#tv-matte-type").replaceChildren(...types.map((t) => el("option", { value: t }, TV_MATTE_TYPES[t])));
    if (!types.includes(state.tvType)) state.tvType = types[0];
    $("#tv-matte-type").value = state.tvType;
    $("#tv-matte-colors").replaceChildren(...r.matte_colors.map((c) =>
      el("button", { type: "button", title: c.color, "data-color": c.color, style: `background: rgb(${c.R},${c.G},${c.B})`,
        onclick: () => { state.tvColor = c.color; applyTvMatte(); } })));
    $("#tv-matte-status").textContent = "The TV draws this matte itself; the preview is approximate.";
  } catch (e) {
    $("#tv-matte-status").textContent = `Couldn't get the TV's mattes: ${e.message}`;
  }
  applyTvMatte();
}
$("#tv-matte-type").addEventListener("change", (e) => { state.tvType = e.target.value; applyTvMatte(); });
function applyTvMatte() {
  document.querySelectorAll("#tv-matte-colors button").forEach((b) => b.classList.toggle("sel", b.dataset.color === state.tvColor));
  if (mode() === "tv") $("#send").disabled = !state.tvMattes;
  renderPreview();
}

function mode() { return document.querySelector("input[name=mode]:checked").value; }
document.querySelectorAll("input[name=mode]").forEach((r) => r.addEventListener("change", applyMode));
function applyMode() {
  const m = mode();
  $("#matte-opts").hidden = m !== "matte";
  $("#tv-matte-opts").hidden = m !== "tv";
  $("#mat-preview").hidden = m === "fill";
  document.querySelector(".stage").classList.toggle("split", m !== "fill");
  // Until the crop is touched: fill starts on the largest 16:9 crop, mattes on the whole work.
  if (!state.cropTouched) { $("#lock").checked = m === "fill"; resetCrop(); }
  $("#send").disabled = m === "tv" && !state.tvMattes;
  if (m === "tv") loadTvMattes();
  placeCrop();
}

function openDetail(item) {
  state.item = item; state.cropTouched = false;
  $("#d-img").src = $("#m-img").src = item.thumb;
  const full = new Image();
  full.onload = () => { if (state.item === item) $("#d-img").src = $("#m-img").src = item.image; };
  full.src = item.image;
  $("#d-title").textContent = item.title;
  $("#d-artist").textContent = [item.artist, item.date].filter(Boolean).join(" · ");
  const size = (w, h) => ($("#d-size").textContent = `Original ${w.toLocaleString()} × ${h.toLocaleString()} px`);
  if (item.width && item.height) size(item.width, item.height);
  else { $("#d-size").textContent = "Original size: loading…"; full.addEventListener("load", () => state.item === item && size(full.naturalWidth, full.naturalHeight)); }
  $("#d-onTv").hidden = !item.on_tv.length;
  $("#d-status").textContent = ""; $("#d-status").className = "small";
  $("#send").textContent = "Send to TV";
  $("#detail").showModal();
  applyMode();
}

/* Crop box: state.crop is in fractions of the work; px geometry comes from the displayed image. */
function imgRatio() {
  const img = $("#d-img");
  return img.naturalWidth && img.naturalHeight ? img.naturalWidth / img.naturalHeight : (state.item?.width / state.item?.height) || TV_RATIO;
}
function cropRatio() { return (state.crop.w / state.crop.h) * imgRatio(); }
const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/* Largest 16:9 box of area close to the current one, around the same center. */
function lockCrop(c, r) {
  let W = Math.sqrt(c.w * r * c.h * TV_RATIO), H = W / TV_RATIO;  // units of image height
  const s = Math.min(1, r / W, 1 / H);
  W *= s; H *= s;
  const cx = (c.x + c.w / 2) * r, cy = c.y + c.h / 2;
  return { x: clamp(cx - W / 2, 0, r - W) / r, y: clamp(cy - H / 2, 0, 1 - H), w: W / r, h: H };
}
function resetCrop() {
  state.crop = $("#lock").checked ? lockCrop({ x: 0, y: 0, w: 1, h: 1 }, imgRatio()) : { x: 0, y: 0, w: 1, h: 1 };
}

function placeCrop() {
  const img = $("#d-img"), dw = img.clientWidth, dh = img.clientHeight, c = state.crop;
  const s = $("#crop").style;
  s.left = `${c.x * dw}px`; s.top = `${c.y * dh}px`; s.width = `${c.w * dw}px`; s.height = `${c.h * dh}px`;
  const off = Math.abs(cropRatio() / TV_RATIO - 1) >= 0.01;
  $("#crop-hint").textContent = "Drag the box to move it, the corners to resize."
    + (mode() === "fill" && off ? " Not 16:9, so it'll get black bars on the TV." : "");
  renderPreview();
}

function renderPreview() {
  const m = mode(), p = $("#mat-preview");
  if (m === "fill" || p.hidden) return;
  const color = m === "tv" ? state.tvMattes?.colors.find((c) => c.color === state.tvColor) : null;
  p.style.setProperty("--mat", m === "tv" ? (color ? `rgb(${color.R},${color.G},${color.B})` : "#e8e6e7") : state.matColor);
  const b = m === "tv" ? TV_MATTE_BORDER[state.tvType] ?? 0.1 : border();
  p.classList.toggle("shadowbox", m === "tv" && state.tvType === "shadowbox");
  // Window onto the cropped region, fitted inside the margin (b is a fraction of panel height).
  const pw = p.clientWidth, ph = pw * 9 / 16, pad = b * ph;
  const aw = pw - 2 * pad, ah = ph - 2 * pad, cr = cropRatio();
  const [ww, wh] = cr > aw / ah ? [aw, aw / cr] : [ah * cr, ah];
  const c = state.crop, win = p.querySelector(".win").style, im = $("#m-img").style;
  win.width = `${ww}px`; win.height = `${wh}px`;
  im.width = `${ww / c.w}px`; im.height = `${wh / c.h}px`;
  im.left = `${-c.x * ww / c.w}px`; im.top = `${-c.y * wh / c.h}px`;
}

applyMat();
$("#d-img").addEventListener("load", () => { if (!state.cropTouched) resetCrop(); placeCrop(); });
window.addEventListener("resize", () => $("#detail").open && placeCrop());

$("#lock").addEventListener("change", () => {
  state.cropTouched = true;
  if ($("#lock").checked) state.crop = lockCrop(state.crop, imgRatio());
  placeCrop();
});
$("#crop-full").addEventListener("click", () => {
  state.cropTouched = true;
  $("#lock").checked = false;
  state.crop = { x: 0, y: 0, w: 1, h: 1 };
  placeCrop();
});

(() => {
  const crop = $("#crop");
  const MIN = 24;  // px
  let start = null;
  crop.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    crop.setPointerCapture(e.pointerId);
    start = { x: e.clientX, y: e.clientY, crop: { ...state.crop }, corner: e.target.dataset.c };
    state.cropTouched = true;
  });
  crop.addEventListener("pointermove", (e) => {
    if (!start) return;
    const img = $("#d-img"), dw = img.clientWidth, dh = img.clientHeight, c0 = start.crop;
    if (!start.corner) {
      state.crop = { ...c0, x: clamp(c0.x + (e.clientX - start.x) / dw, 0, 1 - c0.w), y: clamp(c0.y + (e.clientY - start.y) / dh, 0, 1 - c0.h) };
      return placeCrop();
    }
    // Resize around the opposite corner, in px.
    const sx = start.corner.includes("e") ? 1 : -1, sy = start.corner.includes("s") ? 1 : -1;
    const ax = (sx > 0 ? c0.x : c0.x + c0.w) * dw, ay = (sy > 0 ? c0.y : c0.y + c0.h) * dh;
    const rect = img.getBoundingClientRect();
    const maxW = sx > 0 ? dw - ax : ax, maxH = sy > 0 ? dh - ay : ay;
    let w = sx * (clamp(e.clientX - rect.left, 0, dw) - ax), h = sy * (clamp(e.clientY - rect.top, 0, dh) - ay);
    if ($("#lock").checked) {
      w = Math.min(Math.max(w, h * TV_RATIO, MIN * TV_RATIO), maxW, maxH * TV_RATIO);
      h = w / TV_RATIO;
    } else {
      w = clamp(w, Math.min(MIN, maxW), maxW); h = clamp(h, Math.min(MIN, maxH), maxH);
    }
    state.crop = { x: (sx > 0 ? ax : ax - w) / dw, y: (sy > 0 ? ay : ay - h) / dh, w: w / dw, h: h / dh };
    placeCrop();
  });
  const end = () => (start = null);
  crop.addEventListener("pointerup", end);
  crop.addEventListener("pointercancel", end);
})();

$("#send").addEventListener("click", async () => {
  const item = state.item;
  const m = mode();
  const body = {
    source: item.source, id: item.id, title: item.title, artist: item.artist, date: item.date, image: item.image,
    mode: m, crop: [state.crop.x, state.crop.y, state.crop.w, state.crop.h],
    border_color: state.matColor, border: border(), tv_matte: `${state.tvType}_${state.tvColor}`,
    show: $("#show").checked,
  };
  const status = $("#d-status");
  $("#send").disabled = true; $("#send").textContent = "Sending…";
  status.className = "small muted";
  status.textContent = "Downloading the original, preparing it and uploading. This can take a little while; closing cancels it.";
  state.upload = new AbortController();
  try {
    const r = await api("/api/tv/upload", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body), signal: state.upload.signal,
    });
    item.on_tv.push(r.content_id);
    $("#detail").close();
    toast(body.show ? "Now showing on the TV" : "Added to the TV");
  } catch (e) {
    if (e.name === "AbortError") return;
    status.className = "small err";
    status.textContent = `Failed: ${e.message}. Nothing was left on the TV.`;
    $("#send").disabled = false; $("#send").textContent = "Try again";
  } finally {
    state.upload = null;
  }
});
$("#detail").addEventListener("close", () => {
  if (state.upload) { state.upload.abort(); toast("Cancelled. Nothing was left on the TV."); }
});

/* ---------- on TV ---------- */
function fmtBytes(n) {
  if (!n) return "0 MB";
  return n > 1e9 ? `${(n / 1e9).toFixed(2)} GB` : `${(n / 1e6).toFixed(1)} MB`;
}

/* Refreshes keep the last answer on screen; only the note above it says what's happening. */
async function loadTv() {
  const panel = $("#tv-status"), note = $("#tv-note");
  const seq = (loadTv.seq = (loadTv.seq || 0) + 1);
  const shown = loadTv.loaded;
  if (shown) { note.className = "small muted"; note.textContent = "Updating…"; note.hidden = false; }
  else panel.textContent = "Connecting to the TV…";
  let s, items;
  try {
    [s, items] = await Promise.all([api("/api/tv/status"), api("/api/tv/art")]);
  } catch (e) {
    if (seq !== loadTv.seq) return;
    if (shown) { note.className = "small err"; note.textContent = `Couldn't refresh, showing the last known state. TV unreachable: ${e.message}`; }
    else panel.textContent = `TV unreachable: ${e.message}`;
    return;
  }
  if (seq !== loadTv.seq) return;
  loadTv.loaded = true;
  note.hidden = true;
  const stat = (label, value) => el("div", {}, el("b", {}, value), el("span", { class: "muted small" }, label));
  const storage = Object.entries(s.storage).map(([k, v]) =>
    stat(k === "tv_flash_size" ? "TV storage (total)" : k.replaceAll("_", " "), k === "tv_flash_size" ? `${v} GB` : String(v)));
  const artOn = s.artmode === "on";
  panel.replaceChildren(
    el("div", { class: "stats" },
      stat("Art mode", artOn ? "On" : "Off"),
      stat("Your uploads on TV", String(s.uploads_on_tv)),
      stat("Sent from this app", `${s.app_uploads.count} · ${fmtBytes(s.app_uploads.bytes)}`),
      ...storage),
    el("div", { class: "row" },
      el("button", { class: "ghost", style: "margin:0", onclick: async () => {
        try { await api(`/api/tv/artmode/${artOn ? "off" : "on"}`, { method: "POST" }); loadTv(); }
        catch (e) { toast(e.message); }
      } }, artOn ? "Turn art mode off" : "Turn art mode on")));

  const current = s.current?.content_id;
  $("#tv-art").replaceChildren(...items.map((it) => {
    const title = it.meta?.title || it.content_id;
    const sub = it.meta ? [it.meta.artist, it.meta.date].filter(Boolean).join(" · ") : `${it.width}×${it.height}`;
    return el("button", { class: `card${it.content_id === current ? " current" : ""}`, type: "button", onclick: () => openTvItem(it, title, sub) },
      el("img", { src: `/api/tv/thumb/${it.content_id}`, loading: "lazy", alt: "" }),
      it.content_id === current ? el("span", { class: "flag" }, "Showing") : null,
      el("span", { class: "cap" }, el("span", { class: "t" }, title), el("span", { class: "a" }, sub)));
  }));
}

function openTvItem(it, title, sub) {
  $("#t-img").src = `/api/tv/thumb/${it.content_id}`;
  $("#t-title").textContent = title;
  $("#t-meta").textContent = [sub, `matte: ${it.matte_id}`].join(" · ");
  $("#t-status").textContent = "";
  const run = async (fn, okMsg) => {
    $("#t-status").className = "small muted"; $("#t-status").textContent = "Working…";
    try { await fn(); $("#tv-item").close(); toast(okMsg); loadTv(); }
    catch (e) { $("#t-status").className = "small err"; $("#t-status").textContent = e.message; }
  };
  $("#t-show").onclick = () => run(() => api(`/api/tv/show/${it.content_id}`, { method: "POST" }), "Now showing on the TV");
  $("#t-delete").onclick = () => confirm(`Delete “${title}” from the TV?`) &&
    run(() => api(`/api/tv/art/${it.content_id}`, { method: "DELETE" }), "Deleted from the TV");
  $("#tv-item").showModal();
}

/* ---------- boot ---------- */
(async () => {
  const sources = await api("/api/sources");
  $("#source").replaceChildren(...sources.map((s) => el("option", { value: s.name }, s.label)));
  search(true);
})();
