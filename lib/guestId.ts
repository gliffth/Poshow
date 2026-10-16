// temporary — should come from verified Telegram initData once that exists (˶˃⤙˂˶)

const STORAGE_KEY = 'terminal-battler-guest-id';

export function getOrCreateGuestUserId(): number {
  if (typeof window === 'undefined') return 0;
  const existing = window.localStorage.getItem(STORAGE_KEY);
  if (existing) return parseInt(existing, 10);

  // Stay under Postgres int4 range and away from real Telegram ID space.
  const id = 100000 + Math.floor(Math.random() * 899999);
  window.localStorage.setItem(STORAGE_KEY, String(id));
  return id;
}
