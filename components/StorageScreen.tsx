"use client";

import { useCallback, useEffect, useState } from 'react';
import { getStorage, storageDeposit, storageWithdraw, type StorageMon, type StorageResponse } from '@/lib/apiClient';
import { useGame } from '@/store/GameContext';

/** Team (max 6) and the PC box. Every action is validated by the server; this screen only shows its answer. */
export function StorageScreen({ mode = 'both' }: { mode?: 'team' | 'storage' | 'both' }) {
  const { state, actions, serverAvailable } = useGame();
  const [data, setData] = useState<StorageResponse | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!serverAvailable || !state.guestUserId) return;
    try {
      setError('');
      setData(await getStorage(state.guestUserId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't reach the server.");
    }
  }, [serverAvailable, state.guestUserId]);

  useEffect(() => { void load(); }, [load]);

  async function move(mon: StorageMon, direction: 'deposit' | 'withdraw') {
    if (busyId) return;
    setBusyId(mon.id);
    setMessage('');
    setError('');
    try {
      const fn = direction === 'deposit' ? storageDeposit : storageWithdraw;
      const res = await fn(state.guestUserId, mon.id);
      setData(res);
      setMessage(res.message);
      await actions.refreshRoster();        // keep the party everywhere else in sync with the server
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That did not work.');   // e.g. "Your team is full"
    } finally {
      setBusyId(null);
    }
  }

  if (!serverAvailable) {
    return (
      <div className="w-full max-w-2xl mx-auto p-6 text-center opacity-70">
        The storage box needs a server connection.
      </div>
    );
  }

  const row = (mon: StorageMon, direction: 'deposit' | 'withdraw') => (
    <li key={mon.id} className="flex items-center justify-between gap-2 border border-retro-green/40 p-2">
      <div className="min-w-0">
        <div className="uppercase truncate">{mon.nickname || mon.species_name}</div>
        <div className="text-xs opacity-70">
          LV.{mon.level} · HP {mon.current_hp}/{mon.max_hp}{mon.is_fainted ? ' · FAINTED' : ''}{mon.condition ? ` · ${mon.condition.label}` : ''}
        </div>
      </div>
      <button
        disabled={busyId !== null}
        onClick={() => move(mon, direction)}
        className="shrink-0 px-3 py-1 uppercase text-xs border border-retro-green hover:bg-retro-green hover:text-retro-bg disabled:opacity-40"
      >
        {direction === 'deposit' ? 'Store' : 'To team'}
      </button>
    </li>
  );

  return (
    <div className="w-full max-w-2xl mx-auto p-4 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
      {message && <div className="border border-retro-green p-2 text-sm">{message}</div>}
      {error && (
        <div className="border border-red-500 text-red-400 p-2 text-sm flex justify-between gap-2">
          <span>{error}</span>
          <button className="underline" onClick={() => void load()}>retry</button>
        </div>
      )}
      {mode !== 'storage' && (
        <section>
          <h2 className="uppercase tracking-wide mb-1">Team ({data?.team.length ?? 0}/{data?.team_limit ?? 6})</h2>
          <p className="text-xs opacity-60 mb-2">The Pokémon you take into battle. Store extras to make room.</p>
          <ul className="flex flex-col gap-2">{data?.team.map((m) => row(m, 'deposit'))}</ul>
        </section>
      )}
      {mode !== 'team' && (
        <section>
          <h2 className="uppercase tracking-wide mb-1">Storage ({data?.box.length ?? 0})</h2>
          <p className="text-xs opacity-60 mb-2">Pokémon you own that aren&apos;t on your team.</p>
          {data && data.box.length === 0 && <p className="opacity-60 text-sm">Nothing stored yet.</p>}
          <ul className="flex flex-col gap-2">{data?.box.map((m) => row(m, 'withdraw'))}</ul>
        </section>
      )}
    </div>
  );
}
