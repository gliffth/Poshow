"use client";

import { useState } from 'react';
import { useGame } from '@/store/GameContext';
import { SHOP_ITEMS } from '@/lib/gameData';
import { Wallet, ShoppingCart, AlertCircle } from 'lucide-react';
import { sfx } from '@/lib/sound';

export function ShopScreen() {
  const { state, actions } = useGame();
  const [buyingId, setBuyingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function buy(itemId: (typeof SHOP_ITEMS)[number]['id'], price: number) {
    if (state.currency < price || buyingId) {
      sfx.error();
      return;
    }
    setBuyingId(itemId);
    setError(null);
    try {
      const result = await actions.buyItem(itemId);
      if (!result.success) setError(result.message ?? 'Purchase failed.');
    } finally {
      setBuyingId(null);
    }
  }

  return (
    <div className="w-full max-w-4xl mx-auto h-full flex flex-col p-3 sm:p-6 lg:p-12 overflow-y-auto custom-scrollbar">
      <div className="mb-8 border-b-2 border-retro-green pb-4 flex justify-between items-end">
        <div>
          <h1 className="font-pixel text-lg sm:text-xl leading-relaxed mb-2">Poke Mart</h1>
          <p className="text-retro-green/70">GEAR &amp; SUPPLIES</p>
        </div>
        <div className="flex items-center gap-2 text-xl">
          <Wallet size={20} />
          {state.currency}
        </div>
      </div>

      {error && (
        <div className="mb-4 border-2 border-retro-alert p-3 flex items-center gap-2 text-sm text-retro-alert bg-retro-alert/10">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {SHOP_ITEMS.map((item) => {
          const owned = state.inventory[item.id];
          const affordable = state.currency >= item.price;
          return (
            <div key={item.id} className="relative border-2 border-retro-green/40 p-4 bg-retro-dark box-glow">
              <div className="absolute -top-1 -left-1 w-2 h-2 border-t-2 border-l-2 border-retro-green"></div>
              <div className="absolute -top-1 -right-1 w-2 h-2 border-t-2 border-r-2 border-retro-green"></div>
              <div className="absolute -bottom-1 -left-1 w-2 h-2 border-b-2 border-l-2 border-retro-green"></div>
              <div className="absolute -bottom-1 -right-1 w-2 h-2 border-b-2 border-r-2 border-retro-green"></div>

              <div className="flex justify-between items-start mb-2">
                <h3 className="uppercase tracking-widest text-lg">{item.name}</h3>
                <span className="text-xs opacity-60">OWNED x{owned}</span>
              </div>
              <p className="text-sm opacity-70 mb-4 min-h-[2.5rem]">{item.description}</p>
              <button
                onClick={() => buy(item.id, item.price)}
                disabled={!affordable || buyingId === item.id}
                className="w-full border-2 border-retro-green/50 py-2 flex items-center justify-center gap-2 hover:bg-retro-green hover:text-retro-bg uppercase tracking-widest text-sm disabled:opacity-30 disabled:pointer-events-none"
              >
                <ShoppingCart size={14} />
                {buyingId === item.id ? 'Buying...' : `Buy — ${item.price}`}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
