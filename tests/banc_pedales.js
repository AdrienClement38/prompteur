// Banc d'essai des pédales et des commandes de défilement.
//
// Fait tourner le VRAI static/display.js hors navigateur, image par image, avec
// un faux serveur et une horloge qu'on avance à la main : le résultat ne dépend
// ni de la vitesse de la machine, ni d'un onglet visible ou non.
//
// Lancement (depuis la racine du dépôt) :  node tests/banc_pedales.js
// Code de sortie 1 au premier écart : la CI le lance à chaque envoi.
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SRC = fs.readFileSync(path.join(__dirname, "..", "static", "display.js"), "utf8");

function banc(reglages, options = {}) {
  let maintenant = 0;
  const rafs = [];
  const intervalles = [];
  const ecouteurs = {};
  const envois = [];
  const etat = {
    version: 1,
    settings: Object.assign(
      { speed: 100, mode: "dyn", rampSeconds: 10, fontSize: 64, lineHeight: 1.6, margin: 10,
        keyForward: "ArrowDown", keyBackward: "ArrowUp", keyCenter: "ArrowRight" },
      reglages
    ),
    text: options.texte || "Ligne\n".repeat(400),
    empreinte: "e1",
    marks: options.marks || [],
    control: { cmd: options.cmdAuDemarrage || null, cmdSeq: options.cmdAuDemarrage ? 7 : 0 },
  };
  const veille = { on: false };

  function elt() {
    const e = {
      style: { setProperty() {} }, dataset: {}, childNodes: [], className: "", textContent: "",
      classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
      appendChild(c) { if (c && typeof c === "object") c.parentNode = this; this.childNodes.push(c); return c; },
      remove() {
        const l = this.parentNode && this.parentNode.childNodes;
        const i = l ? l.indexOf(this) : -1;
        if (i >= 0) l.splice(i, 1);
      },
      append(...c) { this.childNodes.push(...c); },
      replaceChildren(...c) { this.childNodes = c.length === 1 && c[0].childNodes ? c[0].childNodes : c; },
      addEventListener() {}, setAttribute() {}, getBoundingClientRect() { return { height: 30 }; },
      querySelector() { return null; },
    };
    return e;
  }
  const elements = {};
  const scroller = elt();
  const HAUT_ECRAN = options.hautEcran || 800;
  const LARG_ECRAN = options.largEcran || 1024;
  // Largeur du texte : celle fixée en pixels (réplique), sinon toute la fenêtre.
  const largeurTexte = () => (/px$/.test(scroller.style.width || "") ? parseFloat(scroller.style.width) : LARG_ECRAN);
  // Hauteur d'une ligne du texte : proportionnelle à la taille des lettres, et
  // inversement à la largeur du texte (plus étroit = plus de retours à la ligne).
  const hauteurLigne = () => ((parseFloat(scroller.style.fontSize) || 64) * 1.5625 * 1024) / largeurTexte();
  // Marge du haut : « 60vh » (fenêtre), ou en pixels quand elle est fixée (réplique).
  const margeHaut = () =>
    /px$/.test(scroller.style.paddingTop || "") ? parseFloat(scroller.style.paddingTop) : HAUT_ECRAN * 0.6;
  // Texte d'un paragraphe (sans ses numéros), et son nombre de lignes à l'écran :
  // une seule, sauf si l'essai fixe un nombre de caractères par ligne.
  const texteDe = (n) => {
    const enfants = (n.childNodes || []).filter((c) => c.className !== "num");
    if (enfants.length) return enfants.map(texteDe).join("");
    return typeof n.t === "string" ? n.t : n.textContent || "";
  };
  const nbLignes = (div) => (options.carParLigne ? Math.max(1, Math.ceil(texteDe(div).length / options.carParLigne)) : 1);
  const lignesAvant = (i) => scroller.childNodes.slice(0, i).reduce((s, d) => s + nbLignes(d), 0);
  scroller.replaceChildren = (...c) => {
    const lignes = c.length === 1 && c[0].childNodes ? c[0].childNodes : c;
    lignes.forEach((ligne, i) => {
      Object.defineProperty(ligne, "offsetTop", { get: () => margeHaut() + lignesAvant(i) * hauteurLigne() });
      Object.defineProperty(ligne, "offsetHeight", { get: () => nbLignes(ligne) * hauteurLigne() });
      ligne.getBoundingClientRect = () => ({ top: ligne.offsetTop, height: ligne.offsetHeight, width: 500 });
    });
    scroller.childNodes = lignes;
  };
  Object.defineProperty(scroller, "children", { get: () => scroller.childNodes });
  scroller.querySelectorAll = () => scroller.childNodes.filter((c) => c.dataset && c.dataset.n);
  Object.defineProperty(scroller, "scrollHeight", {
    get: () => options.hauteur || margeHaut() + lignesAvant(scroller.childNodes.length) * hauteurLigne() + HAUT_ECRAN * 0.8,
  });
  elements.scroller = scroller;
  const viewport = elt();
  viewport.clientHeight = HAUT_ECRAN;
  viewport.clientWidth = LARG_ECRAN;
  elements.viewport = viewport;

  const document = {
    currentScript: { dataset: { mode: options.spectateur ? "viewer" : "presenter" } },
    getElementById(id) { if (!elements[id]) elements[id] = elt(); return elements[id]; },
    createElement: () => elt(), createDocumentFragment: () => elt(), createTextNode: (t) => ({ t }),
    // Plage de texte : un rectangle par ligne à l'écran, en double (le <span> et
    // son texte en donnent chacun un), dans le désordre — comme un vrai navigateur
    // peut le faire.
    createRange: () => ({
      selectNodeContents(div) { this.div = div; },
      getClientRects() {
        const h = hauteurLigne();
        const out = [];
        for (let k = 0; k < nbLignes(this.div); k++) {
          const r = { top: this.div.offsetTop + (k + 0.1) * h, bottom: this.div.offsetTop + (k + 0.9) * h, width: 50, height: 0.8 * h };
          out.push(r, { ...r, top: r.top + 1, bottom: r.bottom - 1 });
        }
        return out.reverse();
      },
    }),
    addEventListener() {}, fullscreenElement: null, hidden: false,
    documentElement: { requestFullscreen: () => Promise.reject(new Error("geste")), style: { setProperty() {} } },
  };
  const reponse = (corps, statut = 200) => ({ ok: statut < 400, status: statut, json: async () => corps });
  async function fetch(url, opts = {}) {
    const corps = opts.body ? JSON.parse(opts.body) : null;
    if (opts.method === "POST") envois.push([url, corps]);
    if (url.startsWith("/api/version")) return reponse({ version: etat.version, cmdSeq: etat.control.cmdSeq, veille: veille.on });
    if (url.startsWith("/api/state")) return reponse(JSON.parse(JSON.stringify(etat)));
    if (url === "/api/scroll" && opts.method === "POST") {
      etat.scroll = { ...corps, seq: (etat.scroll ? etat.scroll.seq : 0) + 1 };
      return reponse({ ok: true });
    }
    if (url === "/api/scroll") return reponse(etat.scroll || { seq: 0, pos: 0, vel: 0 });
    if (url === "/api/settings") { Object.assign(etat.settings, corps); etat.version++; return reponse({ ok: true }); }
    if (url === "/api/command") {
      if (corps.cmd === "faster") { etat.settings.speed += 10; etat.version++; }
      if (corps.cmd === "slower") { etat.settings.speed -= 10; etat.version++; }
      etat.control = { cmd: corps.cmd, ligne: corps.ligne || null, cmdSeq: etat.control.cmdSeq + 1 };
      return reponse({ ok: true, speed: etat.settings.speed });
    }
    if (url === "/api/info") return reponse({ addresses: ["10.42.0.1"], port: 5000 });
    return reponse({ ok: true });
  }
  const window = {
    addEventListener(type, f) { (ecouteurs[type] = ecouteurs[type] || []).push(f); },
    crypto: { randomUUID: () => "jeton" }, sessionStorage: null, opener: null,
    location: { hostname: "10.42.0.1", href: "" }, Commun: null,
  };
  const ctx = {
    window, document, fetch, console, JSON, Math, Number, String, Array, Object, Promise, Set, Error,
    performance: { now: () => maintenant },
    requestAnimationFrame: (f) => rafs.push(f),
    setInterval: (f) => intervalles.push(f), setTimeout: () => 0, clearTimeout() {},
  };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx);

  const vider = () => new Promise((r) => setImmediate(r));
  const api = {
    async demarrer() { for (let i = 0; i < 5; i++) await vider(); await api.sonder(); },
    async sonder() { await intervalles.find((f) => f.name === "pollState")(); for (let i = 0; i < 5; i++) await vider(); }, // pollState
    async suivre() { await intervalles.find((f) => f.name === "pollScroll")(); for (let i = 0; i < 5; i++) await vider(); },
    avancer(ms) {
      const fin = maintenant + ms;
      while (maintenant < fin) {
        maintenant += 16;
        const f = rafs.shift();
        if (f) f(maintenant);
      }
    },
    touche(type, key) {
      for (const f of ecouteurs[type] || []) f({ key, repeat: false, preventDefault() {} });
    },
    async commande(cmd, extra) {
      await fetch("/api/command", { method: "POST", body: JSON.stringify({ cmd, ...extra }) });
      await api.sonder();
    },
    vitesse() {
      // Vitesse instantanée mesurée sur une image : déplacement / durée.
      const avant = api.pos();
      api.avancer(16);
      return (api.pos() - avant) / 0.016;
    },
    pos: () => {
      const m = /translateY\((-?[\d.e+-]+)px\)/.exec(String(scroller.style.transform || ""));
      return m ? -parseFloat(m[1]) : 0;
    },
    echelle: () => {
      const m = /scale\(([\d.e+-]+)\)/.exec(String(scroller.style.transform || ""));
      return m ? parseFloat(m[1]) : 1;
    },
    tag: () => elements.speedTag.textContent,
    lignes: () => scroller.childNodes,
    hauteurLigne,
    redimensionner(largeur, hauteur) {
      viewport.clientWidth = largeur;
      viewport.clientHeight = hauteur;
      for (const f of ecouteurs.resize || []) f();
    },
    etat, envois, veille,
  };
  return api;
}

