// Login session — the token + who it belongs to. Lives in its own localStorage key so
// "Reset save" in Settings (which wipes game progress cache) never logs you out by accident.

const KEY = 'poshow-auth-v1';

export interface AuthSession {
  token: string;
  userId: number;
  username: string;
}

export function loadAuth(): AuthSession | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as AuthSession;
    return s && s.token && typeof s.userId === 'number' ? s : null;
  } catch {
    return null;
  }
}

export function saveAuth(session: AuthSession) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    // storage unavailable — the session just won't survive a reload
  }
}

export function clearAuth() {
  if (typeof window === 'undefined') return;
  window.localStorage.removeItem(KEY);
}

export function getToken(): string | null {
  return loadAuth()?.token ?? null;
}
