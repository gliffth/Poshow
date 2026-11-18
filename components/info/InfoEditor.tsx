"use client";

import { useState } from 'react';
import { ArrowDown, ArrowUp, Loader2, Plus, Trash2 } from 'lucide-react';
import {
  putInfo, resetInfo, ApiError,
  type InfoChangelog, type InfoContent, type InfoGuide, type InfoKey, type InfoLinks,
} from '@/lib/apiClient';
import { RICH_ICONS } from '@/lib/richText';
import { RichText } from '@/components/RichText';

const KINDS = ['new', 'improved', 'fixed', 'known'] as const;
const field = 'w-full bg-retro-bg border border-retro-green/50 px-2 py-1 text-sm';
const smallBtn = 'px-2 py-1 text-xs uppercase border border-retro-green/60 hover:bg-retro-green hover:text-retro-bg disabled:opacity-40';

function move<T>(list: T[], i: number, d: number): T[] {
  const j = i + d;
  if (j < 0 || j >= list.length) return list;
  const next = [...list];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

export function InfoEditor({ info, onSaved }: { info: InfoContent; onSaved: () => Promise<void> }) {
  const [key, setKey] = useState<InfoKey>('guide');
  const [guide, setGuide] = useState<InfoGuide>(() => structuredClone(info.guide));
  const [log, setLog] = useState<InfoChangelog>(() => structuredClone(info.changelog));
  const [links, setLinks] = useState<InfoLinks>(() => ({ ...info.links }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError('');
    setSaved(false);
    try {
      await fn();
      await onSaved();
      setSaved(true);
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : 'That did not save.');
    } finally {
      setBusy(false);
    }
  }

  const save = () => run(() => putInfo(key, key === 'guide' ? guide : key === 'changelog' ? log : links));
  const reset = () => run(async () => { await resetInfo(key); });

  const lines = (v: string[]) => v.join('\n');
  const toLines = (t: string) => t.split('\n');

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {(['guide', 'changelog', 'links'] as InfoKey[]).map((k) => (
          <button key={k} type="button" onClick={() => { setKey(k); setError(''); setSaved(false); }}
            className={`${smallBtn} ${key === k ? 'bg-retro-green text-retro-bg' : ''}`}>{k}</button>
        ))}
      </div>

      {key === 'guide' && (
        <div className="space-y-3">
          {guide.sections.map((s, i) => (
            <div key={i} className="border border-retro-green/40 p-2 space-y-2">
              <div className="flex gap-2">
                <input value={s.title} maxLength={80} aria-label="Section title" className={field}
                  onChange={(e) => setGuide({ sections: guide.sections.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)) })} />
                <select value={s.icon} aria-label="Icon" className="bg-retro-dark border border-retro-green/50 text-xs"
                  onChange={(e) => setGuide({ sections: guide.sections.map((x, j) => (j === i ? { ...x, icon: e.target.value } : x)) })}>
                  {RICH_ICONS.map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
              <textarea value={s.body} rows={5} maxLength={4000} aria-label="Section text" className={`${field} resize-y`}
                onChange={(e) => setGuide({ sections: guide.sections.map((x, j) => (j === i ? { ...x, body: e.target.value } : x)) })} />
              <div className="border-t border-retro-green/30 pt-2"><RichText source={s.body} /></div>
              <div className="flex gap-2">
                <button type="button" aria-label="Move up" className={smallBtn} onClick={() => setGuide({ sections: move(guide.sections, i, -1) })}><ArrowUp size={12} /></button>
                <button type="button" aria-label="Move down" className={smallBtn} onClick={() => setGuide({ sections: move(guide.sections, i, 1) })}><ArrowDown size={12} /></button>
                <button type="button" aria-label="Remove section" className={smallBtn} onClick={() => setGuide({ sections: guide.sections.filter((_, j) => j !== i) })}><Trash2 size={12} /></button>
              </div>
            </div>
          ))}
          <button type="button" className={smallBtn} disabled={guide.sections.length >= 30}
            onClick={() => setGuide({ sections: [...guide.sections, { id: '', title: 'New section', icon: 'book', body: '' }] })}>
            <Plus size={12} className="inline" /> Add section
          </button>
        </div>
      )}

      {key === 'changelog' && (
        <div className="space-y-3">
          <label className="block text-xs uppercase opacity-70">Version
            <input value={log.version} maxLength={20} className={field} onChange={(e) => setLog({ ...log, version: e.target.value })} />
          </label>
          {log.entries.map((en, i) => (
            <div key={i} className="border border-retro-green/40 p-2 space-y-2">
              <div className="flex gap-2">
                <input value={en.version} maxLength={20} placeholder="Version" aria-label="Entry version" className={field}
                  onChange={(e) => setLog({ ...log, entries: log.entries.map((x, j) => (j === i ? { ...x, version: e.target.value } : x)) })} />
                <input value={en.date} maxLength={20} placeholder="Date" aria-label="Entry date" className={field}
                  onChange={(e) => setLog({ ...log, entries: log.entries.map((x, j) => (j === i ? { ...x, date: e.target.value } : x)) })} />
              </div>
              <input value={en.title} maxLength={80} placeholder="Title" aria-label="Entry title" className={field}
                onChange={(e) => setLog({ ...log, entries: log.entries.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)) })} />
              {en.items.map((it, k) => (
                <div key={k} className="flex gap-2">
                  <select value={it.kind} aria-label="Kind" className="bg-retro-dark border border-retro-green/50 text-xs"
                    onChange={(e) => setLog({ ...log, entries: log.entries.map((x, j) => (j === i ? { ...x, items: x.items.map((y, m) => (m === k ? { ...y, kind: e.target.value as typeof KINDS[number] } : y)) } : x)) })}>
                    {KINDS.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                  <input value={it.text} maxLength={300} aria-label="Item text" className={field}
                    onChange={(e) => setLog({ ...log, entries: log.entries.map((x, j) => (j === i ? { ...x, items: x.items.map((y, m) => (m === k ? { ...y, text: e.target.value } : y)) } : x)) })} />
                  <button type="button" aria-label="Remove item" className={smallBtn}
                    onClick={() => setLog({ ...log, entries: log.entries.map((x, j) => (j === i ? { ...x, items: x.items.filter((_, m) => m !== k) } : x)) })}><Trash2 size={12} /></button>
                </div>
              ))}
              <div className="flex gap-2">
                <button type="button" className={smallBtn} onClick={() => setLog({ ...log, entries: log.entries.map((x, j) => (j === i ? { ...x, items: [...x.items, { kind: 'new', text: '' }] } : x)) })}>
                  <Plus size={12} className="inline" /> Item
                </button>
                <button type="button" aria-label="Move up" className={smallBtn} onClick={() => setLog({ ...log, entries: move(log.entries, i, -1) })}><ArrowUp size={12} /></button>
                <button type="button" aria-label="Move down" className={smallBtn} onClick={() => setLog({ ...log, entries: move(log.entries, i, 1) })}><ArrowDown size={12} /></button>
                <button type="button" aria-label="Remove entry" className={smallBtn} onClick={() => setLog({ ...log, entries: log.entries.filter((_, j) => j !== i) })}><Trash2 size={12} /></button>
              </div>
            </div>
          ))}
          <button type="button" className={smallBtn} disabled={log.entries.length >= 50}
            onClick={() => setLog({ ...log, entries: [{ version: log.version, date: '', title: '', items: [] }, ...log.entries] })}>
            <Plus size={12} className="inline" /> Add entry
          </button>
          <label className="block text-xs uppercase opacity-70">Coming up (one per line)
            <textarea rows={3} value={lines(log.upcoming)} className={field} onChange={(e) => setLog({ ...log, upcoming: toLines(e.target.value) })} />
          </label>
          <label className="block text-xs uppercase opacity-70">Known issues (one per line)
            <textarea rows={3} value={lines(log.known)} className={field} onChange={(e) => setLog({ ...log, known: toLines(e.target.value) })} />
          </label>
        </div>
      )}

      {key === 'links' && (
        <label className="block text-xs uppercase opacity-70">Repository link (https, empty to hide)
          <input value={links.repo} maxLength={300} className={field} onChange={(e) => setLinks({ repo: e.target.value })} />
        </label>
      )}

      {error && <p role="alert" className="border border-retro-alert text-retro-alert p-2 text-sm">{error}</p>}
      {saved && <p className="text-sm">Saved.</p>}
      <div className="flex gap-2">
        <button type="button" onClick={save} disabled={busy} className={`${smallBtn} flex items-center gap-1`}>
          {busy && <Loader2 size={12} className="animate-spin" />} Save
        </button>
        <button type="button" onClick={reset} disabled={busy} className={smallBtn}>Reset to default</button>
      </div>
    </div>
  );
}
