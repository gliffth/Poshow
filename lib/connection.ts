// Connection state shown by the indicator. Pure: feed it request results, read the state back.

export type ConnectionState = 'ok' | 'slow' | 'unreachable' | 'waking';

export interface ConnectionSnapshot {
  state: ConnectionState;
  everOk: boolean;
  lastOkAt: number | null;
  lastLatencyMs: number | null;
  failures: number;
  firstFailureAt: number | null;
}

export type ConnectionEvent =
  | { type: 'success'; at: number; ms: number }
  | { type: 'failure'; at: number };

export const SLOW_MS = 1500;
export const UNREACHABLE_FAILURES = 3;
export const UNREACHABLE_SPAN_MS = 45_000;
export const LONG_GAP_MS = 90_000;
export const WAKING_MS = 8_000;

export const initialConnection: ConnectionSnapshot = {
  state: 'waking', everOk: false, lastOkAt: null, lastLatencyMs: null, failures: 0, firstFailureAt: null,
};

export function reduceConnection(s: ConnectionSnapshot, e: ConnectionEvent): ConnectionSnapshot {
  if (e.type === 'success') {
    const state: ConnectionState = e.ms >= WAKING_MS ? 'waking' : e.ms > SLOW_MS ? 'slow' : 'ok';
    return { state, everOk: true, lastOkAt: e.at, lastLatencyMs: e.ms, failures: 0, firstFailureAt: null };
  }
  const failures = s.failures + 1;
  const firstFailureAt = s.firstFailureAt ?? e.at;
  let state: ConnectionState;
  if (failures >= UNREACHABLE_FAILURES && e.at - firstFailureAt >= UNREACHABLE_SPAN_MS) {
    state = 'unreachable';
  } else if (!s.everOk || s.lastOkAt === null || e.at - s.lastOkAt > LONG_GAP_MS) {
    state = 'waking';
  } else {
    state = 'slow';
  }
  return { ...s, state, failures, firstFailureAt };
}

export interface ConnectionText {
  title: string;
  message: string;
}

export function describeConnection(s: ConnectionSnapshot): ConnectionText {
  switch (s.state) {
    case 'ok':
      return {
        title: 'Connected',
        message: s.lastLatencyMs === null ? 'Connected.' : `Connected. The last reply took ${Math.round(s.lastLatencyMs)} ms.`,
      };
    case 'slow':
      return {
        title: 'Slow connection',
        message: 'The server is taking longer than usual. Your game is safe; actions may take a moment. Try again in a few seconds.',
      };
    case 'waking':
      return { title: 'Server waking up', message: 'The server has been asleep. Give it a moment to wake.' };
    case 'unreachable':
      return {
        title: "Can't reach the server",
        message: "We can't reach the server right now. Your progress is saved on the server; nothing is lost.",
      };
  }
}
