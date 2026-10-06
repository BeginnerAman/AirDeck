/* ================================================================
   AirDeck — Client-Side Touch Engine, WebSocket Client,
              Keyboard Bridge, Clipboard, Media, Camera & Mic
   ================================================================ */

(() => {
  "use strict";

  // ── Tuning Constants ───────────────────────────────────────────
  const LONG_PRESS_MS        = 400;   // ms before right-click fires
  const TAP_MAX_MS           = 200;   // max duration for a tap
  const TAP_MAX_PX           = 3.5;   // max movement for a tap (touch-slop)
  const DOUBLE_TAP_MS        = 300;   // window for double-tap-hold drag
  const TRACKPAD_SCROLL_DIV  = 14;    // 2-finger scroll base divisor
  const STRIP_SCROLL_DIV     = 10;    // strip scroll base divisor
  const RECONNECT_BASE       = 1000;  // ms, doubles each attempt
  const RECONNECT_CAP        = 8000;
  const CAM_FPS              = 15;
  const CAM_QUALITY          = 0.70;
  const MIC_SAMPLE_RATE      = 16000;
  const MIC_BUFFER_SIZE      = 4096;

  // ── Lucide SVG Icon Catalog (For Popups / Toasts) ───────────────
  const LUCIDE_ICONS = {
    volup: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>`,
    voldn: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>`,
    mute: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="22" y1="9" x2="16" y2="15"/><line x1="16" y1="9" x2="22" y2="15"/></svg>`,
    play: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 14 10 5 17 5 3"/><line x1="17" y1="4" x2="17" y2="16"/><line x1="21" y1="4" x2="21" y2="16"/></svg>`,
    seekb: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="19 20 9 12 19 4 19 20"/><line x1="5" y1="19" x2="5" y2="5"/></svg>`,
    seekf: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/></svg>`,
    desktop: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>`,
    appswitch: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>`,
    snip: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/></svg>`,
    closetab: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
    lock: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`,
    copy: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
    paste: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>`,
    cam: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3Z"/><circle cx="12" cy="13" r="3"/></svg>`,
    mic: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/></svg>`,
    keyboard: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="M6 8h.01M10 8h.01M14 8h.01M18 8h.01M8 12h.01M12 12h.01M16 12h.01M7 16h10"/></svg>`,
    mouse: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="2" width="14" height="20" rx="7"/><line x1="12" y1="6" x2="12" y2="10"/></svg>`,
    warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    speaker: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>`,
    shield: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
    check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  };

  // ── Auto-Pairing URL Token Detection ──────────────────────────
  const urlParams = new URLSearchParams(window.location.search);
  const queryToken = urlParams.get("token");
  if (queryToken) {
    localStorage.setItem("airdeck_token", queryToken);
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  // ── DOM References ─────────────────────────────────────────────
  const $ = (id) => document.getElementById(id);
  const statusDot       = $("status-dot");
  const statusText      = $("status-text");
  const statusSecBadge  = $("status-sec-badge");
  const toastEl         = $("toast");
  const toastIconWrap   = $("toast-icon-wrap");
  const toastText       = $("toast-text");
  const trackpad        = $("trackpad");
  const scrollStrip     = $("scroll-strip");
  const scrollThumb     = $("scroll-thumb");
  const btnLeft         = $("btn-left");
  const btnMiddle       = $("btn-middle");
  const btnRight        = $("btn-right");

  // Top Power Tools
  const toolDesktop     = $("tool-desktop");
  const toolSwitch      = $("tool-switch");
  const toolSnip        = $("tool-snip");
  const toolClose       = $("tool-close");
  const toolLock        = $("tool-lock");

  // Lock Confirmation Modal
  const modalOverlay    = $("modal-overlay");
  const modalCancelBtn  = $("modal-cancel-btn");
  const modalConfirmBtn = $("modal-confirm-btn");

  // SSL Certificate Modal Elements
  const certModalOverlay       = $("cert-modal-overlay");
  const certDownloadLink       = $("cert-download-link");
  const certInstantDownloadBtn = $("cert-instant-download-btn");
  const certCopyTextBtn        = $("cert-copy-text-btn");
  const certModalCloseBtn      = $("cert-modal-close-btn");
  const tabBtnAndroid          = $("tab-btn-android");
  const tabBtnIos              = $("tab-btn-ios");
  const tabContentAndroid      = $("tab-content-android");
  const tabContentIos          = $("tab-content-ios");

  // Security PIN Pairing Modal
  const pinModalOverlay = $("pin-modal-overlay");
  const pinInput        = $("pin-input");
  const pinSubmitBtn    = $("pin-submit-btn");
  const pinError        = $("pin-error");

  // Lower Action Chips
  const chipCopy        = $("chip-copy");
  const chipPaste       = $("chip-paste");
  const chipMic         = $("chip-mic");
  const chipSpeaker     = $("chip-speaker");
  const chipCam         = $("chip-cam");
  const camSwitchBtn    = $("cam-switch-btn");

  // Bottom Controls
  const kbdBtn          = $("kbd-btn");
  const kbdInput        = $("kbd-input");
  const mediaPlay       = $("media-play");
  const mediaSeekB      = $("media-seekb");
  const mediaSeekF      = $("media-seekf");
  const volDown         = $("vol-down");
  const volUp           = $("vol-up");
  const mediaMute       = $("media-mute");

  // ════════════════════════════════════════════════════════════════
  //  TOAST NOTIFICATIONS (Pure Lucide SVG Icons)
  // ════════════════════════════════════════════════════════════════

  let toastTimer = null;

  function showToast(text, iconName = null, duration = 2000) {
    if (!toastEl) return;

    if (toastIconWrap) {
      if (iconName && LUCIDE_ICONS[iconName]) {
        toastIconWrap.innerHTML = LUCIDE_ICONS[iconName];
        toastIconWrap.style.display = "inline-flex";
      } else {
        toastIconWrap.innerHTML = "";
        toastIconWrap.style.display = "none";
      }
    }

    if (toastText) {
      toastText.textContent = text;
    }

    toastEl.classList.add("show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.classList.remove("show");
    }, duration);
  }

  function vibrate(ms = 20) {
    if (navigator.vibrate) {
      try { navigator.vibrate(ms); } catch (_) {}
    }
  }

  // ════════════════════════════════════════════════════════════════
  //  SCREEN WAKE LOCK API (Prevents phone screen from sleeping)
  // ════════════════════════════════════════════════════════════════

  let wakeLockSentinel = null;

  async function requestWakeLock() {
    if ("wakeLock" in navigator && navigator.wakeLock.request) {
      try {
        wakeLockSentinel = await navigator.wakeLock.request("screen");
        wakeLockSentinel.addEventListener("release", () => {
          wakeLockSentinel = null;
        });
      } catch (_) {}
    }
  }

  document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState === "visible" && !wakeLockSentinel && isAuthorized) {
      await requestWakeLock();
    }
  });

  // ════════════════════════════════════════════════════════════════
  //  SECURITY PIN MODAL CONTROLLER
  // ════════════════════════════════════════════════════════════════

  function showPinModal(errorMsg = "") {
    if (!pinModalOverlay) return;
    pinModalOverlay.classList.add("show");
    if (pinError) pinError.textContent = errorMsg;
    if (pinInput) {
      pinInput.value = "";
      setTimeout(() => pinInput.focus(), 250);
    }
  }

  function hidePinModal() {
    if (!pinModalOverlay) return;
    pinModalOverlay.classList.remove("show");
    if (pinError) pinError.textContent = "";
  }

  function triggerPinShake() {
    vibrate(45);
    const card = document.querySelector(".pin-card");
    if (card) {
      card.classList.remove("pin-shake");
      void card.offsetWidth;
      card.classList.add("pin-shake");
    }
  }

  let pendingPin = null;

  function submitPin() {
    const val = pinInput ? pinInput.value.trim() : "";
    if (val.length !== 4) {
      if (pinError) pinError.textContent = "Please enter a 4-digit PIN";
      triggerPinShake();
      return;
    }
    vibrate(18);
    if (pinError) pinError.textContent = "Verifying…";

    // If WebSocket is still open, send directly
    if (ws && ws.readyState === WebSocket.OPEN) {
      send({ t: "auth", pin: val });
    } else {
      // WS was closed (e.g. after auth_fail 4401) — reconnect and send PIN on the new connection
      pendingPin = val;
      connect();
    }
  }

  if (pinSubmitBtn) pinSubmitBtn.addEventListener("click", submitPin);
  if (pinInput) {
    pinInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitPin();
    });
    pinInput.addEventListener("input", () => {
      if (pinInput.value.length === 4) {
        submitPin();
      }
    });
  }

  // ════════════════════════════════════════════════════════════════
  //  WEBSOCKET MANAGER (With Zero-Trust Auth Handshake)
  // ════════════════════════════════════════════════════════════════

  let ws = null;
  let isAuthorized = false;
  let reconnectDelay = RECONNECT_BASE;
  let reconnectTimer = null;

  function wsUrl() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${location.host}/ws`;
  }

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      if (obj.t === "auth" || isAuthorized) {
        ws.send(JSON.stringify(obj));
      }
    }
  }

  function sendBinary(buf) {
    if (ws && ws.readyState === WebSocket.OPEN && isAuthorized) {
      ws.send(buf);
    }
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      ws = new WebSocket(wsUrl());
      ws.binaryType = "arraybuffer";
    } catch (e) {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      reconnectDelay = RECONNECT_BASE;
      statusDot.className = "authenticating";
      statusText.textContent = "Securing link…";
      isAuthorized = false;

      // If user just typed a PIN and we reconnected to send it
      if (pendingPin) {
        const pin = pendingPin;
        pendingPin = null;
        send({ t: "auth", pin: pin });
        return;
      }

      // Send auth token if we have one, otherwise prompt for PIN
      const savedToken = localStorage.getItem("airdeck_token");
      if (savedToken) {
        send({ t: "auth", token: savedToken });
      } else {
        statusDot.className = "";
        statusText.textContent = "PIN Required";
        showPinModal();
      }
    };

    ws.onclose = (evt) => {
      isAuthorized = false;
      if (statusSecBadge) statusSecBadge.classList.add("hidden");
      // Don't auto-reconnect or overwrite status on auth rejection (code 4401) — PIN modal is already showing
      if (evt.code === 4401) return;
      statusDot.className = "";
      statusText.textContent = "Reconnecting…";
      scheduleReconnect();
    };

    ws.onerror = () => {
      try { ws.close(); } catch (_) {}
    };

    ws.onmessage = (evt) => {
      if (evt.data instanceof ArrayBuffer) {
        handleBinaryMessage(evt.data);
        return;
      }
      try {
        const msg = JSON.parse(evt.data);

        // Security Handshake Responses
        if (msg.t === "auth_ok") {
          isAuthorized = true;
          if (msg.token) {
            localStorage.setItem("airdeck_token", msg.token);
          }
          if (msg.hardware) {
            updateHardwareStatus(msg.hardware);
          }
          if (msg.telemetry) {
            updateTelemetryUI(msg.telemetry);
          }
          if (msg.macros) {
            renderMacroGrid(msg.macros);
          }
          hidePinModal();
          statusDot.className = "connected";
          if (statusSecBadge) statusSecBadge.classList.remove("hidden");
          fetchServerInfo();
          requestWakeLock();
          return;
        }

        if (msg.t === "hardware_status" && msg.data) {
          updateHardwareStatus(msg.data);
          return;
        }

        if (msg.t === "telemetry" && msg.d) {
          updateTelemetryUI(msg.d);
          return;
        }

        if (msg.t === "macros" && msg.d) {
          renderMacroGrid(msg.d);
          return;
        }

        if (msg.t === "macro_result") {
          if (!msg.ok) {
            showToast(msg.msg || "Macro Failed", "warning", 2000);
          }
          return;
        }

        if (msg.t === "cam_status" && !msg.ok) {
          showToast(msg.msg || "Camera Error", "warning", 2500);
          stopCamera();
          return;
        }

        if (msg.t === "mic_status" && !msg.ok) {
          showToast(msg.msg || "Microphone Error", "warning", 2500);
          stopMic();
          return;
        }

        if (msg.t === "speaker_status" && !msg.ok) {
          showToast(msg.msg || "Speaker Error", "warning", 2500);
          speakerActive = false;
          if (chipSpeaker) chipSpeaker.classList.remove("active");
          return;
        }

        if (msg.t === "auth_fail") {
          isAuthorized = false;
          localStorage.removeItem("airdeck_token");
          statusDot.className = "";
          statusText.textContent = "PIN Required";
          if (statusSecBadge) statusSecBadge.classList.add("hidden");
          showPinModal(msg.reason || "Incorrect PIN. Try again.");
          triggerPinShake();
          return;
        }

        // Clipboard
        if (msg.t === "clip" && typeof msg.d === "string") {
          handleClipboardReceive(msg.d);
        }
      } catch (_) {}
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      reconnectDelay = Math.min(reconnectDelay * 1.8, RECONNECT_CAP);
      connect();
    }, reconnectDelay);
  }

  let serverInfo = null;
  let hardwareStatus = {
    webcam: { available: true },
    microphone: { available: true },
  };

  function updateHardwareStatus(hw) {
    if (!hw) return;
    hardwareStatus = hw;
    if (chipMic) {
      if (hw.microphone && !hw.microphone.available) {
        chipMic.classList.add("driver-missing");
        chipMic.title = "Install VB-Audio Cable for Virtual Mic";
      } else {
        chipMic.classList.remove("driver-missing");
        chipMic.title = "Virtual Mic for Zoom / Meet / Discord";
      }
    }
    if (chipCam) {
      if (hw.webcam && !hw.webcam.available) {
        chipCam.classList.add("driver-missing");
        chipCam.title = "Virtual Camera not found on PC";
      } else {
        chipCam.classList.remove("driver-missing");
        chipCam.title = "Toggle HD Webcam";
      }
    }
  }

  async function fetchServerInfo() {
    try {
      const res = await fetch("/api/info");
      if (res.ok) {
        serverInfo = await res.json();
        if (serverInfo.hardware) {
          updateHardwareStatus(serverInfo.hardware);
        }
        if (serverInfo && serverInfo.hostname) {
          statusText.textContent = `${serverInfo.hostname}`;
          showToast(`Connected: ${serverInfo.hostname}`, "lock", 1800);
          return;
        }
      }
    } catch (_) {}
    statusText.textContent = "Connected & Secured";
    showToast("Laptop Paired & Secured", "lock", 1800);
  }

  const statusBarEl = $("status-bar");
  if (statusBarEl) {
    statusBarEl.addEventListener("click", () => {
      if (isAuthorized && serverInfo) {
        showToast(`${serverInfo.hostname} (${serverInfo.ip}:${serverInfo.port})`, "desktop", 2200);
      }
    });
  }

  // ════════════════════════════════════════════════════════════════
  //  TOP POWER TOOLS & LOCK MODAL
  // ════════════════════════════════════════════════════════════════

  function setupTool(btn, action, label, icon) {
    if (!btn) return;
    btn.addEventListener("click", () => {
      vibrate(20);
      send({ t: "action", a: action });
      showToast(label, icon, 1400);
    });
  }

  setupTool(toolDesktop, "desktop",   "Desktop",       "desktop");
  setupTool(toolSwitch,  "appswitch", "Alt + Tab",     "appswitch");
  setupTool(toolSnip,    "snip",      "Snipping Tool", "snip");
  setupTool(toolClose,   "closetab",  "Tab Closed",    "closetab");

  // Lock Modal Handling (Confirmation Dialog to prevent accidental locks)
  if (toolLock) {
    toolLock.addEventListener("click", () => {
      vibrate(20);
      if (modalOverlay) {
        modalOverlay.classList.add("show");
      }
    });
  }

  if (modalCancelBtn) {
    modalCancelBtn.addEventListener("click", () => {
      vibrate(10);
      if (modalOverlay) {
        modalOverlay.classList.remove("show");
      }
    });
  }

  if (modalOverlay) {
    modalOverlay.addEventListener("click", (e) => {
      if (e.target === modalOverlay) {
        modalOverlay.classList.remove("show");
      }
    });
  }

  if (modalConfirmBtn) {
    modalConfirmBtn.addEventListener("click", () => {
      vibrate(35);
      send({ t: "action", a: "lock" });
      if (modalOverlay) {
        modalOverlay.classList.remove("show");
      }
      showToast("PC Locked", "lock", 2000);
    });
  }

  // ════════════════════════════════════════════════════════════════
  //  TRACKPAD — Touch State Machine
  // ════════════════════════════════════════════════════════════════

  const State = Object.freeze({
    IDLE:       0,
    TRACKING:   1,
    MOVING:     2,
    DRAGGING:   3,
    SCROLLING:  4,
    RIGHT_HELD: 5,
  });

  let state           = State.IDLE;
  let startX          = 0, startY = 0;
  let lastX           = 0, lastY  = 0;
  let startTime       = 0;
  let lastTapTime     = 0;
  let lastTapWasClick = false;
  let rightClickTimer = null;
  let activeTouchId   = null;

  // ── High-Frequency 120Hz Touch Engine & Adaptive Micro-Filter ──
  let accumX = 0, accumY = 0;
  let lastMoveSendTime = 0;
  let moveTrailingTimer = null;
  let smoothFilterX = 0, smoothFilterY = 0;
  const MOVE_INTERVAL_MS = 8; // 125Hz high-frequency rate limit to match 120Hz mobile digitizers

  function filterDelta(rawDx, rawDy) {
    const speed = Math.hypot(rawDx, rawDy);
    // At high speed (> 4px/touch tick): alpha = 1.0 -> 1:1 raw bypass (ZERO latency on flicks)
    // At slow speed (< 1.5px/touch tick): alpha ~0.72 -> silky smooth micro-jitter suppression
    const alpha = Math.min(1.0, Math.max(0.70, speed / 4.0));
    smoothFilterX = alpha * rawDx + (1.0 - alpha) * smoothFilterX;
    smoothFilterY = alpha * rawDy + (1.0 - alpha) * smoothFilterY;
    return [smoothFilterX, smoothFilterY];
  }

  function flushMove() {
    if (moveTrailingTimer) {
      clearTimeout(moveTrailingTimer);
      moveTrailingTimer = null;
    }
    if (accumX !== 0 || accumY !== 0) {
      const sx = Math.round(accumX * 100) / 100;
      const sy = Math.round(accumY * 100) / 100;
      if (sx !== 0 || sy !== 0) {
        send({ t: "move", x: sx, y: sy });
      }
      accumX = 0;
      accumY = 0;
      lastMoveSendTime = performance.now();
    }
  }

  function queueMove(dx, dy) {
    const [fdx, fdy] = filterDelta(dx, dy);
    accumX += fdx;
    accumY += fdy;

    const now = performance.now();
    // Immediate / High-Frequency Dispatch: If 8ms has passed, send IMMEDIATELY!
    if (now - lastMoveSendTime >= MOVE_INTERVAL_MS) {
      flushMove();
    } else if (!moveTrailingTimer) {
      // Schedule trailing packet so remaining micro-movements are never dropped
      const delay = Math.max(1, MOVE_INTERVAL_MS - (now - lastMoveSendTime));
      moveTrailingTimer = setTimeout(flushMove, delay);
    }
  }

  function cancelRightClick() {
    if (rightClickTimer) {
      clearTimeout(rightClickTimer);
      rightClickTimer = null;
    }
  }

  trackpad.addEventListener("touchstart", (e) => {
    e.preventDefault();
    const touches = e.touches;

    // Reset smoothing and timing on new touch
    smoothFilterX = 0;
    smoothFilterY = 0;
    lastMoveSendTime = 0;

    if (touches.length >= 2) {
      cancelRightClick();
      activeTouchId = null;
      state = State.SCROLLING;
      lastX = (touches[0].clientX + touches[1].clientX) / 2;
      lastY = (touches[0].clientY + touches[1].clientY) / 2;
      trackpadScrollAccumX = 0;
      trackpadScrollAccumY = 0;
      twoFingerLastTime = performance.now();
      return;
    }

    const t = touches[0];
    activeTouchId = t.identifier;
    startX = lastX = t.clientX;
    startY = lastY = t.clientY;
    startTime = Date.now();

    const sinceLastTap = startTime - lastTapTime;

    if (lastTapWasClick && sinceLastTap < DOUBLE_TAP_MS) {
      cancelRightClick();
      state = State.DRAGGING;
      vibrate(25);
      send({ t: "mdown", b: "left" });
    } else {
      lastTapWasClick = false;
      state = State.TRACKING;
      rightClickTimer = setTimeout(() => {
        if (state !== State.TRACKING) return;
        state = State.RIGHT_HELD;
        vibrate(35);
        send({ t: "click", b: "right" });
        showToast("Right Click", "mouse", 1000);
      }, LONG_PRESS_MS);
    }
  }, { passive: false });

  trackpad.addEventListener("touchmove", (e) => {
    e.preventDefault();
    const touches = e.touches;

    // Two-finger scroll with adaptive acceleration
    if (state === State.SCROLLING && touches.length >= 2) {
      const mx = (touches[0].clientX + touches[1].clientX) / 2;
      const my = (touches[0].clientY + touches[1].clientY) / 2;
      const now = performance.now();
      const dt = Math.max(1, now - twoFingerLastTime);
      twoFingerLastTime = now;
      handleAdaptiveTwoFingerScroll(mx - lastX, my - lastY, dt);
      lastX = mx;
      lastY = my;
      return;
    }

    if (touches.length < 1) return;

    // Find the tracked finger by identifier to prevent multi-finger jumping
    let t = null;
    for (let i = 0; i < touches.length; i++) {
      if (touches[i].identifier === activeTouchId) {
        t = touches[i];
        break;
      }
    }
    if (!t) {
      t = touches[0];
      activeTouchId = t.identifier;
      startX = lastX = t.clientX;
      startY = lastY = t.clientY;
      return;
    }

    const dx = t.clientX - lastX;
    const dy = t.clientY - lastY;

    if (state === State.TRACKING) {
      const totalDx = Math.abs(t.clientX - startX);
      const totalDy = Math.abs(t.clientY - startY);
      if (totalDx > TAP_MAX_PX || totalDy > TAP_MAX_PX) {
        cancelRightClick();
        state = State.MOVING;
        // CRITICAL ZERO-JUMP FIX: Anchor lastX and lastY right here!
        // Prevents the initial deadzone distance from leaking as a 15px sudden leap!
        lastX = t.clientX;
        lastY = t.clientY;
        smoothFilterX = 0;
        smoothFilterY = 0;
        return;
      } else {
        return;
      }
    }

    if (state === State.MOVING || state === State.DRAGGING) {
      lastX = t.clientX;
      lastY = t.clientY;
      queueMove(dx, dy);
    }
  }, { passive: false });

  trackpad.addEventListener("touchend", (e) => {
    e.preventDefault();

    // Flush any pending sub-pixel moves immediately and signal end of move session
    flushMove();
    smoothFilterX = 0;
    smoothFilterY = 0;
    send({ t: "move_end" });

    // Check if tracked finger lifted
    let endedActive = false;
    for (let i = 0; i < e.changedTouches.length; i++) {
      if (e.changedTouches[i].identifier === activeTouchId) {
        endedActive = true;
        break;
      }
    }
    if (endedActive || e.touches.length === 0) {
      activeTouchId = null;
    }

    if (state === State.TRACKING) {
      cancelRightClick();
      const elapsed = Date.now() - startTime;
      if (elapsed < TAP_MAX_MS) {
        vibrate(15);
        send({ t: "click", b: "left" });
        lastTapTime = Date.now();
        lastTapWasClick = true;
      } else {
        lastTapWasClick = false;
      }
      state = State.IDLE;
    } else if (state === State.MOVING) {
      lastTapWasClick = false;
      state = State.IDLE;
    } else if (state === State.DRAGGING) {
      send({ t: "mup", b: "left" });
      lastTapWasClick = false;
      state = State.IDLE;
      lastTapTime = 0;
    } else if (state === State.SCROLLING) {
      lastTapWasClick = false;
      if (e.touches.length === 0) state = State.IDLE;
    } else if (state === State.RIGHT_HELD) {
      lastTapWasClick = false;
      state = State.IDLE;
    }
  }, { passive: false });

  trackpad.addEventListener("touchcancel", (e) => {
    cancelRightClick();
    flushMove();
    smoothFilterX = 0;
    smoothFilterY = 0;
    activeTouchId = null;
    lastTapWasClick = false;
    send({ t: "move_end" });
    if (state === State.DRAGGING) send({ t: "mup", b: "left" });
    state = State.IDLE;
  });

  // ── Adaptive Two-Finger Trackpad Scroll ──
  let trackpadScrollAccumX = 0, trackpadScrollAccumY = 0;
  let trackpadScrollRaf = null;
  let twoFingerLastTime = 0;

  function handleAdaptiveTwoFingerScroll(dx, dy, dt) {
    // Calculate velocity in px/ms
    const speedY = Math.abs(dy) / dt;
    // Adaptive velocity curve: slow swipe is gentle; fast swipe accelerates 1.5x - 3.5x
    const velocityMultiplier = Math.max(1.0, Math.min(3.5, 1.0 + speedY * 1.8));

    trackpadScrollAccumX += dx;
    trackpadScrollAccumY += dy * velocityMultiplier;

    if (!trackpadScrollRaf) {
      trackpadScrollRaf = requestAnimationFrame(flushTrackpadScroll);
    }
  }

  function flushTrackpadScroll() {
    const clicksX = Math.trunc(trackpadScrollAccumX / TRACKPAD_SCROLL_DIV);
    const clicksY = Math.trunc(trackpadScrollAccumY / TRACKPAD_SCROLL_DIV);
    if (clicksX || clicksY) {
      send({ t: "scroll", x: clicksX, y: clicksY });
      trackpadScrollAccumX -= clicksX * TRACKPAD_SCROLL_DIV;
      trackpadScrollAccumY -= clicksY * TRACKPAD_SCROLL_DIV;
    }
    trackpadScrollRaf = null;
  }

  // ════════════════════════════════════════════════════════════════
  //  ADAPTIVE VELOCITY SCROLL STRIP (Physical Mouse Wheel Feel)
  // ════════════════════════════════════════════════════════════════

  let stripLastY = 0;
  let stripLastTime = 0;
  let stripAccumY = 0;
  let stripRaf = null;

  function flushStripScroll() {
    const notches = Math.trunc(stripAccumY / STRIP_SCROLL_DIV);
    if (notches !== 0) {
      // Send true wheel notches. Server scales with WHEEL_DELTA (120) on Windows.
      send({ t: "scroll", x: 0, y: notches });
      stripAccumY -= notches * STRIP_SCROLL_DIV;
    }
    stripRaf = null;
  }

  scrollStrip.addEventListener("touchstart", (e) => {
    e.preventDefault();
    stripLastY = e.touches[0].clientY;
    stripLastTime = performance.now();
    stripAccumY = 0;
    vibrate(10);
  }, { passive: false });

  scrollStrip.addEventListener("touchmove", (e) => {
    e.preventDefault();
    const y = e.touches[0].clientY;
    const now = performance.now();
    const dy = y - stripLastY;
    const dt = Math.max(1, now - stripLastTime);
    stripLastY = y;
    stripLastTime = now;

    // Velocity in px/ms
    const velocity = Math.abs(dy) / dt;

    // True Adaptive Acceleration Curve:
    // - Dragging slow (<0.2 px/ms) -> fine precision (factor ~1.2)
    // - Normal drag (0.2 - 0.8 px/ms) -> natural browsing (factor ~2.5 to 4.5)
    // - Fast flick (>0.8 px/ms) -> rapid power scroll (factor up to 8.5)
    let accelFactor = 1.2;
    if (velocity > 0.2) {
      accelFactor = Math.min(8.5, 1.2 + Math.pow(velocity * 2.2, 1.4));
    }

    // Drag down (dy > 0) -> scroll document down (negative notches)
    const effectiveDelta = -Math.sign(dy) * Math.abs(dy) * accelFactor;
    stripAccumY += effectiveDelta;

    // Visual scroll-thumb feedback
    if (scrollThumb) {
      const rect = scrollStrip.getBoundingClientRect();
      const pct = Math.max(5, Math.min(65, ((y - rect.top) / rect.height) * 100));
      scrollThumb.style.top = `${pct}%`;
    }

    if (!stripRaf) {
      stripRaf = requestAnimationFrame(flushStripScroll);
    }
  }, { passive: false });

  scrollStrip.addEventListener("touchend", (e) => {
    e.preventDefault();
    if (scrollThumb) scrollThumb.style.top = "35%";
  }, { passive: false });

  // ════════════════════════════════════════════════════════════════
  //  BOTTOM MOUSE BUTTONS
  // ════════════════════════════════════════════════════════════════

  function setupMouseBtn(el, button) {
    el.addEventListener("touchstart", (e) => {
      e.preventDefault();
      vibrate(15);
      send({ t: "click", b: button });
    }, { passive: false });
  }

  setupMouseBtn(btnLeft,   "left");
  setupMouseBtn(btnMiddle, "middle");
  setupMouseBtn(btnRight,  "right");

  // ════════════════════════════════════════════════════════════════
  //  TACTILE VOLUME CONTROLS (Vol - / Vol + / Mute with Lucide SVGs)
  // ════════════════════════════════════════════════════════════════

  let volInterval = null;

  function bindVolumeButton(btn, action, label, icon) {
    if (!btn) return;

    function triggerVol() {
      vibrate(12);
      send({ t: "media", a: action });
      showToast(label, icon, 700);
    }

    btn.addEventListener("touchstart", (e) => {
      e.preventDefault();
      triggerVol();
      volInterval = setInterval(triggerVol, 110);
    }, { passive: false });

    btn.addEventListener("touchend", (e) => {
      e.preventDefault();
      if (volInterval) {
        clearInterval(volInterval);
        volInterval = null;
      }
    }, { passive: false });

    btn.addEventListener("touchcancel", () => {
      if (volInterval) {
        clearInterval(volInterval);
        volInterval = null;
      }
    });
  }

  bindVolumeButton(volDown, "voldn", "Volume -", "voldn");
  bindVolumeButton(volUp,   "volup", "Volume +", "volup");

  // Mute toggle with Lucide SVG popup
  let isMuted = false;
  mediaMute.addEventListener("click", () => {
    isMuted = !isMuted;
    mediaMute.dataset.state = isMuted ? "muted" : "unmuted";
    vibrate(18);
    send({ t: "media", a: "mute" });
    showToast(isMuted ? "Muted" : "Unmuted", isMuted ? "mute" : "volup", 1100);
  });

  // ════════════════════════════════════════════════════════════════
  //  MEDIA CONTROLS (Seek & Play/Pause with Lucide SVGs)
  // ════════════════════════════════════════════════════════════════

  mediaPlay.addEventListener("click", () => {
    vibrate(20);
    send({ t: "media", a: "play" });
    showToast("Play / Pause", "play", 1100);
  });

  mediaSeekB.addEventListener("click", () => {
    vibrate(15);
    send({ t: "media", a: "seekb" });
    showToast("-10 Seconds", "seekb", 1000);
  });

  mediaSeekF.addEventListener("click", () => {
    vibrate(15);
    send({ t: "media", a: "seekf" });
    showToast("+10 Seconds", "seekf", 1000);
  });

  // ════════════════════════════════════════════════════════════════
  //  KEYBOARD BRIDGE & VOICE TYPING
  // ════════════════════════════════════════════════════════════════

  let kbdActive = false;
  let isComposing = false;

  kbdBtn.addEventListener("click", () => {
    kbdActive = !kbdActive;
    kbdBtn.classList.toggle("active", kbdActive);
    vibrate(15);
    if (kbdActive) {
      kbdInput.focus();
      showToast("Native Keyboard Active", "keyboard", 1500);
    } else {
      kbdInput.blur();
    }
  });

  kbdInput.addEventListener("compositionstart", () => {
    isComposing = true;
  });

  kbdInput.addEventListener("compositionend", () => {
    isComposing = false;
    const text = kbdInput.value;
    if (text) {
      send({ t: "key", d: text });
      kbdInput.value = "";
    }
  });

  kbdInput.addEventListener("input", () => {
    if (isComposing) return;
    const text = kbdInput.value;
    if (text) {
      send({ t: "key", d: text });
      kbdInput.value = "";
    }
  });

  kbdInput.addEventListener("keydown", (e) => {
    const special = [
      "Backspace", "Enter", "Tab", "Escape", "Delete",
      "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
      "Home", "End", "PageUp", "PageDown",
    ];
    if (special.includes(e.key)) {
      e.preventDefault();
      send({ t: "skey", k: e.key });
    }
  });

  kbdInput.addEventListener("blur", () => {
    if (kbdActive) {
      setTimeout(() => {
        if (kbdActive) kbdInput.focus();
      }, 300);
    }
  });

  // ════════════════════════════════════════════════════════════════
  //  ACTION CHIPS (Thumb Zone: Copy, Paste, Mic, Cam)
  // ════════════════════════════════════════════════════════════════

  let clipboardBuffer = "";

  chipCopy.addEventListener("click", () => {
    vibrate(20);
    send({ t: "hotkey", k: ["mod", "c"] });
    setTimeout(() => send({ t: "clipget" }), 150);
  });

  let pasteTimer = null;
  let pasteLongFired = false;

  chipPaste.addEventListener("touchstart", (e) => {
    e.preventDefault();
    pasteLongFired = false;
    pasteTimer = setTimeout(async () => {
      pasteLongFired = true;
      vibrate(35);
      try {
        if (navigator.clipboard && navigator.clipboard.readText) {
          const text = await navigator.clipboard.readText();
          if (text) {
            send({ t: "clipset", d: text });
            showToast("Clipboard Sent to PC", "paste", 1500);
          }
        }
      } catch (_) {
        showToast("Clipboard Denied", "warning", 1500);
      }
    }, LONG_PRESS_MS);
  }, { passive: false });

  chipPaste.addEventListener("touchend", (e) => {
    e.preventDefault();
    if (pasteTimer) {
      clearTimeout(pasteTimer);
      pasteTimer = null;
    }
    if (!pasteLongFired) {
      vibrate(15);
      send({ t: "hotkey", k: ["mod", "v"] });
      showToast("Pasted (Ctrl+V)", "paste", 1200);
    }
  }, { passive: false });

  chipPaste.addEventListener("touchcancel", () => {
    if (pasteTimer) { clearTimeout(pasteTimer); pasteTimer = null; }
  });

  function handleClipboardReceive(text) {
    clipboardBuffer = text;
    const preview = text.length > 20 ? text.slice(0, 20) + "…" : text;
    showToast(`Copied: "${preview}"`, "copy", 1800);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).catch(() => {});
      }
    } catch (_) {}
  }

  // ════════════════════════════════════════════════════════════════
  //  WEBCAM STREAMING (Independent Toggle)
  // ════════════════════════════════════════════════════════════════

  let camActive = false;
  let camStream = null;
  let camVideo = document.createElement("video");
  let camCanvas = document.createElement("canvas");
  let camCtx = camCanvas.getContext("2d");
  let camInterval = null;
  let facingMode = "environment";

  chipCam.addEventListener("click", async () => {
    if (hardwareStatus.webcam && !hardwareStatus.webcam.available) {
      vibrate(40);
      showToast("Virtual Camera Driver Missing on PC", "warning", 2500);
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showToast("Camera Not Supported on Phone", "warning");
      return;
    }

    camActive = !camActive;
    chipCam.classList.toggle("active", camActive);
    camSwitchBtn.classList.toggle("visible", camActive);
    vibrate(20);

    if (camActive) {
      await startCamera();
    } else {
      stopCamera();
    }
  });

  camSwitchBtn.addEventListener("click", async () => {
    facingMode = facingMode === "environment" ? "user" : "environment";
    vibrate(15);
    if (camActive) {
      stopCamera();
      await startCamera();
    }
  });

  async function startCamera() {
    try {
      send({ t: "cam_start" });
      camStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode, width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      camVideo.srcObject = camStream;
      camVideo.setAttribute("playsinline", "true");
      await camVideo.play();

      camCanvas.width = camVideo.videoWidth || 1280;
      camCanvas.height = camVideo.videoHeight || 720;
      showToast("HD Webcam Live", "cam", 1600);

      camInterval = setInterval(() => {
        if (!camStream || camVideo.readyState < 2) return;
        camCtx.drawImage(camVideo, 0, 0, camCanvas.width, camCanvas.height);
        camCanvas.toBlob(
          (blob) => {
            if (!blob) return;
            blob.arrayBuffer().then((buf) => {
              const frame = new Uint8Array(buf.byteLength + 1);
              frame[0] = 0x01; // webcam marker
              frame.set(new Uint8Array(buf), 1);
              sendBinary(frame.buffer);
            });
          },
          "image/jpeg",
          CAM_QUALITY,
        );
      }, 1000 / CAM_FPS);
    } catch (err) {
      console.error("[CAM] getUserMedia error:", err);
      showToast("Camera Access Denied", "warning");
      camActive = false;
      chipCam.classList.remove("active");
      camSwitchBtn.classList.remove("visible");
      send({ t: "cam_stop" });
    }
  }

  function stopCamera() {
    send({ t: "cam_stop" });
    if (camInterval) {
      clearInterval(camInterval);
      camInterval = null;
    }
    if (camStream) {
      camStream.getTracks().forEach((t) => t.stop());
      camStream = null;
    }
    camVideo.srcObject = null;
    showToast("Webcam Stopped", "cam", 1200);
  }

  // ════════════════════════════════════════════════════════════════
  //  MICROPHONE STREAMING (Independent Toggle with PC Driver Check)
  // ════════════════════════════════════════════════════════════════

  let micActive = false;
  let micStream = null;
  let micContext = null;
  let micProcessor = null;

  chipMic.addEventListener("click", async () => {
    if (hardwareStatus.microphone && !hardwareStatus.microphone.available) {
      vibrate(40);
      showToast("Install VB-Audio Cable for Virtual Mic", "warning", 3000);
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      showToast("Microphone Not Supported on Phone", "warning");
      return;
    }

    micActive = !micActive;
    chipMic.classList.toggle("active", micActive);
    vibrate(20);

    if (micActive) {
      await startMic();
    } else {
      stopMic();
    }
  });

  async function startMic() {
    try {
      send({ t: "mic_start" });
      micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: MIC_SAMPLE_RATE,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      micContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: MIC_SAMPLE_RATE,
      });
      const source = micContext.createMediaStreamSource(micStream);

      let workletLoaded = false;
      if (micContext.audioWorklet && micContext.audioWorklet.addModule) {
        try {
          await micContext.audioWorklet.addModule("/static/mic-processor.js");
          micProcessor = new AudioWorkletNode(micContext, "airdeck-mic-processor");
          micProcessor.port.onmessage = (e) => {
            if (!ws || ws.readyState !== WebSocket.OPEN) return;
            const int16Buffer = e.data;
            const payload = new Uint8Array(int16Buffer.byteLength + 1);
            payload[0] = 0x02; // mic marker
            payload.set(new Uint8Array(int16Buffer), 1);
            sendBinary(payload.buffer);
          };
          source.connect(micProcessor);
          workletLoaded = true;
        } catch (_) {}
      }

      // Graceful fallback to ScriptProcessor if AudioWorklet failed
      if (!workletLoaded) {
        micProcessor = micContext.createScriptProcessor(MIC_BUFFER_SIZE, 1, 1);
        micProcessor.onaudioprocess = (e) => {
          if (!ws || ws.readyState !== WebSocket.OPEN) return;
          const float32 = e.inputBuffer.getChannelData(0);
          const int16 = new Int16Array(float32.length);
          for (let i = 0; i < float32.length; i++) {
            const s = Math.max(-1, Math.min(1, float32[i]));
            int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          const payload = new Uint8Array(int16.buffer.byteLength + 1);
          payload[0] = 0x02; // mic marker
          payload.set(new Uint8Array(int16.buffer), 1);
          sendBinary(payload.buffer);
        };
        const muteNode = micContext.createGain();
        muteNode.gain.value = 0; // Completely silence local speaker playback to eliminate echo
        source.connect(micProcessor);
        micProcessor.connect(muteNode);
        muteNode.connect(micContext.destination);
      }

      showToast("Virtual Mic Live — Use as Mic in Zoom/Meet", "mic", 2200);
    } catch (err) {
      console.error("[MIC] getUserMedia error:", err);
      showToast("Mic Access Denied", "warning");
      micActive = false;
      chipMic.classList.remove("active");
      send({ t: "mic_stop" });
    }
  }

  function stopMic() {
    send({ t: "mic_stop" });
    if (micProcessor) {
      try { micProcessor.disconnect(); } catch (_) {}
      micProcessor = null;
    }
    if (micContext) {
      micContext.close().catch(() => {});
      micContext = null;
    }
    if (micStream) {
      micStream.getTracks().forEach((t) => t.stop());
      micStream = null;
    }
    micActive = false;
    chipMic.classList.remove("active");
    showToast("Microphone Stopped", "mic", 1200);
  }

  // ════════════════════════════════════════════════════════════════
  //  PC-TO-PHONE WIRELESS EXTENDED SPEAKER (WASAPI Loopback Player)
  // ════════════════════════════════════════════════════════════════

  let speakerActive = false;
  let speakerAudioCtx = null;
  let speakerNextPlayTime = 0;

  if (chipSpeaker) {
    chipSpeaker.addEventListener("click", async () => {
      vibrate(20);
      speakerActive = !speakerActive;
      chipSpeaker.classList.toggle("active", speakerActive);

      if (speakerActive) {
        try {
          if (!speakerAudioCtx) {
            speakerAudioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
          }
          if (speakerAudioCtx.state === "suspended") {
            await speakerAudioCtx.resume();
          }
          speakerNextPlayTime = speakerAudioCtx.currentTime;
          send({ t: "speaker_start" });
          showToast("Wireless Speaker Live (Laptop ➔ Phone)", "speaker", 2200);
        } catch (e) {
          showToast("Could not start audio context", "warning");
          speakerActive = false;
          chipSpeaker.classList.remove("active");
        }
      } else {
        send({ t: "speaker_stop" });
        showToast("Wireless Speaker Stopped", "speaker", 1500);
      }
    });
  }

  function handleBinaryMessage(buffer) {
    const bytes = new Uint8Array(buffer);
    const marker = bytes[0];

    // Marker 0x03 = Wireless Extended Speaker (PC WASAPI Loopback 16-bit Stereo PCM @ 48kHz)
    if (marker === 0x03 && speakerActive) {
      playSpeakerChunk(buffer.slice(1));
    }
  }

  function playSpeakerChunk(rawPcmBuffer) {
    if (!speakerAudioCtx || !speakerActive) return;

    if (speakerAudioCtx.state === "suspended") {
      speakerAudioCtx.resume();
    }

    const int16 = new Int16Array(rawPcmBuffer);
    const numFrames = Math.floor(int16.length / 2); // Stereo: 2 channels
    if (numFrames <= 0) return;

    try {
      const audioBuf = speakerAudioCtx.createBuffer(2, numFrames, 48000);
      const leftCh = audioBuf.getChannelData(0);
      const rightCh = audioBuf.getChannelData(1);

      for (let i = 0; i < numFrames; i++) {
        leftCh[i] = int16[i * 2] / 32768.0;
        rightCh[i] = int16[i * 2 + 1] / 32768.0;
      }

      const src = speakerAudioCtx.createBufferSource();
      src.buffer = audioBuf;
      src.connect(speakerAudioCtx.destination);

      const currentTime = speakerAudioCtx.currentTime;
      if (speakerNextPlayTime < currentTime) {
        speakerNextPlayTime = currentTime + 0.025; // 25ms low-latency jitter buffer
      }

      src.start(speakerNextPlayTime);
      speakerNextPlayTime += audioBuf.duration;
    } catch (_) {}
  }

  // ════════════════════════════════════════════════════════════════
  //  SSL CERTIFICATE IN-MEMORY BLOB DOWNLOAD & INSTALL GUIDE MODAL
  // ════════════════════════════════════════════════════════════════

  if (certDownloadLink) {
    certDownloadLink.addEventListener("click", (e) => {
      e.preventDefault();
      vibrate(15);
      if (certModalOverlay) certModalOverlay.classList.add("show");
    });
  }

  if (certModalCloseBtn) {
    certModalCloseBtn.addEventListener("click", () => {
      vibrate(15);
      if (certModalOverlay) certModalOverlay.classList.remove("show");
    });
  }

  if (certModalOverlay) {
    certModalOverlay.addEventListener("click", (e) => {
      if (e.target === certModalOverlay) {
        certModalOverlay.classList.remove("show");
      }
    });
  }

  if (certInstantDownloadBtn) {
    certInstantDownloadBtn.addEventListener("click", async () => {
      vibrate(25);
      try {
        showToast("Generating certificate…", "shield", 1200);
        // Fetch via in-page secure session (bypasses Android DownloadManager TLS rejection)
        const res = await fetch("/api/cert/download");
        if (!res.ok) throw new Error("HTTP " + res.status);
        const certBlob = await res.blob();
        const blobUrl = URL.createObjectURL(certBlob);
        const a = document.createElement("a");
        a.href = blobUrl;
        a.download = "airdeck_cert.crt";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(blobUrl), 4000);
        showToast("Certificate Saved to Downloads!", "check", 2800);
      } catch (err) {
        showToast("Download failed: " + err.message, "warning", 3000);
      }
    });
  }

  if (certCopyTextBtn) {
    certCopyTextBtn.addEventListener("click", async () => {
      vibrate(20);
      try {
        const res = await fetch("/api/cert/download");
        const text = await res.text();
        await navigator.clipboard.writeText(text);
        showToast("Certificate PEM copied to clipboard!", "check", 2200);
      } catch (e) {
        showToast("Could not copy certificate", "warning");
      }
    });
  }

  if (tabBtnAndroid && tabBtnIos) {
    tabBtnAndroid.addEventListener("click", () => {
      tabBtnAndroid.classList.add("active");
      tabBtnIos.classList.remove("active");
      if (tabContentAndroid) tabContentAndroid.classList.remove("hidden");
      if (tabContentIos) tabContentIos.classList.add("hidden");
    });
    tabBtnIos.addEventListener("click", () => {
      tabBtnIos.classList.add("active");
      tabBtnAndroid.classList.remove("active");
      if (tabContentIos) tabContentIos.classList.remove("hidden");
      if (tabContentAndroid) tabContentAndroid.classList.add("hidden");
    });
  }

  // ════════════════════════════════════════════════════════════════
  //  MULTI-DECK PROFILE MANAGER (Trackpad, Stream Deck, Numpad, Presenter)
  // ════════════════════════════════════════════════════════════════

  let telemetryPollTimer = null;

  function updateTelemetryUI(telem) {
    if (!telem || !telem.available) return;

    const cpuVal = $("telem-cpu-val");
    const cpuFill = $("telem-cpu-fill");
    if (cpuVal) cpuVal.textContent = `${telem.cpu_percent}%`;
    if (cpuFill) {
      cpuFill.style.width = `${Math.min(100, telem.cpu_percent)}%`;
      cpuFill.style.background = telem.cpu_percent > 85 ? "#ef4444" : (telem.cpu_percent > 60 ? "#f59e0b" : "#6C63FF");
    }

    const ramVal = $("telem-ram-val");
    const ramFill = $("telem-ram-fill");
    if (ramVal) ramVal.textContent = `${telem.ram_percent}%`;
    if (ramFill) {
      ramFill.style.width = `${Math.min(100, telem.ram_percent)}%`;
      ramFill.style.background = telem.ram_percent > 85 ? "#ef4444" : (telem.ram_percent > 70 ? "#f59e0b" : "#3b82f6");
    }

    const battVal = $("telem-batt-val");
    const battFill = $("telem-batt-fill");
    if (battVal && telem.battery) {
      const bPct = telem.battery.percent;
      battVal.textContent = `${bPct}%${telem.battery.power_plugged ? '⚡' : ''}`;
      if (battFill) {
        battFill.style.width = `${Math.min(100, bPct)}%`;
        battFill.style.background = bPct < 20 ? "#ef4444" : "#22c55e";
      }
    }
  }

  // ── Dynamic Stream Deck Macro Grid ──
  const macroGrid = $("macro-grid");
  let activeMacros = [];

  function getMacroIconSvg(iconName) {
    const iconSvgs = {
      activity: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
      folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/></svg>',
      terminal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>',
      settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
      globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
      micoff: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="2" y1="2" x2="22" y2="22"/><path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2"/><path d="M5 10v2a7 7 0 0 0 12 5"/><line x1="12" y1="19" x2="12" y2="22"/></svg>',
      maximize: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>',
      scissors: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><line x1="20" y1="4" x2="8.12" y2="15.88"/><line x1="14.47" y1="14.48" x2="20" y2="20"/><line x1="8.12" y1="8.12" x2="12" y2="12"/></svg>',
      switch: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>',
      monitor: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>',
      calculator: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="8" y1="10" x2="8.01" y2="10"/><line x1="12" y1="10" x2="12.01" y2="10"/><line x1="16" y1="10" x2="16.01" y2="10"/><line x1="8" y1="14" x2="8.01" y2="14"/><line x1="12" y1="14" x2="12.01" y2="14"/><line x1="16" y1="14" x2="16.01" y2="14"/><line x1="8" y1="18" x2="8.01" y2="18"/><line x1="12" y1="18" x2="12.01" y2="18"/><line x1="16" y1="18" x2="16.01" y2="18"/></svg>',
      filetext: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
      x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
      lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
    };
    return iconSvgs[iconName] || iconSvgs.activity;
  }

  function renderMacroGrid(macrosList) {
    if (!macroGrid) return;
    activeMacros = macrosList || [];
    macroGrid.innerHTML = "";

    activeMacros.forEach((m) => {
      const card = document.createElement("button");
      card.className = "macro-card" + (m.confirm ? " danger-card" : "");
      card.dataset.id = m.id;

      const iconWrap = document.createElement("div");
      iconWrap.className = "macro-icon";
      if (m.color) iconWrap.style.color = m.color;
      iconWrap.innerHTML = getMacroIconSvg(m.icon);

      const label = document.createElement("span");
      label.className = "macro-label";
      label.textContent = m.label;

      card.appendChild(iconWrap);
      card.appendChild(label);

      card.addEventListener("click", () => {
        vibrate(20);
        if (m.confirm) {
          if (modalOverlay) modalOverlay.classList.add("show");
        } else {
          send({ t: "macro", id: m.id });
          showToast(m.label, null, 1100);
        }
      });

      macroGrid.appendChild(card);
    });
  }

  const tabButtons = document.querySelectorAll(".tab-btn");
  const deckPanes  = document.querySelectorAll(".deck-pane");

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const deck = btn.dataset.deck;
      if (!deck) return;

      tabButtons.forEach((b) => b.classList.toggle("active", b === btn));
      deckPanes.forEach((p) => p.classList.toggle("active", p.id === `deck-${deck}`));
      vibrate(14);

      if (deck === "macro") {
        send({ t: "get_telemetry" });
        if (!telemetryPollTimer) {
          telemetryPollTimer = setInterval(() => send({ t: "get_telemetry" }), 2500);
        }
      } else {
        if (telemetryPollTimer) {
          clearInterval(telemetryPollTimer);
          telemetryPollTimer = null;
        }
      }

      const deckNames = {
        trackpad: "Trackpad & Remote",
        macro: "Macro Stream Deck",
        numpad: "Tactile Numpad",
        presenter: "Presenter Remote",
      };
      showToast(deckNames[deck] || "Deck Switched", null, 900);
    });
  });

  // ── Macro Creation & Reset Actions ──
  const macroModalOverlay = $("macro-modal-overlay");
  const macroAddBtn = $("macro-add-btn");
  const macroCancelBtn = $("macro-cancel-btn");
  const macroSaveBtn = $("macro-save-btn");
  const macroResetBtn = $("macro-reset-btn");

  if (macroAddBtn && macroModalOverlay) {
    macroAddBtn.addEventListener("click", () => {
      vibrate(15);
      macroModalOverlay.classList.add("show");
    });
  }

  if (macroCancelBtn && macroModalOverlay) {
    macroCancelBtn.addEventListener("click", () => {
      vibrate(10);
      macroModalOverlay.classList.remove("show");
    });
  }

  // ── Authenticated HTTP Fetch Helper ──
  async function authFetch(url, options = {}) {
    const token = localStorage.getItem("airdeck_token");
    options.headers = options.headers || {};
    if (token) {
      if (options.headers instanceof Headers) {
        options.headers.set("Authorization", `Bearer ${token}`);
      } else {
        options.headers["Authorization"] = `Bearer ${token}`;
      }
    }
    return fetch(url, options);
  }

  if (macroSaveBtn) {
    macroSaveBtn.addEventListener("click", async () => {
      const lbl = $("macro-input-label")?.value.trim();
      const typ = $("macro-input-type")?.value;
      const tgt = $("macro-input-target")?.value.trim();
      if (!lbl || !tgt) {
        showToast("Enter label & target", "warning", 1800);
        return;
      }
      try {
        const res = await authFetch("/api/macros", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ label: lbl, type: typ, target: tgt, icon: "activity" })
        });
        if (res.ok) {
          showToast(`Macro '${lbl}' Created!`, null, 1500);
          if (macroModalOverlay) macroModalOverlay.classList.remove("show");
          send({ t: "get_macros" });
        } else {
          showToast("Unauthorized / Failed", "warning", 1800);
        }
      } catch (_) {}
    });
  }

  if (macroResetBtn) {
    macroResetBtn.addEventListener("click", async () => {
      vibrate(25);
      try {
        const res = await authFetch("/api/macros/reset", { method: "POST" });
        if (res.ok) {
          showToast("Macros Reset to Default", null, 1500);
          send({ t: "get_macros" });
        } else {
          showToast("Unauthorized / Failed", "warning", 1800);
        }
      } catch (_) {}
    });
  }

  // ── Deck 3: Numpad Listeners ──
  document.querySelectorAll(".num-key[data-key]").forEach((keyEl) => {
    keyEl.addEventListener("touchstart", (e) => {
      e.preventDefault();
      vibrate(12);
      send({ t: "key", d: keyEl.dataset.key });
    }, { passive: false });
  });

  document.querySelectorAll(".num-key[data-skey]").forEach((keyEl) => {
    keyEl.addEventListener("touchstart", (e) => {
      e.preventDefault();
      vibrate(15);
      send({ t: "skey", k: keyEl.dataset.skey });
    }, { passive: false });
  });

  // ── Deck 4: Presenter Deck Listeners ──
  const presPrevBtn = $("pres-prev-btn");
  const presNextBtn = $("pres-next-btn");

  if (presPrevBtn) {
    presPrevBtn.addEventListener("click", () => {
      vibrate(20);
      send({ t: "action", a: "slide_prev" });
      showToast("Previous Slide", "seekb", 1000);
    });
  }

  if (presNextBtn) {
    presNextBtn.addEventListener("click", () => {
      vibrate(20);
      send({ t: "action", a: "slide_next" });
      showToast("Next Slide", "seekf", 1000);
    });
  }

  document.querySelectorAll(".pres-tool-card[data-action]").forEach((card) => {
    card.addEventListener("click", () => {
      vibrate(18);
      send({ t: "action", a: card.dataset.action });
      const txt = card.querySelector("span")?.textContent || "Tool";
      showToast(txt, null, 1000);
    });
  });

  // ── Live Presentation Stopwatch ──
  let presSeconds = 0;
  let presTimerInterval = null;
  const presTimerDisplay = $("pres-timer-display");
  const presTimerToggle  = $("pres-timer-toggle");
  const presTimerReset   = $("pres-timer-reset");

  function formatTimer(s) {
    const mins = String(Math.floor(s / 60)).padStart(2, "0");
    const secs = String(s % 60).padStart(2, "0");
    return `${mins}:${secs}`;
  }

  if (presTimerToggle) {
    presTimerToggle.addEventListener("click", () => {
      vibrate(15);
      if (presTimerInterval) {
        clearInterval(presTimerInterval);
        presTimerInterval = null;
        presTimerToggle.textContent = "Resume";
        presTimerToggle.classList.add("sec");
      } else {
        presTimerInterval = setInterval(() => {
          presSeconds++;
          if (presTimerDisplay) presTimerDisplay.textContent = formatTimer(presSeconds);
        }, 1000);
        presTimerToggle.textContent = "Pause";
        presTimerToggle.classList.remove("sec");
      }
    });
  }

  if (presTimerReset) {
    presTimerReset.addEventListener("click", () => {
      vibrate(15);
      if (presTimerInterval) {
        clearInterval(presTimerInterval);
        presTimerInterval = null;
      }
      presSeconds = 0;
      if (presTimerDisplay) presTimerDisplay.textContent = "00:00";
      if (presTimerToggle) {
        presTimerToggle.textContent = "Start";
        presTimerToggle.classList.remove("sec");
      }
    });
  }

  // ── PWA Service Worker Registration ──
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
  }

  // ════════════════════════════════════════════════════════════════
  //  INIT
  // ════════════════════════════════════════════════════════════════

  connect();

  document.addEventListener("touchmove", (e) => {
    if (e.target.closest("#trackpad, #scroll-strip, .numpad-grid")) {
      e.preventDefault();
    }
  }, { passive: false });

})();
