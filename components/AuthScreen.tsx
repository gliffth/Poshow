"use client";

import { useEffect, useRef, useState } from 'react';
import { Send, UserPlus, LogIn, Loader2, Copy, WifiOff } from 'lucide-react';
import { useGame } from '@/store/GameContext';
import * as api from '@/lib/apiClient';
import { ApiError } from '@/lib/apiClient';
import { sfx } from '@/lib/sound';

type Mode = 'register' | 'login' | 'telegram';

export function AuthScreen() {
  const { actions, serverReachable, serverChecked } = useGame();
  const [mode, setMode] = useState<Mode>('register');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // telegram link login
  const [tg, setTg] = useState<{ code: string; botUrl: string | null; bot: string | null } | null>(null);
  const [tgStatus, setTgStatus] = useState<'idle' | 'starting' | 'waiting' | 'expired'>('idle');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function stopPolling() {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }
  useEffect(() => stopPolling, []);

  async function submit() {
    if (busy) return;
    setError('');
    if (username.trim().length < 3) return setError('Username needs at least 3 characters.');
    if (password.length < 6) return setError('Password needs at least 6 characters.');
    setBusy(true);
    try {
      const res = mode === 'register'
        ? await api.authRegister(username.trim(), password)
        : await api.authLogin(username.trim(), password);
      sfx.coin();
      await actions.login({ token: res.token, userId: res.user_id, username: res.username }, res.needs_starter);
    } catch (err) {
      sfx.error();
      setError(err instanceof ApiError ? err.message : 'Could not reach the server — try again in a moment.');
    } finally {
      setBusy(false);
    }
  }

  async function startTelegram() {
    setError('');
    setTgStatus('starting');
    try {
      const res = await api.telegramStart();
      setTg({ code: res.code, botUrl: res.bot_url, bot: res.bot_username });
      setTgStatus('waiting');
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const r = await api.telegramPoll(res.code);
          if (r.status === 'ok' && r.token && r.user_id) {
            stopPolling();
            sfx.coin();
            await actions.login(
              { token: r.token, userId: r.user_id, username: r.username ?? 'TRAINER' },
              !!r.needs_starter
            );
          } else if (r.status === 'expired') {
            stopPolling();
            setTgStatus('expired');
          }
        } catch {
          // transient network error — keep polling
        }
      }, 2500);
    } catch (err) {
      setTgStatus('idle');
      setError(err instanceof ApiError ? err.message : 'Could not reach the server — try again in a moment.');
    }
  }

  function switchMode(next: Mode) {
    stopPolling();
    setTg(null);
    setTgStatus('idle');
    setError('');
    setMode(next);
  }

  const tabClass = (m: Mode) =>
    `flex-1 py-2 text-xs uppercase tracking-widest border-2 flex items-center justify-center gap-1 ${
      mode === m ? 'bg-retro-green text-retro-bg border-retro-green' : 'border-retro-green/40 hover:border-retro-green'
    }`;

  return (
    <div className="w-full h-full overflow-y-auto flex items-center justify-center p-4 bg-retro-bg text-retro-green">
      <div className="w-full max-w-sm space-y-5">
        <div className="text-center space-y-1">
          <h1 className="font-pixel text-xl leading-relaxed">POSHOW</h1>
          <p className="text-xs uppercase tracking-widest opacity-60">Trainer terminal — sign in to begin</p>
        </div>

        {!serverReachable && (
          <div className="border-2 border-retro-alert/60 bg-retro-alert/10 text-retro-alert p-3 text-xs flex items-start gap-2">
            {serverChecked ? <WifiOff size={16} className="shrink-0 mt-0.5" /> : <Loader2 size={16} className="shrink-0 mt-0.5 animate-spin" />}
            <p>
              {serverChecked
                ? 'Server is waking up — the first connection can take up to a minute. This page keeps retrying by itself.'
                : 'Connecting to the server…'}
            </p>
          </div>
        )}

        <div className="flex gap-2">
          <button className={tabClass('register')} onClick={() => switchMode('register')}><UserPlus size={13} /> New</button>
          <button className={tabClass('login')} onClick={() => switchMode('login')}><LogIn size={13} /> Log in</button>
          <button className={tabClass('telegram')} onClick={() => switchMode('telegram')}><Send size={13} /> Telegram</button>
        </div>

        {mode !== 'telegram' ? (
          <div className="border-2 border-retro-green/40 bg-retro-dark p-4 space-y-3 box-glow">
            <p className="text-xs opacity-70">
              {mode === 'register'
                ? 'Create a guest account with a username and password — no email needed.'
                : 'Welcome back, trainer.'}
            </p>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              autoCapitalize="none"
              autoCorrect="off"
              autoComplete="username"
              maxLength={20}
              className="w-full bg-retro-bg border-2 border-retro-green/40 px-3 py-2 text-sm focus:border-retro-green outline-none"
            />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') submit(); }}
              placeholder="Password"
              type="password"
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              className="w-full bg-retro-bg border-2 border-retro-green/40 px-3 py-2 text-sm focus:border-retro-green outline-none"
            />
            {error && <p className="text-xs text-retro-alert">{error}</p>}
            <button
              onClick={submit}
              disabled={busy}
              className="w-full border-2 border-retro-green py-2 uppercase tracking-widest text-sm hover:bg-retro-green hover:text-retro-bg disabled:opacity-40 flex items-center justify-center gap-2"
            >
              {busy ? <><Loader2 size={14} className="animate-spin" /> {serverReachable ? 'Working…' : 'Waiting for server…'}</> : mode === 'register' ? 'Create account' : 'Log in'}
            </button>
          </div>
        ) : (
          <div className="border-2 border-retro-green/40 bg-retro-dark p-4 space-y-3 box-glow">
            <p className="text-xs opacity-70">
              Use your Telegram trainer. Your team and progress are shared between the bot and this site.
            </p>
            {tgStatus === 'idle' || tgStatus === 'starting' || tgStatus === 'expired' ? (
              <>
                {tgStatus === 'expired' && <p className="text-xs text-retro-alert">That code expired — get a new one.</p>}
                {error && <p className="text-xs text-retro-alert">{error}</p>}
                <button
                  onClick={startTelegram}
                  disabled={tgStatus === 'starting'}
                  className="w-full border-2 border-retro-green py-2 uppercase tracking-widest text-sm hover:bg-retro-green hover:text-retro-bg disabled:opacity-40 flex items-center justify-center gap-2"
                >
                  {tgStatus === 'starting' ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Continue with Telegram
                </button>
              </>
            ) : (
              tg && (
                <div className="space-y-3">
                  <p className="text-xs uppercase tracking-widest opacity-60">Your code</p>
                  <div className="flex items-center justify-between border-2 border-retro-green/50 px-3 py-2">
                    <span className="font-pixel text-sm tracking-widest">{tg.code}</span>
                    <button
                      onClick={() => navigator.clipboard?.writeText(tg.code).catch(() => {})}
                      aria-label="Copy code"
                      className="opacity-70 hover:opacity-100"
                    ><Copy size={14} /></button>
                  </div>
                  {tg.botUrl ? (
                    <a
                      href={tg.botUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="block w-full text-center border-2 border-retro-green bg-retro-green text-retro-bg py-2 uppercase tracking-widest text-sm"
                    >
                      Open the Telegram bot
                    </a>
                  ) : (
                    <p className="text-xs opacity-70">
                      Open the bot in Telegram and send <span className="font-pixel">/weblogin {tg.code}</span>
                    </p>
                  )}
                  <p className="text-xs opacity-60 flex items-center gap-2">
                    <Loader2 size={12} className="animate-spin" /> Waiting for you to confirm in Telegram…
                  </p>
                  <p className="text-[10px] opacity-50">Tip: tap Start in the bot. If the button doesn&apos;t open it, send the /weblogin message above.</p>
                </div>
              )
            )}
          </div>
        )}

        <button
          onClick={() => actions.playOffline()}
          className="w-full text-[11px] uppercase tracking-widest opacity-50 hover:opacity-90 underline underline-offset-4"
        >
          Play offline demo (progress is not saved to the server)
        </button>
      </div>
    </div>
  );
}
