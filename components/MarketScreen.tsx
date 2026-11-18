"use client";

import { useCallback, useEffect, useState } from 'react';
import {
  getStorage, marketBrowse, marketCancel, marketMine,
  type MarketListing, type ServerPokemon,
} from '@/lib/apiClient';
import type { ReactNode } from 'react';
import { useGame } from '@/store/GameContext';
import { Tip } from '@/components/Tip';

type Tab = 'browse' | 'mine' | 'sell';

function when(expires: number): string {
  return new Date(expires * 1000).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' });
}

/** Buy and sell Pokémon for coins. Every purchase, listing and cancellation is checked and saved by the server. */
export function MarketScreen() {
  const { state, actions, serverAvailable } = useGame();
  const [tab, setTab] = useState<Tab>('browse');
  const [browse, setBrowse] = useState<MarketListing[]>([]);
  const [mine, setMine] = useState<MarketListing[]>([]);
  const [sellable, setSellable] = useState<ServerPokemon[]>([]);
  const [pickId, setPickId] = useState('');
  const [price, setPrice] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!serverAvailable || !state.guestUserId) return;
    try {
      setError('');
      const [b, m, s] = await Promise.all([marketBrowse(), marketMine(state.guestUserId), getStorage(state.guestUserId)]);
      setBrowse(b.listings);
      setMine(m.listings);
      setSellable([...s.team, ...s.box]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't reach the market.");
    }
  }, [serverAvailable, state.guestUserId]);

  useEffect(() => { void load(); }, [load]);

  async function run(key: string, action: () => Promise<{ message: string }>) {
    if (busy) return;
    setBusy(key);
    setMessage('');
    setError('');
    try {
      const res = await action();
      setMessage(res.message);
      await actions.refreshRoster();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'That did not work.');
    } finally {
      setBusy(null);
    }
  }

  function sell() {
    const p = Number(price);
    if (!pickId || !Number.isInteger(p) || p < 1) {
      setError('Choose a Pokémon and a whole-number price.');
      return;
    }
    void run('sell', async () => {
      const r = await actions.recoverable('market-list', 'listing', { userId: state.guestUserId, pokemonId: pickId, price: p });
      setPickId('');
      setPrice('');
      setTab('mine');
      return r;
    });
  }

  if (!serverAvailable) {
    return <div className="w-full max-w-2xl mx-auto p-6 text-center opacity-70">The market needs a server connection.</div>;
  }

  const tabBtn = (t: Tab, label: string) => (
    <button
      key={t}
      aria-current={tab === t ? 'page' : undefined}
      onClick={() => setTab(t)}
      className={`px-3 py-1 uppercase text-xs border border-retro-green ${tab === t ? 'bg-retro-green text-retro-bg' : ''}`}
    >
      {label}
    </button>
  );

  const card = (l: MarketListing, action: ReactNode) => (
    <li key={l.listing_id} className="flex items-center justify-between gap-2 border border-retro-green/40 p-2">
      <div className="min-w-0">
        <div className="uppercase truncate">{l.species} · LV.{l.level}</div>
        <div className="text-xs opacity-70">
          {l.price} coins · {l.mine ? 'yours' : `from ${l.seller}`} · {l.expired ? 'expired' : `until ${when(l.expires)}`}
        </div>
      </div>
      {action}
    </li>
  );

  return (
    <div className="w-full max-w-2xl mx-auto p-4 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
      <h1 className="uppercase tracking-widest text-center">Market <Tip id="market-listing" title="Selling"><p>Pick a Pokémon and a price. A small fee is taken when it sells, and unsold listings expire.</p></Tip></h1>
      <div className="flex justify-center gap-2" role="tablist">
        {tabBtn('browse', 'Browse')}{tabBtn('mine', 'My listings')}{tabBtn('sell', 'Sell')}
      </div>
      {message && <div className="border border-retro-green p-2 text-sm">{message}</div>}
      {error && (
        <div className="border border-red-500 text-red-400 p-2 text-sm flex justify-between gap-2">
          <span>{error}</span>
          <button className="underline" onClick={() => void load()}>retry</button>
        </div>
      )}

      {tab === 'browse' && (
        <section>
          {browse.length === 0 && <p className="opacity-60 text-sm">Nothing for sale right now.</p>}
          <ul className="flex flex-col gap-2">
            {browse.filter((l) => !l.expired).map((l) =>
              card(l, (
                <button
                  disabled={busy !== null}
                  onClick={() => run(l.listing_id, () => actions.recoverable('market-buy', 'purchase', { userId: state.guestUserId, listingId: l.listing_id }))}
                  className="shrink-0 px-3 py-1 uppercase text-xs border border-retro-green hover:bg-retro-green hover:text-retro-bg disabled:opacity-40"
                >
                  buy · {l.price}
                </button>
              )),
            )}
          </ul>
        </section>
      )}

      {tab === 'mine' && (
        <section>
          {mine.length === 0 && <p className="opacity-60 text-sm">You have nothing listed.</p>}
          <ul className="flex flex-col gap-2">
            {mine.map((l) =>
              card(l, (
                <button
                  disabled={busy !== null}
                  onClick={() => run(l.listing_id, () => marketCancel(state.guestUserId, l.listing_id))}
                  className="shrink-0 px-3 py-1 uppercase text-xs border border-retro-green disabled:opacity-40"
                >
                  {l.expired ? 'take back' : 'cancel'}
                </button>
              )),
            )}
          </ul>
        </section>
      )}

      {tab === 'sell' && (
        <section className="flex flex-col gap-3">
          {sellable.length === 0 && <p className="opacity-60 text-sm">You have no Pokémon to sell.</p>}
          <select
            aria-label="Pokémon to sell"
            value={pickId}
            onChange={(e) => setPickId(e.target.value)}
            className="bg-retro-bg border border-retro-green/60 px-2 py-1"
          >
            <option value="">choose a Pokémon…</option>
            {sellable.map((m) => (
              <option key={m.id} value={m.id}>{m.nickname || m.species_name} · LV.{m.level}</option>
            ))}
          </select>
          <div className="flex items-center gap-2">
            <input
              aria-label="Price in coins"
              inputMode="numeric"
              placeholder="price in coins"
              value={price}
              onChange={(e) => setPrice(e.target.value.replace(/[^0-9]/g, ''))}
              className="bg-retro-bg border border-retro-green/60 px-2 py-1 w-40"
            />
            <button
              disabled={busy !== null || !pickId || !price}
              onClick={sell}
              className="px-3 py-1 uppercase text-xs border border-retro-green disabled:opacity-40"
            >
              list it
            </button>
          </div>
          <p className="text-xs opacity-60">
            A listed Pokémon leaves your team while it is for sale. The buyer pays the price; the market keeps 5%.
            Listings last three days.
          </p>
        </section>
      )}
    </div>
  );
}
