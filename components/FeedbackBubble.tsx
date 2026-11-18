"use client";

import { useState } from 'react';
import { Bug, Check, X } from 'lucide-react';
import { submitFeedback, type FeedbackCategory } from '@/lib/apiClient';
import { useGame } from '@/store/GameContext';
import { sfx } from '@/lib/sound';

const MAX = 1000;
const CATEGORIES: { id: FeedbackCategory; label: string }[] = [
  { id: 'bug', label: 'Bug' },
  { id: 'idea', label: 'Idea' },
  { id: 'other', label: 'Other' },
];

/** A small bug-shaped bubble: tap it, say what went wrong, send. Context (theme, screen size) rides along. */
export function FeedbackBubble() {
  const { state } = useGame();
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory>('bug');
  const [message, setMessage] = useState('');
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const [error, setError] = useState('');

  async function send() {
    if (status === 'sending' || message.trim().length < 5) return;
    setStatus('sending');
    setError('');
    try {
      await submitFeedback(category, message.trim(), {
        app: 'web',
        theme: state.settings.theme,
        screen: `${window.innerWidth}x${window.innerHeight}`,
        ua: navigator.userAgent,
      });
      sfx.menuSelect();
      setStatus('sent');
      setMessage('');
    } catch (e) {
      sfx.error();
      setError(e instanceof Error ? e.message : "Couldn't send that — try again.");
      setStatus('error');
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => { setOpen(true); setStatus('idle'); }}
        className="flex items-center gap-2 border border-retro-green/40 rounded-full px-4 py-2 text-sm hover:bg-retro-green hover:text-retro-bg transition-colors"
        aria-label="Report a bug"
      >
        <Bug size={16} /> Report a bug
      </button>
    );
  }

  return (
    <div className="border border-retro-green/40 bg-retro-dark p-3 sm:p-4 space-y-3" role="dialog" aria-label="Report a bug">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 uppercase tracking-wide text-sm"><Bug size={16} /> Report a bug</p>
        <button onClick={() => setOpen(false)} aria-label="Close" className="opacity-70 hover:opacity-100"><X size={16} /></button>
      </div>

      {status === 'sent' ? (
        <p className="flex items-center gap-2 text-sm"><Check size={16} /> Thanks — that reached the developer.</p>
      ) : (
        <>
          <div className="flex gap-2">
            {CATEGORIES.map((c) => (
              <button
                key={c.id}
                onClick={() => setCategory(c.id)}
                className={`px-3 py-1 text-xs uppercase border ${category === c.id ? 'border-retro-green bg-retro-green text-retro-bg' : 'border-retro-green/40'}`}
              >
                {c.label}
              </button>
            ))}
          </div>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value.slice(0, MAX))}
            rows={4}
            placeholder="What happened? What did you expect?"
            className="w-full bg-retro-bg border border-retro-green/40 p-2 text-sm outline-none focus:border-retro-green resize-none"
          />
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs opacity-60">{message.length}/{MAX}</span>
            <button
              onClick={send}
              disabled={status === 'sending' || message.trim().length < 5}
              className="px-4 py-1.5 text-sm uppercase border border-retro-green hover:bg-retro-green hover:text-retro-bg disabled:opacity-40"
            >
              {status === 'sending' ? 'Sending…' : 'Send'}
            </button>
          </div>
          {status === 'error' && <p className="text-xs text-retro-alert">{error}</p>}
        </>
      )}
    </div>
  );
}
