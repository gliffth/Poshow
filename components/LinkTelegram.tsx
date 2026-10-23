"use client";

import { useEffect, useRef, useState } from 'react';
import { Link2, Loader2, Send } from 'lucide-react';
import * as api from '@/lib/apiClient';
import { useGame } from '@/store/GameContext';
import { sfx } from '@/lib/sound';

const WEB_ID_BASE = 1_000_000_000_000;   // web accounts live above this; Telegram ids are far below

type Phase = 'idle' | 'starting' | 'waiting' | 'linked' | 'expired';

/** Settings card: join this web account to your Telegram account so the bot and the site are one player. */
export function LinkTelegram() {
  const { auth, actions } = useGame();
  const [phase, setPhase] = useState<Phase>('idle');
  const [info, setInfo] = useState<{ code: string; botUrl: string | null; command: string } | null>(null);
  const [error, setError] = useState('');
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timer.current) clearInterval(timer.current); }, []);

  if (auth.status !== 'in') return null;
  const isWebAccount = auth.session.userId >= WEB_ID_BASE;

  if (!isWebAccount) {
    return (
      <div className="border border-retro-green/40 bg-retro-dark p-3 sm:p-4">
        <p className="uppercase tracking-wide text-sm flex items-center gap-2"><Send size={16} /> Telegram</p>
        <p className="text-xs opacity-70 mt-1">You&apos;re signed in with Telegram — your team and progress are the same in the bot and on the site.</p>
      </div>
    );
  }

  async function start() {
    setError('');
    setPhase('starting');
    try {
      const res = await api.startTelegramLink();
      setInfo({ code: res.code, botUrl: res.bot_url, command: res.command });
      setPhase('waiting');
      if (timer.current) clearInterval(timer.current);
      timer.current = setInterval(async () => {
        try {
          const r = await api.telegramPoll(res.code);
          if (r.status === 'ok' && r.token && r.user_id) {
            if (timer.current) clearInterval(timer.current);
            sfx.coin();
            setPhase('linked');
            // the player you now are may be the Telegram one: switch the session to whoever the server says
            await actions.login({ token: r.token, userId: r.user_id, username: r.username ?? 'TRAINER' }, !!r.needs_starter);
          } else if (r.status === 'expired') {
            if (timer.current) clearInterval(timer.current);
            setPhase('expired');
          }
        } catch {
          // transient network error — keep polling
        }
      }, 3000);
    } catch (e) {
      setPhase('idle');
      setError(e instanceof Error ? e.message : "Couldn't start linking — try again.");
    }
  }

  return (
    <div className="border border-retro-green/40 bg-retro-dark p-3 sm:p-4 space-y-2">
      <p className="uppercase tracking-wide text-sm flex items-center gap-2"><Link2 size={16} /> Link Telegram</p>
      <p className="text-xs opacity-70">
        Play the same trainer in the bot and on the site. If both already have Pokémon, the bot asks which one to keep
        (the other is archived, not deleted).
      </p>

      {phase === 'linked' ? (
        <p className="text-sm">Linked — Telegram and this site are now the same player.</p>
      ) : phase === 'waiting' && info ? (
        <div className="space-y-2 text-sm">
          {info.botUrl && (
            <a href={info.botUrl} target="_blank" rel="noreferrer" className="inline-block border border-retro-green px-3 py-1.5 uppercase text-xs hover:bg-retro-green hover:text-retro-bg">
              Open the bot
            </a>
          )}
          <p className="text-xs opacity-80">
            Or send <span className="font-pixel text-[11px]">{info.command}</span> to the bot.
          </p>
          <p className="text-xs opacity-60 flex items-center gap-1"><Loader2 size={12} className="animate-spin" /> Waiting for you in Telegram…</p>
        </div>
      ) : (
        <button
          onClick={start}
          disabled={phase === 'starting'}
          className="border border-retro-green px-3 py-1.5 text-xs uppercase hover:bg-retro-green hover:text-retro-bg disabled:opacity-40"
        >
          {phase === 'expired' ? 'Code expired — try again' : phase === 'starting' ? 'Starting…' : 'Link Telegram'}
        </button>
      )}
      {error && <p className="text-xs text-retro-alert">{error}</p>}
    </div>
  );
}
