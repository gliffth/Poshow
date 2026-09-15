"use client";

import { useEffect } from 'react';
import { useGame } from '@/store/GameContext';

// syncs data-theme onto <html> — flashes weathered briefly before a saved cream/paper choice kicks in post-hydration ⤙•
export function ThemeSync() {
  const { state } = useGame();

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', state.settings.theme);
  }, [state.settings.theme]);

  return null;
}
