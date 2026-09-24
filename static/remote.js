/* Prompteur — logique de la vue Settings (téléphone, petit écran, PC de régie).
   Envoie le texte, les réglages et les commandes au serveur du boîtier. */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const Commun = window.Commun;
  const toastEl = $("toast");
  let toastTimer = null;
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastTimer);
    // Assez long pour lire un message d'erreur d'une phrase.
    toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2600);
  }

  async function api(path, opts) {
    const r = await fetch(path, Object.assign({ cache: "no-store" }, opts));
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }
  const postJSON = (path, body) =>
    api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

  // Construction d'elements : on n'ecrit JAMAIS de HTML depuis du JavaScript.
  // Les noms de fichiers et de textes viennent du boitier ; passer par du balisage
  // obligerait a se fier a un echappement, alors que textContent ne peut pas se
  // tromper. La CI interdit desormais innerHTML (voir eslint.config.mjs).
  function el(tag, cls, texte) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (texte != null) n.textContent = texte;
    return n;
  }

  // récupère le message d'erreur lisible renvoyé par le serveur (corps JSON)
  function errText(err) {
    try { return JSON.parse(err && err.message).error; } catch { return null; }
  }

  // Adresses des trois vues, montrées dans la fenêtre Info de « Vue du
  // journaliste ». On écrit dans le gabarit lui-même : chaque ouverture de la
  // fenêtre en fait une copie, déjà à jour.
  async function loadAddresses() {
    let base = "http://10.42.0.1:5000";
    try {
      const info = await api("/api/info");
      base = `http://${(info.addresses || [])[0] || "10.42.0.1"}:${info.port || 5000}`;
    } catch {
      /* l'adresse du WiFi du boîtier reste la bonne dans l'immense majorité des cas */
    }
    document.querySelectorAll("template").forEach((gabarit) =>
      gabarit.content.querySelectorAll("[data-adresse]").forEach((n) => {
        n.textContent = base + n.dataset.adresse;
      }));
  }

  let settings = {};
  // Version connue de l'état du boîtier, et drapeau de saisie en cours : on ne
  // remplace JAMAIS un texte que quelqu'un est en train d'écrire.
  let knownVersion = null;
  let knownLibSeq = null;
  let textDirty = false;
  // Texte reellement a l'ecran, pour savoir si la zone de saisie en differe.
  let sentText = null;
  let sentMarks = "[]"; // mise en forme réellement à l'écran (JSON)
  // Empreinte du texte ET de la mise en forme du boîtier, lus en dernier.
  let contenuBoitier = null;
  const signature = (st) => (st.title || "") + "\u0000" + (st.text || "") + "\u0000" + JSON.stringify(st.marks || []);

  // --- Onglets --------------------------------------------------------------
  document.querySelectorAll(".tabbtns button").forEach((btn) => {
    btn.addEventListener("click", () => {
      // Un apprentissage de pédale oublié en cours avalait toutes les touches,
      // y compris la frappe dans la zone de texte.
      if (capturing) capturing.cancel();
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
    contenuBoitier = signature(s);
    $("title").value = s.title || "";
    // Les marques AVANT setText : c'est setText qui redessine la zone de saisie,
    // et il lit « marks ». Dans l'autre ordre, l'editeur affichait la mise en forme
    // du texte precedent — et rien du tout au premier chargement.
    marks = Array.isArray(s.marks) ? s.marks : [];
    setText(s.text || "");
    sentText = s.text || "";
    sentMarks = JSON.stringify(marks);
    texteAvant = s.text || "";
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
    // Le texte OU sa mise en forme : une couleur ajoutée sans toucher au texte
    // n'est pas encore à l'écran non plus.
    const differe = sentText !== null && (getText() !== sentText || JSON.stringify(marks) !== sentMarks);
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
    Commun.veille.maj(v.veille);
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
    // Un simple réglage (la vitesse posée au pied, la taille…) fait aussi
    // avancer la version : on ne touche à la zone de saisie QUE si le texte ou sa
    // mise en forme ont réellement changé. Sinon on effacerait une sélection en
    // cours, et l'on crierait « le texte a changé » à tort.
    const contenu = signature(st);
    if (contenu === contenuBoitier) return;
    contenuBoitier = contenu;
    sentText = st.text || "";
    sentMarks = JSON.stringify(Array.isArray(st.marks) ? st.marks : []);
    if (textDirty) {
      // Quelqu'un a envoyé un autre texte pendant qu'on écrivait : on prévient,
      // mais on n'écrase pas la saisie en cours.
      refreshUnsent();
      toast("Le texte a changé sur le boîtier");
      return;
    }
    $("title").value = st.title || "";
    marks = Array.isArray(st.marks) ? st.marks : []; // avant setText : voir plus haut
    setText(st.text || "");
    sentText = st.text || "";
    sentMarks = JSON.stringify(marks);
    texteAvant = st.text || "";
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

  // Le mode d'emploi est dans la fenêtre Info : ici, seulement l'état.
  function refreshFmtInfo() {
    $("fmtInfo").textContent = marks.length
      ? marks.length + (marks.length > 1 ? " passages mis en forme." : " passage mis en forme.")
      : "";
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
    } else if (marks.length >= 500) {
      // Même plafond que le boîtier, qui garde les 500 PREMIÈRES : ici, on
      // supprimait au contraire les premières, en silence.
      toast("Limite de 500 passages mis en forme atteinte");
      return;
    } else {
      marks.push({ start: debut, end: fin, [cle]: valeur });
    }
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

  // Le texte change : on recale les plages sur les parties intactes
  // (static/plages.js, vérifié par tests/banc_plages.js).
  function remapMarks(avant, apres) {
    if (!marks.length || avant === apres) return;
    marks = window.Plages.recaler(marks, avant, apres);
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
    try {
      await postJSON("/api/text", { text: envoye, title: $("title").value, marks });
    } catch (err) {
      // Un envoi qui échoue DOIT se voir : sinon on croit le texte à l'écran.
      toast(errText(err) || "Envoi impossible : le boîtier n'a pas répondu");
      return;
    }
    sentText = envoye;
    sentMarks = JSON.stringify(marks);
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
    box.replaceChildren();
    if (!items.length) { box.appendChild(el("div", "muted", "Aucun texte enregistré.")); return; }
    items.forEach((it) => {
      const row = document.createElement("div");
      row.className = "item";
      row.appendChild(el("span", "name", it.name));
      const load = mkBtn("Charger", "primary");
      const del = mkBtn("✕", "danger");
      load.onclick = async () => {
        // POST : charger un texte modifie ce qui est à l'antenne (voir server.py).
        try {
          const res = await postJSON("/api/library/load", { name: it.name });
          await loadState();
          toast("« " + res.title + " » chargé");
        } catch (err) {
          toast(errText(err) || "Chargement impossible");
        }
      };
      del.onclick = async () => {
        // Suppression definitive : ni corbeille, ni sauvegarde, et le dossier des
        // textes n'est pas versionne. Un doigt qui derape un jour de tournage
        // effacerait le script sans aucun recours. On demande donc confirmation,
        // et on dit si le boitier a refuse.
        if (!confirm("Supprimer definitivement « " + it.name + " » ? Cette action est irreversible.")) return;
        try {
          await postJSON("/api/library/delete", { name: it.name });
          toast("« " + it.name + " » supprime");
        } catch (err) {
          toast(errText(err) || "Suppression impossible");
        }
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
    // Un plafond qui s'applique en silence ferait croire que la fin du document
    // n'était pas mise en forme. On le dit.
    toast(res.marksTruncated
      ? "Importé : " + res.title + " — document long : mise en forme gardée sur les premiers passages"
      : "Importé : " + res.title + " — appuyez sur « Envoyer à l'écran »");
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
    let files;
    try {
      files = await api("/api/usb");
    } catch {
      toast("Le boîtier n'a pas répondu");
      return;
    }
    const box = $("usbList");
    box.replaceChildren();
    if (!files.length) {
      box.appendChild(el("div", "muted",
        "Aucun fichier détecté sur une clé USB. Branchez la clé sur le boîtier puis réessayez."));
      return;
    }
    files.forEach((f) => {
      const row = document.createElement("div");
      row.className = "item";
      row.appendChild(el("span", "name", f.name));
      if (f.tropGros) {
        // Plus de 5 Mo : on le montre quand même, sinon on croit la clé illisible.
        row.appendChild(el("span", "muted", "trop lourd (plus de 5 Mo)"));
        box.appendChild(row);
        return;
      }
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
      pousserReglage({ [key]: value });
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
      pousserReglage({ [key]: e.target.checked });
    });
  }
  bindToggle("mirrorH", "mirrorH");
  bindToggle("mirrorV", "mirrorV");
  bindToggle("guide", "guide");

  // --- Réglages : boutons (align / police / mode) --------------------------
  // Envoi d'un réglage. Le serveur répond 400 si la valeur est refusée : sans ce
  // traitement, le bouton resterait coloré et l'on croirait avoir changé de mode
  // alors que rien n'aurait bougé sur l'écran. On le dit, et on remet l'interface
  // en accord avec l'état RÉEL du boîtier.
  async function pousserReglage(corps) {
    try {
      await postJSON("/api/settings", corps);
      return true;
    } catch (err) {
      toast(errText(err) || "Réglage refusé par le boîtier");
      try {
        const st = await api("/api/state");
        settings = st.settings || {};
        reflectSettings();
      } catch {
        /* liaison perdue : la boucle de synchronisation reprendra la main */
      }
      return false;
    }
  }

  function bindChoice(selector, attr, key) {
    document.querySelectorAll(selector).forEach((b) =>
      b.addEventListener("click", () => {
        settings[key] = b.dataset[attr];
        markSel(selector, attr, b.dataset[attr]);
        pousserReglage({ [key]: b.dataset[attr] });
      }));
  }
  bindChoice(".alignBtn", "align", "align");
  bindChoice(".modeBtn", "mode", "mode");
  bindSlider("rampSeconds", "rampSeconds", (v) => v + " s");

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
        await postJSON("/api/settings", { [key]: k }); // relecture dédiée juste après
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
  window.addEventListener("keydown", (e) => {
    if (!capturing) return;
    // Une frappe dans un champ de saisie n'est pas une pédale.
    const cible = e.target;
    if (cible && (cible.isContentEditable || cible.tagName === "INPUT" || cible.tagName === "TEXTAREA")) return;
    capturing.capture(e);
  });

  bindKeyLearn("keyForward", ["keyBackward", "keyCenter"]);
  bindKeyLearn("keyBackward", ["keyForward", "keyCenter"]);
  bindKeyLearn("keyCenter", ["keyForward", "keyBackward"]);

  // --- Ouvrir la vue Journaliste sur cet appareil ---------------------------
  // (pédalier branché sur un ordinateur portable ; bouton dans l'Info de « Vue
  // du journaliste »). Un onglet ordinaire garde sa barre d'adresse et ses
  // onglets : ce n'est pas un écran de prompteur. On ouvre donc une FENÊTRE
  // dédiée (window.open en mode « popup »), sans barre d'adresse ni onglets.
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
  function openMainScreen() {
    const w = Math.max(640, window.screen.availWidth || 1280);
    const h = Math.max(480, window.screen.availHeight || 720);
    const win = window.open("/journaliste", "prompteurPrincipal", `popup=yes,width=${w},height=${h},left=0,top=0`);
    if (!win) {
      window.location.href = "/journaliste";
      return;
    }
    win.focus();
  }
  // Délégation : le bouton vit dans un gabarit, recopié à chaque ouverture de la
  // fenêtre Info.
  document.addEventListener("click", (e) => {
    if (!e.target.closest('[data-action="journaliste-ici"]')) return;
    Commun.fermer();
    openMainScreen();
  });

  // --- Vue du journaliste : ce que montre le grand écran ---------------------
  // Trois choix : la vue Journaliste (le prompteur), la vue Settings, ou le
  // bureau (navigateur fermé). L'état est relu tout seul toutes les quelques
  // secondes : plus de bouton « Actualiser ».
  const NOMS_GRAND = { journaliste: "la vue Journaliste", settings: "la vue Settings", bureau: "le bureau" };
  let grandActuel = null; // "journaliste" | "settings" | "bureau" | null (inconnu)
  let grandEnCours = false; // un changement est en cours : on ne réécrit pas l'état

  function dessinerGrand(texteEtat, nom) {
    const etat = $("grandEtat");
    if (nom) {
      etat.replaceChildren(document.createTextNode(texteEtat), el("b", null, nom), document.createTextNode("."));
    } else {
      etat.textContent = texteEtat;
    }
    document.querySelectorAll("[data-grand]").forEach((b) => {
      b.classList.toggle("actif", b.dataset.grand === grandActuel);
      b.disabled = grandActuel === null || grandEnCours;
    });
  }

  async function refreshKiosk() {
    if (grandEnCours) return;
    let info;
    try {
      info = await api("/api/kiosk");
    } catch {
      return; // serveur muet : on garde le dernier état connu plutôt qu'un état faux
    }
    if (!info.available) return;
    $("grand").classList.remove("hide");
    if (info.running === null) {
      // État indéterminé : on le dit, plutôt que de faire disparaître la section.
      grandActuel = null;
      dessinerGrand("État du grand écran inconnu : ces boutons ne fonctionnent que sur le boîtier lui-même.");
      return;
    }
    grandActuel = info.running ? info.vue || "journaliste" : "bureau";
    dessinerGrand("Le grand écran affiche ", NOMS_GRAND[grandActuel]);
  }

  async function choisirGrand(cible) {
    if (grandActuel === null || grandEnCours || cible === grandActuel) return;
    // Quitter la vue Journaliste retire le texte du grand écran : depuis un
    // téléphone, un appui involontaire couperait la lecture en pleine prise.
    if (grandActuel === "journaliste") {
      const oui = await Commun.confirmer({
        titre: "Retirer le prompteur du grand écran ?",
        texte: `Le grand écran affichera ${NOMS_GRAND[cible]}. Le texte et la position sont conservés.`,
        ok: cible === "bureau" ? "Afficher le bureau" : "Afficher Settings",
        danger: true,
      });
      if (!oui) return;
    }
    grandEnCours = true;
    dessinerGrand("Changement en cours…");
    try {
      if (cible === "bureau") await postJSON("/api/kiosk/close", {});
      else await postJSON("/api/kiosk/launch", { vue: cible });
    } catch (err) {
      toast(errText(err) || "Commande impossible");
    }
    // Chromium met un instant à s'ouvrir ou à se fermer : on relit après.
    setTimeout(() => {
      grandEnCours = false;
      refreshKiosk();
    }, 1500);
  }

  document.querySelectorAll("[data-grand]").forEach((b) =>
    b.addEventListener("click", () => choisirGrand(b.dataset.grand)));

  // --- Utilitaires ----------------------------------------------------------
  function mkBtn(label, cls) {
    const b = document.createElement("button");
    b.textContent = label;
    if (cls) b.className = cls;
    return b;
  }

  loadState().catch(() => toast("Erreur de connexion au boîtier"));
  refreshFmtInfo();
  refreshKiosk();
  pollVersion();
  setInterval(pollVersion, 1500);
  setInterval(refreshKiosk, 3000);
  loadAddresses();
})();
