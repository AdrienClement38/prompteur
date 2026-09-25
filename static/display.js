/* Prompteur — logique de l'écran (défilement + pédales + synchro temps réel).

   Deux modes (indiqués par le serveur via l'attribut data-mode du script) :
   - "presenter" (/journaliste) : vue JOURNALISTE, l'écran meneur. Pilotée aux pédales
     EN LOCAL (latence nulle), elle DIFFUSE sa position de défilement au serveur.
   - "viewer" (/spectateur) : vue SPECTATEUR (régie…). Lecture seule : elle SUIT le meneur
     en temps réel, avec anticipation (connaît la vitesse) pour un défilement fluide et collé.

   Texte, réglages et position sont synchronisés par interrogation rapide du serveur ;
   le spectateur anticipe le mouvement entre deux lectures -> retard imperceptible. */

(() => {
  "use strict";

  // Le serveur indique la surface par un attribut sur la balise de script :
  // aucun script en ligne, donc rien qui contrevienne a la politique de securite.
  const MODE = document.currentScript?.dataset.mode === "viewer" ? "viewer" : "presenter";
  const isViewer = MODE === "viewer";
  // Éléments communs (veille…). Leur absence ne doit JAMAIS empêcher l'écran de
  // lecture de fonctionner : tout appel passe par ce garde-fou.
  const Commun = window.Commun || null;

  const scroller = document.getElementById("scroller");
  const viewport = document.getElementById("viewport");
  const stage = document.getElementById("stage");
  const guide = document.getElementById("guide");
  const hud = document.getElementById("hud");
  const speedTag = document.getElementById("speedTag");
  const emptyMsg = document.getElementById("empty");
  const netinfo = document.getElementById("netinfo");

  // --- État courant de l'affichage -----------------------------------------
  let settings = null;
  let pos = 0; // décalage de défilement en px (0 = haut du texte)
  let autoPlay = false; // défilement automatique mains-libres (meneur)
  let speed = 70; // px / seconde
  const keys = { forward: false, backward: false };
  let lastText = null;
  let lastMarks = null; // mise en forme affichée (JSON), comparée à chaque mise à jour
  let lastVersion = -1;
  let lastCmdSeq = -1;
  let lastTime = 0;

  // Suivi (spectateur) : dernier point connu du meneur (pos, vitesse, instant, n° de séquence)
  const follow = { pos: 0, vel: 0, at: 0, seq: -1, repere: null };

  // --- Application des réglages reçus du serveur ----------------------------
  function applySettings(s, text, marks) {
    // Même texte, présentation qui change (taille, interligne, marges) : on note
    // la phrase sous la ligne rouge AVANT, pour y revenir APRÈS. Sans cela, la
    // lecture sautait ailleurs, voire sur un écran vide.
    const repereAvant = !isViewer && lastText !== null && text === lastText ? repereDepuisPosition(pos) : null;
    const vitesseAvant = settings ? Number(settings.speed) || 70 : null;
    settings = s;
    speed = Number(s.speed) || 70;
    // Une vitesse changée ailleurs (curseur, Plus vite / Moins vite) s'applique
    // aussi à la vitesse posée au pied en mode dynamique.
    if (!isViewer && vitesseAvant !== null && speed !== vitesseAvant) adopterVitesse(speed);

    const fontMap = {
      "sans-serif": "system-ui, 'Segoe UI', Roboto, Arial, sans-serif",
      serif: "Georgia, 'Times New Roman', serif",
      monospace: "'Consolas', 'Courier New', monospace",
    };
    scroller.style.fontFamily = fontMap[s.font] || fontMap["sans-serif"];
    scroller.style.fontSize = Math.max(8, Math.min(400, Number(s.fontSize) || 64)) + "px";
    scroller.style.lineHeight = String(Math.max(0.8, Math.min(4, Number(s.lineHeight) || 1.6)));
    scroller.style.textAlign = s.align === "center" ? "center" : "left";

    mettreEnPage();

    const sx = s.mirrorH ? -1 : 1;
    const sy = s.mirrorV ? -1 : 1;
    stage.style.transform = `scale(${sx}, ${sy})`;

    if (s.guide) {
      guide.style.display = "block";
      guide.style.top = Math.max(0, Math.min(100, Number(s.guidePos) || 42)) + "vh";
    } else {
      guide.style.display = "none";
    }

    // On redessine si le texte OU sa mise en forme ont changé : une couleur posée
    // sur un texte déjà à l'écran ne s'affichait jamais, faute de comparer les
    // plages. Le défilement ne revient au début que si le TEXTE a changé.
    const marksJson = JSON.stringify(marks || []);
    if (text !== lastText || marksJson !== lastMarks) {
      renderScript(text || "", marks);
      lastMarks = marksJson;
    }
    if (text !== lastText) {
      lastText = text;
      if (!isViewer) {
        // Nouveau texte : on repart du haut, À L'ARRÊT, quel que soit le mode.
        pos = 0;
        arretTout();
      }
    }
    if (repereAvant) {
      const apres = positionDepuisRepere(repereAvant);
      if (apres !== null && Math.abs(apres - pos) > 0.5) {
        pos = Math.max(0, Math.min(maxScrollPos(), apres));
        placer();
        forceResync();
      }
    }
    emptyMsg.style.display = text && text.trim() ? "none" : "flex";
    updateSpeedTag();
  }

  // Construit l'affichage à partir du texte : les lignes « # / ## / ### » deviennent
  // des TITRES (gros/gras) ; les autres lignes et les lignes vides sont préservées.
  // Classes de mise en forme actives a une position donnee du texte.
  const SIZE_CLASS = { s: "ms", l: "ml", xl: "mxl" };
  const ALIGN_CLASS = { center: "al-c", right: "al-r" };

  // L'alignement ne porte pas sur des caracteres mais sur la LIGNE entiere : on le
  // lit donc a son premier caractere. Les plages d'alignement sont isolees en amont
  // parce qu'elles sont rares : sans cela, chaque ligne d'un script de 300 000
  // signes reparcourrait toute la mise en forme.
  function alignementAt(alignements, index) {
    for (const m of alignements) {
      if (index >= m.start && index < m.end) return ALIGN_CLASS[m.align];
    }
    return "";
  }

  function styleClassesAt(marks, index) {
    let cls = "";
    let taille = null;
    let couleur = null;
    for (const m of marks) {
      if (index < m.start || index >= m.end) continue;
      if (m.b && !cls.includes("mb")) cls += " mb";
      if (m.i && !cls.includes("mi")) cls += " mi";
      if (m.u && !cls.includes("mu")) cls += " mu";
      // Taille et couleur ne s'additionnent pas : la derniere plage l'emporte.
      if (SIZE_CLASS[m.size]) taille = SIZE_CLASS[m.size];
      if (m.color >= 1 && m.color <= 5) couleur = "c" + m.color;
    }
    if (taille) cls += " " + taille;
    if (couleur) cls += " " + couleur;
    return cls.trim();
  }

  // Remplit une ligne en respectant les plages qui la traversent.
  // On ne calcule le style qu'aux FRONTIERES des plages, pas a chaque caractere :
  // un script de plusieurs centaines de milliers de signes reste instantane.
  function fillLine(div, line, lineStart, marks, bornes) {
    const lineEnd = lineStart + line.length;
    const coupes = [lineStart];
    for (const b of bornes) {
      if (b > lineStart && b < lineEnd) coupes.push(b);
    }
    coupes.push(lineEnd);

    let pose = false;
    for (let k = 0; k < coupes.length - 1; k++) {
      const debut = coupes[k];
      const fin = coupes[k + 1];
      if (fin <= debut) continue;
      const morceau = line.slice(debut - lineStart, fin - lineStart);
      const cls = styleClassesAt(marks, debut);
      if (!cls) {
        div.appendChild(document.createTextNode(morceau));
      } else {
        const span = document.createElement("span");
        span.className = cls;
        span.textContent = morceau; // textContent -> aucun risque d'injection
        div.appendChild(span);
        pose = true;
      }
    }
    if (!pose && div.childNodes.length === 1) {
      // Ligne sans mise en forme : on garde un simple noeud de texte.
      div.textContent = line;
    }
  }

  // Marqueurs de DEBUT DE LIGNE, traites ici, au rendu. C'est ce qui les fait
  // marcher aussi bien sur un fichier importe que sur du texte TAPE dans la zone
  // de saisie, ou aucune conversion n'a lieu. Le diese le faisait deja ; le tiret
  // de puce et l'alignement suivent desormais la meme regle, plutot que d'etre
  // convertis a l'import seulement — un signe qui marche a un endroit et pas a
  // l'autre passe pour une panne.
  const RE_TITRE = /^(#{1,3})[ \t]+(.*)$/;
  // « + » n'en fait pas partie : jamais documenté, il faisait disparaître le plus
  // d'une ligne comme « + 3 degrés ».
  const RE_PUCE = /^[-*•][ \t]+(.*)$/;
  const RE_ALIGNE = /^\[(centre|droite)\][ \t]*/i;

  function renderScript(text, marks) {
    const plages = Array.isArray(marks) ? marks : [];
    const bornes = [];
    for (const m of plages) bornes.push(m.start, m.end);
    bornes.sort((a, b) => a - b);

    const alignements = plages.filter((m) => ALIGN_CLASS[m.align]);
    const frag = document.createDocumentFragment();
    let offset = 0;
    for (const brute of String(text).split("\n")) {
      const div = document.createElement("div");
      // L'alignement se retire en premier : il peut precéder un titre ou une puce.
      let line = brute;
      let base = offset;
      let classeAligne = "";
      const al = RE_ALIGNE.exec(line);
      if (al) {
        classeAligne = al[1].toLowerCase() === "centre" ? " al-c" : " al-r";
        base += al[0].length;
        line = line.slice(al[0].length);
      }
      const m = RE_TITRE.exec(line);
      const puce = m ? null : RE_PUCE.exec(line);
      if (m) {
        div.className = "ln h" + m[1].length;
        // Le dièse et son espace ne sont pas affichés : les plages du titre sont
        // donc décalées d'autant.
        const decalage = line.length - m[2].length;
        if (plages.length) fillLine(div, m[2], base + decalage, plages, bornes);
        else div.textContent = m[2]; // textContent -> aucun risque d'injection
      } else if (puce) {
        div.className = "ln puce";
        // Le point de puce est un element a part : le retrait pendant du CSS le
        // laisse seul dans la marge, et une puce dont le texte passe a la ligne
        // reste alignee sur son texte au lieu de revenir sous le point.
        const point = document.createElement("span");
        point.className = "bul";
        point.textContent = "• ";
        div.appendChild(point);
        const corps = document.createElement("span");
        const decalage = line.length - puce[1].length;
        if (plages.length) fillLine(corps, puce[1], base + decalage, plages, bornes);
        else corps.textContent = puce[1];
        div.appendChild(corps);
      } else if (line.trim() === "") {
        div.className = "ln blank";
      } else {
        div.className = "ln";
        if (plages.length) fillLine(div, line, base, plages, bornes);
        else div.textContent = line;
      }
      div.className += classeAligne;
      const aligne = alignementAt(alignements, offset);
      if (aligne && !classeAligne) div.className += " " + aligne;
      frag.appendChild(div);
      // Longueur de la ligne BRUTE : « [centre] » ou « [droite] » a été retiré
      // de « line » pour l'affichage, mais ses caractères comptent dans les
      // indices des plages. Avec « line », toute la mise en forme des lignes
      // suivantes glissait de quelques lettres.
      offset += brute.length + 1; // +1 pour le saut de ligne retiré par split
    }
    scroller.replaceChildren(frag);
  }

  // --- Lecture, pause, début : les mêmes gestes dans les trois modes ---------
  // Les boutons de Settings (et la barre d'espace) n'agissaient qu'en mode
  // Maintien : en Impulsion et en Dynamique, le défilement ne dépend pas de
  // « autoPlay », et Lecture ou Pause ne faisaient rien. Chaque geste passe
  // désormais par ces fonctions, qui connaissent les trois modes.
  function enMouvement() {
    const mode = currentMode();
    if (mode === "dyn") return !dynPaused && Math.abs(dynVel) >= 1;
    if (mode === "tap") return tapDir !== 0;
    return autoPlay || keys.forward || keys.backward;
  }

  function lecture() {
    const mode = currentMode();
    if (mode === "dyn") {
      // Vers l'avant, à la vitesse posée au pied ; à défaut, à celle du réglage.
      dynVel = Math.abs(dynVel) >= 1 ? Math.abs(dynVel) : speed;
      dynPaused = false;
    } else if (mode === "tap") {
      tapDir = 1;
    } else {
      autoPlay = true;
    }
  }

  // Pédale centrale (mode dynamique) : repart dans le sens d'avant la pause, à
  // la même vitesse. Sans vitesse posée, vers l'avant à la vitesse du réglage.
  function repriseCentrale() {
    if (Math.abs(dynVel) < 1) dynVel = speed;
    dynPaused = false;
  }

  // Tout s'arrête ; la vitesse, elle, est conservée pour la reprise.
  function arretTout() {
    autoPlay = false;
    tapDir = 0;
    dynPaused = true;
    reprise = null;
    forceResync();
  }

  function revenirAuDebut() {
    pos = 0;
    arretTout();
  }

  function applyCommand(cmd) {
    // En veille, rien ne doit se mettre à défiler dans le noir.
    if (Commun && Commun.veille.active() && (cmd === "play" || cmd === "toggle")) return;
    switch (cmd) {
      case "play": lecture(); break;
      case "pause": arretTout(); break;
      case "toggle":
        if (enMouvement()) arretTout();
        else lecture();
        break;
      case "restart":
      case "top":
        revenirAuDebut();
        break;
      // faster/slower : le serveur a déjà ajusté settings.speed, appliqué via applySettings.
    }
    updateSpeedTag();
  }

  // Vitesse venue d'ailleurs (Settings) : en mode dynamique, elle remplace la
  // vitesse posée au pied, sens conservé. Pas pendant un appui : la pédale a la
  // priorité, et sa nouvelle vitesse partira au relâchement.
  function adopterVitesse(v) {
    if (keys.forward || keys.backward) return;
    if (Math.abs(dynVel) >= 1) dynVel = Math.sign(dynVel) * v;
    renderSpeedTag();
  }

  // Vitesse posée au pied : on la confie au serveur, qui en fait LA vitesse du
  // prompteur. Le curseur de Settings la montre, et Plus vite / Moins vite
  // partent d'elle au lieu d'une valeur périmée.
  function envoyerVitesse(v) {
    if (!isLeading || v === Math.round(speed)) return;
    speed = v;
    if (settings) settings.speed = v;
    postJson("/api/settings", { speed: v }).catch(() => {});
  }

  function envoyerCommande(cmd) {
    postJson("/api/command", { cmd }).catch(() => {});
  }

  // Écrit l'indicateur sans le faire clignoter : en mode dynamique il change à
  // chaque image tant qu'une pédale est enfoncée.
  function renderSpeedTag() {
    if (isViewer) return;
    const mode = currentMode();
    let icon = "⏸";
    let valeur = Math.round(speed);
    if (mode === "dyn") {
      // Sans vitesse posée au pied, c'est celle du réglage qui servira à la reprise.
      valeur = Math.round(Math.abs(dynVel) >= 1 ? Math.abs(dynVel) : speed);
      if (!dynPaused && dynVel > 0.5) icon = "▶︎";
      else if (!dynPaused && dynVel < -0.5) icon = "◀︎";
    } else if (mode === "tap") {
      if (tapDir > 0) icon = "▶︎";
      else if (tapDir < 0) icon = "◀︎";
    } else if (autoPlay || keys.forward) {
      icon = "▶︎";
    } else if (keys.backward) {
      icon = "◀︎";
    }
    speedTag.textContent = `${icon} ${valeur}`;
  }

  function updateSpeedTag() {
    if (isViewer) return;
    renderSpeedTag();
    flash(speedTag);
  }

  let hudTimer = null;
  function flash(el) {
    el.classList.remove("hidden");
    if (el === hud) {
      clearTimeout(hudTimer);
      hudTimer = setTimeout(() => hud.classList.add("hidden"), 5000);
    }
  }

  // --- Vue Spectateur : une réplique du grand écran ---------------------------
  // Une fenêtre d'une autre taille coupait les lignes ailleurs : la régie ne
  // voyait pas la même phrase sous la ligne rouge, et un redimensionnement la
  // décalait encore. La vue Spectateur reproduit donc la mise en page de la vue
  // Journaliste — même largeur de texte, donc mêmes coupures de lignes — puis la
  // met à l'échelle de sa propre fenêtre. Le meneur donne ses dimensions avec sa
  // position (/api/scroll). Sans elles (aucune vue Journaliste ouverte), la vue
  // Spectateur se met en page à sa propre taille, comme avant.
  const replique = { largeur: 0, hauteur: 0, echelle: 1 };

  function mettreEnPage() {
    const s = settings || {};
    // 0 % est une valeur voulue : « || 10 » la remplaçait par 10 %.
    const m = Math.max(0, Math.min(45, Number.isFinite(Number(s.margin)) ? Number(s.margin) : 10));
    const L = replique.largeur;
    const H = replique.hauteur;
    if (isViewer && L > 0 && H > 0) {
      // L'échelle qui fait tenir l'écran du journaliste dans cette fenêtre. Une
      // fenêtre plus haute que lui montre simplement plus de lignes au-dessus et
      // au-dessous ; une fenêtre plus large le centre.
      const e = Math.min(viewport.clientWidth / L, viewport.clientHeight / H);
      replique.echelle = Number.isFinite(e) && e > 0 ? e : 1;
      scroller.style.width = L + "px";
      scroller.style.left = Math.max(0, (viewport.clientWidth - L * replique.echelle) / 2) + "px";
      // En pixels du grand écran : les pourcentages se rapporteraient ici à la
      // fenêtre, et plus à la largeur du texte.
      scroller.style.paddingLeft = (L * m) / 100 + "px";
      scroller.style.paddingRight = (L * m) / 100 + "px";
      scroller.style.paddingTop = 0.6 * H + "px";
      scroller.style.paddingBottom = 0.8 * H + "px";
    } else {
      replique.echelle = 1;
      scroller.style.width = "100%";
      scroller.style.left = "0px";
      scroller.style.paddingLeft = m + "%";
      scroller.style.paddingRight = m + "%";
      scroller.style.paddingTop = "60vh";
      scroller.style.paddingBottom = "80vh";
    }
  }

  // Hauteur visible, dans les unités de la mise en page (avant mise à l'échelle).
  function hauteurVisible() {
    return viewport.clientHeight / replique.echelle;
  }

  function placer() {
    scroller.style.transform =
      replique.echelle === 1 ? `translateY(${-pos}px)` : `scale(${replique.echelle}) translateY(${-pos}px)`;
  }

  function maxScrollPos() {
    return Math.max(0, scroller.scrollHeight - hauteurVisible());
  }

  // --- Repère dans le TEXTE, et non en pixels --------------------------------
  // Une position en pixels ne désigne le même passage que sur un écran de même
  // taille : ailleurs, les lignes ne se coupent pas au même endroit. On repère
  // donc la ligne du texte qui passe sous la ligne rouge, et la fraction de cette
  // ligne déjà passée. Sert à la vue Spectateur (écran d'une autre taille) et au
  // changement de taille du texte en pleine lecture (on reste sur la même phrase).
  function hauteurRepere() {
    const s = settings || {};
    const pourcent = Number.isFinite(Number(s.guidePos)) ? Number(s.guidePos) : 42;
    return (hauteurVisible() * Math.max(0, Math.min(100, pourcent))) / 100;
  }

  function repereDepuisPosition(p) {
    const lignes = scroller.children;
    if (!lignes.length) return null;
    const y = p + hauteurRepere();
    // Recherche dichotomique : un script peut compter des milliers de lignes.
    let bas = 0;
    let haut = lignes.length - 1;
    while (bas < haut) {
      const milieu = (bas + haut + 1) >> 1;
      if (lignes[milieu].offsetTop <= y) bas = milieu;
      else haut = milieu - 1;
    }
    const ligne = lignes[bas];
    const h = Math.max(1, ligne.offsetHeight);
    return { ligne: bas, frac: (y - ligne.offsetTop) / h, h };
  }

  function positionDepuisRepere(repere) {
    const ligne = repere && scroller.children[repere.ligne];
    if (!ligne) return null;
    return ligne.offsetTop + repere.frac * Math.max(1, ligne.offsetHeight) - hauteurRepere();
  }

  // --- Diffusion de la position (meneur -> serveur -> spectateurs) ----------
  let lastSentVel = null;
  let lastSentAt = 0;
  function forceResync() {
    lastSentVel = null; // force l'envoi à la prochaine frame
  }
  function pushScroll(p, v) {
    const repere = repereDepuisPosition(p) || {};
    fetch("/api/scroll", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      keepalive: true,
      body: JSON.stringify({
        pos: p,
        vel: v,
        playing: autoPlay || v > 0,
        largeur: viewport.clientWidth,
        hauteur: viewport.clientHeight,
        ...repere,
      }),
    }).catch(() => {});
  }
  function maybePush(now, v) {
    if (!isLeading) return; // pas le meneur : on n'impose sa position à personne
    // En mouvement, un point toutes les 250 ms ; à l'arrêt, toutes les 2 s : une
    // vue Spectateur ouverte (ou rechargée) après l'arrêt se cale quand même.
    const KEYFRAME_MS = v !== 0 ? 250 : 2000;
    const changed = v !== lastSentVel;
    const keyframe = now - lastSentAt > KEYFRAME_MS;
    if (changed || keyframe) {
      lastSentVel = v;
      lastSentAt = now;
      pushScroll(pos, v);
    }
  }

  // --- Boucle d'animation ---------------------------------------------------
  function framePresenter(now, dt) {
    const mode = currentMode();
    let v = 0;

    if (mode === "dyn") {
      // Rampe intégrée image par image : on atteint la vitesse maximale après
      // « rampSeconds » d'appui continu. La vitesse traverse zéro sans à-coup,
      // ce qui donne le passage progressif de l'avant vers l'arrière.
      // Pas de rampe à l'arrêt, ni au début d'un appui de reprise : reprendre
      // après une pause se fait à la vitesse d'avant. Maintenu plus longtemps,
      // l'appui de reprise se remet à accélérer.
      const secondes = Math.max(1, Math.min(30, Number((settings || {}).rampSeconds) || 10));
      const accel = SPEED_MAX / secondes; // px/s²
      const retenue = reprise && now - reprise.depuis < DELAI_REPRISE_MS ? reprise.cle : null;
      if (!dynPaused) {
        if (keys.forward && retenue !== "forward") dynVel = Math.min(SPEED_MAX, dynVel + accel * dt);
        if (keys.backward && retenue !== "backward") dynVel = Math.max(-SPEED_MAX, dynVel - accel * dt);
        if (keys.forward || keys.backward) renderSpeedTag();
      }
      v = dynPaused ? 0 : dynVel;
    } else if (mode === "tap") {
      v = tapDir * speed;
    } else {
      if (keys.backward) v = -speed * 2.2; // reculer plus vite pour retrouver sa place
      else if (keys.forward) v = +speed;
      else if (autoPlay) v = +speed;
    }

    if (v !== 0) {
      pos += v * dt;
      const maxPos = maxScrollPos();
      let butee = false;
      if (pos < 0) {
        pos = 0;
        butee = v < 0;
      } else if (pos > maxPos) {
        pos = maxPos;
        butee = v > 0;
      }
      // Mode dynamique : arrivé en haut ou en bas du texte, on se met en pause.
      // Sans cela la vitesse restait lancée contre la butée, et la pédale
      // opposée semblait morte le temps de la faire redescendre. La vitesse est
      // conservée : un appui sur l'autre pédale repart aussitôt dans l'autre sens.
      if (butee && mode === "dyn") {
        dynPaused = true;
        v = 0;
        updateSpeedTag();
      }
    }
    maybePush(now, v);
    placer();
  }

  function frameViewer(now, dt) {
    // anticipation : on extrapole la position du meneur à partir de sa vitesse,
    // puis on rapproche doucement la position locale de cette cible (anti-saccade).
    // Une seconde au plus : le meneur envoie un point toutes les 250 ms quand il
    // bouge. S'il se tait (fermé en plein défilement), on s'arrête au lieu de
    // défiler seul jusqu'à la fin du texte.
    const elapsed = Math.min(1, (now - follow.at) / 1000);
    // Le repère dans le texte d'abord ; les pixels seulement à défaut (meneur
    // d'une version antérieure, ou texte pas encore chargé ici).
    const base = positionDepuisRepere(follow.repere);
    let target;
    if (base !== null) {
      const ligne = scroller.children[follow.repere.ligne];
      const echelle = follow.repere.h > 0 ? ligne.offsetHeight / follow.repere.h : 1;
      target = base + follow.vel * echelle * elapsed;
    } else {
      target = follow.pos + follow.vel * elapsed;
    }
    // Bornes larges : une fenêtre plus haute que le grand écran doit pouvoir
    // descendre le début du texte jusqu'à sa ligne rouge (ou y monter la fin),
    // quitte à laisser du noir au-dessus ou au-dessous. Bornée à 0, elle butait
    // et montrait une autre phrase que celle du journaliste.
    const bas = -hauteurVisible();
    const haut = scroller.scrollHeight;
    if (target < bas) target = bas;
    else if (target > haut) target = haut;
    const k = Math.min(1, dt * 20); // vitesse de convergence
    pos += (target - pos) * k;
    if (Math.abs(target - pos) < 0.5) pos = target;
    placer();
  }

  function frame(now) {
    if (!lastTime) lastTime = now;
    const dt = Math.min(0.1, (now - lastTime) / 1000);
    lastTime = now;
    if (isViewer) frameViewer(now, dt);
    else framePresenter(now, dt);
    requestAnimationFrame(frame);
  }

  // --- Réservation de la place de meneur ------------------------------------
  // Un seul écran principal à la fois : deux meneurs pousseraient chacun leur
  // position de défilement, et le texte sauterait en pleine lecture.
  // Bail à renouveler, jamais verrou : si ce navigateur disparaît sans prévenir,
  // la place se libère seule au bout de quelques secondes. Et la reprise en main
  // forcée est toujours offerte — on ne doit jamais pouvoir s'enfermer dehors.
  const takenBox = document.getElementById("taken");
  let presenterToken = null;
  let isLeading = false;

  function newToken() {
    if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID();
    return "t" + Date.now() + Math.random().toString(36).slice(2);
  }

  function postJson(path, body) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
    });
  }

  function showTaken(title, sub) {
    if (title) document.getElementById("takenTitle").textContent = title;
    if (sub) document.getElementById("takenSub").textContent = sub;
    takenBox.style.display = "flex";
  }

  async function claimPresenter(force) {
    try {
      const sess = window.sessionStorage;
      presenterToken = (sess && sess.getItem("prompteurToken")) || presenterToken || newToken();
      if (sess) sess.setItem("prompteurToken", presenterToken);
    } catch {
      presenterToken = presenterToken || newToken();
    }
    try {
      const r = await postJson("/api/presenter/claim", { token: presenterToken, force: !!force });
      if (r.status === 409) {
        isLeading = false;
        showTaken();
        return;
      }
      isLeading = r.ok;
      takenBox.style.display = "none";
    } catch {
      // Serveur injoignable : on laisse l'écran fonctionner en local plutôt que
      // de le bloquer. L'alerte de liaison perdue prendra le relais.
      isLeading = true;
    }
  }

  async function pingPresenter() {
    if (!presenterToken) return;
    try {
      const r = await postJson("/api/presenter/ping", { token: presenterToken });
      const body = await r.json().catch(() => ({}));
      if (body.ok === false) {
        if (isLeading) {
          isLeading = false;
          showTaken(
            "Un autre appareil a pris la main.",
            "Cet écran ne pilote plus le défilement. Il reprendra la main tout seul dès que l'autre sera fermé."
          );
        }
      } else if (body.ok === true && !isLeading) {
        // La place s'est libérée (l'autre écran a été fermé, ou son bail a
        // expiré) : le serveur nous l'a rendue. Sans ce retour, le voile restait
        // affiché pour toujours, sur un écran qui pilotait de nouveau.
        isLeading = true;
        takenBox.style.display = "none";
        forceResync();
      }
    } catch {
      /* liaison perdue : déjà signalée par ailleurs */
    }
  }

  if (!isViewer) {
    document.getElementById("takeOver").addEventListener("click", () => claimPresenter(true));
    claimPresenter(false);
    setInterval(pingPresenter, 4000);
    window.addEventListener("pagehide", () => {
      // Meilleur effort : si ce message n'arrive pas, le bail expire tout seul.
      if (presenterToken) postJson("/api/presenter/release", { token: presenterToken });
    });
  }

  // --- Mise en place du haut de l'écran -------------------------------------
  // Le bandeau d'aide est en haut (en bas, le texte défilant lui passait dessus).
  // Sur un écran étroit il se replie sur plusieurs lignes : la carte d'adresses
  // doit donc se caler SOUS lui, hauteur réelle mesurée, et pas à une distance
  // fixe devinée pour un grand écran.
  function layoutTop() {
    const h = hud.getBoundingClientRect().height;
    netinfo.style.top = Math.round(h + 16) + "px";
  }
  layoutTop();
  window.addEventListener("resize", layoutTop);
  // Fenêtre redimensionnée : la réplique se remet à l'échelle, et la même phrase
  // reste sous la ligne rouge (la position est recalculée à chaque image).
  if (isViewer) window.addEventListener("resize", mettreEnPage);

  // --- Plein écran (écran principal uniquement) ------------------------------
  // On veut un écran de lecture sans barre d'adresse ni onglet. Deux obstacles,
  // tous deux contournés ici :
  //
  // 1. Un navigateur REFUSE le plein écran demandé au chargement : il exige un
  //    geste de l'utilisateur. On tente quand même (certains contextes, dont le
  //    kiosque du boîtier, l'acceptent), et sinon on l'installe au PREMIER geste
  //    venu — un clic, une touche, un appui de pédale. En pratique c'est
  //    invisible : on appuie de toute façon sur une pédale pour commencer.
  //
  // 2. En plein écran, Échap est CONFISQUÉE par le navigateur pour en sortir :
  //    notre gestionnaire ne la verrait jamais. On écoute donc la sortie de
  //    plein écran elle-même et on la traite comme la demande de quitter. Pour
  //    l'utilisateur, le geste reste « Échap », et l'invite s'affiche.
  //
  // L'écran secondaire, lui, reste une page ordinaire : on y revient en arrière
  // avec les flèches du navigateur, comme sur n'importe quel site.
  const wantsFullscreen = !isViewer;
  let fullscreenAsked = false;
  let leavingOnPurpose = false;

  function enterFullscreen() {
    if (!wantsFullscreen || document.fullscreenElement) return;
    const el = document.documentElement;
    if (!el.requestFullscreen) return;
    fullscreenAsked = true;
    el.requestFullscreen().catch(() => {
      /* refusé faute de geste : on retentera au premier geste réel */
    });
  }

  if (wantsFullscreen) {
    enterFullscreen();
    // Filet : le premier geste, quel qu'il soit, installe le plein écran.
    const once = () => {
      enterFullscreen();
      if (document.fullscreenElement) {
        window.removeEventListener("keydown", once, true);
        window.removeEventListener("click", once, true);
      }
    };
    window.addEventListener("keydown", once, true);
    window.addEventListener("click", once, true);

    document.addEventListener("fullscreenchange", () => {
      if (document.fullscreenElement) return;
      if (!fullscreenAsked) return;
      if (leavingOnPurpose) {
        leavingOnPurpose = false;
        return; // sortie volontaire par la touche F : on ne propose pas de quitter
      }
      // Sortie du plein écran non demandée : c'est l'Échap de l'utilisateur.
      askQuit();
    });
  }

  // --- Quitter la vue Journaliste (Échap) -----------------------------------
  // C'est le SEUL endroit où l'on est prisonnier : les vues Settings et
  // Spectateur sont des pages web ordinaires, qu'on ferme quand on veut. Ici le
  // navigateur est en plein écran, sans barre ni onglet.
  //
  // Échap RAMÈNE À LA VUE SETTINGS, il ne ferme pas le navigateur. Deux actions
  // distinctes, pour deux besoins distincts :
  //   Échap ................. revient à la vue Settings, partout, toujours ;
  //   « Bureau » (section Vue du journaliste) ferme le navigateur et rend la
  //                           main au bureau du Raspberry.
  // Faire tuer le navigateur par une touche serait à la fois plus risqué et sans
  // effet visible hors du mode kiosque — là où l'on teste, justement.
  // Confirmation en deux temps : une touche unique suffirait à couper l'écran en
  // pleine prise si un clavier de secours est branché.
  const quitAsk = document.getElementById("quitAsk");
  let quitPending = false;

  function askQuit() {
    quitPending = true;
    quitAsk.style.display = "block";
  }
  function cancelQuit() {
    quitPending = false;
    quitAsk.style.display = "none";
    restoreQuitText();
  }

  const QUIT_TITLE = "Quitter la vue Journaliste ?";
  // On mémorise les NŒUDS d'origine, pas du balisage : rien n'est reconstruit à
  // partir d'une chaîne, donc rien à échapper.
  const QUIT_SUB_NODES = [...document.getElementById("quitSub").childNodes];

  function restoreQuitText() {
    document.getElementById("quitTitle").textContent = QUIT_TITLE;
    document.getElementById("quitSub").replaceChildren(...QUIT_SUB_NODES);
  }

  // Refus de quitter : on le dit dans la même fenêtre, et elle se referme seule.
  function refuseQuit() {
    quitPending = false;
    document.getElementById("quitTitle").textContent = "Impossible de quitter la vue Journaliste.";
    const petit = document.createElement("span");
    petit.style.fontSize = "15px";
    petit.textContent =
      "Le texte reste lisible et les pédales fonctionnent. " +
      "Réessayez quand le bandeau rouge aura disparu.";
    document.getElementById("quitSub").replaceChildren(
      document.createTextNode(
        "La liaison avec le boîtier est perdue : la vue Settings ne répondrait pas, " +
          "et il n'y a pas de flèche retour ici."
      ),
      document.createElement("br"),
      petit
    );
    quitAsk.style.display = "block";
    setTimeout(() => {
      if (!quitPending) cancelQuit();
    }, 6000);
  }
  function doQuit() {
    // En kiosque il n'y a NI barre d'adresse NI flèche retour : si le serveur est
    // tombé, partir vers Settings mènerait à une page d'erreur sans aucun moyen de
    // revenir. On refuse donc de quitter tant que la liaison est perdue, et on le
    // dit — mieux vaut rester sur un texte lisible que s'échouer sur une impasse.
    // Refermer une fenêtre ne demande rien au serveur : on ne refuse que la
    // navigation, qui, elle, aboutirait à une page d'erreur sans retour possible.
    const peutFermer = window.opener && !window.opener.closed;
    if (!peutFermer && failures >= FAILURES_BEFORE_WARNING) {
      refuseQuit();
      return;
    }
    cancelQuit();
    leavingOnPurpose = true;
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
    // Fenêtre ouverte par Settings : on la referme, et Settings est déjà là
    // derrière. Aucune navigation, donc aucune impasse même serveur coupé.
    if (window.opener && !window.opener.closed) {
      window.close();
      return;
    }
    // Sur le boîtier, c'est le grand écran qu'on change de vue, par le même
    // chemin que la section « Vue du journaliste » : l'état qu'elle affiche
    // reste juste, et « Journaliste » y ramène d'un appui.
    // Seulement si c'est bien le kiosque qui affiche cette vue : une fenêtre
    // ordinaire ouverte sur le boîtier navigue, simplement.
    const naviguer = () => {
      window.location.href = "/settings";
    };
    if (!["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) {
      naviguer();
      return;
    }
    fetch("/api/kiosk", { cache: "no-store" })
      .then((r) => r.json())
      .then((etat) => {
        if (!etat.running || etat.vue !== "journaliste") return naviguer();
        return postJson("/api/kiosk/launch", { vue: "settings" }).then((r) => {
          if (!r.ok) naviguer();
        });
      })
      .catch(naviguer);
  }

  // --- Les trois modes de pédalier ------------------------------------------
  // MAINTIEN  : pédale enfoncée = ça défile, relâchée = ça s'arrête. Pédale
  //             centrale sans fonction.
  // IMPULSION : une pression lance le défilement dans un sens, une seconde
  //             pression sur la MÊME pédale met en pause. Centrale sans fonction.
  // DYNAMIQUE : la centrale fait lecture/pause ; la droite accélère vers l'avant
  //             tant qu'on appuie, la gauche ralentit puis repart en arrière, de
  //             plus en plus vite. La vitesse atteinte est CONSERVÉE au
  //             relâchement : le présentateur pose la vitesse une fois, puis lit.
  //
  // Le mode dynamique n'utilise pas le réglage « vitesse » : sa vitesse est
  // construite au pied. Les événements clavier servent seulement à savoir si une
  // pédale est enfoncée ; toute la rampe est intégrée image par image dans la
  // boucle d'animation, avec le même dt borné que le reste.
  const SPEED_MAX = 600; // même borne que le serveur
  let dynVel = 0; // vitesse signée construite au pied, en px/s
  let dynPaused = true; // la pédale centrale bascule ce drapeau
  let tapDir = 0; // -1 arrière, 0 pause, +1 avant (mode impulsion)
  // Reprise après une pause (mode dynamique) : la pédale choisit le SENS, la
  // vitesse reste celle d'avant la pause. { cle, depuis } tant que la pédale de
  // reprise est enfoncée.
  let reprise = null;
  const DELAI_REPRISE_MS = 400; // au-delà, l'appui de reprise se remet à accélérer

  function currentMode() {
    return (settings || {}).mode || "hold";
  }

  // --- Touches (pédales + raccourcis) — meneur uniquement pour le pilotage --
  function keyName(e) {
    const map = { Down: "ArrowDown", Up: "ArrowUp", Left: "ArrowLeft", Right: "ArrowRight", Spacebar: " ", Esc: "Escape" };
    return map[e.key] || e.key;
  }

  window.addEventListener("keydown", (e) => {
    const k = keyName(e);
    // En veille, la première touche (une pédale, le plus souvent) rallume tout
    // et ne fait rien d'autre : pas de défilement surprise au réveil.
    if (!isViewer && Commun && Commun.veille.active()) {
      e.preventDefault();
      if (!e.repeat) Commun.veille.rallumer();
      return;
    }
    if (k === "f" || k === "F") {
      toggleFullscreen();
      return;
    }
    if (isViewer) return; // spectateur = lecture seule, les pédales sont ignorées

    // Échap : demande, puis confirme. Toute autre touche annule la demande.
    if (k === "Escape") {
      e.preventDefault();
      if (quitPending) doQuit();
      else askQuit();
      return;
    }
    if (quitPending) {
      cancelQuit();
      return; // la touche qui annule ne fait rien d'autre : pas de pédale par surprise
    }

    const s = settings || {};
    const kf = s.keyForward || "ArrowDown";
    const kb = s.keyBackward || "ArrowUp";
    const kc = s.keyCenter || "ArrowRight";
    const mode = s.mode || "hold";

    if (k === kf || k === kb) {
      e.preventDefault();
      const sens = k === kf ? 1 : -1;
      const cle = sens > 0 ? "forward" : "backward";
      // L'autorépétition du clavier est ignorée : une pédale maintenue
      // basculerait sinon des dizaines de fois par seconde.
      if (e.repeat) return;
      if (mode === "tap") {
        // Deuxième appui sur la MÊME pédale = pause. Sur l'autre = on repart
        // dans l'autre sens.
        tapDir = tapDir === sens ? 0 : sens;
      } else if (mode === "dyn" && dynPaused) {
        // Reprise après une pause : droite = vers l'avant, gauche = vers
        // l'arrière, à la vitesse d'avant la pause (à défaut, celle du réglage).
        const v = Math.abs(dynVel) >= 1 ? Math.abs(dynVel) : speed;
        dynVel = sens * v;
        dynPaused = false;
        reprise = { cle, depuis: performance.now() };
        keys[cle] = true;
      } else {
        keys[cle] = true; // maintien et dynamique : pédale enfoncée
      }
      updateSpeedTag();
      return;
    }
    if (k === kc) {
      e.preventDefault();
      // Pédale centrale : lecture/pause, et UNIQUEMENT en mode dynamique. Dans
      // les deux autres modes le client la veut explicitement sans fonction.
      if (mode === "dyn" && !e.repeat) {
        if (!dynPaused) arretTout();
        else repriseCentrale();
      }
      updateSpeedTag();
      return;
    }

    switch (k) {
      case " ":
        e.preventDefault();
        if (!e.repeat) applyCommand("toggle");
        break;
      // Plus vite / moins vite passent par le serveur, comme les boutons de
      // Settings : sinon le réglage s'annulait à la mise à jour suivante.
      case "+": case "=": envoyerCommande("faster"); break;
      case "-": case "_": envoyerCommande("slower"); break;
      case "r": case "R": revenirAuDebut(); updateSpeedTag(); break;
      case "m": case "M":
        // Enregistré par le boîtier, comme l'interrupteur de Settings : il
        // retourne aussi le reste du grand écran (Settings, bureau), et
        // l'interrupteur du téléphone reste juste.
        if (settings) {
          settings.mirrorH = !settings.mirrorH;
          stage.style.transform = `scale(${settings.mirrorH ? -1 : 1}, ${settings.mirrorV ? -1 : 1})`;
          postJson("/api/settings", { mirrorH: settings.mirrorH }).catch(() => {});
        }
        break;
      case "h": case "H": hud.classList.toggle("hidden"); break;
      case "i": case "I": netinfo.classList.toggle("hidden"); break;
    }
  });

  window.addEventListener("keyup", (e) => {
    if (isViewer) return;
    const s = settings || {};
    const k = keyName(e);
    let cle = null;
    if (k === (s.keyForward || "ArrowDown")) cle = "forward";
    else if (k === (s.keyBackward || "ArrowUp")) cle = "backward";
    if (!cle) return;
    keys[cle] = false;
    if (reprise && reprise.cle === cle) reprise = null;
    // Mode dynamique : la vitesse posée au pied devient celle du prompteur.
    if (currentMode() === "dyn" && Math.abs(dynVel) >= 1) {
      envoyerVitesse(Math.max(10, Math.min(SPEED_MAX, Math.round(Math.abs(dynVel)))));
    }
    updateSpeedTag();
  });

  // Sécurité meneur : perte de focus pédale enfoncée -> on relâche (pas de « pédale collée »)
  function releasePedals() {
    // Perte de focus : aucune pédale ne doit rester « collée ». En impulsion et
    // en dynamique, le défilement est en cours SANS qu'aucune touche soit
    // enfoncée : on le met aussi en pause, sinon le texte continuerait de défiler
    // derrière une fenêtre que plus personne ne regarde.
    const enMouvement = keys.forward || keys.backward || tapDir !== 0 || !dynPaused;
    if (!enMouvement) return;
    keys.forward = false;
    keys.backward = false;
    tapDir = 0;
    dynPaused = true; // la vitesse acquise est conservée, on la reprend au pied
    reprise = null;
    forceResync();
    updateSpeedTag();
  }
  window.addEventListener("blur", releasePedals);
  window.addEventListener("pagehide", releasePedals);
  document.addEventListener("visibilitychange", () => { if (document.hidden) releasePedals(); });

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      fullscreenAsked = true;
      document.documentElement.requestFullscreen?.().catch(() => {});
    } else {
      leavingOnPurpose = true; // bascule voulue : pas d'invite « quitter ? »
      document.exitFullscreen?.();
    }
  }
  window.addEventListener("click", () => { if (!isViewer) flash(hud); });

  // --- Synchronisation avec le serveur (interrogation rapide) ---------------
  // Texte + réglages + commandes : on lit /api/version (léger) et on ne recharge
  // le texte complet (/api/state) que si quelque chose a changé.
  // Liaison perdue : on ne crie pas au premier raté (le service se relance tout
  // seul en deux secondes), mais on finit par le DIRE. Sans cela l'écran reste
  // noir et muet, et personne ne peut savoir si le texte est encore à jour.
  const linkLost = document.getElementById("linkLost");
  let failures = 0;
  const FAILURES_BEFORE_WARNING = 4;

  function linkOk() {
    failures = 0;
    linkLost.style.display = "none";
  }
  function linkFailed() {
    failures += 1;
    if (failures >= FAILURES_BEFORE_WARNING) linkLost.style.display = "block";
  }

  async function pollState() {
    try {
      const v = await (await fetch("/api/version", { cache: "no-store" })).json();
      linkOk();
      if (Commun) Commun.veille.maj(v.veille);
      if (v.version === lastVersion && v.cmdSeq === lastCmdSeq) return;
      // On demande les réglages DÉJÀ résolus pour cette surface : l'écran ne
      // porte aucune logique de portée, il applique ce qu'on lui donne.
      const st = await (
        await fetch(`/api/state?surface=${isViewer ? "view" : "display"}`, { cache: "no-store" })
      ).json();
      if (st.version !== lastVersion) {
        lastVersion = st.version;
        applySettings(st.settings, st.text, st.marks);
      }
      if (st.control && st.control.cmdSeq !== lastCmdSeq) {
        // À l'ouverture de l'écran, la dernière commande envoyée est de
        // l'histoire ancienne : la rejouer faisait défiler le texte tout seul
        // dès le démarrage du boîtier.
        const ouverture = lastCmdSeq === -1;
        lastCmdSeq = st.control.cmdSeq;
        if (!ouverture && !isViewer && st.control.cmd) applyCommand(st.control.cmd);
      }
    } catch {
      // le serveur peut redémarrer : on réessaie au prochain tick, et on
      // n'avertit qu'après plusieurs échecs d'affilée
      linkFailed();
    }
  }

  // Position du meneur (spectateur uniquement) : lue très souvent ; le rendu la
  // SUIT avec anticipation (voir frameViewer) pour un défilement fluide et collé.
  const SCROLL_LEAD_MS = 30; // compense le délai de détection d'un nouveau point (interrogation)
  async function pollScroll() {
    try {
      // instant d'ENVOI : la position lue reflète l'état du meneur au milieu de l'aller-retour,
      // donc dater le point à l'envoi (et non à la réception) compense la latence de la requête.
      const sent = performance.now();
      const s = await (await fetch("/api/scroll", { cache: "no-store" })).json();
      // On ne se re-cale QUE sur un nouveau point du meneur (seq changé) ; entre deux,
      // on continue d'anticiper avec la vitesse -> le défilement reste fluide et collé.
      const L = Number(s.largeur) || 0;
      const H = Number(s.hauteur) || 0;
      if (L !== replique.largeur || H !== replique.hauteur) {
        replique.largeur = L;
        replique.hauteur = H;
        mettreEnPage();
      }
      if (s.seq !== follow.seq) {
        follow.seq = s.seq;
        follow.pos = Number(s.pos) || 0;
        follow.vel = Number(s.vel) || 0;
        follow.repere = Number.isInteger(s.ligne)
          ? { ligne: s.ligne, frac: Number(s.frac) || 0, h: Number(s.h) || 0 }
          : null;
        follow.at = sent - (follow.vel ? SCROLL_LEAD_MS : 0);
      }
    } catch {
      /* réessai au prochain tick */
    }
  }

  // --- Adresse(s) du boîtier (meneur : affiche où lire depuis un PC/tablette) -
  async function loadInfo() {
    try {
      const info = await (await fetch("/api/info", { cache: "no-store" })).json();
      const addresses = info.addresses || [];
      const port = info.port || 5000;
      const primary = addresses[0] || "10.42.0.1";
      const main = `http://${primary}:${port}/journaliste`;
      const spec = `http://${primary}:${port}/spectateur`;
      // Construit element par element : les adresses viennent du systeme, et
      // aucune chaine de balisage n'est assemblee a la main.
      const bloc = (cls, texte, style) => {
        const d = document.createElement("div");
        if (cls) d.className = cls;
        if (style) d.setAttribute("style", style);
        d.textContent = texte;
        return d;
      };
      const ligneSpec = document.createElement("div");
      ligneSpec.setAttribute("style", "margin-top:10px");
      ligneSpec.append(
        document.createTextNode("Vue "),
        Object.assign(document.createElement("b"), { textContent: "Spectateur" }),
        document.createTextNode(" (régie, suit en direct) :")
      );
      const ligneWifi = document.createElement("div");
      ligneWifi.setAttribute("style", "font-size:14px;opacity:.65;margin-top:8px");
      ligneWifi.append(
        document.createTextNode("connecte l'appareil au WiFi "),
        Object.assign(document.createElement("b"), { textContent: "Prompteur" })
      );
      // Branché aussi à une box (câble Ethernet) : ses autres adresses, pour s'y
      // connecter depuis un ordinateur de ce réseau-là (ACCES-A-DISTANCE.md).
      const autres = addresses.slice(1);
      const ligneAutres = autres.length
        ? bloc("", "Autres adresses du boîtier : " + autres.join(" · "), "font-size:14px;opacity:.65;margin-top:6px")
        : document.createTextNode("");
      netinfo.replaceChildren(
        document.createTextNode("Vue Journaliste (PC / tablette) :"),
        bloc("addr", main),
        ligneSpec,
        bloc("addr", spec, "color:#ffd400"),
        ligneWifi,
        ligneAutres
      );
      const addrSpan = document.getElementById("emptyAddr");
      if (addrSpan) addrSpan.textContent = main;
    } catch {
      /* réessai possible plus tard */
    }
  }

  // --- Démarrage ------------------------------------------------------------
  requestAnimationFrame(frame);
  pollState();
  setInterval(pollState, 300); // texte / réglages / commandes

  if (isViewer) {
    hud.style.display = "none";
    speedTag.style.display = "none";
    pollScroll();
    setInterval(pollScroll, 66); // suivi fin de la position du meneur
  } else {
    loadInfo().then(() => {
      netinfo.classList.remove("hidden");
      setTimeout(() => netinfo.classList.add("hidden"), 12000);
    });
    setTimeout(() => hud.classList.add("hidden"), 6000);
    // Mise en veille : le texte s'arrête là où il est, pédales relâchées.
    if (Commun) {
      Commun.veille.surChangement((endormi) => {
        if (!endormi) return;
        releasePedals();
        arretTout();
        updateSpeedTag();
      });
    }
  }
})();
