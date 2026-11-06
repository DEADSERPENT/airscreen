"use strict";
window.__errs = [];
window.addEventListener("error", e => window.__errs.push(String(e.message) + " @" + e.lineno));
window.addEventListener("unhandledrejection", e => window.__errs.push("rej: " + String(e.reason)));
/* AirScreen UI. Talks to Python via window.pywebview.api and polls state with an adaptive interval.
   Follows docs/AirScreen_Design_System.md: truthful states, friendly errors (raw detail stays in Logs), no focus theft. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const api = () => window.pywebview.api;
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let S = null;                      // last state from Python
let target = null;                 // selected TV {name, ip, port, id, paired}
let view = "cast";
let pairOpen = false, codeSubmitted = false, pairTrigger = null;
let allLogs = [], logFilter = "all", logQuery = "";
const cache = {};                  // last rendered value per key: skip redundant DOM writes

function setText(id, v) { const el = $("#" + id); if (cache[id] !== v) { cache[id] = v; el.textContent = v; } }
function setClass(el, cls, on) { if (el.classList.contains(cls) !== on) el.classList.toggle(cls, on); }
function setHTML(key, el, html, after) { if (cache[key] !== html) { cache[key] = html; el.innerHTML = html; if (after) after(); } }

/* ---------- toasts (max three) ---------- */
function toast(msg) {
  const box = $("#toasts");
  while (box.children.length >= 3) box.firstChild.remove();
  const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; box.appendChild(t);
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 200); }, 3200);
}

/* ---------- navigation ---------- */
$$(".nav").forEach(b => b.addEventListener("click", () => go(b.dataset.view)));
document.addEventListener("click", e => { const g = e.target.closest("[data-goto]"); if (g) go(g.dataset.goto); });
function go(v) {
  view = v;
  $$(".nav").forEach(b => { setClass(b, "active", b.dataset.view === v); b.setAttribute("aria-current", b.dataset.view === v ? "page" : "false"); });
  $$(".view").forEach(s => setClass(s, "active", s.id === "view-" + v));
  if (v === "logs") loadLogs(true);
  if (v === "about") runChecks();
  if (S) renderViewSpecific();
  schedule(0);
}

/* ---------- friendly language (11) ---------- */
function friendly(st, phase, name) {
  const n = name || "your TV";
  if (phase === "connecting") return `Connecting to ${n}…`;
  if (phase === "streaming") return "Streaming";
  if (phase === "reconnecting") return "Connection interrupted. Reconnecting…";
  if (phase === "pairing") return "Pairing required";
  if (phase === "error") {
    if (/Cannot reach receiver|refused|timed out|10061|10060|unreachable/i.test(st)) return "Can’t reach your TV. Check that both devices are on the same network and the AirScreen app is open on the TV.";
    if (/Authentication failed|pairing code|wrong pairing/i.test(st)) return "Pairing didn’t work. Check the code on your TV and try again.";
    if (/NVENC/i.test(st)) return "Hardware video encoding isn’t available. Run diagnostics in About.";
    if (/connection lost|reset|aborted/i.test(st)) return "Connection interrupted. Try again.";
    return "Streaming stopped. Open Logs for details.";
  }
  return "Ready";
}
const sev = m => /^Error|failed|Authentication failed|NVENC unavailable/i.test(m) ? "error" : /Reconnecting|lost|interrupted|Note:|disabled|unavailable/i.test(m) ? "warn" : "info";

