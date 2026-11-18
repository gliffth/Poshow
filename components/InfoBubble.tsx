"use client";

import { useCallback, useEffect, useState } from 'react';
import { Info, Loader2, Pencil, X } from 'lucide-react';
import { getInfo, type InfoContent } from '@/lib/apiClient';
import { useGame } from '@/store/GameContext';
import { IconByName, RichText } from '@/components/RichText';
import { IdeasTab } from '@/components/info/IdeasTab';
import { InfoEditor } from '@/components/info/InfoEditor';

type Tab = 'guide' | 'updates' | 'ideas';
const TABS: { id: Tab; label: string }[] = [
  { id: 'guide', label: 'Guide' },
  { id: 'updates', label: 'Updates' },
  { id: 'ideas', label: 'Ideas' },
];
const KIND_LABEL = { new: 'New', improved: 'Improved', fixed: 'Fixed', known: 'Known' } as const;

let cached: InfoContent | null = null;

/** A quiet corner bubble that opens the guide, the update notes and community ideas. It is never a route. */
export function InfoBubble({ aboveDock = true }: { aboveDock?: boolean }) {
  const { isAdmin, serverReachable } = useGame();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>('guide');
  const [info, setInfo] = useState<InfoContent | null>(cached);
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);

  const load = useCallback(async () => {
    try {
      cached = await getInfo();
      setInfo(cached);
      setError('');
    } catch {
      setError("Couldn't load this right now.");
    }
  }, []);

  useEffect(() => {
    if (serverReachable && !cached) void load();
  }, [serverReachable, load]);

  useEffect(() => {
    if (!open) return;
    void load();
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, load]);

  const repo = info?.links.repo;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Information"
        className={`fixed right-3 z-30 w-10 h-10 rounded-full border border-retro-green/40 bg-retro-dark/60 backdrop-blur-sm flex items-center justify-center opacity-50 hover:opacity-100 focus-visible:opacity-100 transition-opacity ${aboveDock ? 'bottom-[calc(env(safe-area-inset-bottom,0px)+4.5rem)]' : 'bottom-[calc(env(safe-area-inset-bottom,0px)+0.75rem)]'}`}
      >
        <Info size={18} />
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button aria-label="Close information" className="absolute inset-0 bg-black/50 cursor-default" onClick={() => setOpen(false)} />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Information"
            className="relative w-full sm:w-[28rem] h-full bg-retro-dark border-l-2 border-retro-green flex flex-col pt-[env(safe-area-inset-top,0px)] pb-[env(safe-area-inset-bottom,0px)]"
          >
            <div className="flex items-center justify-between gap-2 px-3 py-2 border-b border-retro-green/50">
              <nav className="flex gap-1" aria-label="Information sections">
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    aria-current={tab === t.id ? 'page' : undefined}
                    onClick={() => { setTab(t.id); setEditing(false); }}
                    className={`px-3 py-1 text-xs uppercase border border-retro-green ${tab === t.id ? 'bg-retro-green text-retro-bg' : ''}`}
                  >
                    {t.label}
                  </button>
                ))}
              </nav>
              <div className="flex items-center gap-2">
                {isAdmin && tab !== 'ideas' && info && (
                  <button type="button" onClick={() => setEditing((e) => !e)} aria-pressed={editing} aria-label="Edit"
                    className={`p-1 border border-retro-green/60 ${editing ? 'bg-retro-green text-retro-bg' : ''}`}><Pencil size={14} /></button>
                )}
                <button type="button" onClick={() => setOpen(false)} aria-label="Close" className="p-1 opacity-70 hover:opacity-100"><X size={18} /></button>
              </div>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
              {tab === 'ideas' && <IdeasTab />}
              {tab !== 'ideas' && !info && !error && <p className="flex items-center gap-2 text-sm opacity-70"><Loader2 size={14} className="animate-spin" /> Loading…</p>}
              {tab !== 'ideas' && !info && error && (
                <div className="space-y-2">
                  <p className="text-sm">{error}</p>
                  <button type="button" onClick={load} className="px-3 py-1 text-xs uppercase border border-retro-green hover:bg-retro-green hover:text-retro-bg">Try again</button>
                </div>
              )}
              {tab !== 'ideas' && info && editing && <InfoEditor info={info} onSaved={load} />}

              {tab === 'guide' && info && !editing && info.guide.sections.map((s, i) => (
                <details key={s.id} open={i === 0} className="border border-retro-green/40">
                  <summary className="cursor-pointer px-2 py-2 flex items-center gap-2 uppercase text-sm tracking-wide">
                    <IconByName name={s.icon} size={16} className="shrink-0" /> {s.title}
                  </summary>
                  <div className="px-3 pb-3"><RichText source={s.body} /></div>
                </details>
              ))}

              {tab === 'updates' && info && !editing && (
                <div className="space-y-4">
                  {info.changelog.entries.map((en, i) => (
                    <section key={i} className="space-y-1">
                      <h3 className="uppercase text-sm tracking-wide">{[en.version && `v${en.version}`, en.date, en.title].filter(Boolean).join(' · ')}</h3>
                      <ul className="space-y-1 text-sm">
                        {en.items.map((it, j) => (
                          <li key={j} className="flex gap-2">
                            <span className="shrink-0 w-16 text-xs uppercase opacity-70 pt-0.5">{KIND_LABEL[it.kind]}</span>
                            <span className="min-w-0 break-words">{it.text}</span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  ))}
                  {info.changelog.upcoming.length > 0 && (
                    <section><h3 className="uppercase text-sm tracking-wide mb-1">Coming up</h3>
                      <ul className="list-disc pl-5 text-sm">{info.changelog.upcoming.map((t, i) => <li key={i}>{t}</li>)}</ul></section>
                  )}
                  {info.changelog.known.length > 0 && (
                    <section><h3 className="uppercase text-sm tracking-wide mb-1">Known issues</h3>
                      <ul className="list-disc pl-5 text-sm">{info.changelog.known.map((t, i) => <li key={i}>{t}</li>)}</ul></section>
                  )}
                </div>
              )}
            </div>

            <div className="px-3 py-2 border-t border-retro-green/50 flex items-center justify-between text-xs opacity-70">
              <span>{info ? `Version ${info.version}` : ''}</span>
              {repo && repo.startsWith('https://') && (
                <a href={repo} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">Repository</a>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
