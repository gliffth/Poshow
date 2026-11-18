// Retry-safe actions: one request id per click, reused for every retry of that click.

export const newRequestId = (): string =>
  (globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`).replace(/[^A-Za-z0-9_-]/g, '');

export type PendingKind = 'shop-buy' | 'gym-buy' | 'quest-claim' | 'market-list' | 'market-buy';

export interface PendingAction {
  kind: PendingKind;
  label: string;
  payload: Record<string, unknown>;
  requestId: string;
  ts: number;
}

const KEY = 'poshow:pending';
export const PENDING_MAX_AGE_MS = 10 * 60 * 1000;
export const RETRY_DELAYS_MS = [1500, 3000];

type Store = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

function store(): Store | null {
  try {
    return typeof window !== 'undefined' ? window.sessionStorage : null;
  } catch {
    return null;
  }
}

export function loadPending(now = Date.now(), s: Store | null = store()): PendingAction | null {
  if (!s) return null;
  try {
    const raw = s.getItem(KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as PendingAction;
    if (!p || typeof p.requestId !== 'string' || typeof p.ts !== 'number' || now - p.ts > PENDING_MAX_AGE_MS) {
      s.removeItem(KEY);
      return null;
    }
    return p;
  } catch {
    return null;
  }
}

export function savePending(p: PendingAction, s: Store | null = store()): void {
  try {
    s?.setItem(KEY, JSON.stringify(p));
  } catch {
    // storage full or blocked: the in-memory copy still protects this page load
  }
}

export function clearPending(s: Store | null = store()): void {
  try {
    s?.removeItem(KEY);
  } catch {
    // ignore
  }
}

export const samePayload = (a: Record<string, unknown>, b: Record<string, unknown>): boolean =>
  JSON.stringify(Object.entries(a).sort()) === JSON.stringify(Object.entries(b).sort());

/** The id to use for this action: a pending one for the same action, never a fresh one. */
export function idFor(kind: PendingKind, payload: Record<string, unknown>, pending: PendingAction | null): string {
  return pending && pending.kind === kind && samePayload(pending.payload, payload) ? pending.requestId : newRequestId();
}

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

/** Run `run`, retrying only retryable failures after each delay. The last failure is thrown. */
export async function withRetries<T>(
  run: () => Promise<T>,
  isRetryable: (err: unknown) => boolean,
  delays: number[] = RETRY_DELAYS_MS,
  sleep: (ms: number) => Promise<void> = wait,
): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await run();
    } catch (err) {
      if (!isRetryable(err) || attempt >= delays.length) throw err;
      await sleep(delays[attempt]);
    }
  }
}