/* ---------- device picker ---------- */
const card = $("#devicecard"), menu = $("#devmenu");
card.addEventListener("click", () => toggleMenu());
function toggleMenu(force) {
  const open = force ?? menu.hidden;
  menu.hidden = !open; card.setAttribute("aria-expanded", String(open));
  if (open) { if (S && !S.devices.length && !S.scanning) api().scan(); renderMenu(true); }
}
document.addEventListener("click", e => { if (!e.target.closest(".device-wrap")) toggleMenu(false); });
$("#scanbtn").addEventListener("click", () => { api().scan(); schedule(0); });
$("#scanbtn2").addEventListener("click", () => { api().scan(); schedule(0); });
$("#manualuse").addEventListener("click", useManual);
$("#manualip").addEventListener("keydown", e => { if (e.key === "Enter") useManual(); });
function useManual() {
  const ip = $("#manualip").value.trim();
  if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(ip)) { showErr("Enter a valid address like 192.168.1.2"); return; }
  select({ name: "TV at " + ip, ip, port: 5000, id: "", paired: false, manual: true }); toggleMenu(false); card.focus();
}
function select(t) { target = t; showErr(""); renderTarget(); }
function renderTarget() {
  if (!target) { setText("devname", "No TV selected"); setText("devsub", "Scan for TVs on your network, or enter an address"); setHTML("badges", $("#devbadges"), ""); return; }
  setText("devname", target.name);
  setText("devsub", target.manual ? "Entered manually" : "Found on your network");
  setHTML("badges", $("#devbadges"), target.paired ? '<span class="badge ok">Paired</span>' : '<span class="badge info">Pairing required</span>');
}
function renderMenu(force) {
  if (menu.hidden && !force) return;
  const items = S.devices;
  const html = items.length ? items.map((d, i) => `<button class="item" role="option" data-i="${i}"><img class="i3d" src="icons/icon-device-tv@64.png" alt=""><span class="grow"><b>${esc(d.name)}</b><small>${d.paired ? "Paired" : "Pairing required"}</small></span></button>`).join("")
    : `<div class="empty">${S.scanning ? "Searching your network…" : "No TVs found. Make sure your TV and PC are on the same network, then scan again."}</div>`;
  setHTML("menu", $("#devlist"), html, () => $$(".item", $("#devlist")).forEach(el => el.addEventListener("click", () => { select(S.devices[+el.dataset.i]); toggleMenu(false); card.focus(); })));
  setText("scanstate", S.scanning ? "Scanning…" : items.length ? `${items.length} TV${items.length > 1 ? "s" : ""} found` : "TVs on your network");
  $("#scanbtn").disabled = S.scanning;
}

/* ---------- start / stop ---------- */
async function startOrStop() {
  if (!S) return;
  if (["streaming", "reconnecting", "connecting"].includes(S.phase)) { await api().disconnect(); schedule(0); return; }
  if (!target) { toggleMenu(true); showErr("Choose a TV first."); return; }
  showErr("");
  pairTrigger = $("#cta");
  const r = await api().connect(target.ip, target.port, "");
  if (!r.ok) showErr(r.error);
  schedule(0);
}
$("#cta").addEventListener("click", startOrStop);
$("#stopbtn").addEventListener("click", startOrStop);
function showErr(m) { const e = $("#casterr"); if (e.textContent !== m) e.textContent = m; }
$("#mutebtn").addEventListener("click", async () => { await api().set_muted(!S.muted); schedule(0); });

/* ---------- pairing dialog (6.5): focus enters and returns; Esc dismisses ---------- */
const boxes = $$("#codeboxes input");
boxes.forEach((b, i) => {
  b.addEventListener("input", () => { b.value = b.value.toUpperCase().replace(/[^A-Z0-9]/g, ""); if (b.value.length === 4 && i < 3) boxes[i + 1].focus(); });
  b.addEventListener("keydown", e => { if (e.key === "Backspace" && !b.value && i > 0) boxes[i - 1].focus(); if (e.key === "Enter") submitPair(); });
  b.addEventListener("paste", e => {
    const t = (e.clipboardData.getData("text") || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    if (t.length >= 8) { e.preventDefault(); boxes.forEach((x, k) => x.value = t.slice(k * 4, k * 4 + 4)); boxes[Math.min(3, Math.floor(t.length / 4))].focus(); }
  });
});
function openPair(name, err) {
  $("#pairname").textContent = name || "your TV"; $("#pairerr").textContent = err || "";
  $("#pairmodal").hidden = false; pairOpen = true;
  setTimeout(() => (boxes.find(b => !b.value) || boxes[0]).focus(), 30);
}
function closePair(restoreFocus = true) {
  $("#pairmodal").hidden = true; pairOpen = false; boxes.forEach(b => b.value = "");
  if (restoreFocus && pairTrigger) pairTrigger.focus();
}
async function submitPair() {
  const code = boxes.map(b => b.value).join("");
  if (code.length !== 16) { $("#pairerr").textContent = "The code has 16 characters, in 4 groups of 4."; return; }
  codeSubmitted = true; closePair();
  const r = await api().connect(target.ip, target.port, code);
  if (!r.ok) showErr(r.error);
  schedule(0);
}
async function cancelPair() { closePair(); codeSubmitted = false; await api().disconnect(); schedule(0); }
$("#pairgo").addEventListener("click", submitPair);
$("#paircancel").addEventListener("click", cancelPair);
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  if (pairOpen) cancelPair(); else if (!menu.hidden) { toggleMenu(false); card.focus(); }
});

