const lib = (name: string) => import(new URL(`../../lib/${name}.ts`, import.meta.url).href);
const { initialConnection, reduceConnection, describeConnection, SLOW_MS } = await lib('connection');
const { withRetries, idFor, loadPending, savePending, clearPending, newRequestId, PENDING_MAX_AGE_MS } = await lib('actionRecovery');
let bad = 0;
const ok = (c: boolean, m: string) => { console.log((c ? 'PASS ' : 'FAIL ') + m); if (!c) bad++; };
let s: any = initialConnection;
ok(s.state === 'waking', 'starts as waking until first contact');
s = reduceConnection(s, { type: 'success', at: 1000, ms: 240 });
ok(s.state === 'ok' && describeConnection(s).message === 'Connected. The last reply took 240 ms.', 'a fast reply is ok');
s = reduceConnection(s, { type: 'success', at: 2000, ms: SLOW_MS + 1 });
ok(s.state === 'slow', 'a reply over 1.5 s is slow');
s = reduceConnection(s, { type: 'success', at: 3000, ms: 100 });
s = reduceConnection(s, { type: 'failure', at: 20_000 });
ok(s.state === 'slow', 'one failure is slow, never unreachable');
s = reduceConnection(s, { type: 'failure', at: 40_000 });
s = reduceConnection(s, { type: 'failure', at: 44_000 });
ok(s.failures === 3 && s.state === 'slow', 'three failures within 45 s are still slow');
s = reduceConnection(s, { type: 'failure', at: 70_000 });
ok(s.state === 'unreachable', 'three failures spanning 45 s are unreachable');
s = reduceConnection(s, { type: 'success', at: 71_000, ms: 300 });
ok(s.state === 'ok' && s.failures === 0, 'the next success clears unreachable');
let w = reduceConnection(reduceConnection(initialConnection, { type: 'failure', at: 5000 }), { type: 'failure', at: 6000 });
ok(w.state === 'waking', 'failures before first contact read as waking');
let g = reduceConnection(initialConnection, { type: 'success', at: 0, ms: 100 });
g = reduceConnection(g, { type: 'failure', at: 200_000 });
ok(g.state === 'waking', 'a failure after a long gap reads as waking');
ok(reduceConnection(initialConnection, { type: 'success', at: 0, ms: 20_000 }).state === 'waking', 'a very slow first answer is a cold start');
ok(!/offline/i.test(describeConnection(reduceConnection(g, { type: 'failure', at: 200_100 })).message), 'the text never says offline');

{
  let n = 0; const slept: number[] = [];
  const net = (e: unknown) => e === 'net';
  const v = await withRetries(async () => { if (++n < 3) throw 'net'; return 'done'; }, net, [10, 20], async (ms) => { slept.push(ms); });
  ok(v === 'done' && n === 3 && slept.join() === '10,20', 'a network failure is retried twice with the delays');
  n = 0;
  let thrown = '';
  try { await withRetries(async () => { n++; throw 'net'; }, net, [1, 1], async () => {}); } catch (e) { thrown = String(e); }
  ok(thrown === 'net' && n === 3, 'after the last retry the failure is thrown');
  n = 0; thrown = '';
  try { await withRetries(async () => { n++; throw 'rejected'; }, net, [1, 1], async () => {}); } catch (e) { thrown = String(e); }
  ok(thrown === 'rejected' && n === 1, 'a server rejection is not retried');

  const mem: Record<string, string> = {};
  const fake = { getItem: (k: string) => mem[k] ?? null, setItem: (k: string, v: string) => { mem[k] = v; }, removeItem: (k: string) => { delete mem[k]; } };
  const p = { kind: 'shop-buy' as const, label: 'x', payload: { item: 'potion', qty: 1 }, requestId: newRequestId(), ts: 1000 };
  ok(/^[A-Za-z0-9_-]{8,64}$/.test(p.requestId), 'request ids match the server rule');
  savePending(p, fake);
  ok(loadPending(2000, fake)?.requestId === p.requestId, 'a pending action survives a reload');
  ok(loadPending(1000 + PENDING_MAX_AGE_MS + 1, fake) === null && fake.getItem('poshow:pending') === null, 'a stale pending action is dropped');
  savePending(p, fake);
  ok(idFor('shop-buy', { qty: 1, item: 'potion' }, p) === p.requestId, 'the same action reuses its pending id');
  ok(idFor('shop-buy', { item: 'ball', qty: 1 }, p) !== p.requestId && idFor('market-buy', { item: 'potion', qty: 1 }, p) !== p.requestId, 'a different action gets a new id');
  clearPending(fake);
  ok(loadPending(2000, fake) === null, 'clearing removes it');
}
if (bad) throw new Error(`${bad} failed`);