async function appui(b, key, ms) {
  b.touche("keydown", key);
  b.avancer(ms);
  b.touche("keyup", key);
}

(async () => {
  const resultats = [];
  const verifier = (nom, ok, detail) => resultats.push(`${ok ? "OK  " : "ÉCHEC"} ${nom}${detail ? "  (" + detail + ")" : ""}`);

  // --- Point 2 : Lecture / Pause dans les trois modes ----------------------
  for (const mode of ["hold", "tap", "dyn"]) {
    const b = banc({ mode });
    await b.demarrer();
    b.avancer(200);
    const p0 = b.pos();
    await b.commande("play");
    b.avancer(1000);
    const p1 = b.pos();
    await b.commande("pause");
    b.avancer(500);
    const p2 = b.pos();
    b.avancer(500);
    verifier(`Lecture fait défiler (mode ${mode})`, p1 - p0 > 80, `${Math.round(p1 - p0)} px en 1 s`);
    verifier(`Pause arrête (mode ${mode})`, Math.abs(b.pos() - p2) < 0.01);
  }

  // --- Dernière commande pas rejouée à l'ouverture ---------------------------
  {
    const b = banc({ mode: "hold" }, { cmdAuDemarrage: "play" });
    await b.demarrer();
    b.avancer(1000);
    verifier("Un « Lecture » ancien n'est pas rejoué à l'ouverture", b.pos() === 0, `pos ${b.pos()}`);
  }

  // --- Mode dynamique : les règles du journaliste (retour n° 3) --------------
  // Vitesse signée ; une pédale maintenue la pousse dans son sens, d'autant plus
  // qu'on appuie longtemps ; relâchée, elle reste ; un changement de sens passe
  // TOUJOURS par 0 ; la centrale ne fait que PAUSE ; à l'arrêt, on repart de 0.
  {
    const b = banc({ mode: "dyn", speed: 100, rampSeconds: 1 }); // 600 px/s² : chiffres lisibles
    await b.demarrer();
    b.avancer(300);
    await appui(b, "ArrowDown", 150); // appui court
    const lente = b.vitesse();
    verifier("À l'arrêt, appui court : avance lente", lente > 40 && lente < 140, `${Math.round(lente)} px/s`);
    await appui(b, "ArrowDown", 350); // appui plus long : on accélère encore
    const rapide = b.vitesse();
    verifier("Appui prolongé : avance plus rapide", rapide > lente + 150, `${Math.round(lente)} -> ${Math.round(rapide)} px/s`);
    b.avancer(1000);
    verifier("Pédale relâchée : la vitesse atteinte reste", Math.abs(b.vitesse() - rapide) < 2, `${Math.round(b.vitesse())} px/s`);

    // Le bug signalé : une fois accéléré, on ne pouvait plus ralentir.
    await appui(b, "ArrowUp", 150);
    const ralentie = b.vitesse();
    verifier(
      "Pédale gauche brève en avançant : on ralentit, sans reculer",
      ralentie > 0 && ralentie < rapide - 60,
      `${Math.round(rapide)} -> ${Math.round(ralentie)} px/s`
    );
    b.avancer(1000);
    verifier("Et le ralentissement tient (aucune vitesse ancienne ne revient)", Math.abs(b.vitesse() - ralentie) < 2,
      `${Math.round(b.vitesse())} px/s`);
    verifier(
      "La vitesse au pied n'est plus renvoyée au boîtier",
      !b.envois.some(([u, c]) => u === "/api/settings" && c && "speed" in c),
      JSON.stringify(b.envois.filter(([u]) => u === "/api/settings"))
    );

    // Changement de sens : toujours en passant par 0, jamais d'un coup.
    const vitesses = [];
    b.touche("keydown", "ArrowUp");
    for (let i = 0; i < 60; i++) vitesses.push(b.vitesse());
    b.touche("keyup", "ArrowUp");
    const sauts = vitesses.slice(1).map((v, i) => Math.abs(v - vitesses[i]));
    verifier(
      "Pédale gauche maintenue : passe par 0 puis recule, sans à-coup",
      vitesses[0] > 0 && vitesses[vitesses.length - 1] < 0 && Math.max(...sauts) < 15,
      `${Math.round(vitesses[0])} -> ${Math.round(vitesses[vitesses.length - 1])} px/s, saut max ${Math.max(...sauts).toFixed(1)}`
    );

    // Pédale centrale : PAUSE seulement ; ensuite, une pédale repart de 0.
    await appui(b, "ArrowRight", 50);
    verifier("Pédale centrale : pause (vitesse 0)", Math.abs(b.vitesse()) < 0.01 && b.tag().startsWith("⏸"), b.tag());
    await appui(b, "ArrowRight", 50);
    verifier("Pédale centrale à l'arrêt : ne relance rien", Math.abs(b.vitesse()) < 0.01, b.tag());
    await appui(b, "ArrowDown", 150);
    const repart = b.vitesse();
    verifier("Après la pause, la pédale droite repart de 0 (lentement)", repart > 40 && repart < 140, `${Math.round(repart)} px/s`);

    // Depuis Settings : Plus vite agit sur la vitesse en cours, Lecture part à
    // la vitesse du curseur, Pause arrête.
    const avant = b.vitesse();
    await b.commande("faster");
    verifier("Plus vite (téléphone) : un cran de plus sur la vitesse en cours", Math.abs(b.vitesse() - avant - 10) < 2,
      `${Math.round(avant)} -> ${Math.round(b.vitesse())} px/s`);
    await b.commande("pause");
    await b.commande("play");
    verifier("Lecture (téléphone) : avance à la vitesse du curseur", Math.abs(b.vitesse() - b.etat.settings.speed) < 2,
      `${Math.round(b.vitesse())} px/s`);
    await b.commande("pause");
    verifier("Pause (téléphone) : arrêt", Math.abs(b.vitesse()) < 0.01);
  }

  // --- Commencer à une ligne -----------------------------------------------
  {
    const b = banc({ mode: "hold", speed: 100 });
    await b.demarrer();
    await b.commande("play");
    b.avancer(1000);
    await b.commande("ligne", { ligne: 10 });
    b.avancer(300);
    // Ligne 10 à la place qu'occupe la ligne 1 au début du texte : 9 lignes plus bas.
    verifier("Commencer à la ligne 10 : bonne place, à l'arrêt", Math.abs(b.pos() - 9 * b.hauteurLigne()) < 0.5 && b.tag().startsWith("⏸"),
      `pos ${Math.round(b.pos())}, ${b.tag()}`);
    await b.commande("ligne", { ligne: 1 });
    verifier("Ligne 1 = le début du texte", b.pos() === 0, `pos ${b.pos()}`);
    await b.commande("ligne", { ligne: 99999 });
    verifier("Numéro trop grand : la dernière ligne", b.pos() > 0, `pos ${Math.round(b.pos())}`);
  }

  // --- Butée en bas du texte en mode dynamique -------------------------------
  {
    const b = banc({ mode: "dyn", speed: 300 }, { hauteur: 1400 }); // 600 px de course
    await b.demarrer();
    await b.commande("play");
    b.avancer(4000);
    verifier("En bas du texte : arrêt automatique", b.tag().startsWith("⏸"), b.tag());
    await appui(b, "ArrowUp", 400);
    const p = b.pos();
    b.avancer(500);
    verifier("Pédale gauche après la butée : repart en arrière", p - b.pos() > 5, `${Math.round(p - b.pos())} px`);
  }

  // --- Mise en forme après une ligne « [centre] » ---------------------------
  // Le préfixe est retiré à l'affichage mais compte dans les indices : le gras
  // de la ligne suivante tombait quelques lettres trop loin.
  {
    const texte = "[centre] Titre\nsuite en gras";
    const debut = texte.indexOf("suite");
    const b = banc({ mode: "hold" }, { texte, marks: [{ start: debut, end: debut + 5, b: true }] });
    await b.demarrer();
    const ligne2 = b.lignes()[1];
    const gras = (ligne2.childNodes || []).find((n) => n.className === "mb");
    verifier("Gras juste après une ligne [centre]", gras && gras.textContent === "suite", gras && gras.textContent);
  }

  // --- Vue Spectateur : réplique du grand écran ----------------------------
  // Une fenêtre de téléphone doit montrer la MÊME phrase sous sa ligne rouge,
  // avec les mêmes coupures de lignes, en plus petit.
  {
    const texte = "Ligne\n".repeat(400);
    const meneur = banc({ mode: "hold", speed: 100 }, { texte, largEcran: 1024, hautEcran: 600 });
    await meneur.demarrer();
    await meneur.commande("play");
    meneur.avancer(4000);
    await meneur.commande("pause");
    meneur.avancer(2100); // le meneur renvoie sa position à l'arrêt
    const point = meneur.etat.scroll;
    verifier(
      "Le meneur envoie la ligne lue et ses dimensions",
      point && Number.isInteger(point.ligne) && point.largeur === 1024 && point.hauteur === 600,
      JSON.stringify(point)
    );

    const tel = banc({ mode: "hold" }, { texte, spectateur: true, largEcran: 400, hautEcran: 800 });
    tel.etat.scroll = point;
    await tel.demarrer();
    await tel.suivre();
    tel.avancer(1500);
    const e = tel.echelle();
    verifier("Réplique à l'échelle de la fenêtre", Math.abs(e - 400 / 1024) < 1e-6, `échelle ${e.toFixed(3)}`);
    // Ligne sous le repère du téléphone (42 % de SA hauteur, en unités du grand écran).
    const lue = (tel.pos() + (800 / e) * 0.42 - 600 * 0.6) / tel.hauteurLigne();
    const attendue = point.ligne + point.frac;
    verifier(
      "Même phrase sous la ligne rouge, en plus petit",
      Math.abs(lue - attendue) < 0.02 && Math.abs(tel.hauteurLigne() - meneur.hauteurLigne()) < 1e-6,
      `ligne ${lue.toFixed(2)} pour ${attendue.toFixed(2)}`
    );

    // Fenêtre redimensionnée (tablette posée en paysage) : toujours la même phrase.
    tel.redimensionner(1200, 500);
    tel.avancer(1500);
    const e2 = tel.echelle();
    const lue2 = (tel.pos() + (500 / e2) * 0.42 - 600 * 0.6) / tel.hauteurLigne();
    verifier(
      "Fenêtre redimensionnée : réplique réajustée, même phrase",
      Math.abs(e2 - 500 / 600) < 1e-6 && Math.abs(lue2 - attendue) < 0.02,
      `échelle ${e2.toFixed(3)}, ligne ${lue2.toFixed(2)}`
    );

    // Sans dimensions du meneur (version antérieure) : mise en page à sa taille.
    const ancien = banc({ mode: "hold" }, { texte, spectateur: true, largEcran: 400, hautEcran: 800 });
    ancien.etat.scroll = { seq: 3, pos: 300, vel: 0, ligne: point.ligne, frac: point.frac, h: point.h };
    await ancien.demarrer();
    await ancien.suivre();
    ancien.avancer(1500);
    const lueAncien = (ancien.pos() + 800 * 0.42 - 800 * 0.6) / ancien.hauteurLigne();
    verifier(
      "Meneur d'une version antérieure : suivi par la ligne, sans réplique",
      ancien.echelle() === 1 && Math.abs(lueAncien - attendue) < 0.02,
      `ligne ${lueAncien.toFixed(2)}`
    );
  }

  // --- Changer la taille du texte en pleine lecture ----------------------------
  {
    const texte = "Ligne\n".repeat(400);
    const b = banc({ mode: "hold", speed: 100, fontSize: 64 }, { texte });
    await b.demarrer();
    await b.commande("play");
    b.avancer(5000);
    await b.commande("pause");
    const hAvant = b.hauteurLigne();
    const ligneAvant = (b.pos() + 800 * 0.42 - 800 * 0.6) / hAvant;
    b.etat.settings.fontSize = 128;
    b.etat.version++;
    await b.sonder();
    const ligneApres = (b.pos() + 800 * 0.42 - 800 * 0.6) / b.hauteurLigne();
    verifier(
      "Taille changée en pleine lecture : même phrase sous le repère",
      Math.abs(ligneApres - ligneAvant) < 0.01,
      `ligne ${ligneAvant.toFixed(2)} -> ${ligneApres.toFixed(2)}`
    );
  }

  // --- Numéros de ligne ------------------------------------------------------
  {
    const b = banc({ mode: "hold" }, { texte: "# Titre\n\nPremier paragraphe\n- une puce\n[centre] centré\n\n" });
    await b.demarrer();
    const numeros = b.lignes().map((l) => l.dataset.n || "");
    verifier("Numéros : lignes de texte seulement, pas les lignes vides", JSON.stringify(numeros) === JSON.stringify(["1", "", "2", "3", "4", "", ""]),
      JSON.stringify(numeros));
  }

  // --- Numéros : un par ligne À L'ÉCRAN (retour n° 4) ------------------------
  {
    const b = banc({ mode: "hold" }, { texte: "Court\n\n" + "x".repeat(25) + "\nFin", carParLigne: 10 });
    await b.demarrer();
    b.avancer(32); // la mesure se fait dans la boucle d'affichage
    const numeros = b.lignes().flatMap((l) => l.childNodes.filter((c) => c.className === "num").map((c) => c.textContent));
    verifier(
      "Un numéro par ligne à l'écran (un paragraphe de 3 lignes en porte 3)",
      JSON.stringify(numeros) === JSON.stringify(["1", "2", "3", "4", "5"]),
      JSON.stringify(numeros)
    );
    b.avancer(32);
    const encore = b.lignes().flatMap((l) => l.childNodes.filter((c) => c.className === "num"));
    verifier("Mesurés à nouveau : pas de numéros en double", encore.length === 5, String(encore.length));
    await b.commande("ligne", { ligne: 3 });
    verifier(
      "Commencer à la ligne 3 = la 2e ligne du long paragraphe",
      Math.abs(b.pos() - 3 * b.hauteurLigne()) < 0.5,
      `pos ${Math.round(b.pos())}, attendu ${Math.round(3 * b.hauteurLigne())}`
    );
    const carte = b.envois.filter(([u]) => u === "/api/lignes").pop();
    verifier(
      "Carte envoyée au boîtier : numéro de la 1re ligne de chaque paragraphe",
      carte && carte[1].empreinte === "e1" && JSON.stringify(carte[1].debuts) === JSON.stringify([1, 0, 2, 5]),
      carte && JSON.stringify(carte[1])
    );
  }

  // --- Vitesse maximale : 1200, et le mode dynamique garde sa sensation -------
  {
    const b = banc({ mode: "dyn", rampSeconds: 1 });
    await b.demarrer();
    await appui(b, "ArrowDown", 1000); // 1 s : 600 px/s, comme avant
    const uneSeconde = b.vitesse();
    await appui(b, "ArrowDown", 3000); // on garde le pied : jusqu'à 1200, pas plus
    const auBout = b.vitesse();
    verifier(
      "Dynamique : même accélération qu'avant, et on monte jusqu'à 1200",
      Math.abs(uneSeconde - 600) < 30 && Math.abs(auBout - 1200) < 2,
      `${Math.round(uneSeconde)} puis ${Math.round(auBout)} px/s`
    );
  }

  // --- Sans commun.js, l'écran de lecture tourne quand même ---------------
  {
    const b = banc({ mode: "hold" });
    await b.demarrer();
    await b.commande("play");
    b.avancer(500);
    verifier("L'écran fonctionne sans commun.js", b.pos() > 20, `${Math.round(b.pos())} px`);
  }

  console.log(resultats.join("\n"));
  process.exit(resultats.some((r) => r.startsWith("ÉCHEC")) ? 1 : 0);
})();
