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

  // récupère le message d'erreur lisible renvoyé par le serveur (corps JSON)
  function errText(err) {
    try { return JSON.parse(err && err.message).error; } catch { return null; }
  }

  // Lien pour l'écran régie / spectateur (affiché dans l'onglet Contrôle)
  async function loadViewLink() {
    try {
      const info = await api("/api/info");
      const ip = (info.addresses || [])[0] || "10.42.0.1";
      $("viewLink").textContent = `http://${ip}:${info.port || 5000}/view`;
    } catch {
      $("viewLink").textContent = "http://10.42.0.1:5000/view";
    }
  }

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
    refreshPedals();
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
        // POST : charger un texte modifie ce qui est à l'antenne (voir server.py).
        const res = await postJSON("/api/library/load", { name: it.name });
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
    try {
      // En-tête maison exigé par le serveur : une page tierce ne peut pas le poser
      // sans pré-vol CORS, ce qui protège cette route (multipart, donc sans la
      // barrière Content-Type des routes JSON).
      const r = await fetch("/api/upload", {
        method: "POST",
        headers: { "X-Prompteur-Client": "1" },
        body: fd,
      });
      const res = await r.json().catch(() => ({}));
      if (!r.ok || !res.ok) { toast(res.error || "Import impossible"); return; }
      await loadState();
      toast("Importé : " + res.title);
    } catch {
      toast("Import impossible");
    } finally {
      e.target.value = "";
    }
  });

  // --- Import clé USB -------------------------------------------------------
  $("scanUsb").addEventListener("click", async () => {
    toast("Recherche de clés USB…");
    const files = await api("/api/usb");
    const box = $("usbList");
    box.innerHTML = "";
    if (!files.length) { box.innerHTML = '<div class="muted">Aucun fichier détecté sur une clé USB. Branche la clé sur le boîtier puis réessaie.</div>'; return; }
    files.forEach((f) => {
      const row = document.createElement("div");
      row.className = "item";
      row.innerHTML = `<span class="name">${escapeHtml(f.name)}</span>`;
      const load = mkBtn("Charger", "primary");
      load.onclick = async () => {
        try {
          const res = await postJSON("/api/usb/load", { path: f.path });
          await loadState();
          toast("Chargé : " + res.title);
        } catch (err) {
          toast(errText(err) || "Lecture impossible");
        }
      };
      row.appendChild(load);
      box.appendChild(row);
    });
  });

  // --- Commandes de contrôle ------------------------------------------------
  // Reflète la vitesse renvoyée par le serveur sur la barre « Vitesse de lecture »
  function reflectSpeed(v) {
    if (v == null) return;
    settings.speed = v;
    if ($("speed")) $("speed").value = v;
    if ($("speedVal")) $("speedVal").textContent = v;
  }

  document.querySelectorAll("[data-cmd]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const cmd = btn.dataset.cmd;
      const labels = { play: "Lecture", pause: "Pause", restart: "Début", faster: "Plus vite", slower: "Moins vite" };
      toast(labels[cmd] || "OK");
      try {
        const res = await postJSON("/api/command", { cmd });
        // Plus vite / Moins vite : on fait bouger la barre de vitesse et sa valeur
        if (cmd === "faster" || cmd === "slower") reflectSpeed(res.speed);
      } catch {
        toast("Commande impossible");
      }
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
  // Deux garanties, apprises d'un incident réel :
  //  1. RIEN n'est envoyé au boîtier tant que « Enregistrer » n'a pas été appuyé ;
  //  2. la confirmation n'est affichée qu'après RELECTURE de l'état du boîtier —
  //     « enregistré » veut donc dire réellement enregistré, pas « envoyé en aveugle ».
  // On refuse aussi les deux cas qui rendent une pédale muette sans prévenir :
  // la touche F (interceptée avant les pédales) et une touche déjà prise par l'autre pédale.
  const PEDAL_LABEL = { keyForward: "pédale droite (avancer)", keyBackward: "pédale gauche (reculer)" };
  const RESERVED = {
    " ": "Espace (lecture/pause)",
    r: "R (retour au début)", R: "R (retour au début)",
    m: "M (miroir)", M: "M (miroir)",
    h: "H (bandeau d'aide)", H: "H (bandeau d'aide)",
    i: "I (adresse du boîtier)", I: "I (adresse du boîtier)",
    "+": "+ (plus vite)", "=": "+ (plus vite)",
    "-": "− (moins vite)", _: "− (moins vite)",
  };
  // Touches seules qui ne sont pas des touches de pédale : on continue d'attendre.
  const IGNORED = ["Shift", "Control", "Alt", "AltGraph", "Meta", "CapsLock", "Dead", "Unidentified"];
  // Certaines touches s'affichent « vides » : sans ça, l'utilisateur croit qu'aucune touche
  // n'est réglée alors qu'il y en a une. On garde la valeur technique, on affiche un libellé.
  const KEY_LABEL = { " ": "Espace" };
  const keyLabel = (k) => (k ? KEY_LABEL[k] || k : "");

  const pedals = {};
  let capturing = null; // un seul apprentissage à la fois

  function refreshPedals() {
    Object.keys(pedals).forEach((k) => pedals[k].refresh());
  }

  function bindKeyLearn(key, otherKey) {
    const el = $(key);
    const box = $("pedal-" + key);
    const stat = $(key + "Stat");
    const bLearn = $(key + "Learn");
    const bSave = $(key + "Save");
    const bCancel = $(key + "Cancel");
    const self = { pending: null };
    pedals[key] = self;

    function setStat(msg, cls) {
      stat.textContent = msg;
      stat.className = "pedalstat" + (cls ? " " + cls : "");
    }
    function show(state) {
      box.classList.toggle("capture", state === "capture");
      box.classList.toggle("pending", state === "pending");
      bLearn.classList.toggle("hide", state !== "idle");
      bSave.classList.toggle("hide", state !== "pending");
      bCancel.classList.toggle("hide", state === "idle");
      bSave.disabled = state === "saving";
      bCancel.disabled = state === "saving";
    }
    function toIdle(msg, cls) {
      self.pending = null;
      if (capturing === self) capturing = null;
      el.value = keyLabel(settings[key]);
      show("idle");
      setStat(msg, cls);
    }

    self.refresh = () => {
      if (self.pending || capturing === self) return; // ne casse pas un apprentissage en cours
      const cur = settings[key];
      if (!cur) return toIdle("Aucune touche réglée : cette pédale ne fera rien.", "warn");
      if (RESERVED[cur]) {
        return toIdle("Active sur le boîtier, mais « " + keyLabel(cur) + " » est aussi le raccourci " +
          RESERVED[cur] + " : ce raccourci ne marche plus.", "warn");
      }
      toIdle("Touche active sur le boîtier.", "ok");
    };
    self.cancel = () => toIdle("Annulé — rien n'a été changé.", "");

    // Appel depuis l'écouteur global : la pédale envoie sa touche à la page entière.
    self.capture = (e) => {
      const k = e.key;
      if (IGNORED.indexOf(k) !== -1) return;
      e.preventDefault();
      if (k === "f" || k === "F") {
        setStat("Impossible : F est réservé au plein écran, une pédale réglée sur F ne marcherait jamais. Appuie sur une autre pédale.", "err");
        return;
      }
      if (settings[otherKey] && k === settings[otherKey]) {
        setStat("Impossible : « " + keyLabel(k) + " » est déjà la touche de la " + PEDAL_LABEL[otherKey] +
          ". Les deux pédales doivent envoyer des touches différentes, sinon l'une des deux devient muette.", "err");
        return;
      }
      self.pending = k;
      el.value = keyLabel(k);
      show("pending");
      setStat("Touche détectée : « " + keyLabel(k) + " ». Rien n'est encore envoyé au boîtier — appuie sur Enregistrer." +
        (RESERVED[k] ? " ⚠ Cette touche sert aussi au raccourci " + RESERVED[k] + ", qui sera remplacé." : ""), "warn");
    };

    bLearn.addEventListener("click", () => {
      if (capturing && capturing !== self) capturing.cancel();
      capturing = self;
      self.pending = null;
      el.value = "Appuie sur la pédale…";
      show("capture");
      setStat("En attente. Appuie une fois sur la " + PEDAL_LABEL[key] + ". Rien n'est enregistré à ce stade.", "");
    });

    bCancel.addEventListener("click", () => self.cancel());

    bSave.addEventListener("click", async () => {
      const k = self.pending;
      if (!k) return;
      show("saving");
      setStat("Envoi au boîtier…", "");
      try {
        await postJSON("/api/settings", { [key]: k });
        // Relecture de l'état réel du boîtier : seule preuve fiable que c'est gardé.
        const st = await api("/api/state");
        settings = st.settings || settings;
        if (settings[key] === k) {
          toIdle("✓ Enregistré sur le boîtier : « " + keyLabel(k) + " ».", "ok");
          toast("Touche enregistrée : " + keyLabel(k));
        } else {
          toIdle("✗ Le boîtier n'a pas accepté cette touche. Rien n'a été changé.", "err");
        }
      } catch {
        toIdle("✗ Échec : le boîtier n'a pas répondu. Rien n'a été changé.", "err");
      }
      if (pedals[otherKey]) pedals[otherKey].refresh();
    });
  }

  // Les pédales envoient leur touche à la page, pas à un champ précis : on écoute globalement,
  // et on ne réagit que pendant un apprentissage explicitement démarré.
  window.addEventListener("keydown", (e) => { if (capturing) capturing.capture(e); });

  bindKeyLearn("keyForward", "keyBackward");
  bindKeyLearn("keyBackward", "keyForward");

  // --- Barre « Écran du boîtier » ------------------------------------------
  // Le prompteur est une application qu'on ouvre et qu'on ferme : plus besoin de
  // redémarrer le boîtier pour y revenir. Le serveur ne déclare ces commandes
  // disponibles que si la page est ouverte SUR le boîtier : depuis un téléphone,
  // elles n'auraient aucun sens (il n'affiche pas le prompteur) et un appui
  // accidentel fermerait l'écran en pleine prise.
  async function refreshKiosk() {
    let info;
    try {
      info = await api("/api/kiosk");
    } catch {
      return; // serveur muet : on laisse la barre cachée plutôt que d'afficher un état faux
    }
    if (!info.available) return;
    $("boxbar").classList.remove("hide");
    if (info.running === null) {
      // État indéterminé : on le dit, plutôt que de faire disparaître la barre.
      $("kioskState").innerHTML =
        "État de l'écran <b>indéterminé</b> : le script de lancement n'a pas pu être " +
        "exécuté ici. Ces boutons ne fonctionnent que sur le boîtier lui-même.";
      $("kioskLaunch").disabled = true;
      $("kioskClose").disabled = true;
      return;
    }
    const running = !!info.running;
    $("kioskState").innerHTML = running
      ? "Le prompteur est <b>affiché</b> sur l'écran du boîtier."
      : "Le prompteur est <b>fermé</b> : l'écran du boîtier montre le bureau.";
    $("kioskLaunch").disabled = running;
    $("kioskClose").disabled = !running;
  }

  function bindKiosk() {
    const act = async (btn, path, attente) => {
      btn.disabled = true;
      $("kioskState").textContent = attente;
      try {
        await postJSON(path, {});
      } catch (err) {
        toast(errText(err) || "Commande impossible");
      }
      // Chromium met un instant à s'ouvrir ou à se fermer : on relit après.
      setTimeout(refreshKiosk, 1200);
    };
    $("kioskLaunch").addEventListener("click", (e) =>
      act(e.currentTarget, "/api/kiosk/launch", "Ouverture du prompteur…"));
    $("kioskClose").addEventListener("click", (e) => {
      // Confirmation sur ce seul bouton : il est atteignable depuis un téléphone,
      // et un appui involontaire couperait l'écran en pleine prise.
      if (!confirm("Fermer le prompteur et revenir au bureau du boîtier ?")) return;
      act(e.currentTarget, "/api/kiosk/close", "Fermeture du prompteur…");
    });
    $("kioskRefresh").addEventListener("click", refreshKiosk);
    $("openView").addEventListener("click", () => window.open("/view", "_blank"));
  }
  bindKiosk();

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
  refreshKiosk();
  loadViewLink();
})();
