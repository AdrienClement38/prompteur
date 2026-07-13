/* Prompteur — logique de la télécommande (téléphone).
   Envoie le texte, les réglages et les commandes au serveur du boîtier. */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const toastEl = $("toast");
  let toastTimer = null;
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 1600);
  }

  async function api(path, opts) {
    const r = await fetch(path, Object.assign({ cache: "no-store" }, opts));
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }
  const postJSON = (path, body) =>
    api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  let settings = {};

  // --- Onglets --------------------------------------------------------------
  document.querySelectorAll(".tabbtns button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tabbtns button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      ["texte", "controle", "reglages"].forEach((t) =>
        $("tab-" + t).classList.toggle("hide", t !== btn.dataset.tab));
    });
  });

  // --- Chargement de l'état courant ----------------------------------------
  async function loadState() {
    const s = await api("/api/state");
    settings = s.settings || {};
    $("title").value = s.title || "";
    $("text").value = s.text || "";
    reflectSettings();
    refreshLibrary();
  }

  function reflectSettings() {
    setSlider("speed", settings.speed, (v) => v);
    setSlider("fontSize", settings.fontSize, (v) => v);
    setSlider("lineHeight", Math.round((settings.lineHeight || 1.6) * 10), (v) => (v / 10).toFixed(1));
    setSlider("margin", settings.margin, (v) => v + "%");
    $("mirrorH").checked = !!settings.mirrorH;
    $("mirrorV").checked = !!settings.mirrorV;
    $("guide").checked = !!settings.guide;
    $("keyForward").value = settings.keyForward || "ArrowDown";
    $("keyBackward").value = settings.keyBackward || "ArrowUp";
    markSel(".alignBtn", "align", settings.align || "left");
    markSel(".fontBtn", "font", settings.font || "sans-serif");
    markSel(".modeBtn", "mode", settings.mode || "hold");
    renderSwatches();
  }

  function setSlider(id, raw, fmt) {
    const el = $(id);
    if (!el) return;
    if (raw != null) el.value = raw;
    $(id + "Val").textContent = fmt(Number(el.value));
  }

  function markSel(selector, attr, value) {
    document.querySelectorAll(selector).forEach((b) =>
      b.classList.toggle("primary", b.dataset[attr] === String(value)));
  }

  // --- Envoi du texte -------------------------------------------------------
  $("send").addEventListener("click", async () => {
    await postJSON("/api/text", { text: $("text").value, title: $("title").value });
    toast("Texte envoyé à l'écran ✓");
  });

  async function saveLibrary(overwrite) {
    const name = ($("title").value || "").trim() || "Sans titre";
    const r = await fetch("/api/library/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, text: $("text").value, overwrite: !!overwrite }),
    });
    if (r.status === 409) {
      // un texte du même nom existe déjà : on demande confirmation au lieu d'écraser
      const info = await r.json();
      if (confirm(`Un texte « ${info.name} » existe déjà. L'écraser ?`)) return saveLibrary(true);
      return;
    }
    if (!r.ok) { toast("Erreur d'enregistrement"); return; }
    const res = await r.json();
    toast(res.sanitized ? `Enregistré sous « ${res.name} »` : "Enregistré ✓");
    refreshLibrary();
  }
  $("saveLib").addEventListener("click", () => saveLibrary(false));

  // --- Bibliothèque ---------------------------------------------------------
  async function refreshLibrary() {
    const items = await api("/api/library");
    const box = $("libList");
    box.innerHTML = "";
    if (!items.length) { box.innerHTML = '<div class="muted">Aucun texte enregistré.</div>'; return; }
    items.forEach((it) => {
      const row = document.createElement("div");
      row.className = "item";
      row.innerHTML = `<span class="name">${escapeHtml(it.name)}</span>`;
      const load = mkBtn("Charger", "primary");
      const del = mkBtn("✕", "danger");
      load.onclick = async () => {
        const res = await api("/api/library/load?name=" + encodeURIComponent(it.name));
        await loadState();
        toast("« " + res.title + " » chargé");
      };
      del.onclick = async () => {
        await postJSON("/api/library/delete", { name: it.name });
        refreshLibrary();
      };
      row.appendChild(load); row.appendChild(del);
      box.appendChild(row);
    });
  }

  // --- Import fichier -------------------------------------------------------
  $("pickFile").addEventListener("click", () => $("file").click());
  $("file").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    const res = await api("/api/upload", { method: "POST", body: fd });
    await loadState();
    toast("Importé : " + res.title);
    e.target.value = "";
  });

  // --- Import clé USB -------------------------------------------------------
  $("scanUsb").addEventListener("click", async () => {
    toast("Recherche de clés USB…");
    const files = await api("/api/usb");
    const box = $("usbList");
    box.innerHTML = "";
    if (!files.length) { box.innerHTML = '<div class="muted">Aucune clé USB / fichier .txt détecté. Branche la clé sur le boîtier puis réessaie.</div>'; return; }
    files.forEach((f) => {
      const row = document.createElement("div");
      row.className = "item";
      row.innerHTML = `<span class="name">${escapeHtml(f.name)}</span>`;
      const load = mkBtn("Charger", "primary");
      load.onclick = async () => {
        const res = await postJSON("/api/usb/load", { path: f.path });
        await loadState();
        toast("Chargé : " + res.title);
      };
      row.appendChild(load);
      box.appendChild(row);
    });
  });

  // --- Commandes de contrôle ------------------------------------------------
  document.querySelectorAll("[data-cmd]").forEach((btn) => {
    btn.addEventListener("click", () => {
      postJSON("/api/command", { cmd: btn.dataset.cmd });
      const labels = { play: "Lecture", pause: "Pause", restart: "Début", faster: "Plus vite", slower: "Moins vite" };
      toast(labels[btn.dataset.cmd] || "OK");
    });
  });

  // --- Réglages : sliders ---------------------------------------------------
  function bindSlider(id, key, fmt, transform) {
    const el = $(id);
    const apply = () => {
      const v = Number(el.value);
      $(id + "Val").textContent = fmt(v);
      const value = transform ? transform(v) : v;
      settings[key] = value;
      postJSON("/api/settings", { [key]: value });
    };
    el.addEventListener("input", () => { $(id + "Val").textContent = fmt(Number(el.value)); });
    el.addEventListener("change", apply);
  }
  bindSlider("speed", "speed", (v) => String(v));
  bindSlider("fontSize", "fontSize", (v) => String(v));
  bindSlider("lineHeight", "lineHeight", (v) => (v / 10).toFixed(1), (v) => v / 10);
  bindSlider("margin", "margin", (v) => v + "%");

  // --- Réglages : interrupteurs --------------------------------------------
  function bindToggle(id, key) {
    $(id).addEventListener("change", (e) => {
      settings[key] = e.target.checked;
      postJSON("/api/settings", { [key]: e.target.checked });
    });
  }
  bindToggle("mirrorH", "mirrorH");
  bindToggle("mirrorV", "mirrorV");
  bindToggle("guide", "guide");

  // --- Réglages : boutons (align / police / mode) --------------------------
  function bindChoice(selector, attr, key) {
    document.querySelectorAll(selector).forEach((b) =>
      b.addEventListener("click", () => {
        settings[key] = b.dataset[attr];
        markSel(selector, attr, b.dataset[attr]);
        postJSON("/api/settings", { [key]: b.dataset[attr] });
      }));
  }
  bindChoice(".alignBtn", "align", "align");
  bindChoice(".fontBtn", "font", "font");
  bindChoice(".modeBtn", "mode", "mode");

  // --- Couleurs -------------------------------------------------------------
  const FG_COLORS = ["#ffffff", "#ffd400", "#eaeaea", "#00e0ff", "#9dff70", "#000000"];
  const BG_COLORS = ["#000000", "#101010", "#0a1a2f", "#003300", "#1a1a1a", "#ffffff"];
  function renderSwatches() {
    fillSwatches("fgSwatches", FG_COLORS, settings.textColor || "#ffffff", "textColor");
    fillSwatches("bgSwatches", BG_COLORS, settings.bgColor || "#000000", "bgColor");
  }
  function fillSwatches(id, colors, current, key) {
    const box = $(id);
    box.innerHTML = "";
    colors.forEach((c) => {
      const s = document.createElement("div");
      s.className = "swatch" + (c.toLowerCase() === String(current).toLowerCase() ? " sel" : "");
      s.style.background = c;
      s.onclick = () => {
        settings[key] = c;
        postJSON("/api/settings", { [key]: c });
        fillSwatches(id, colors, c, key);
      };
      box.appendChild(s);
    });
  }

  // --- Apprentissage des touches de pédale ---------------------------------
  function bindKeyLearn(id, key) {
    const el = $(id);
    el.addEventListener("focus", () => { el.value = "… appuie sur la pédale"; });
    el.addEventListener("keydown", (e) => {
      e.preventDefault();
      settings[key] = e.key;
      el.value = e.key;
      postJSON("/api/settings", { [key]: e.key });
      toast("Touche enregistrée : " + e.key);
      el.blur();
    });
  }
  bindKeyLearn("keyForward", "keyForward");
  bindKeyLearn("keyBackward", "keyBackward");

  // --- Utilitaires ----------------------------------------------------------
  function mkBtn(label, cls) {
    const b = document.createElement("button");
    b.textContent = label;
    if (cls) b.className = cls;
    return b;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  loadState().catch(() => toast("Erreur de connexion au boîtier"));
})();
