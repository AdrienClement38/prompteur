/* Prompteur — tableau de bord du boîtier (petit écran tactile).

   Cette page est volontairement autonome et minuscule : elle est faite pour
   rester affichée en permanence sur l'écran de 3,5 pouces du boîtier, pendant
   que le grand écran montre le prompteur. Elle ne fait que trois choses :
   montrer l'état, ouvrir les trois écrans, et fermer le prompteur.

   Elle fonctionne AUSSI sur n'importe quel autre appareil : si le petit écran ne
   peut pas être piloté séparément, on y accède simplement par son adresse. */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  async function api(chemin) {
    const r = await fetch(chemin, { cache: "no-store" });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }

  function poster(chemin) {
    return fetch(chemin, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
  }

  // --- Adresse à taper sur le téléphone -------------------------------------
  async function chargerAdresse() {
    try {
      const info = await api("/api/info");
      const ip = (info.addresses || [])[0] || "10.42.0.1";
      $("adresse").textContent = `http://${ip}:${info.port || 5000}`;
    } catch {
      $("adresse").textContent = "http://10.42.0.1:5000";
    }
  }

  // --- État du prompteur ----------------------------------------------------
  // Le bouton « Fermer » n'a de sens que sur le boîtier lui-même : ailleurs, le
  // serveur répond que la commande n'est pas disponible, et on le grise plutôt
  // que de le laisser échouer sous le doigt.
  let pilotable = false;

  async function rafraichir() {
    let etat;
    try {
      etat = await api("/api/kiosk");
    } catch {
      $("etat").textContent = "boîtier injoignable";
      $("voyant").classList.add("off");
      $("bFermer").disabled = true;
      return;
    }
    pilotable = !!etat.available;
    const affiche = etat.running === true;
    $("voyant").classList.toggle("off", !affiche);
    $("etat").textContent = !pilotable
      ? "prêt"
      : affiche
        ? "prompteur affiché"
        : "prompteur fermé";
    $("bFermer").disabled = !pilotable || !affiche;
    $("bPrompteur").textContent = "";
    $("bPrompteur").append(
      document.createTextNode(affiche || !pilotable ? "▶ Prompteur" : "▶ Ouvrir"),
      Object.assign(document.createElement("span"), {
        className: "sous",
        textContent: affiche || !pilotable ? "l'écran de lecture" : "relancer sur le boîtier",
      })
    );
  }

  // Ouvrir : sur le boîtier on relance le kiosque (plein écran, sans bordure) ;
  // ailleurs, on navigue simplement vers l'écran de lecture.
  $("bPrompteur").addEventListener("click", async (e) => {
    if (!pilotable) return; // lien normal
    e.preventDefault();
    await poster("/api/kiosk/launch").catch(() => {});
    setTimeout(rafraichir, 1200);
  });

  $("bFermer").addEventListener("click", async () => {
    $("bFermer").disabled = true;
    await poster("/api/kiosk/close").catch(() => {});
    setTimeout(rafraichir, 1200);
  });

  chargerAdresse();
  rafraichir();
  setInterval(rafraichir, 3000);
})();
