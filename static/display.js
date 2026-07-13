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
  function applySettings(s, text) {
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
      renderScript(text || "");
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
  function renderScript(text) {
    const frag = document.createDocumentFragment();
    for (const line of String(text).split("\n")) {
      const div = document.createElement("div");
      const m = /^(#{1,3})\s+(.*)$/.exec(line);
      if (m) {
        div.className = "ln h" + m[1].length;
        div.textContent = m[2]; // textContent -> aucun risque d'injection
      } else if (line.trim() === "") {
        div.className = "ln blank";
      } else {
        div.className = "ln";
        div.textContent = line;
      }
      frag.appendChild(div);
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

  function updateSpeedTag() {
    if (isViewer) return;
    const icon = autoPlay || keys.forward ? "▶︎" : keys.backward ? "◀︎" : "⏸";
    speedTag.textContent = `${icon} ${Math.round(speed)}`;
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
    let v = 0;
    if (keys.backward) v = -speed * 2.2; // reculer plus vite pour retrouver sa place
    else if (keys.forward) v = +speed;
    else if (autoPlay) v = +speed;

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

    const s = settings || {};
    const kf = s.keyForward || "ArrowDown";
    const kb = s.keyBackward || "ArrowUp";
    const mode = s.mode || "hold";

    if (k === kf) {
      e.preventDefault();
      if (mode === "hold") keys.forward = true;
      else if (!e.repeat) autoPlay = !autoPlay; // impulsion : play/pause (on ignore l'autorepeat)
      updateSpeedTag();
      return;
    }
    if (k === kb) {
      e.preventDefault();
      if (mode === "hold") keys.backward = true;
      else if (!e.repeat) {
        pos = 0;
        autoPlay = false;
        forceResync();
      }
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
    if (keys.forward || keys.backward) {
      keys.forward = false;
      keys.backward = false;
      forceResync();
      updateSpeedTag();
    }
  }
  window.addEventListener("blur", releasePedals);
  window.addEventListener("pagehide", releasePedals);
  document.addEventListener("visibilitychange", () => { if (document.hidden) releasePedals(); });

  function toggleFullscreen() {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => {});
    else document.exitFullscreen?.();
  }
  window.addEventListener("click", () => { if (!isViewer) flash(hud); });

  // --- Synchronisation avec le serveur (interrogation rapide) ---------------
  // Texte + réglages + commandes : on lit /api/version (léger) et on ne recharge
  // le texte complet (/api/state) que si quelque chose a changé.
  async function pollState() {
    try {
      const v = await (await fetch("/api/version", { cache: "no-store" })).json();
      if (v.version === lastVersion && v.cmdSeq === lastCmdSeq) return;
      const st = await (await fetch("/api/state", { cache: "no-store" })).json();
      if (st.version !== lastVersion) {
        lastVersion = st.version;
        applySettings(st.settings, st.text);
      }
      if (st.control && st.control.cmdSeq !== lastCmdSeq) {
        lastCmdSeq = st.control.cmdSeq;
        if (!isViewer && st.control.cmd) applyCommand(st.control.cmd);
      }
    } catch {
      /* le serveur peut redémarrer : on réessaie au prochain tick */
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
