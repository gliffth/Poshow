"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, pvpAction, pvpState, pvpWait, type PvpAction, type PvpMatch, type PvpPoll, type PvpSummary } from '@/lib/apiClient';
import { newRequestId, withRetries } from '@/lib/actionRecovery';

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
const DISMISSED_KEY = 'poshow:pvp-dismissed';
const LONG_POLL_FAILS_BEFORE_FALLBACK = 2;
const FALLBACK_CYCLES = 6;

// A request that never reached the server, or a gateway error: the same request id may be sent again safely.
const retryable = (e: unknown) => e instanceof ApiError && (e.status === undefined || [502, 503, 504].includes(e.status));

function dismissedId(): string | null {
  try { return window.sessionStorage.getItem(DISMISSED_KEY); } catch { return null; }
}

export type PvpLink = 'live' | 'polling';

/**
 * PvP state for the screen that is open. While mounted and visible it holds one long poll: the server answers the
 * moment the match changes. If long polls keep failing it falls back to ordinary polling (4 s in a match, 15 s
 * otherwise) for a while and then tries again. Nothing runs while the tab is hidden or the screen is closed.
 */
export function usePvp(uid: number | null | undefined, enabled: boolean) {
  const [summary, setSummary] = useState<PvpSummary | null>(null);
  const [link, setLink] = useState<PvpLink>('live');
  const [dismissed, setDismissed] = useState<string | null>(null);
  const ref = useRef<PvpSummary | null>(null);
  ref.current = summary;

  useEffect(() => { setDismissed(dismissedId()); }, []);

  const apply = useCallback((res: PvpPoll) => {
    if ('unchanged' in res) {
      setSummary((s) => (s && s.active && res.deadline !== undefined ? { ...s, active: { ...s.active, deadline: res.deadline } } : s));
    } else {
      setSummary(res);
    }
  }, []);

  const refresh = useCallback(async () => {
    if (!uid) return;
    try { apply(await pvpState(uid)); } catch { /* keep what is shown */ }
  }, [uid, apply]);

  useEffect(() => {
    if (!enabled || !uid) return;
    let cancelled = false;
    let fails = 0;
    let fallbackLeft = 0;
    let quick = 0;
    const visible = () => typeof document === 'undefined' || document.visibilityState === 'visible';

    (async () => {
      while (!cancelled) {
        if (!visible()) { await sleep(1000); continue; }
        const cur = ref.current;
        const since = cur?.active?.seq ?? 0;
        const inc = cur?.incoming.length ?? 0;
        const started = Date.now();
        try {
          let res: PvpPoll;
          if (fallbackLeft > 0) {
            fallbackLeft -= 1;
            setLink('polling');
            await sleep(cur?.active?.status === 'active' ? 4000 : 15000);
            if (cancelled) return;
            res = await pvpState(uid, cur?.active?.seq);
          } else {
            res = await pvpWait(uid, since, inc);
            if (fails > 0) setLink('live');
            fails = 0;
          }
          if (cancelled) return;
          apply(res);
          quick = Date.now() - started < 300 ? quick + 1 : 0;
          if (quick >= 3) { await sleep(1000); quick = 0; }
        } catch {
          if (cancelled) return;
          fails += 1;
          if (fails >= LONG_POLL_FAILS_BEFORE_FALLBACK) { fallbackLeft = FALLBACK_CYCLES; fails = 0; setLink('polling'); }
          await sleep(Math.min(8000, 1000 * 2 ** fails));
        }
      }
    })();

    const onVisible = () => { if (visible()) void refresh(); };
    document.addEventListener('visibilitychange', onVisible);
    return () => { cancelled = true; document.removeEventListener('visibilitychange', onVisible); };
  }, [enabled, uid, apply, refresh]);

  // first picture of the screen, before the first long poll returns
  useEffect(() => { if (enabled && uid) void refresh(); }, [enabled, uid, refresh]);

  const dismiss = useCallback((id: string) => {
    try { window.sessionStorage.setItem(DISMISSED_KEY, id); } catch { /* the screen still hides it */ }
    setDismissed(id);
  }, []);

  const active: PvpMatch | null = summary?.active && summary.active.id !== dismissed ? summary.active : null;

  /**
   * Send one action. The request id is made once per click and reused for every retry, so a slow or repeated
   * request can never play a move twice. If the answer never arrives, the saved state is fetched instead.
   */
  const act = useCallback(async (match: PvpMatch, action: PvpAction): Promise<string | null> => {
    if (!uid) return 'Not signed in.';
    const rid = newRequestId();
    try {
      const view = await withRetries(() => pvpAction(uid, match.id, action, match.turn, rid), retryable);
      setSummary((s) => (s ? { ...s, active: view } : s));
      return null;
    } catch (e) {
      if (retryable(e)) {
        await refresh();
        return "Couldn't confirm that move. Showing the latest saved state.";
      }
      await refresh();
      return e instanceof ApiError ? e.message : 'That did not work.';
    }
  }, [uid, refresh]);

  return { summary, active, link, refresh, dismiss, act, setSummary };
}
