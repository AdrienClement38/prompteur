// Banc d'essai du petit écran : les pédales qu'il reçoit doivent arriver au
// prompteur, dans l'ordre, sans jamais rester « enfoncées ».
//
// Fait tourner le VRAI static/commun.js hors navigateur, en mode petit écran
// (?petit=1), avec un faux boîtier qui répond dans le désordre (délais au
// hasard) : c'est le cas qui retournerait un appui bref si les envois
// n'étaient pas mis en file.
//
// Lancement (depuis la racine du dépôt) :  node tests/banc_petit_ecran.js
// Code de sortie 1 au premier écart : la CI le lance à chaque envoi.
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SRC = fs.readFileSync(path.join(__dirname, "..", "static", "commun.js"), "utf8");

function banc({ apprentissage = false } = {}) {
  const ecouteurs = {};
  const recus = []; // ce que le boîtier a reçu, dans l'ordre d'ARRIVÉE
  let graine = 7;
  const hasard = () => {
    graine = (graine * 1103515245 + 12345) % 2147483648;
    return graine / 2147483648;
  };
  const elt = () => ({
    className: "", textContent: "", style: {}, dataset: {}, childNodes: [],
    classList: { add() {}, remove() {}, toggle() {} },
    append() {}, appendChild() {}, remove() {}, addEventListener() {}, setAttribute() {},
    getAttribute: () => "/settings",
  });
  const document = {
    createElement: () => elt(),
    body: Object.assign(elt(), { dataset: {} }),
    documentElement: elt(),
    getElementById: () => null,
    querySelectorAll: () => [],
    querySelector: (sel) => (sel === ".pedal.capture" && apprentissage ? elt() : null),
    addEventListener() {},
  };
  const window = {
    location: { search: "?petit=1" },
    addEventListener(type, f) {
      (ecouteurs[type] = ecouteurs[type] || []).push(f);
    },
  };
  async function fetch(url, opts = {}) {
    if (url === "/api/state") {
      return { ok: true, json: async () => ({ settings: { keyForward: "ArrowDown", keyBackward: "ArrowUp", keyCenter: "ArrowRight" } }) };
    }
    // Le boîtier met un temps variable à répondre : deux envois lancés en même
    // temps arriveraient dans le désordre.
    await new Promise((ok) => setTimeout(ok, Math.floor(hasard() * 30)));
    if (url === "/api/pedale") recus.push(JSON.parse(opts.body));
    return { ok: true, json: async () => ({ ok: true }) };
  }
  const ctx = {
    window, document, fetch, console, JSON, Math, Number, String, Array, Object, Promise, Set, Error, URLSearchParams,
    setTimeout, clearTimeout, setInterval: () => 0, Date,
  };
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx);
  const touche = (type, key, extra = {}) => {
    const e = { key, repeat: false, target: { tagName: "BODY" }, defaut: false, preventDefault() { this.defaut = true; }, ...extra };
    for (const f of ecouteurs[type] || []) f(e);
    return e;
  };
  return {
    touche,
    evenement: (type) => (ecouteurs[type] || []).forEach((f) => f({})),
    recus,
    attendre: (ms = 400) => new Promise((ok) => setTimeout(ok, ms)),
  };
}

(async () => {
  const resultats = [];
  const verifier = (nom, ok, detail) => resultats.push(`${ok ? "OK  " : "ÉCHEC"} ${nom}${detail ? "  (" + detail + ")" : ""}`);
  const suite = (b) => b.recus.map((r) => `${r.type}:${r.key}`).join(" ");

  {
    const b = banc();
    await b.attendre(); // touches des pédales lues
    for (let i = 0; i < 20; i++) {
      b.touche("keydown", "ArrowDown");
      b.touche("keyup", "ArrowDown");
    }
    await b.attendre(2500); // 40 envois, l'un après l'autre
    const attendu = Array(20).fill("down:ArrowDown up:ArrowDown").join(" ");
    verifier("Appuis brefs transmis dans l'ordre (jamais « relâchée » avant « enfoncée »)", suite(b) === attendu,
      suite(b).slice(0, 80));
  }
  {
    const b = banc();
    await b.attendre();
    const e = b.touche("keydown", "ArrowDown");
    b.touche("keydown", "ArrowDown", { repeat: true });
    b.touche("keydown", "ArrowDown", { repeat: true });
    b.touche("keyup", "ArrowDown");
    await b.attendre();
    verifier("Pédale tenue : un seul « enfoncée » (l'autorépétition n'est pas transmise)", suite(b) === "down:ArrowDown up:ArrowDown", suite(b));
    verifier("La page du petit écran ne défile pas avec la pédale", e.defaut === true);
  }
  {
    const b = banc();
    await b.attendre();
    b.touche("keydown", "ArrowUp");
    b.evenement("blur"); // la page perd la main pédale enfoncée
    await b.attendre();
    verifier("Perte de la main pédale enfoncée : le relâchement est envoyé", suite(b) === "down:ArrowUp up:ArrowUp", suite(b));
  }
  {
    const b = banc();
    await b.attendre();
    b.touche("keydown", "ArrowDown", { target: { tagName: "INPUT" } });
    b.touche("keyup", "ArrowDown", { target: { tagName: "INPUT" } });
    await b.attendre();
    verifier("Un champ a la main : la pédale fait quand même défiler le texte", suite(b) === "down:ArrowDown up:ArrowDown", suite(b));
  }
  {
    const b = banc();
    await b.attendre();
    b.touche("keydown", "a");
    b.touche("keydown", "Escape");
    await b.attendre();
    verifier("Les autres touches ne sont pas transmises (Échap ne quitte pas le prompteur)", b.recus.length === 0, suite(b));
  }
  {
    const b = banc({ apprentissage: true });
    await b.attendre();
    b.touche("keydown", "ArrowDown");
    b.touche("keyup", "ArrowDown");
    await b.attendre();
    verifier("Apprentissage d'une touche en cours : la pédale reste sur la page", b.recus.length === 0, suite(b));
  }

  console.log(resultats.join("\n"));
  const echecs = resultats.filter((r) => r.startsWith("ÉCHEC")).length;
  console.log(`\n${resultats.length - echecs}/${resultats.length} vérifications réussies.`);
  process.exit(echecs ? 1 : 0);
})();
