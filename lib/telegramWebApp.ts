// Telegram Mini App bridge. Outside Telegram none of this exists and every helper returns null / does nothing.

interface TelegramWebApp {
  initData?: string;
  ready?: () => void;
  expand?: () => void;
}

function webApp(): TelegramWebApp | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as { Telegram?: { WebApp?: TelegramWebApp } };
  return w.Telegram?.WebApp ?? null;
}

/** The signed initData string Telegram gives a Mini App, or null when not running inside Telegram. */
export function getTelegramInitData(): string | null {
  const data = webApp()?.initData;
  return data ? data : null;
}

export function readyTelegramApp() {
  const app = webApp();
  app?.ready?.();
  app?.expand?.();
}
