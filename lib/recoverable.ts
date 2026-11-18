// The API call behind each retry-safe action. The banner can resend any of them after a page reload.
import * as api from './apiClient';
import type { PendingKind } from './actionRecovery';

export type Payloads = {
  'shop-buy': { userId: number; itemId: string; quantity: number };
  'gym-buy': { userId: number; itemId: string; quantity: number };
  'quest-claim': { userId: number; questId: string };
  'market-list': { userId: number; pokemonId: string; price: number };
  'market-buy': { userId: number; listingId: string };
};

export type Results = {
  'shop-buy': Awaited<ReturnType<typeof api.buyItem>>;
  'gym-buy': Awaited<ReturnType<typeof api.gymShopBuy>>;
  'quest-claim': Awaited<ReturnType<typeof api.claimQuest>>;
  'market-list': Awaited<ReturnType<typeof api.marketList>>;
  'market-buy': Awaited<ReturnType<typeof api.marketBuy>>;
};

const RUNNERS: { [K in PendingKind]: (p: Payloads[K], id: string) => Promise<Results[K]> } = {
  'shop-buy': (p, id) => api.buyItem(p.userId, p.itemId, p.quantity, id),
  'gym-buy': (p, id) => api.gymShopBuy(p.userId, p.itemId, p.quantity, id),
  'quest-claim': (p, id) => api.claimQuest(p.userId, p.questId, id),
  'market-list': (p, id) => api.marketList(p.userId, p.pokemonId, p.price, id),
  'market-buy': (p, id) => api.marketBuy(p.userId, p.listingId, id),
};

export function runAction<K extends PendingKind>(kind: K, payload: Payloads[K], requestId: string): Promise<Results[K]> {
  return RUNNERS[kind](payload, requestId);
}

export const UNCONFIRMED_MESSAGE = "Couldn't confirm that. It may or may not have gone through.";

export class UnconfirmedError extends Error {
  constructor() {
    super(UNCONFIRMED_MESSAGE);
    this.name = 'UnconfirmedError';
  }
}

export class BattleEndedError extends Error {
  constructor() {
    super('That battle already ended; your result was saved.');
    this.name = 'BattleEndedError';
  }
}