/* ---------- render ---------- */
let lastPhase = "idle";
function render() {
  const ph = S.phase, live = ph === "streaming" || ph === "reconnecting";
  const st = S.stats || {}, receiving = ph === "streaming" && st.fps_in > 0;   // never claim "Streaming" before frames are being sent

  setClass($("#netstatus"), "off", !S.ssid);
  setText("netlabel", S.ssid ? "Connected to " + S.ssid : "Local network");
  setText("pcname", S.pc_name || "This PC");
  $("#navlive").hidden = !receiving;

  // Wi-Fi icon animates only while connecting or scanning (spec 3.7: loading uses a dedicated indicator, not a looping object)
  const wifiSrc = (ph === "connecting" || S.scanning) ? "icons/icon-network-wifi-connecting.svg" : null;
  $$("#netstatus img, .hero-wifi").forEach(el => {
    const want = wifiSrc || (el.classList.contains("hero-wifi") ? "icons/icon-network-wifi@128.png" : "icons/icon-network-wifi@64.png");
    if (el.getAttribute("src") !== want) el.setAttribute("src", want);
  });

  // CTA: loading prevents duplicate activation
  const cta = $("#cta");
  setClass(document.body, "streaming", ph === "streaming");
  setClass(cta, "loading", ph === "connecting"); setClass(cta, "stop", live); setClass(cta, "primary", !live);
  setText("ctalabel", ph === "connecting" ? friendly("", ph, target && target.name) : live ? "Stop streaming" : (!target ? "Choose a TV" : "Start streaming"));
  setClass(cta, "needs-tv", !live && ph !== "connecting" && !target);
  cta.setAttribute("aria-busy", String(ph === "connecting"));

  if (!target && S.settings.last_receiver) {
    const f = S.devices.find(d => d.ip === S.settings.last_receiver);
    target = f || { name: "TV at " + S.settings.last_receiver, ip: S.settings.last_receiver, port: 5000, id: "", paired: S.paired.length > 0, manual: true };
    renderTarget();
  }
  renderMenu();

  // summary: configured vs negotiated vs measured
  const m = /(\d+)x(\d+) @ (\d+) fps, (\d+) Mbit\/s/.exec(S.status || "");
  const cfgRes = S.settings.resolution === "auto" ? "Automatic" : S.settings.resolution.replace("x", "×");
  setText("chipvideo", live && m ? `${m[1]}×${m[2]} · ${m[3]} fps` : cfgRes);
  setText("chipvideo-t", live && m ? "Negotiated" : "Configured");
  setText("chipaudio", S.settings.audio ? "Opus stereo" : "Off");
  setText("chiprate", receiving ? st.mbps.toFixed(1) + " Mbit/s" : "—");

  // status / errors
  if (ph === "error" && !(codeSubmitted && !pairOpen)) showErr(friendly(S.status, ph, target && target.name));
  else if (ph !== "error" && cache.errClear !== ph) { showErr(""); }
  cache.errClear = ph;

  // pairing flow
  if (ph === "pairing" && !pairOpen) { codeSubmitted = false; openPair(S.pairing_for, ""); }
  if (ph === "error" && codeSubmitted && !pairOpen) { codeSubmitted = false; openPair(target ? target.name : "", friendly(S.status, ph)); }
  if (ph === "streaming") codeSubmitted = false;

  // transitions -> toasts (non-blocking), disconnect remains persistent in the Streaming view
  if (lastPhase !== ph) {
    if (ph === "streaming") toast("Streaming started");
    if (lastPhase === "streaming" && ph === "idle") toast("Streaming stopped");
    lastPhase = ph;
  }
  renderViewSpecific();
}

