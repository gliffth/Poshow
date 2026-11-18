"use client";

import { useCallback, useEffect, useState } from 'react';
import { Check, ChevronUp, Loader2 } from 'lucide-react';
import {
  adminIdeas, adminUpdateIdea, getIdeas, postIdea, voteIdea, ApiError,
  type AdminIdea, type Idea, type IdeaStatus,
} from '@/lib/apiClient';
import { useGame } from '@/store/GameContext';

const STATUSES: { id: IdeaStatus; label: string }[] = [
  { id: 'pending', label: 'Waiting for review' },
  { id: 'under_consideration', label: 'Under consideration' },
  { id: 'planned', label: 'Planned' },
  { id: 'in_development', label: 'In development' },
  { id: 'implemented', label: 'Implemented' },
  { id: 'declined', label: 'Declined' },
  { id: 'archived', label: 'Archived' },
];
const TITLE_MAX = 80;
const BODY_MAX = 600;

const msg = (e: unknown, fallback: string) => (e instanceof ApiError || e instanceof Error ? e.message : fallback);

function StatusSelect({ idea, onChange, disabled }: { idea: { id: number; status: IdeaStatus }; onChange: (s: IdeaStatus) => void; disabled: boolean }) {
  return (
    <select
      value={idea.status}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as IdeaStatus)}
      aria-label="Status"
      className="bg-retro-dark border border-retro-green/50 text-xs px-1 py-0.5 max-w-full"
    >
      {STATUSES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
    </select>
  );
}

export function IdeasTab() {
  const { auth, isAdmin } = useGame();
  const loggedIn = auth.status === 'in';
  const [ideas, setIdeas] = useState<Idea[] | null>(null);
  const [review, setReview] = useState<AdminIdea[]>([]);
  const [canPost, setCanPost] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<number | null>(null);
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await getIdeas();
      setIdeas(r.ideas);
      setCanPost(r.can_post);
      if (isAdmin) setReview((await adminIdeas()).ideas.filter((i) => i.status === 'pending'));
      setError('');
    } catch (e) {
      setError(msg(e, "Couldn't load ideas."));
    }
  }, [isAdmin]);

  useEffect(() => { void load(); }, [load]);

  async function vote(idea: Idea) {
    if (busy !== null) return;
    setBusy(idea.id);
    setError('');
    try {
      const r = await voteIdea(idea.id);
      setIdeas((list) => list?.map((i) => (i.id === idea.id ? { ...i, voted: r.voted, votes: r.votes } : i)) ?? list);
    } catch (e) {
      setError(msg(e, "Couldn't register that vote."));
    } finally {
      setBusy(null);
    }
  }

  async function submit() {
    if (sending || title.trim().length < 6) return;
    setSending(true);
    setError('');
    setSent(false);
    try {
      const r = await postIdea(title.trim(), body.trim());
      setIdeas((list) => [r.idea, ...(list ?? [])]);
      setTitle('');
      setBody('');
      setSent(true);
    } catch (e) {
      setError(msg(e, "Couldn't send that idea."));
    } finally {
      setSending(false);
    }
  }

  async function setStatus(id: number, status: IdeaStatus) {
    setBusy(id);
    setError('');
    try {
      await adminUpdateIdea(id, { status });
      await load();
    } catch (e) {
      setError(msg(e, "Couldn't change that status."));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {error && <p className="border border-retro-alert text-retro-alert p-2 text-sm" role="alert">{error}</p>}

      {isAdmin && review.length > 0 && (
        <section className="border border-retro-green/50 p-2 space-y-2">
          <h3 className="uppercase text-xs tracking-widest opacity-70">Waiting for review</h3>
          {review.map((r) => (
            <div key={r.id} className="text-sm space-y-1">
              <p className="font-bold break-words">{r.title}</p>
              {r.body && <p className="opacity-80 break-words">{r.body}</p>}
              <p className="text-xs opacity-60">from {r.username ?? r.user_id}</p>
              <StatusSelect idea={r} disabled={busy === r.id} onChange={(s) => setStatus(r.id, s)} />
            </div>
          ))}
        </section>
      )}

      {loggedIn && canPost ? (
        <section className="border border-retro-green/50 p-2 space-y-2">
          <h3 className="uppercase text-xs tracking-widest opacity-70">Suggest an idea</h3>
          <input
            value={title}
            maxLength={TITLE_MAX}
            onChange={(e) => { setTitle(e.target.value); setSent(false); }}
            placeholder="A short title"
            aria-label="Idea title"
            className="w-full bg-retro-bg border border-retro-green/50 px-2 py-1 text-sm"
          />
          <textarea
            value={body}
            maxLength={BODY_MAX}
            onChange={(e) => setBody(e.target.value)}
            placeholder="What would it do? (optional)"
            aria-label="Idea description"
            rows={3}
            className="w-full bg-retro-bg border border-retro-green/50 px-2 py-1 text-sm resize-none"
          />
          <div className="flex items-center justify-between gap-2 text-xs opacity-70">
            <span>{title.length}/{TITLE_MAX} · {body.length}/{BODY_MAX}</span>
            <button
              type="button"
              onClick={submit}
              disabled={sending || title.trim().length < 6}
              className="flex items-center gap-1 px-3 py-1 uppercase border border-retro-green opacity-100 hover:bg-retro-green hover:text-retro-bg disabled:opacity-40"
            >
              {sending && <Loader2 size={12} className="animate-spin" />} Send
            </button>
          </div>
          {sent && <p className="flex items-center gap-1 text-sm"><Check size={14} /> Your idea is waiting for review.</p>}
        </section>
      ) : (
        <p className="text-sm opacity-70">Log in to suggest an idea or vote.</p>
      )}

      {ideas === null && !error && <p className="flex items-center gap-2 text-sm opacity-70"><Loader2 size={14} className="animate-spin" /> Loading…</p>}
      {ideas?.length === 0 && <p className="text-sm opacity-70">No ideas yet. Be the first.</p>}

      <ul className="space-y-2">
        {ideas?.map((i) => (
          <li key={i.id} className="border border-retro-green/40 p-2 flex gap-3">
            <button
              type="button"
              onClick={() => vote(i)}
              disabled={!i.votable || !loggedIn || busy !== null}
              aria-label={i.voted ? 'Remove your vote' : 'Vote for this idea'}
              aria-pressed={i.voted}
              className={`shrink-0 w-11 h-12 flex flex-col items-center justify-center border text-xs ${i.voted ? 'bg-retro-green text-retro-bg border-retro-green' : 'border-retro-green/50'} disabled:opacity-40`}
            >
              <ChevronUp size={16} />
              {i.votes}
            </button>
            <div className="min-w-0 flex-1 space-y-1">
              <p className="font-bold text-sm break-words">{i.title}</p>
              {i.body && <p className="text-sm opacity-80 break-words">{i.body}</p>}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs uppercase tracking-wide border border-retro-green/40 px-1.5 py-0.5">{i.status_label}</span>
                {i.mine && <span className="text-xs opacity-60">yours</span>}
                {isAdmin && <StatusSelect idea={i} disabled={busy === i.id} onChange={(s) => setStatus(i.id, s)} />}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
