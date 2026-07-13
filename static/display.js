/* Prompteur — logique de l'écran (défilement + pédales).
   Cet écran interroge le serveur toutes les ~300 ms pour récupérer le texte,
   les réglages et les commandes envoyées depuis le téléphone.
   Les pédales (branchées en USB sur le boîtier) envoient de simples touches
   clavier : on les traite ici, en local, pour un défilement instantané. */

(() => {
  "use strict";

  const scroller = document.getElementById("scroller");
  const viewport = document.getElementById("viewport");
  const stage    = document.getElementById("stage");
  const guide    = document.getElementById("guide");
  const hud       = document.getElementById("hud");
  const speedTag  = document.getElementById("speedTag");
  const emptyMsg  = document.getElementById("empty");
  const netinfo   = document.getElementById("netinfo");

  // --- État courant de l'affichage -----------------------------------------
  let settings = null;
  let pos = 0;                 // décalage de défilement en px (0 = haut du texte)
  let autoPlay = false;        // défilement automatique mains-libres
  let speed = 70;              // px / seconde
  const keys = { forward: false, backward: false };
  let lastText = null;
  let lastVersion = -1;
  let lastCmdSeq = -1;
  let lastTime = 0;

  // --- Application des réglages reçus du serveur ----------------------------
  function applySettings(s, text) {
    settings = s;
    speed = Number(s.speed) || 70;

    // Couleurs
    document.documentElement.style.setProperty("--bg", s.bgColor || "#000");
    document.documentElement.style.setProperty("--fg", s.textColor || "#fff");

    // Typographie
    const fontMap = {
      "sans-serif": "system-ui, 'Segoe UI', Roboto, Arial, sans-serif",
      "serif": "Georgia, 'Times New Roman', serif",
      "monospace": "'Consolas', 'Courier New', monospace",
    };
    scroller.style.fontFamily = fontMap[s.font] || fontMap["sans-serif"];
    scroller.style.fontSize   = Math.max(8, Math.min(400, Number(s.fontSize) || 64)) + "px";
    scroller.style.lineHeight = String(Math.max(0.8, Math.min(4, Number(s.lineHeight) || 1.6)));
    scroller.style.textAlign  = s.align === "center" ? "center" : "left";

    // Marges latérales
    const m = Math.max(0, Math.min(45, Number(s.margin) || 10));
    scroller.style.paddingLeft  = m + "%";
    scroller.style.paddingRight = m + "%";
    // Marge haut/bas : on laisse défiler depuis sous l'écran jusqu'au dessus
    scroller.style.paddingTop    = "60vh";
    scroller.style.paddingBottom = "80vh";

    // Miroir (vitre sans tain) : on transforme toute la scène
    const sx = s.mirrorH ? -1 : 1;
    const sy = s.mirrorV ? -1 : 1;
    stage.style.transform = `scale(${sx}, ${sy})`;

    // Ligne de repère
    if (s.guide) {
      guide.style.display = "block";
      guide.style.top = (Math.max(0, Math.min(100, Number(s.guidePos) || 42))) + "vh";
    } else {
      guide.style.display = "none";
    }

    // Texte (on ne remet à zéro le défilement que si le texte a vraiment changé)
    if (text !== lastText) {
      scroller.textContent = text || "";
      lastText = text;
      pos = 0;
      autoPlay = false;
    }
    emptyMsg.style.display = (text && text.trim()) ? "none" : "flex";

    updateSpeedTag();
  }

  // --- Commandes ponctuelles envoyées depuis le téléphone -------------------
  function applyCommand(cmd) {
    switch (cmd) {
      case "play":    autoPlay = true; break;
      case "pause":   autoPlay = false; break;
      case "toggle":  autoPlay = !autoPlay; break;
      case "restart":
      case "top":     pos = 0; autoPlay = false; break;
      // faster/slower : le serveur a déjà ajusté settings.speed, appliqué via applySettings.
    }
    updateSpeedTag();
  }

  function changeSpeed(delta) {
    speed = Math.max(10, Math.min(600, speed + delta));
    updateSpeedTag();
  }

  function updateSpeedTag() {
    const icon = (autoPlay || keys.forward) ? "▶︎" : (keys.backward ? "◀︎" : "⏸");
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

  // --- Boucle de défilement -------------------------------------------------
  function frame(now) {
    if (!lastTime) lastTime = now;
    const dt = Math.min(0.1, (now - lastTime) / 1000); // s, plafonné pour éviter les sauts
    lastTime = now;

    // Vitesse instantanée selon les pédales / l'auto-play
    let v = 0;
    if (keys.backward)      v = -speed * 2.2;   // reculer plus vite pour retrouver sa place
    else if (keys.forward)  v = +speed;
    else if (autoPlay)      v = +speed;

    if (v !== 0) {
      pos += v * dt;
      // borne basse = haut du texte ; borne haute = fin du texte arrivée en bas d'écran
      const maxPos = Math.max(0, scroller.scrollHeight - viewport.clientHeight);
      if (pos < 0) pos = 0;
      else if (pos > maxPos) pos = maxPos;
    }

    scroller.style.transform = `translateY(${-pos}px)`;
    requestAnimationFrame(frame);
  }

  // --- Gestion des touches (pédales + clavier de test) ----------------------
  function keyName(e) {
    // Normalise les anciens noms de touches (IE/Edge/certaines pédales) vers le standard,
    // pour qu'une pédale renvoyant "Down"/"Up"/"Spacebar" ne casse pas silencieusement.
    const map = { Down: "ArrowDown", Up: "ArrowUp", Left: "ArrowLeft", Right: "ArrowRight",
                  Spacebar: " ", Esc: "Escape" };
    return map[e.key] || e.key;
  }

  window.addEventListener("keydown", (e) => {
    const s = settings || {};
    const kf = s.keyForward || "ArrowDown";
    const kb = s.keyBackward || "ArrowUp";
    const mode = s.mode || "hold";
    const k = keyName(e);

    // Pédales
    if (k === kf) {
      e.preventDefault();
      if (mode === "hold") { keys.forward = true; }
      else if (!e.repeat) { autoPlay = !autoPlay; }   // impulsion : play/pause (on ignore l'autorepeat)
      updateSpeedTag();
      return;
    }
    if (k === kb) {
      e.preventDefault();
      if (mode === "hold") { keys.backward = true; }
      else if (!e.repeat) { pos = 0; autoPlay = false; }  // impulsion : retour au début (on ignore l'autorepeat)
      updateSpeedTag();
      return;
    }

    // Raccourcis clavier (test / réglage rapide sur le boîtier)
    switch (k) {
      case " ": e.preventDefault(); autoPlay = !autoPlay; updateSpeedTag(); break;
      case "+": case "=": changeSpeed(+10); break;
      case "-": case "_": changeSpeed(-10); break;
      case "r": case "R": pos = 0; autoPlay = false; updateSpeedTag(); break;
      case "m": case "M":
        if (settings) { settings.mirrorH = !settings.mirrorH;
          stage.style.transform = `scale(${settings.mirrorH?-1:1}, ${settings.mirrorV?-1:1})`; }
        break;
      case "f": case "F": toggleFullscreen(); break;
      case "h": case "H": hud.classList.toggle("hidden"); break;
      case "i": case "I": netinfo.classList.toggle("hidden"); break;
    }
  });

  window.addEventListener("keyup", (e) => {
    const s = settings || {};
    const k = keyName(e);
    if (k === (s.keyForward || "ArrowDown"))  { keys.forward = false; updateSpeedTag(); }
    if (k === (s.keyBackward || "ArrowUp"))   { keys.backward = false; updateSpeedTag(); }
  });

  // Sécurité : si l'écran perd le focus (dialogue, bascule plein écran, veille) alors
  // qu'une pédale est enfoncée, le « keyup » n'arrive jamais et le défilement resterait
  // « collé ». On relâche donc les pédales. N'affecte pas l'auto-play (défilement voulu).
  function releasePedals() {
    if (keys.forward || keys.backward) {
      keys.forward = false;
      keys.backward = false;
      updateSpeedTag();
    }
  }
  window.addEventListener("blur", releasePedals);
  window.addEventListener("pagehide", releasePedals);
  document.addEventListener("visibilitychange", () => { if (document.hidden) releasePedals(); });

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.();
    }
  }

  // Toucher l'écran = plein écran (utile en mode kiosque tactile) + montrer l'aide
  window.addEventListener("click", () => { flash(hud); });

  // --- Adresse du boîtier (pour afficher le prompteur depuis un PC/tablette) -
  let netAddresses = [];
  async function loadInfo() {
    try {
      const r = await fetch("/api/info", { cache: "no-store" });
      const info = await r.json();
      netAddresses = info.addresses || [];
      const port = info.port || 5000;
      const primary = netAddresses[0] || "10.42.0.1";
      const url = `http://${primary}:${port}/display`;
      const others = netAddresses.slice(1).map((ip) => `http://${ip}:${port}/display`);
      netinfo.innerHTML =
        'Pour lire sur un <b>PC ou une tablette</b> :<br>' +
        'connecte l\'appareil au WiFi <b>Prompteur</b>, puis ouvre' +
        `<div class="addr">${url}</div>` +
        (others.length ? `<div style="font-size:14px;opacity:.65;margin-top:8px">autres adresses : ${others.join(" · ")}</div>` : "");
      const addrSpan = document.getElementById("emptyAddr");
      if (addrSpan) addrSpan.textContent = url;
    } catch (e) { /* réessai possible plus tard */ }
  }

  // --- Synchronisation avec le serveur (polling) ----------------------------
  async function poll() {
    try {
      // sonde légère : on ne télécharge le texte complet que si quelque chose a changé
      const v = await (await fetch("/api/version", { cache: "no-store" })).json();
      if (v.version === lastVersion && v.cmdSeq === lastCmdSeq) return;

      const state = await (await fetch("/api/state", { cache: "no-store" })).json();

      if (state.version !== lastVersion) {
        lastVersion = state.version;
        applySettings(state.settings, state.text);
      }
      const cmdSeq = state.control ? state.control.cmdSeq : 0;
      if (cmdSeq !== lastCmdSeq) {
        lastCmdSeq = cmdSeq;
        if (state.control && state.control.cmd) applyCommand(state.control.cmd);
      }
    } catch (err) {
      /* le serveur peut redémarrer : on réessaie au prochain tick */
    }
  }

  // Premier chargement immédiat, puis toutes les 300 ms
  poll();
  setInterval(poll, 300);
  requestAnimationFrame(frame);

  // Récupère l'adresse du boîtier et l'affiche au démarrage (12 s), puis la masque.
  // La touche « i » permet de la rappeler à tout moment.
  loadInfo().then(() => {
    netinfo.classList.remove("hidden");
    setTimeout(() => netinfo.classList.add("hidden"), 12000);
  });

  // Masque l'aide après quelques secondes
  setTimeout(() => hud.classList.add("hidden"), 6000);
})();
