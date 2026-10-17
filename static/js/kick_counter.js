(function () {
  const root = document.getElementById("kick-counter");
  if (!root) return;

  const STORAGE_KEY = "kickCounterSession";
  const WARNING_SECONDS = 2 * 60 * 60;
  const target = Number(root.dataset.target);
  const el = (name) => root.querySelector(`[data-el="${name}"]`);
  const idleView = root.querySelector('[data-view="idle"]');
  const countingView = root.querySelector('[data-view="counting"]');
  const undoButton = root.querySelector('[data-action="undo"]');
  const saveButton = root.querySelector('[data-action="save"]');
  const dialog = el("dialog");

  // state: {startedAt: ISO, offsets: [seconds], endedAt: ms|null, reason: "goal"|"finish"|null, goalSeen, notes}
  let state = load();
  let ticker = null;
  let wakeLock = null;

  function load() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (saved && typeof saved.startedAt === "string" && Array.isArray(saved.offsets)) return saved;
    } catch (e) {}
    return null;
  }

  function persist() {
    try {
      if (state) localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      else localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
  }

  function elapsedSeconds(until) {
    return Math.max(0, ((until ?? Date.now()) - Date.parse(state.startedAt)) / 1000);
  }

  function format(seconds) {
    const total = Math.floor(seconds);
    const h = Math.floor(total / 3600);
    const mmss = `${String(Math.floor((total % 3600) / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
    return h ? `${h}:${mmss}` : mmss;
  }

  function render() {
    idleView.hidden = !!state;
    countingView.hidden = !state;
    if (!state) return;
    const elapsed = elapsedSeconds(state.endedAt);
    const count = state.offsets.length;
    el("timer").textContent = format(elapsed);
    el("count").textContent = count;
    el("warning").hidden = !(elapsed >= WARNING_SECONDS && count < target);
    undoButton.disabled = count === 0;
  }

  function startTicker() {
    stopTicker();
    ticker = setInterval(render, 1000);
  }

  function stopTicker() {
    clearInterval(ticker);
    ticker = null;
  }

  async function requestWakeLock() {
    try {
      wakeLock = await navigator.wakeLock?.request("screen");
    } catch (e) {
      wakeLock = null;
    }
  }

  function releaseWakeLock() {
    wakeLock?.release().catch(() => {});
    wakeLock = null;
  }

  function openDialog() {
    state.endedAt = state.endedAt ?? Date.now();
    persist();
    stopTicker();
    const count = state.offsets.length;
    const total = format(elapsedSeconds(state.endedAt));
    el("dialog-title").textContent = state.reason === "goal" ? "¡Meta alcanzada!" : "Terminar sesión";
    let summary = `${count} pataditas en ${total}`;
    if (count >= target) summary += ` · meta en ${format(state.offsets[target - 1])}`;
    el("dialog-summary").textContent = summary;
    el("notes").value = state.notes || "";
    el("dialog-error").hidden = true;
    saveButton.disabled = false;
    if (!dialog.open) dialog.showModal();
    render();
  }

  function start() {
    state = { startedAt: new Date().toISOString(), offsets: [], endedAt: null, reason: null, goalSeen: false, notes: "" };
    persist();
    requestWakeLock();
    startTicker();
    render();
  }

  function kick() {
    if (!state || state.endedAt) return;
    state.offsets.push(Math.round(elapsedSeconds() * 10) / 10);
    navigator.vibrate?.(30);
    if (state.offsets.length === target && !state.goalSeen) {
      state.goalSeen = true;
      state.reason = "goal";
      openDialog();
      return;
    }
    persist();
    render();
  }

  function undo() {
    if (!state || !state.offsets.length) return;
    state.offsets.pop();
    if (state.offsets.length < target) state.goalSeen = false;
    persist();
    render();
  }

  function finish() {
    state.reason = "finish";
    openDialog();
  }

  function continueCounting() {
    state.notes = el("notes").value;
    state.endedAt = null;
    state.reason = null;
    persist();
    dialog.close();
    requestWakeLock();
    startTicker();
    render();
  }

  function clear() {
    state = null;
    persist();
    stopTicker();
    releaseWakeLock();
    if (dialog.open) dialog.close();
    render();
  }

  function discard() {
    if (confirm("¿Descartar esta sesión? No se guardará.")) clear();
  }

  async function save() {
    saveButton.disabled = true;
    state.notes = el("notes").value;
    persist();
    try {
      const response = await fetch(root.dataset.saveUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": root.dataset.csrf },
        body: JSON.stringify({
          started_at: state.startedAt,
          duration_seconds: Math.round(elapsedSeconds(state.endedAt)),
          kick_offsets: state.offsets,
          notes: state.notes,
        }),
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || "No se pudo guardar la sesión.");
      }
      clear();
      window.location.reload();
    } catch (error) {
      el("dialog-error").textContent =
        error instanceof TypeError ? "Sin conexión. Intenta de nuevo; la sesión sigue guardada en el teléfono." : error.message;
      el("dialog-error").hidden = false;
      saveButton.disabled = false;
    }
  }

  const actions = { start, kick, undo, finish, continue: continueCounting, save, discard };
  root.addEventListener("click", (event) => {
    const action = event.target.closest("[data-action]")?.dataset.action;
    actions[action]?.();
  });

  // Escape closes a modal dialog natively; treat it as "keep counting" so state stays consistent.
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    continueCounting();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && state && !state.endedAt) {
      requestWakeLock();
      render();
    }
  });

  if (state) {
    if (state.endedAt) {
      openDialog();
    } else {
      requestWakeLock();
      startTicker();
    }
  }
  render();
})();