function renderViewSpecific() {
  const ph = S.phase, live = ph === "streaming" || ph === "reconnecting", st = S.stats || {};
  if (view === "streaming") {
    $("#stream-empty").hidden = live; $("#stream-live").hidden = !live;
    const badge = $("#streambadge");
    const label = ph === "streaming" ? (st.fps_in > 0 ? "Streaming" : "Starting…") : ph === "reconnecting" ? "Interrupted" : ph === "connecting" ? "Connecting" : ph === "error" ? "Failed" : ph === "pairing" ? "Pairing required" : "Idle";
    setText("streambadge", label);
    badge.className = "badge " + (ph === "streaming" && st.fps_in > 0 ? "ok" : ph === "reconnecting" ? "warn" : ph === "error" ? "bad" : ph === "connecting" ? "info" : "");
    setText("streamsub", live ? "Live to " + (S.receiver || "your TV") : friendly(S.status, ph, target && target.name));
    if (live) {
      const m = /(\d+)x(\d+) @ (\d+) fps, (\d+) Mbit\/s/.exec(S.status || "");
      setText("livetitle", S.receiver || "TV");
      setText("livesub", ph === "reconnecting" ? "Connection interrupted. Reconnecting…" : "Encrypted · H.264");
      setText("t-res", m ? `${m[1]} × ${m[2]} @ ${m[3]} fps` : "—");
      setText("t-fps", st.fps_in ? st.fps_in.toFixed(0) + " fps" : "—");
      setText("t-rate", st.mbps !== undefined ? st.mbps.toFixed(1) + " Mbit/s" : "—");
      setText("t-drop", st.dropped !== undefined ? String(Math.round(st.dropped)) : "—");
      setText("sparkval", st.mbps !== undefined ? st.mbps.toFixed(1) + " Mbit/s" : "—");
      drawSpark(S.history);
      const mb = $("#mutebtn"); mb.setAttribute("aria-pressed", String(S.muted));
      setText("mutelabel", S.muted ? "Audio muted" : "Audio on");
      const ic = S.muted ? "icons/icon-audio-mute@64.png" : "icons/icon-audio-volume@64.png";
      if (cache.muteicon !== ic) { cache.muteicon = ic; $("#muteicon").src = ic; }
    }
  }
  if (view === "devices") renderDevices();
  if (view === "settings") { renderSettings(); setText("netinfo", (S.ssid ? S.ssid + " · " : "") + "port 5000"); }
  if (view === "logs") loadLogs(false);
}

function drawSpark(h) {
  if (!h.length) return;
  const n = h.length, max = Math.max(...h, 1) * 1.15, w = 300, ht = 56;
  const pts = h.map((v, i) => `${(n === 1 ? w : i * w / (n - 1)).toFixed(1)},${(ht - 4 - v / max * (ht - 10)).toFixed(1)}`);
  const key = pts.join(" "); if (cache.spark === key) return; cache.spark = key;
  $("#sparkline").setAttribute("points", key);
  $("#sparkfill").setAttribute("d", `M0,${ht} L${pts.join(" L")} L${w},${ht} Z`);
}

/* ---------- devices (7.2): no raw IP unless asked ---------- */
function renderDevices() {
  const found = S.devices.length ? S.devices.map((d, i) => `<div class="card row-card"><img class="i3d md" src="icons/icon-device-tv@128.png" alt=""><div class="grow"><b>${esc(d.name)}</b><small>${d.paired ? "Paired" : "Pairing required"}</small><details><summary>Details</summary>Address ${esc(d.ip)}:${esc(d.port)}</details></div><button class="btn secondary" data-use="${i}">Use this TV</button></div>`).join("")
    : `<div class="card empty-state slim"><h2>${S.scanning ? "Searching your network…" : "No TVs found"}</h2><p>${S.scanning ? "This takes a few seconds." : "Make sure your TV and PC are on the same network, and that AirScreen is open on the TV."}</p>${S.scanning ? "" : '<button class="btn secondary" data-rescan>Scan again</button>'}</div>`;
  const paired = S.paired.length ? S.paired.map(p => `<div class="card row-card"><img class="i3d md" src="icons/icon-security-shield@128.png" alt=""><div class="grow"><b>${esc(p.name)}</b><small>Trusted · encrypted</small></div><button class="btn danger sm" data-forget="${esc(p.id)}">Forget</button></div>`).join("")
    : `<div class="card empty-state slim"><h2>No paired TVs yet</h2><p>Pair a TV to connect more quickly next time. You’ll be asked the first time you connect.</p></div>`;
  setHTML("devfound", $("#devices-found"), found, () => {
    $$("[data-use]").forEach(b => b.addEventListener("click", () => { select(S.devices[+b.dataset.use]); go("cast"); }));
    $$("[data-rescan]").forEach(b => b.addEventListener("click", () => { api().scan(); schedule(0); }));
  });
  setHTML("devpaired", $("#devices-paired"), paired, () =>
    $$("[data-forget]").forEach(b => b.addEventListener("click", async () => { await api().forget(b.dataset.forget); toast("TV forgotten"); cache.devpaired = ""; schedule(0); })));
  $("#scanbtn2").disabled = S.scanning;
}

