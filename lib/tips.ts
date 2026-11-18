// First-visit tips: which ones the player has already opened. Stored per device.
import { useCallback, useEffect, useState } from 'react';

const KEY = 'poshow:tips';
const EVENT = 'poshow-tips-changed';

function read(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

function write(ids: string[]) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(ids));
  } catch {
    // storage blocked: tips simply show again next time
  }
  window.dispatchEvent(new Event(EVENT));
}

export function resetTips() {
  write([]);
}

export function useSeen(id: string): [boolean, () => void] {
  const [seen, setSeen] = useState(true);
  useEffect(() => {
    const sync = () => setSeen(read().includes(id));
    sync();
    window.addEventListener(EVENT, sync);
    return () => window.removeEventListener(EVENT, sync);
  }, [id]);
  const markSeen = useCallback(() => {
    const ids = read();
    if (!ids.includes(id)) write([...ids, id]);
  }, [id]);
  return [seen, markSeen];
}

// One pulsing tip per screen visit: the first unseen tip claims the visit.
let visitOwner: string | null = null;
export const claimTipVisit = (id: string): boolean => {
  if (visitOwner === null || visitOwner === id) {
    visitOwner = id;
    return true;
  }
  return false;
};
export const releaseTipVisit = (id: string) => {
  if (visitOwner === id) visitOwner = null;
};
export const resetTipVisit = () => {
  visitOwner = null;
};
