const KEY_PREFIX = "lp_mission_cache_";

export function cacheMission(teamId, state) {
  try {
    localStorage.setItem(`${KEY_PREFIX}${teamId}`, JSON.stringify({ cached_at: Date.now(), state }));
  } catch {}
}

export function readCachedMission(teamId) {
  try {
    const raw = localStorage.getItem(`${KEY_PREFIX}${teamId}`);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearCachedMission(teamId) {
  localStorage.removeItem(`${KEY_PREFIX}${teamId}`);
}

export function registerServiceWorker() {
  if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/service-worker.js").catch(() => {});
    });
  }
}
