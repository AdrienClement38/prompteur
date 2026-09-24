/* Prompteur — recalage des plages de mise en forme quand le texte change.

   Fonction PURE, sans page ni navigateur : c'est ce qui permet de la vérifier à
   part (tests/banc_plages.js). La vue Settings l'appelle à chaque frappe.

   Les plages sont des indices dans le texte brut. Quand on tape, colle ou efface,
   on compare le texte d'avant et d'après : leur début commun et leur fin commune
   encadrent la zone modifiée. */

(() => {
  "use strict";

  function recaler(marks, avant, apres) {
    if (!marks.length || avant === apres) return marks;
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
    const finAvant = avant.length - s; // la zone modifiée : [p, finAvant) avant…
    const finApres = apres.length - s; // … et [p, finApres) après
    const delta = apres.length - avant.length;

    return marks
      .map((m) => {
        if (m.end <= p) return m; // entièrement avant la modification
        if (m.start >= finAvant) return { ...m, start: m.start + delta, end: m.end + delta }; // entièrement après
        // La plage chevauche la zone modifiée. Elle garde son début, englobe ce
        // qui a été tapé à l'intérieur, et — c'était le défaut — garde aussi sa
        // FIN quand elle déborde après la zone : corriger une faute au milieu d'un
        // passage en gras retirait le gras de toute la suite du passage.
        const start = Math.min(m.start, p);
        const end = m.end >= finAvant ? m.end + delta : Math.min(m.end, finApres);
        return end > start ? { ...m, start, end } : null;
      })
      .filter(Boolean);
  }

  const racine = typeof window !== "undefined" ? window : globalThis;
  racine.Plages = { recaler };
})();
