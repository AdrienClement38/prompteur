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
    marks: options.marks || [],
    control: { cmd: options.cmdAuDemarrage || null, cmdSeq: options.cmdAuDemarrage ? 7 : 0 },
  };
  const veille = { on: false };

  function elt() {
    const e = {
      style: {}, dataset: {}, childNodes: [], className: "", textContent: "",
      classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
      appendChild(c) { this.childNodes.push(c); return c; },
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
  scroller.replaceChildren = (...c) => {
    const lignes = c.length === 1 && c[0].childNodes ? c[0].childNodes : c;
    lignes.forEach((ligne, i) => {
      Object.defineProperty(ligne, "offsetTop", { get: () => margeHaut() + i * hauteurLigne() });
      Object.defineProperty(ligne, "offsetHeight", { get: () => hauteurLigne() });
    });
    scroller.childNodes = lignes;
  };
  Object.defineProperty(scroller, "children", { get: () => scroller.childNodes });
  Object.defineProperty(scroller, "scrollHeight", {
    get: () => options.hauteur || margeHaut() + scroller.childNodes.length * hauteurLigne() + HAUT_ECRAN * 0.8,
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
      etat.control = { cmd: corps.cmd, cmdSeq: etat.control.cmdSeq + 1 };
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
    async commande(cmd) {
      await fetch("/api/command", { method: "POST", body: JSON.stringify({ cmd }) });
      await api.sonder();
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

  // --- Point 10 : reprise après pause en mode dynamique ----------------------
  {
    const b = banc({ mode: "dyn", speed: 100 });
    await b.demarrer();
    await b.commande("play");
    b.avancer(2000); // ~200 px vers l'avant
    await appui(b, "ArrowRight", 50); // pause (pédale centrale)
    const pPause = b.pos();
    b.avancer(500);
    verifier("Pédale centrale : pause", Math.abs(b.pos() - pPause) < 0.01);

    await appui(b, "ArrowUp", 100); // gauche -> doit RECULER à la même vitesse
    const pA = b.pos();
    b.avancer(1000);
    const recul = pA - b.pos();
    verifier("Après pause, pédale gauche : repart en arrière", recul > 90 && recul < 110, `${Math.round(recul)} px/s vers l'arrière`);

    await appui(b, "ArrowRight", 50); // pause
    await appui(b, "ArrowDown", 100); // droite -> doit AVANCER à la même vitesse
    const pB = b.pos();
    b.avancer(1000);
    const avance = b.pos() - pB;
    verifier("Après pause, pédale droite : repart en avant", avance > 90 && avance < 110, `${Math.round(avance)} px/s vers l'avant`);

    // Appui de reprise court : la vitesse ne bouge pas.
    await appui(b, "ArrowRight", 50);
    await appui(b, "ArrowDown", 300);
    verifier("Appui de reprise court : vitesse inchangée", b.tag().endsWith(" 100"), b.tag());

    // Appui maintenu : accélère après le délai, puis la vitesse part au serveur.
    await appui(b, "ArrowDown", 1400);
    const envoi = b.envois.filter(([u, c]) => u === "/api/settings" && c.speed).pop();
    verifier("Pédale maintenue : accélère", Number(b.tag().split(" ")[1]) > 170, b.tag());
    verifier("Vitesse posée au pied envoyée au boîtier", envoi && envoi[1].speed === Number(b.tag().split(" ")[1]), JSON.stringify(envoi));

    // Plus vite depuis Settings : part de la vitesse posée au pied.
    await b.sonder();
    const avant = Number(b.tag().split(" ")[1]);
    await b.commande("faster");
    verifier("Plus vite part de la vitesse au pied", Number(b.tag().split(" ")[1]) === avant + 10, `${avant} -> ${b.tag()}`);

    // Début : revient en haut, à l'arrêt, vitesse gardée.
    await b.commande("restart");
    b.avancer(500);
    verifier("Début : en haut et à l'arrêt", b.pos() === 0 && b.tag().startsWith("⏸"), b.tag());
  }

  // --- Butée en bas du texte en mode dynamique -------------------------------
  {
    const b = banc({ mode: "dyn", speed: 300 }, { hauteur: 1400 }); // 600 px de course
    await b.demarrer();
    await b.commande("play");
    b.avancer(4000);
    verifier("En bas du texte : pause automatique", b.tag().startsWith("⏸"), b.tag());
    await appui(b, "ArrowUp", 50);
    const p = b.pos();
    b.avancer(500);
    verifier("Pédale gauche après la butée : repart aussitôt en arrière", p - b.pos() > 100, `${Math.round(p - b.pos())} px`);
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
