/* Prompteur — logique de l'écran (défilement + pédales + synchro temps réel).

   Deux modes (injectés par le serveur via window.PROMPTEUR_MODE) :
   - "presenter" (/display) : écran MENEUR. Piloté aux pédales EN LOCAL (latence nulle),
     il DIFFUSE sa position de défilement au serveur.
   - "viewer" (/view) : écran SPECTATEUR (régie…). Lecture seule : il SUIT le meneur en
     temps réel, avec anticipation (connaît la vitesse) pour un défilement fluide et collé.

   Texte, réglages et position sont synchronisés par interrogation rapide du serveur ;
   le spectateur anticipe le mouvement entre deux lectures -> retard imperceptible. */

(() => {
  "use strict";

  const MODE = window.PROMPTEUR_MODE === "viewer" ? "viewer" : "presenter";
  const isViewer = MODE === "viewer";

  const scroller = document.getElementById("scroller");
  const viewport = document.getElementById("viewport");
  const stage = document.getElementById("stage");
  const guide = document.getElementById("guide");
  const hud = document.getElementById("hud");
  const speedTag = document.getElementById("speedTag");
  const emptyMsg = document.getElementById("empty");
  const netinfo = document.getElementById("netinfo");
  const specBadge = document.getElementById("specBadge");

  // --- État courant de l'affichage -----------------------------------------
  let settings = null;
  let pos = 0; // décalage de défilement en px (0 = haut du texte)
  let autoPlay = false; // défilement automatique mains-libres (meneur)
  let speed = 70; // px / seconde
  const keys = { forward: false, backward: false };
  let lastText = null;
  let lastVersion = -1;
  let lastCmdSeq = -1;
  let lastTime = 0;

  // Suivi (spectateur) : dernier point connu du meneur (pos, vitesse, instant, n° de séquence)
  const follow = { pos: 0, vel: 0, at: 0, seq: -1 };

  // --- Application des réglages reçus du serveur ----------------------------
  function applySettings(s, text, marks) {
    settings = s;
    speed = Number(s.speed) || 70;

    document.documentElement.style.setProperty("--bg", s.bgColor || "#000");
    document.documentElement.style.setProperty("--fg", s.textColor || "#fff");

    const fontMap = {
      "sans-serif": "system-ui, 'Segoe UI', Roboto, Arial, sans-serif",
      serif: "Georgia, 'Times New Roman', serif",
      monospace: "'Consolas', 'Courier New', monospace",
    };
    scroller.style.fontFamily = fontMap[s.font] || fontMap["sans-serif"];
    scroller.style.fontSize = Math.max(8, Math.min(400, Number(s.fontSize) || 64)) + "px";
    scroller.style.lineHeight = String(Math.max(0.8, Math.min(4, Number(s.lineHeight) || 1.6)));
    scroller.style.textAlign = s.align === "center" ? "center" : "left";

    const m = Math.max(0, Math.min(45, Number(s.margin) || 10));
    scroller.style.paddingLeft = m + "%";
    scroller.style.paddingRight = m + "%";
    scroller.style.paddingTop = "60vh";
    scroller.style.paddingBottom = "80vh";

    const sx = s.mirrorH ? -1 : 1;
    const sy = s.mirrorV ? -1 : 1;
    stage.style.transform = `scale(${sx}, ${sy})`;

    if (s.guide) {
      guide.style.display = "block";
      guide.style.top = Math.max(0, Math.min(100, Number(s.guidePos) || 42)) + "vh";
    } else {
      guide.style.display = "none";
    }

    // Texte : on ne remet à zéro le défilement (côté meneur) que s'il a vraiment changé
    if (text !== lastText) {
      renderScript(text || "", marks);
      lastText = text;
      if (!isViewer) {
        pos = 0;
        autoPlay = false;
      }
    }
    emptyMsg.style.display = text && text.trim() ? "none" : "flex";
    updateSpeedTag();
  }

  // Construit l'affichage à partir du texte : les lignes « # / ## / ### » deviennent
  // des TITRES (gros/gras) ; les autres lignes et les lignes vides sont préservées.
  // Classes de mise en forme actives a une position donnee du texte.
  const SIZE_CLASS = { s: "ms", l: "ml", xl: "mxl" };

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

  function renderScript(text, marks) {
    const plages = Array.isArray(marks) ? marks : [];
    const bornes = [];
    for (const m of plages) bornes.push(m.start, m.end);
    bornes.sort((a, b) => a - b);

    const frag = document.createDocumentFragment();
    let offset = 0;
    for (const line of String(text).split("\n")) {
      const div = document.createElement("div");
      const m = /^(#{1,3})\s+(.*)$/.exec(line);
      if (m) {
        div.className = "ln h" + m[1].length;
        // Le dièse et son espace ne sont pas affichés : les plages du titre sont
        // donc décalées d'autant.
        const decalage = line.length - m[2].length;
        if (plages.length) fillLine(div, m[2], offset + decalage, plages, bornes);
        else div.textContent = m[2]; // textContent -> aucun risque d'injection
      } else if (line.trim() === "") {
        div.className = "ln blank";
      } else {
        div.className = "ln";
        if (plages.length) fillLine(div, line, offset, plages, bornes);
        else div.textContent = line;
      }
      frag.appendChild(div);
      offset += line.length + 1; // +1 pour le saut de ligne retiré par split
    }
    scroller.replaceChildren(frag);
  }

  // --- Commandes ponctuelles (meneur uniquement) ---------------------------
  function applyCommand(cmd) {
    switch (cmd) {
      case "play": autoPlay = true; break;
      case "pause": autoPlay = false; break;
      case "toggle": autoPlay = !autoPlay; break;
      case "restart":
      case "top":
        pos = 0;
        autoPlay = false;
        resetPedalState(); // revenir au début remet aussi le pilotage au repos
        forceResync();
        break;
      // faster/slower : le serveur a déjà ajusté settings.speed, appliqué via applySettings.
    }
    updateSpeedTag();
  }

  function changeSpeed(delta) {
    speed = Math.max(10, Math.min(600, speed + delta));
    updateSpeedTag();
  }

  // Écrit l'indicateur sans le faire clignoter : en mode dynamique il change à
  // chaque image tant qu'une pédale est enfoncée.
  function renderSpeedTag() {
    if (isViewer) return;
    const mode = currentMode();
    let icon = "⏸";
    let valeur = Math.round(speed);
    if (mode === "dyn") {
      valeur = Math.round(Math.abs(dynVel));
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

  function maxScrollPos() {
    return Math.max(0, scroller.scrollHeight - viewport.clientHeight);
  }

  // --- Diffusion de la position (meneur -> serveur -> spectateurs) ----------
  let lastSentVel = null;
  let lastSentAt = 0;
  function forceResync() {
    lastSentVel = null; // force l'envoi à la prochaine frame
  }
  function pushScroll(p, v) {
    fetch("/api/scroll", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      keepalive: true,
      body: JSON.stringify({ pos: p, vel: v, playing: autoPlay || v > 0 }),
    }).catch(() => {});
  }
  function maybePush(now, v) {
    if (!isLeading) return; // pas le meneur : on n'impose sa position à personne
    const KEYFRAME_MS = 250;
    const changed = v !== lastSentVel;
    const keyframe = v !== 0 && now - lastSentAt > KEYFRAME_MS;
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
      const secondes = Math.max(1, Math.min(30, Number((settings || {}).rampSeconds) || 10));
      const accel = SPEED_MAX / secondes; // px/s²
      if (keys.forward) dynVel = Math.min(SPEED_MAX, dynVel + accel * dt);
      if (keys.backward) dynVel = Math.max(-SPEED_MAX, dynVel - accel * dt);
      if (keys.forward || keys.backward) renderSpeedTag();
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
      if (pos < 0) pos = 0;
      else if (pos > maxPos) pos = maxPos;
    }
    maybePush(now, v);
    scroller.style.transform = `translateY(${-pos}px)`;
  }

  function frameViewer(now, dt) {
    // anticipation : on extrapole la position du meneur à partir de sa vitesse,
    // puis on rapproche doucement la position locale de cette cible (anti-saccade).
    const elapsed = (now - follow.at) / 1000;
    let target = follow.pos + follow.vel * elapsed;
    const maxPos = maxScrollPos();
    if (target < 0) target = 0;
    else if (target > maxPos) target = maxPos;
    const k = Math.min(1, dt * 20); // vitesse de convergence
    pos += (target - pos) * k;
    if (Math.abs(target - pos) < 0.5) pos = target;
    scroller.style.transform = `translateY(${-pos}px)`;
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
        isLeading = false;
        showTaken(
          "Un autre appareil a pris la main.",
          "Cet écran ne pilote plus le défilement. Il continue d'afficher le texte."
        );
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

  // --- Revenir à la page d'accueil (Échap) ----------------------------------
  // C'est le SEUL endroit où l'on est prisonnier : la télécommande et l'écran de
  // régie sont des pages web ordinaires, qu'on ferme quand on veut. Ici le
  // navigateur est en plein écran, sans barre ni onglet.
  //
  // Échap RAMÈNE À L'ACCUEIL, il ne ferme pas le navigateur. Deux actions
  // distinctes, pour deux besoins distincts :
  //   Échap ................. revient à la page d'accueil, partout, toujours ;
  //   « Fermer le prompteur » (barre de l'accueil) ferme le navigateur et rend
  //                           la main au bureau du Raspberry.
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

  const QUIT_TITLE = "Revenir à la page d'accueil ?";
  const QUIT_SUB = document.getElementById("quitSub").innerHTML;

  function restoreQuitText() {
    document.getElementById("quitTitle").textContent = QUIT_TITLE;
    document.getElementById("quitSub").innerHTML = QUIT_SUB;
  }

  // Refus de quitter : on le dit dans la même fenêtre, et elle se referme seule.
  function refuseQuit() {
    quitPending = false;
    document.getElementById("quitTitle").textContent = "Impossible de revenir à l'accueil.";
    document.getElementById("quitSub").innerHTML =
      "La liaison avec le boîtier est perdue : la page d'accueil ne répondrait pas, " +
      "et il n'y a pas de flèche retour ici.<br>" +
      "<span style=\"font-size:15px;\">Le texte reste lisible et les pédales fonctionnent. " +
      "Réessayez quand le bandeau rouge aura disparu.</span>";
    quitAsk.style.display = "block";
    setTimeout(() => {
      if (!quitPending) cancelQuit();
    }, 6000);
  }
  function doQuit() {
    // En kiosque il n'y a NI barre d'adresse NI flèche retour : si le serveur est
    // tombé, partir vers « / » mènerait à une page d'erreur sans aucun moyen de
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
    // Fenêtre ouverte par l'accueil : on la referme, et l'accueil est déjà là
    // derrière. Aucune navigation, donc aucune impasse même serveur coupé.
    if (window.opener && !window.opener.closed) {
      window.close();
      return;
    }
    window.location.href = "/";
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

  function currentMode() {
    return (settings || {}).mode || "hold";
  }

  function resetPedalState() {
    dynVel = 0;
    dynPaused = true;
    tapDir = 0;
  }

  // --- Touches (pédales + raccourcis) — meneur uniquement pour le pilotage --
  function keyName(e) {
    const map = { Down: "ArrowDown", Up: "ArrowUp", Left: "ArrowLeft", Right: "ArrowRight", Spacebar: " ", Esc: "Escape" };
    return map[e.key] || e.key;
  }

  window.addEventListener("keydown", (e) => {
    const k = keyName(e);
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

    if (k === kf) {
      e.preventDefault();
      if (mode === "tap") {
        // Deuxième appui sur la MÊME pédale = pause. Sur l'autre = on repart
        // dans l'autre sens. L'autorépétition du clavier est ignorée, sinon une
        // pédale maintenue basculerait des dizaines de fois par seconde.
        if (!e.repeat) tapDir = tapDir === 1 ? 0 : 1;
      } else {
        keys.forward = true; // maintien et dynamique : pédale enfoncée
        if (mode === "dyn") dynPaused = false;
      }
      updateSpeedTag();
      return;
    }
    if (k === kb) {
      e.preventDefault();
      if (mode === "tap") {
        if (!e.repeat) tapDir = tapDir === -1 ? 0 : -1;
      } else {
        keys.backward = true;
        if (mode === "dyn") dynPaused = false;
      }
      updateSpeedTag();
      return;
    }
    if (k === kc) {
      e.preventDefault();
      // Pédale centrale : lecture/pause, et UNIQUEMENT en mode dynamique. Dans
      // les deux autres modes le client la veut explicitement sans fonction.
      if (mode === "dyn" && !e.repeat) dynPaused = !dynPaused;
      updateSpeedTag();
      return;
    }

    switch (k) {
      case " ": e.preventDefault(); autoPlay = !autoPlay; updateSpeedTag(); break;
      case "+": case "=": changeSpeed(+10); break;
      case "-": case "_": changeSpeed(-10); break;
      case "r": case "R": pos = 0; autoPlay = false; forceResync(); updateSpeedTag(); break;
      case "m": case "M":
        if (settings) {
          settings.mirrorH = !settings.mirrorH;
          stage.style.transform = `scale(${settings.mirrorH ? -1 : 1}, ${settings.mirrorV ? -1 : 1})`;
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
    if (k === (s.keyForward || "ArrowDown")) { keys.forward = false; updateSpeedTag(); }
    if (k === (s.keyBackward || "ArrowUp")) { keys.backward = false; updateSpeedTag(); }
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
        lastCmdSeq = st.control.cmdSeq;
        if (!isViewer && st.control.cmd) applyCommand(st.control.cmd);
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
      if (s.seq !== follow.seq) {
        follow.seq = s.seq;
        follow.pos = Number(s.pos) || 0;
        follow.vel = Number(s.vel) || 0;
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
      const main = `http://${primary}:${port}/display`;
      const spec = `http://${primary}:${port}/view`;
      netinfo.innerHTML =
        "Écran principal (PC / tablette) :" +
        `<div class="addr">${main}</div>` +
        '<div style="margin-top:10px">Écran <b>spectateur / régie</b> (suit en direct) :</div>' +
        `<div class="addr" style="color:#ffd400">${spec}</div>` +
        '<div style="font-size:14px;opacity:.65;margin-top:8px">connecte l\'appareil au WiFi <b>Prompteur</b></div>';
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
    specBadge.style.display = "block";
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
  }
})();