/* ---------- settings ---------- */
function renderSettings() {
  $$(".seg[data-key]").forEach(seg => $$("button", seg).forEach(b => { const on = String(S.settings[seg.dataset.key]) === b.dataset.v; setClass(b, "on", on); b.setAttribute("aria-checked", String(on)); }));
  $$("input[data-key]").forEach(i => { if (document.activeElement !== i) i.checked = !!S.settings[i.dataset.key]; });
}
$$(".seg[data-key]").forEach(seg => seg.addEventListener("click", async e => {
  const b = e.target.closest("button"); if (!b) return;
  S.settings = await api().save_settings({ [seg.dataset.key]: b.dataset.v }); renderSettings();
  if (S.phase === "streaming") toast("Applies the next time you start streaming");
}));
$$("input[data-key]").forEach(i => i.addEventListener("change", async () => { S.settings = await api().save_settings({ [i.dataset.key]: i.checked }); if (S.phase === "streaming") toast("Applies the next time you start streaming"); }));

/* ---------- logs (7.6): severity filter + search ---------- */
let logsShown = "";
async function loadLogs(force) {
  const logs = await api().get_logs();
  if (!force && logs.length === allLogs.length) return;
  allLogs = logs; paintLogs();
}
function paintLogs() {
  const q = logQuery.toLowerCase();
  const rows = allLogs.map(l => ({ ...l, sev: sev(l.msg) })).filter(l => (logFilter === "all" || (logFilter === "warn" ? l.sev !== "info" : l.sev === "error")) && (!q || l.msg.toLowerCase().includes(q)));
  const html = rows.length ? rows.map(l => `<div class="${l.sev}"><span>${l.t}</span>${esc(l.msg)}</div>`).join("") : `<div class="empty">${allLogs.length ? "No entries match." : "Logs will appear after AirScreen performs an operation."}</div>`;
  if (html === logsShown) return; logsShown = html;
  const box = $("#logbox"), stick = box.scrollTop + box.clientHeight >= box.scrollHeight - 30;
  box.innerHTML = html; if (stick) box.scrollTop = box.scrollHeight;
}
$("#logfilter").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; logFilter = b.dataset.v; $$("#logfilter button").forEach(x => { setClass(x, "on", x === b); x.setAttribute("aria-checked", String(x === b)); }); paintLogs(); });
$("#logsearch").addEventListener("input", e => { logQuery = e.target.value; paintLogs(); });
$("#copylogs").addEventListener("click", async () => { const l = await api().get_logs(); navigator.clipboard.writeText(l.map(x => `${x.t} ${x.msg}`).join("\n")); toast("Logs copied"); });
$("#openfolder").addEventListener("click", () => api().open_data_folder());

/* ---------- about ---------- */
async function runChecks() {
  setText("aboutver", "v" + S.version); setText("aboutproto", String(S.protocol));
  const c = await api().checks();
  $("#checks").innerHTML = c.map(x => `<div class="chk"><span class="badge ${x.ok ? "ok" : "bad"}">${x.ok ? "OK" : "Needs attention"}</span><div><b>${esc(x.name)}</b><small>${esc(x.detail)}</small></div></div>`).join("");
}
$("#rerun").addEventListener("click", runChecks);

/* ---------- adaptive polling (fast when something is changing, quiet when idle or hidden) ---------- */
let timer = null, busy = false;
function interval() {
  if (document.hidden) return 4000;
  if (!S) return 200;
  if (S.phase === "streaming") return 1000;
  if (S.phase !== "idle" || S.scanning) return 400;
  return 1500;
}
async function tick() {
  if (busy) return; busy = true;
  try { S = await api().state(); render(); } catch (e) { /* bridge not ready yet */ }
  busy = false; schedule();
}
function schedule(ms) { clearTimeout(timer); timer = setTimeout(tick, ms ?? interval()); }
document.addEventListener("visibilitychange", () => schedule(0));
window.__boot = st => { S = st; render(); schedule(); };   // pushed by Python on page load: first paint without waiting for the bridge
window.addEventListener("pywebviewready", () => schedule(0));
if (window.pywebview && window.pywebview.api) schedule(0);
