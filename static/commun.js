/* Prompteur — éléments communs aux vues Settings, Spectateur et Journaliste.

   - la barre de navigation (Settings / Spectateur / Veille) ;
   - les fenêtres « Info » : les explications ne sont plus affichées en
     permanence, on les ouvre à la demande (écran de 7 pouces oblige) ;
   - la fenêtre de confirmation, grande et tactile, à la place de celle du
     navigateur ;
   - la veille du système : fond noir sur toutes les vues, et un appui pour
     rallumer.

   Chargé AVANT le script propre à chaque page, qui s'en sert via window.Commun.
   Aucun HTML n'est construit à partir de chaînes : éléments et textContent. */

(() => {
  "use strict";

  function el(tag, cls, texte) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (texte != null) n.textContent = texte;
    return n;
  }

  async function poster(chemin, corps) {
    const r = await fetch(chemin, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps || {}),
      cache: "no-store",
    });
    const reponse = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(reponse.error || "refusé par le boîtier");
    return reponse;
  }

  // --- Fenêtre modale -------------------------------------------------------
  // Une seule à la fois. Échap, un appui à côté ou « Fermer » la referment.
  let modale = null; // { fond, terminer }

  function fermerModale() {
    if (modale) modale.terminer(false);
  }

  function ouvrirModale(titre, contenu, boutons) {
    fermerModale();
    return new Promise((resolve) => {
      const fond = el("div", "modalfond");
      const boite = el("div", "modale");
      boite.setAttribute("role", "dialog");
      boite.setAttribute("aria-modal", "true");
      boite.setAttribute("aria-label", titre);
      const corps = el("div", "modalecorps");
      corps.append(...contenu);
      const actions = el("div", "modaleactions");

      const terminer = (valeur) => {
        if (!modale || modale.fond !== fond) return;
        modale = null;
        fond.remove();
        resolve(valeur);
      };

      let defaut = null;
      for (const b of boutons) {
        const bouton = el("button", b.cls || "", b.libelle);
        bouton.type = "button";
        bouton.addEventListener("click", () => terminer(b.valeur));
        actions.append(bouton);
        if (b.defaut) defaut = bouton;
      }
      boite.append(el("h3", null, titre), corps, actions);
      fond.append(boite);
      fond.addEventListener("click", (e) => {
        if (e.target === fond) terminer(false);
      });
      modale = { fond, terminer };
      document.body.append(fond);
      // Sans faire défiler : une aide longue doit s'ouvrir sur son début.
      (defaut || actions.lastChild).focus({ preventScroll: true });
    });
  }

  // Phase de capture : la touche Échap ferme la fenêtre et ne va pas plus loin
  // (sur la vue Journaliste, Échap sert aussi à quitter).
  document.addEventListener(
    "keydown",
    (e) => {
      if (modale && e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        fermerModale();
      }
    },
    true
  );

  function info(titre, gabaritId) {
    const gabarit = document.getElementById(gabaritId);
    const contenu = gabarit ? [gabarit.content.cloneNode(true)] : [el("p", null, "Aucune aide pour ce bloc.")];
    return ouvrirModale(titre, contenu, [{ libelle: "Fermer", valeur: true, cls: "primary", defaut: true }]);
  }

  async function confirmer({ titre, texte, ok = "Confirmer", annuler = "Annuler", danger = false }) {
    const contenu = (Array.isArray(texte) ? texte : [texte]).map((t) => el("p", null, t));
    const valeur = await ouvrirModale(titre, contenu, [
      { libelle: annuler, valeur: false },
      { libelle: ok, valeur: true, cls: danger ? "danger" : "primary", defaut: true },
    ]);
    return valeur === true;
  }

  function avertir(titre, texte) {
    return ouvrirModale(titre, [el("p", null, texte)], [{ libelle: "OK", valeur: true, cls: "primary", defaut: true }]);
  }

  // Boutons « Info » : le titre vient du bloc lui-même, le contenu d'un <template>.
  document.querySelectorAll(".infobtn").forEach((bouton) => {
    bouton.addEventListener("click", () => {
      const titre = bouton.dataset.titre || bouton.closest("h2")?.querySelector("span")?.textContent || "Info";
      info(titre, bouton.dataset.info);
    });
  });

  // --- Veille ---------------------------------------------------------------
  // Sur la vue Journaliste (grand écran), le fond est entièrement noir : pas de
  // bouton, seulement une ligne discrète, car c'est l'écran de la vitre.
  const surGrandEcran = document.body.dataset.veille === "noir";
  const veille = { active: false, fond: null, detail: null, armeA: 0, abonnes: [] };

  function construireFondVeille() {
    const fond = el("div", "veillefond" + (surGrandEcran ? " noir" : ""));
    fond.setAttribute("role", "button");
    fond.setAttribute("aria-label", "Rallumer le système");
    if (!surGrandEcran) fond.append(el("span", "rallumer", "⏻  Rallumer"));
    fond.append(
      el(
        "div",
        "petit",
        surGrandEcran
          ? "En veille — une pédale ou un appui rallume le système."
          : "Système en veille. Touchez l'écran pour tout rallumer."
      )
    );
    veille.detail = el("div", "petit detail");
    fond.append(veille.detail);
    fond.addEventListener("click", rallumer);
    return fond;
  }

  function majVeille(active, detail) {
    active = !!active;
    if (veille.detail && detail !== undefined) veille.detail.textContent = detail || "";
    if (active === veille.active) return;
    veille.active = active;
    if (active) {
      if (!veille.fond) veille.fond = construireFondVeille();
      if (detail !== undefined) veille.detail.textContent = detail || "";
      fermerModale();
      document.body.append(veille.fond);
      // Un double appui ne doit pas rallumer aussitôt ce qu'il vient d'éteindre.
      veille.armeA = Date.now() + 1000;
    } else if (veille.fond) {
      veille.fond.remove();
      veille.detail.textContent = "";
    }
    veille.abonnes.forEach((f) => f(active));
  }

  async function rallumer() {
    if (!veille.active || Date.now() < veille.armeA) return;
    veille.armeA = Date.now() + 1500; // pas de rafale pendant la requête
    try {
      await poster("/api/veille", { on: false });
      majVeille(false);
    } catch {
      if (veille.detail) veille.detail.textContent = "Le boîtier ne répond pas. Réessayez dans un instant.";
      veille.armeA = 0;
    }
  }

  async function mettreEnVeille() {
    const oui = await confirmer({
      titre: "Mettre le système en veille ?",
      texte: [
        "Le grand écran s'éteint et le petit écran passe au noir.",
        "Le texte, la position et les réglages sont conservés. Pour rallumer : un appui sur le petit écran, ou une pédale.",
      ],
      ok: "Mettre en veille",
    });
    if (!oui) return;
    try {
      const r = await poster("/api/veille", { on: true });
      majVeille(true, r.ecran ? "" : "L'écran du boîtier n'a pas pu être éteint : il reste allumé, en noir.");
    } catch (err) {
      avertir("Veille impossible", "Le boîtier n'a pas répondu (" + err.message + "). Rien n'a changé.");
    }
  }

  document.querySelectorAll(".veillebtn").forEach((b) => b.addEventListener("click", mettreEnVeille));

  window.Commun = {
    el,
    poster,
    info,
    confirmer,
    avertir,
    fermer: fermerModale,
    veille: {
      maj: (active) => majVeille(active),
      active: () => veille.active,
      rallumer,
      surChangement: (f) => veille.abonnes.push(f),
    },
  };
})();
