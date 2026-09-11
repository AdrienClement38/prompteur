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
  // Version connue de l'état du boîtier, et drapeau de saisie en cours : on ne
  // remplace JAMAIS un texte que quelqu'un est en train d'écrire.
  let knownVersion = null;
  let knownLibSeq = null;
  let textDirty = false;
  // Texte reellement a l'ecran, pour savoir si la zone de saisie en differe.
  let sentText = null;

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
    try {
      knownLibSeq = (await api("/api/version")).libSeq;
    } catch {
      knownLibSeq = null;
    }
    settings = s.settings || {};
    knownVersion = s.version;
    $("title").value = s.title || "";
    setText(s.text || "");
    sentText = s.text || "";
    texteAvant = s.text || "";
    marks = Array.isArray(s.marks) ? s.marks : [];
    textDirty = false;
    reflectSettings();
    refreshLibrary();
    refreshUnsent();
  }

  // --- Repère « pas encore à l'écran » --------------------------------------
  // Depuis que l'import ne part plus seul à l'écran, il FAUT dire quand la zone
  // de saisie diffère de ce qui est diffusé. Sans ce repère, on importe, on ne
  // voit rien changer, et on croit que le boîtier ne répond plus — une bizarrerie
  // signalée serait devenue une panne perçue, en plein tournage.
  function refreshUnsent() {
    const differe = sentText !== null && getText() !== sentText;
    $("unsent").classList.toggle("hide", !differe);
  }

  // --- Synchronisation entre appareils --------------------------------------
  // Plusieurs pages sont ouvertes en même temps : le téléphone du présentateur,
  // l'écran du boîtier, l'ordinateur de la régie. Jusqu'ici, un réglage modifié
  // par l'un n'apparaissait chez les autres qu'après un rechargement manuel.
  // On interroge /api/version, qui ne renvoie que deux entiers, et on ne relit
  // l'état complet que lorsqu'il a réellement changé. Pas de websocket : le seul
  // chemin qui compte — pédale vers écran — ne passe par aucun réseau.
  async function pollVersion() {
    let v;
    try {
      v = await api("/api/version");
    } catch {
      return; // liaison perdue : on réessaiera au tour suivant
    }
    // La bibliothèque a son propre compteur : un texte enregistré ou supprimé
    // ailleurs doit apparaître ou disparaître ici sans recharger la page, mais
    // sans perturber pour autant les écrans de lecture.
    if (knownLibSeq === null) knownLibSeq = v.libSeq;
    else if (v.libSeq !== knownLibSeq) {
      knownLibSeq = v.libSeq;
      refreshLibrary();
    }
    if (knownVersion === null || v.version === knownVersion) return;
    knownVersion = v.version;
    let st;
    try {
      st = await api("/api/state");
    } catch {
      return;
    }
    settings = st.settings || {};
    reflectSettings();
    sentText = st.text || "";
    if (textDirty) {
      // Quelqu'un a envoyé un autre texte pendant qu'on écrivait : on prévient,
      // mais on n'écrase pas la saisie en cours.
      refreshUnsent();
      toast("Le texte a changé sur le boîtier");
      return;
    }
    $("title").value = st.title || "";
    setText(st.text || "");
    sentText = st.text || "";
    texteAvant = st.text || "";
    marks = Array.isArray(st.marks) ? st.marks : [];
    refreshLibrary();
    refreshUnsent();
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
    markSel(".modeBtn", "mode", settings.mode || "hold");
    setSlider("rampSeconds", settings.rampSeconds, (v) => v + " s");
    // Le réglage de montée n'a de sens qu'en mode dynamique : on le masque ailleurs
    // plutôt que d'offrir un curseur sans effet.
    $("rampRow").classList.toggle("hide", (settings.mode || "hold") !== "dyn");
    // Une seule explication a l'ecran : celle du mode choisi. Les trois ensemble
    // faisaient un pave que plus personne ne lisait.
    document.querySelectorAll(".modeHelp").forEach((p) =>
      p.classList.toggle("hide", p.dataset.mode !== (settings.mode || "hold")));
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

  let texteAvant = "";
  ["text", "title"].forEach((id) =>
    $(id).addEventListener("input", () => {
      if (id === "text") {
        // On NE reconstruit PAS la zone a chaque frappe : cela deplacerait le
        // curseur a chaque caractere. Les plages sont recalees, le rendu suit au
        // prochain bouton de mise en forme.
        remapMarks(texteAvant, getText());
        texteAvant = getText();
      }
      textDirty = true;
      refreshUnsent();
    }));

  // --- Zone de saisie riche -------------------------------------------------
  // Une <textarea> ne sait afficher que du texte nu : c'est ce qui avait imposé
  // un aperçu à côté. Ici la mise en forme se voit LÀ OÙ L'ON TAPE, avec les
  // mêmes classes que l'écran, donc le même rendu.
  //
  // « plaintext-only » est essentiel : le navigateur n'insère alors que du texte
  // et des sauts de ligne, jamais ses propres balises, et un collage arrive
  // débarrassé de la mise en forme de sa provenance. Le texte reste donc une
  // chaîne brute, et la mise en forme reste notre liste de plages.
  const editor = $("text");
  const SIZE_CLASS = { s: "ms", l: "ml", xl: "mxl" };

  const getText = () => editor.textContent;

  function classesAt(index) {
    let cls = "";
    let taille = null;
    let couleur = null;
    for (const m of marks) {
      if (index < m.start || index >= m.end) continue;
      if (m.b && !cls.includes("mb")) cls += " mb";
      if (m.i && !cls.includes("mi")) cls += " mi";
      if (m.u && !cls.includes("mu")) cls += " mu";
      if (SIZE_CLASS[m.size]) taille = SIZE_CLASS[m.size];
      if (m.color >= 1 && m.color <= 5) couleur = "c" + m.color;
    }
    if (taille) cls += " " + taille;
    if (couleur) cls += " " + couleur;
    return cls.trim();
  }

  // Reconstruit la zone à partir du texte et des plages. On ne coupe qu'aux
  // FRONTIÈRES des plages, pas à chaque caractère.
  function renderEditor(texte) {
    const bornes = [0, texte.length];
    for (const m of marks) bornes.push(m.start, m.end);
    const coupes = [...new Set(bornes)]
      .filter((b) => b >= 0 && b <= texte.length)
      .sort((a, b) => a - b);
    editor.replaceChildren();
    for (let k = 0; k < coupes.length - 1; k++) {
      const morceau = texte.slice(coupes[k], coupes[k + 1]);
      if (!morceau) continue;
      const cls = classesAt(coupes[k]);
      if (!cls) {
        editor.appendChild(document.createTextNode(morceau));
      } else {
        const span = document.createElement("span");
        span.className = cls;
        span.textContent = morceau; // textContent -> aucun risque d'injection
        editor.appendChild(span);
      }
    }
  }

  function setText(texte) {
    renderEditor(texte || "");
  }

  // --- Position de la sélection, en indices de caractères -------------------
  // Dans une zone éditable, la sélection désigne un nœud et un décalage dans ce
  // nœud. Nos plages, elles, sont des indices dans le texte entier : il faut donc
  // traduire dans les deux sens.
  function offsetDe(noeud, decalage) {
    if (noeud === editor) {
      let total = 0;
      for (let i = 0; i < decalage && i < editor.childNodes.length; i++) {
        total += editor.childNodes[i].textContent.length;
      }
      return total;
    }
    let total = 0;
    const marcheur = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = marcheur.nextNode())) {
      if (n === noeud) return total + decalage;
      total += n.nodeValue.length;
    }
    return total;
  }

  function selectionCourante() {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return null;
    const plage = sel.getRangeAt(0);
    if (!editor.contains(plage.startContainer) && plage.startContainer !== editor) return null;
    const a = offsetDe(plage.startContainer, plage.startOffset);
    const b = offsetDe(plage.endContainer, plage.endOffset);
    return { debut: Math.min(a, b), fin: Math.max(a, b) };
  }

  function replacerSelection(debut, fin) {
    const marcheur = document.createTreeWalker(editor, NodeFilter.SHOW_TEXT);
    let total = 0;
    let noeudD = null;
    let decD = 0;
    let noeudF = null;
    let decF = 0;
    let n;
    while ((n = marcheur.nextNode())) {
      const longueur = n.nodeValue.length;
      if (noeudD === null && debut <= total + longueur) {
        noeudD = n;
        decD = debut - total;
      }
      if (fin <= total + longueur) {
        noeudF = n;
        decF = fin - total;
        break;
      }
      total += longueur;
    }
    if (!noeudD) return;
    if (!noeudF) {
      noeudF = noeudD;
      decF = decD;
    }
    const plage = document.createRange();
    plage.setStart(noeudD, Math.max(0, Math.min(decD, noeudD.nodeValue.length)));
    plage.setEnd(noeudF, Math.max(0, Math.min(decF, noeudF.nodeValue.length)));
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(plage);
  }

  // --- Mise en forme : gras / italique / souligné ---------------------------
  // Le texte reste une CHAÎNE BRUTE ; la mise en forme est une liste de plages
  // posées dessus. Aucun HTML n'est stocké ni transmis : l'écran construit ses
  // éléments un par un. Un texte sans plages s'affiche exactement comme avant.
  let marks = [];

  function refreshFmtInfo() {
    $("fmtInfo").textContent = marks.length
      ? marks.length + (marks.length > 1 ? " passages mis en forme." : " passage mis en forme.")
      : "Sélectionnez un passage, puis un bouton. Rappuyez dessus pour l'enlever.";
  }

  function applyAttr(cle, valeur) {
    const sel = selectionCourante();
    if (!sel || sel.fin <= sel.debut) {
      toast("Sélectionnez d'abord un passage");
      return;
    }
    const { debut, fin } = sel;
    // Déjà entièrement dans ce style ? On l'enlève. Sinon on l'ajoute.
    // Rappuyer sur le meme bouton retire le style : c'est la seule facon de
    // revenir en arriere sans tout effacer.
    const dedans = marks.filter((m) => m[cle] === valeur && m.start <= debut && m.end >= fin);
    if (dedans.length) {
      marks = marks.flatMap((m) => {
        if (m[cle] !== valeur || m.start > debut || m.end < fin) return [m];
        const morceaux = [];
        if (m.start < debut) morceaux.push({ ...m, end: debut });
        if (m.end > fin) morceaux.push({ ...m, start: fin });
        return morceaux;
      });
    } else {
      marks.push({ start: debut, end: fin, [cle]: valeur });
    }
    if (marks.length > 500) marks = marks.slice(-500);
    textDirty = true;
    refreshUnsent();
    refreshFmtInfo();
    // On reconstruit la zone, puis on remet la sélection là où elle était : sans
    // cela le passage qu'on vient de marquer se désélectionne, et enchaîner
    // gras puis italique devient impossible.
    renderEditor(getText());
    editor.focus();
    replacerSelection(debut, fin);
  }

  // Le texte change : on recale les plages sur les parties intactes.
  // On compare le préfixe et le suffixe communs — c'est exact pour une frappe ou
  // un collage ordinaire, et une plage qui chevauche la zone modifiée est
  // rognée plutôt que laissée à une position devenue fausse.
  function remapMarks(avant, apres) {
    if (!marks.length || avant === apres) return;
    let p = 0;
    while (p < avant.length && p < apres.length && avant[p] === apres[p]) p++;
    let s = 0;
    while (
      s < avant.length - p &&
      s < apres.length - p &&
      avant[avant.length - 1 - s] === apres[apres.length - 1 - s]
    ) {
      s++;
    }
    const finAvant = avant.length - s;
    const delta = apres.length - avant.length;
    marks = marks
      .map((m) => {
        if (m.end <= p) return m; // entièrement avant la modification
        if (m.start >= finAvant) return { ...m, start: m.start + delta, end: m.end + delta };
        const start = Math.min(m.start, p);
        const end = Math.max(p, Math.min(m.end, finAvant) + delta);
        return end > start ? { ...m, start, end } : null;
      })
      .filter(Boolean);
    refreshFmtInfo();
  }

  // mousedown + preventDefault : le bouton ne prend pas le focus, donc la
  // sélection reste en place dans la zone de texte au moment du clic. Sans cela,
  // certains navigateurs la vident avant même que le clic soit traité.
  document.querySelectorAll(".fmtbar button, .fmtcolors button").forEach((b) =>
    b.addEventListener("mousedown", (e) => e.preventDefault()));

  $("fmtB").addEventListener("click", () => applyAttr("b", true));
  $("fmtI").addEventListener("click", () => applyAttr("i", true));
  $("fmtU").addEventListener("click", () => applyAttr("u", true));
  $("fmtS").addEventListener("click", () => applyAttr("size", "s"));
  $("fmtL").addEventListener("click", () => applyAttr("size", "l"));
  $("fmtXL").addEventListener("click", () => applyAttr("size", "xl"));
  document.querySelectorAll(".swatchBtn").forEach((b) =>
    b.addEventListener("click", () => applyAttr("color", Number(b.dataset.color))));
  $("fmtClear").addEventListener("click", () => {
    marks = [];
    textDirty = true;
    refreshUnsent();
    refreshFmtInfo();
    renderEditor(getText());
    toast("Mise en forme effacée");
  });

  // --- Envoi du texte -------------------------------------------------------
  $("send").addEventListener("click", async () => {
    const envoye = getText();
    await postJSON("/api/text", { text: envoye, title: $("title").value, marks });
    sentText = envoye;
    textDirty = false;
    refreshUnsent();
    toast("Texte envoyé à l'écran ✓");
  });

  async function saveLibrary(overwrite) {
    const name = ($("title").value || "").trim() || "Sans titre";
    const r = await fetch("/api/library/save", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, text: getText(), overwrite: !!overwrite, marks }),
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

  // Remplit la zone de saisie avec un texte importé, sans rien diffuser.
  function fillFromImport(res) {
    $("title").value = res.title || "";
    texteAvant = res.text || "";
    // Le gras, l'italique et le souligne du document importe arrivent avec lui.
    marks = Array.isArray(res.marks) ? res.marks : [];
    setText(res.text || ""); // apres les plages : le rendu les utilise
    textDirty = true;
    refreshUnsent();
    toast("Importé : " + res.title + " — appuyez sur « Envoyer à l'écran »");
  }

  // --- Import fichier -------------------------------------------------------
  $("pickFile").addEventListener("click", () => $("file").click());
  $("file").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    // On recupere le texte SANS l'envoyer a l'ecran : c'etait le comportement
    // surprenant signale par l'utilisateur. L'envoi reste un geste explicite.
    fd.append("apply", "false");
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
      fillFromImport(res);
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
          const res = await postJSON("/api/usb/load", { path: f.path, apply: false });
          fillFromImport(res);
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
  bindChoice(".modeBtn", "mode", "mode");
  bindSlider("rampSeconds", "rampSeconds", (v) => v + " s");

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
  const PEDAL_LABEL = {
    keyForward: "pédale droite (avancer)",
    keyBackward: "pédale gauche (reculer)",
    keyCenter: "pédale centrale (lecture/pause)",
  };
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

  function bindKeyLearn(key, otherKeys) {
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
      if (k === "Escape") {
        // Échap ferme le prompteur : une pédale réglée dessus couperait l'écran
        // au premier appui, en pleine lecture.
        setStat("Impossible : Échap sert à quitter le prompteur. Une pédale réglée sur Échap fermerait l'écran au premier appui.", "err");
        return;
      }
      const conflit = otherKeys.find((autre) => settings[autre] && k === settings[autre]);
      if (conflit) {
        setStat("Impossible : « " + keyLabel(k) + " » est déjà la touche de la " + PEDAL_LABEL[conflit] +
          ". Chaque pédale doit envoyer une touche différente, sinon l'une d'elles devient muette.", "err");
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
      otherKeys.forEach((autre) => pedals[autre] && pedals[autre].refresh());
    });
  }

  // Les pédales envoient leur touche à la page, pas à un champ précis : on écoute globalement,
  // et on ne réagit que pendant un apprentissage explicitement démarré.
  window.addEventListener("keydown", (e) => { if (capturing) capturing.capture(e); });

  bindKeyLearn("keyForward", ["keyBackward", "keyCenter"]);
  bindKeyLearn("keyBackward", ["keyForward", "keyCenter"]);
  bindKeyLearn("keyCenter", ["keyForward", "keyBackward"]);

  // --- Ouvrir l'écran principal hors du navigateur --------------------------
  // Un onglet ordinaire garde sa barre d'adresse et ses onglets : ce n'est pas un
  // écran de prompteur. On ouvre donc une FENÊTRE dédiée (window.open en mode
  // « popup »), que le navigateur affiche sans barre d'adresse ni onglets, à la
  // taille de l'écran.
  //
  // Deux bénéfices au passage :
  //   * le plein écran y est demandé depuis un vrai geste utilisateur, donc
  //     accepté — au chargement d'un onglet, il est systématiquement refusé ;
  //   * Échap peut REFERMER cette fenêtre (window.close n'est autorisé que sur
  //     une fenêtre ouverte par script), et l'on retombe sur cette page, restée
  //     ouverte derrière. Plus de navigation, donc plus d'impasse possible si le
  //     serveur ne répond pas.
  //
  // Si le navigateur refuse la fenêtre (bloqueur), on retombe sur la navigation
  // classique : mieux vaut un onglet avec barre d'adresse que rien du tout.
  function openMainScreen(e) {
    if (e) e.preventDefault();
    const w = Math.max(640, window.screen.availWidth || 1280);
    const h = Math.max(480, window.screen.availHeight || 720);
    const win = window.open(
      "/display",
      "prompteurPrincipal",
      `popup=yes,width=${w},height=${h},left=0,top=0`
    );
    if (!win) {
      window.location.href = "/display";
      return;
    }
    win.focus();
  }

  // --- Écran principal déjà pris ? -----------------------------------------
  // On grise le bouton plutôt que de laisser quelqu'un entrer et bousculer le
  // défilement de celui qui est en train de lire.
  async function refreshPresenter() {
    const btn = document.querySelector(".readbtn.main");
    if (!btn) return;
    let info;
    try {
      info = await api("/api/presenter");
    } catch {
      return;
    }
    const busy = info.taken && !info.mine;
    btn.classList.toggle("busy", busy);
    btn.querySelector(".tiny").textContent = busy
      ? "déjà utilisé par un autre appareil"
      : "celui qu'on pilote aux pédales";
  }

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
      if (!confirm("Fermer le prompteur sur l'écran du boîtier et revenir à son bureau ?")) return;
      act(e.currentTarget, "/api/kiosk/close", "Fermeture du prompteur…");
    });
    $("kioskRefresh").addEventListener("click", refreshKiosk);
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
  refreshFmtInfo();
  refreshKiosk();
  setInterval(pollVersion, 1500);
  const mainBtn = document.querySelector(".readbtn.main");
  if (mainBtn) mainBtn.addEventListener("click", openMainScreen);
  refreshPresenter();
  setInterval(refreshPresenter, 3000);
  loadViewLink();
})();
