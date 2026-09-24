// Banc d'essai du recalage de la mise en forme pendant la frappe (static/plages.js).
//
// Lancement (depuis la racine du dépôt) :  node tests/banc_plages.js
// Code de sortie 1 au premier écart : la CI le lance à chaque envoi.
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ctx = { globalThis: null };
ctx.globalThis = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "static", "plages.js"), "utf8"), ctx);
const { recaler } = ctx.Plages;

const resultats = [];
function verifier(nom, apres, marks, attendu) {
  const vus = marks.map((m) => apres.slice(m.start, m.end));
  const ok = JSON.stringify(vus) === JSON.stringify(attendu);
  resultats.push(`${ok ? "OK  " : "ÉCHEC"} ${nom}  (${JSON.stringify(vus)})`);
}
function plage(texte, mot) {
  const debut = texte.indexOf(mot);
  return { start: debut, end: debut + mot.length, b: true };
}

{
  const avant = "Le passage important ici";
  const apres = "Le passage importent ici";
  verifier("Corriger une faute au milieu du gras", apres,
    recaler([plage(avant, "passage important")], avant, apres), ["passage importent"]);
}
{
  const avant = "Un mot gras ici";
  const apres = "Un mot trés gras ici";
  verifier("Taper à l'intérieur d'un passage l'allonge", apres,
    recaler([plage(avant, "mot gras")], avant, apres), ["mot trés gras"]);
}
{
  const avant = "Voici gras.";
  const apres = "Voici du gras.";
  verifier("Taper juste avant : le passage se décale sans s'étendre", apres,
    recaler([plage(avant, "gras")], avant, apres), ["gras"]);
}
{
  const avant = "Voici gras.";
  const apres = "Voici gras et plus.";
  verifier("Taper juste après : le passage ne s'étend pas", apres,
    recaler([plage(avant, "gras")], avant, apres), ["gras"]);
}
{
  const avant = "Garder ceci et supprimer.";
  const apres = "Garder  et supprimer.";
  verifier("Effacer tout le passage le retire", apres,
    recaler([plage(avant, "ceci")], avant, apres), []);
}
{
  const avant = "Début du passage fin";
  const apres = "Déssage fin";
  verifier("Effacer par-dessus le début du passage le rogne", apres,
    recaler([plage(avant, "passage")], avant, apres), ["ssage"]);
}
{
  const avant = "Un passage souligné, puis la suite.";
  const apres = "Un passage soulXXXX la suite.";
  verifier("Coller par-dessus la fin du passage", apres,
    recaler([plage(avant, "passage souligné")], avant, apres), ["passage soulXXXX"]);
}
{
  const avant = "A gras B italique C";
  const apres = "A gras B nouveau italique C";
  verifier("Deux passages : seul celui d'après se décale", apres,
    recaler([plage(avant, "gras"), plage(avant, "italique")], avant, apres), ["gras", "italique"]);
}

console.log(resultats.join("\n"));
process.exit(resultats.some((r) => r.startsWith("ÉCHEC")) ? 1 : 0);
