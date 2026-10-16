// Interface preferences (not game progress): they live in their own localStorage key so
// "Reset save" and logging out never touch them.
import { useCallback, useEffect, useState } from 'react';

const KEY = 'poshow-ui-prefs-v1';
const EVENT = 'poshow-prefs-changed';

export interface UiPrefs {
  /** CRT flicker, moving scanlines, pulsing dots, boot-text flashes */
  flicker: boolean;
  /** walking cutscenes between locations / on the starter screens */
  cutscenes: boolean;
}

export const DEFAULT_PREFS: UiPrefs = { flicker: true, cutscenes: true };

export function loadPrefs(): UiPrefs {
  if (typeof window === 'undefined') return DEFAULT_PREFS;
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? { ...DEFAULT_PREFS, ...(JSON.parse(raw) as Partial<UiPrefs>) } : DEFAULT_PREFS;
  } catch {
    return DEFAULT_PREFS;
  }
}

export function applyPrefs(p: UiPrefs) {
  if (typeof document === 'undefined') return;
  document.documentElement.classList.toggle('no-flicker', !p.flicker);
}

export function savePrefs(p: UiPrefs) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    // storage unavailable — the choice just won't persist
  }
  applyPrefs(p);
  window.dispatchEvent(new Event(EVENT));
}

export function usePrefs(): [UiPrefs, (patch: Partial<UiPrefs>) => void] {
  const [prefs, setPrefs] = useState<UiPrefs>(DEFAULT_PREFS);
  useEffect(() => {
    const sync = () => setPrefs(loadPrefs());
    sync();
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, []);
  const update = useCallback((patch: Partial<UiPrefs>) => savePrefs({ ...loadPrefs(), ...patch }), []);
  return [prefs, update];
}
