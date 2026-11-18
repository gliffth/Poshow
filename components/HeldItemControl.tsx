"use client";

import { useState } from 'react';
import { heldEquip, heldUnequip, HELD_ITEM_LABELS, type ServerPokemon } from '@/lib/apiClient';
import { useGame } from '@/store/GameContext';
import { Hint } from '@/components/Hint';

/** What a Pokémon is holding, and buttons to hold or give back an item. The server decides everything: this only
 *  shows its answer, and it refuses changes during a battle (the message is shown here). */
export function HeldItemControl({ mon, onChanged }: { mon: ServerPokemon; onChanged: () => void }) {
  const { state, actions } = useGame();
  const [choice, setChoice] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // the bag is typed for the known consumables; held items are looked up by name as plain strings
  const inventory = state.inventory as Record<string, number | undefined>;
  const held = mon.held_item ? HELD_ITEM_LABELS[mon.held_item] ?? mon.held_item : null;
  const owned = Object.keys(HELD_ITEM_LABELS).filter((k) => (inventory[k] ?? 0) > 0);

  async function run(action: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      await action();
      await actions.refreshRoster();
      setChoice('');
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "That didn't work.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-1 text-xs flex flex-wrap items-center gap-2">
      <span className="opacity-70">Holding: {held ?? 'nothing'} <Hint term="held-item" /></span>
      {held && (
        <button
          disabled={busy}
          onClick={() => run(() => heldUnequip(state.guestUserId, mon.id))}
          className="underline disabled:opacity-40"
        >
          take back
        </button>
      )}
      {owned.length > 0 && (
        <>
          <select
            aria-label="Item to hold"
            value={choice}
            disabled={busy}
            onChange={(e) => setChoice(e.target.value)}
            className="bg-retro-bg border border-retro-green/60 px-1 py-0.5"
          >
            <option value="">choose an item…</option>
            {owned.map((k) => (
              <option key={k} value={k}>{HELD_ITEM_LABELS[k]} ×{inventory[k]}</option>
            ))}
          </select>
          <button
            disabled={!choice || busy}
            onClick={() => run(() => heldEquip(state.guestUserId, mon.id, choice))}
            className="border border-retro-green px-2 py-0.5 uppercase disabled:opacity-40"
          >
            hold
          </button>
        </>
      )}
      {error && <span className="text-red-400 basis-full">{error}</span>}
    </div>
  );
}
