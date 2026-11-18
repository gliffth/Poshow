"use client";

import { useCallback, useEffect, useState } from 'react';
import { getQuests, type QuestReward, type QuestStatus } from '@/lib/apiClient';
import { useGame } from '@/store/GameContext';
import { Hint } from '@/components/Hint';
import { Tip } from '@/components/Tip';

const ITEM_NAMES: Record<string, string> = {
  potion: 'Potion', superpotion: 'Super Potion', rare_candy: 'Rare Candy', exp_all: 'EXP. All',
};

/** "500 coins, 3 Potion" — what a quest pays. */
export function describeReward(reward: QuestReward): string {
  return Object.entries(reward)
    .map(([k, v]) => (k === 'coins' ? `${v} coins` : `${v} ${ITEM_NAMES[k] ?? k}`))
    .join(', ');
}

/** Finished quests are paid out once, by the player. The server checks every claim. */
export function QuestsScreen() {
  const { state, actions, serverAvailable } = useGame();
  const [quests, setQuests] = useState<QuestStatus[] | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!serverAvailable || !state.guestUserId) return;
    try {
      setError('');
      setQuests((await getQuests(state.guestUserId)).quests);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't reach the server.");
    }
  }, [serverAvailable, state.guestUserId]);

  useEffect(() => { void load(); }, [load]);

  async function claim(q: QuestStatus) {
    if (busy) return;
    setBusy(q.id);
    setMessage('');
    setError('');
    try {
      const res = await actions.recoverable('quest-claim', 'reward', { userId: state.guestUserId, questId: q.id });
      setQuests(res.quests);
      setMessage(res.replayed || !res.granted ? res.message : `${res.message} You got ${describeReward(res.granted as QuestReward)}.`);
      await actions.refreshRoster();          // coins and items are shown elsewhere too
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That did not work.');
    } finally {
      setBusy(null);
    }
  }

  if (!serverAvailable) {
    return <div className="w-full max-w-2xl mx-auto p-6 text-center opacity-70">Quests need a server connection.</div>;
  }

  const section = (title: string, daily: boolean) => (
    <section>
      <h2 className="uppercase tracking-wide mb-2">{title}{daily && <> <Hint term="daily-quest" /></>}</h2>
      <ul className="flex flex-col gap-2">
        {quests?.filter((q) => q.daily === daily).map((q) => {
          const pct = Math.min(100, Math.round((q.progress / q.target) * 100));
          return (
            <li key={q.id} className="border border-retro-green/40 p-2 flex flex-col gap-1">
              <div className="flex items-center justify-between gap-2">
                <span className="uppercase">{q.name}</span>
                <span className="text-xs opacity-70">{q.progress}/{q.target}</span>
              </div>
              <div className="h-2 bg-retro-green/15" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
                <div className="h-2 bg-retro-green" style={{ width: `${pct}%` }} />
              </div>
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="opacity-70">Reward: {describeReward(q.reward)}</span>
                {q.claimed ? (
                  <span className="opacity-60 uppercase">claimed</span>
                ) : (
                  <button
                    disabled={!q.done || busy !== null}
                    onClick={() => claim(q)}
                    className="shrink-0 px-3 py-1 uppercase border border-retro-green hover:bg-retro-green hover:text-retro-bg disabled:opacity-40"
                  >
                    {q.done ? 'claim' : 'in progress'}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );

  return (
    <div className="w-full max-w-2xl mx-auto p-4 flex flex-col gap-5 overflow-y-auto custom-scrollbar">
      <h1 className="uppercase tracking-widest text-center">Quests <Tip id="quest-board" title="Quest board"><p>Finish the goal, then tap Claim to collect the reward.</p></Tip></h1>
      {message && <div className="border border-retro-green p-2 text-sm">{message}</div>}
      {error && (
        <div className="border border-red-500 text-red-400 p-2 text-sm flex justify-between gap-2">
          <span>{error}</span>
          <button className="underline" onClick={() => void load()}>retry</button>
        </div>
      )}
      {!quests && !error && <p className="opacity-60 text-sm">Loading…</p>}
      {quests && section('Today', true)}
      {quests && section('Ongoing', false)}
    </div>
  );
}
