"use client";

import { useEffect, useState } from 'react';
import { StatCard } from './StatCard';
import { RosterStrip } from './terminal/RosterStrip';
import { ShieldAlert, Book, Settings, Radar, ShoppingBag, Wifi, WifiOff, AlertTriangle, Skull, Candy, Landmark, Compass, Lock, ArrowRight, HeartPulse, Swords } from 'lucide-react';
import { getBossToday, BossInfo, gymStatus, evolve as apiEvolve } from '@/lib/apiClient';
import { GymStatus } from '@/lib/types';
import { CareCenter } from '@/components/CareCenter';
import { DuelsAndTrades } from '@/components/DuelsAndTrades';
import { Cutscene } from '@/components/Cutscene';
import { usePrefs } from '@/lib/prefs';
import { useGame } from '@/store/GameContext';
import { ViewName } from './terminal/IconDock';

interface RosterScreenProps {
  onScout: () => void;
  onEncounter: () => void;
  onNavigate: (view: ViewName) => void;
}

export function RosterScreen({ onScout, onEncounter, onNavigate }: RosterScreenProps) {
  const { state, dispatch, actions, serverAvailable, serverPersistent, journey } = useGame();
  const [journeyBusy, setJourneyBusy] = useState(false);
  const [prefs] = usePrefs();
  const [scene, setScene] = useState<{ kind: 'route' | 'town'; region: string; title: string } | null>(null);
  const onJourney = serverAvailable && journey?.mode === 'journey';
  const [scanning, setScanning] = useState(false);
  const [selectedUid, setSelectedUid] = useState<string | undefined>(state.party[0]?.uid);
  const [boss, setBoss] = useState<BossInfo | null>(null);
  const [bossBusy, setBossBusy] = useState(false);
  const [gym, setGym] = useState<GymStatus | null>(null);
  const [gymBusy, setGymBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const caughtCount = Object.values(state.pokedex).filter((e) => e.caught).length;

  // keep viewport pointed at a real party member as the roster changes underneath it
  useEffect(() => {
    if (!state.party.some((m) => m.uid === selectedUid)) {
      setSelectedUid(state.party[0]?.uid);
    }
  }, [state.party, selectedUid]);

  const selected = state.party.find((m) => m.uid === selectedUid) ?? state.party[0];

  // today's boss — refreshed whenever the party changes (a win/loss changes what "claimed" means)
  useEffect(() => {
    if (!serverAvailable) { setBoss(null); return; }
    let cancelled = false;
    getBossToday(state.guestUserId)
      .then((b) => { if (!cancelled) setBoss(b); })
      .catch(() => { if (!cancelled) setBoss(null); });
    return () => { cancelled = true; };
  }, [serverAvailable, state.guestUserId, state.party]);

  // journey state changes after trainer fights (badges, unlocks, blackouts) — refetch when the party changes
  useEffect(() => {
    if (serverAvailable) actions.refreshJourney();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverAvailable, state.party]);

  // Battle Gym status — refreshed when the party changes (a finished fight changes floor/BP)
  useEffect(() => {
    if (!serverAvailable) { setGym(null); return; }
    let cancelled = false;
    gymStatus(state.guestUserId)
      .then((g) => { if (!cancelled) setGym(g); })
      .catch(() => { if (!cancelled) setGym(null); });
    return () => { cancelled = true; };
  }, [serverAvailable, state.guestUserId, state.party]);

  async function handleGym() {
    if (gymBusy) return;
    setGymBusy(true);
    setNotice('');
    try {
      const res = await actions.startGym();
      if (res.success) onEncounter();
      else setNotice(res.message ?? "Couldn't enter the gym.");
    } finally {
      setGymBusy(false);
    }
  }

  async function journeyDo(fn: () => Promise<{ success: boolean; message?: string }>, thenEncounter = false) {
    if (journeyBusy) return;
    setJourneyBusy(true);
    setNotice('');
    try {
      const res = await fn();
      if (!res.success) setNotice(res.message ?? 'That did not work.');
      else if (thenEncounter) onEncounter();
    } finally {
      setJourneyBusy(false);
    }
  }

  async function travelTo(exit: { id: string; name: string; kind: 'town' | 'route' }) {
    if (journeyBusy) return;
    setJourneyBusy(true);
    setNotice('');
    try {
      const res = await actions.journeyTravel(exit.id);
      if (!res.success) setNotice(res.message ?? "You can't go there yet.");
      else if (prefs.cutscenes && journey) setScene({ kind: exit.kind, region: journey.region, title: exit.name });
    } finally {
      setJourneyBusy(false);
    }
  }

  async function handleBoss() {
    if (bossBusy) return;
    setBossBusy(true);
    setNotice('');
    try {
      const res = await actions.startBoss();
      if (res.success) onEncounter();
      else setNotice(res.message ?? "Couldn't start the boss fight.");
    } finally {
      setBossBusy(false);
    }
  }

  async function handleEvolve(to: string) {
    if (!selected) return;
    setNotice('');
    try {
      const res = await apiEvolve(state.guestUserId, selected.uid, to);
      setNotice(res.message);
      await actions.refreshRoster();
    } catch (err) {
      setNotice(err instanceof Error ? err.message : 'It could not evolve.');
    }
  }

  async function handleCandy() {
    if (!selected) return;
    setNotice('');
    const res = await actions.useRareCandy(selected.uid);
    if (!res.success) setNotice(res.message ?? "Couldn't use that Rare Candy.");
  }

  async function handleScan() {
    const alive = state.party.some((m) => m.hp > 0);
    if (!alive || scanning) return;

    // Scout (pick from 3 candidates) needs the server — offline mode keeps
    // the old instant-random-encounter behavior since there's nothing to scout.
    if (serverAvailable) {
      onScout();
      return;
    }

    setScanning(true);
    try {
      const res = await actions.scanArea();
      if (!res.ok) { setNotice(res.message ?? "Couldn't start that battle."); return; }
      onEncounter();
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className="w-full max-w-5xl mx-auto h-full flex flex-col p-3 sm:p-6 lg:p-12 overflow-y-auto custom-scrollbar">

      <div className="flex flex-row justify-between items-end gap-3 mb-4 sm:mb-8 border-b border-retro-green/40 pb-3">
        <div className="min-w-0">
          <h1 className="font-pixel text-base sm:text-lg lg:text-xl leading-relaxed mb-2 truncate">Journey</h1>
          <p className="text-retro-green/70 flex items-center gap-2 text-sm">
            {state.party.length} / 6 IN YOUR TEAM
            <span title={serverAvailable ? 'Connected to server' : 'Offline — using local rules'} className="opacity-60 shrink-0">
              {serverAvailable ? <Wifi size={12} /> : <WifiOff size={12} />}
            </span>
            {serverAvailable && !serverPersistent && (
              <span title="Server has no database connected — progress won't survive a restart" className="text-retro-alert flex items-center gap-1 shrink-0">
                <AlertTriangle size={12} /> unsaved
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-4">
           <button
             onClick={handleScan}
             disabled={!state.party.some((m) => m.hp > 0) || scanning || (onJourney && !journey?.can_scan)}
             title={onJourney && !journey?.can_scan ? 'No wild Pokémon in town — travel to a route' : undefined}
             className="border-2 border-retro-green bg-retro-green/10 hover:bg-retro-green hover:text-retro-bg px-4 sm:px-6 py-2 uppercase tracking-wide sm:tracking-widest text-sm sm:text-base flex items-center gap-2 box-glow group disabled:opacity-30 disabled:pointer-events-none shrink-0"
           >
             <Radar size={18} className={scanning ? 'animate-spin' : 'group-hover:animate-spin'} />
             {scanning ? 'Scanning...' : 'Scan Area'}
           </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5 sm:gap-8 flex-1">
        <div className="space-y-4">
           <h2 className="text-base uppercase tracking-widest border-b border-retro-green/20 pb-1.5 flex items-center gap-2">
             <ShieldAlert size={18} /> Active Team
           </h2>

           {/* Party lineup strip — tap one to view it in the frame below */}
           {state.party.length > 0 && (
             <RosterStrip party={state.party} selectedUid={selected?.uid} onSelect={setSelectedUid} slots={6} />
           )}

           {notice && (
             <div className="border-2 border-retro-alert p-2 text-xs text-retro-alert bg-retro-alert/10">{notice}</div>
           )}

           {/* Main viewport — the currently selected monster, in detail */}
           {selected && (
             <StatCard
               monster={selected}
               showXp
               onFeed={() => dispatch({ type: 'FEED_MONSTER', uid: selected.uid })}
               onHeal={(item) => actions.healMonster(selected.uid, item)}
               potionCount={state.inventory.potion}
               superpotionCount={state.inventory.superpotion}
             />
           )}

           {selected?.evolutions?.some((e) => e.ready) && (
             <div className="border-2 border-retro-green p-3 space-y-2 box-glow">
               <p className="text-xs uppercase tracking-widest">{selected.name} is ready to evolve!</p>
               <div className="flex flex-wrap gap-2">
                 {selected.evolutions.filter((e) => e.ready).map((e) => (
                   <button key={e.to} onClick={() => handleEvolve(e.to)}
                     className="border-2 border-retro-green px-3 py-1.5 text-xs uppercase tracking-widest hover:bg-retro-green hover:text-retro-bg">
                     Evolve → {e.to} ({e.label})
                   </button>
                 ))}
               </div>
             </div>
           )}

           {selected && (state.extras?.rare_candy ?? 0) > 0 && (
             <button
               onClick={handleCandy}
               className="w-full border border-retro-green/50 py-2 flex items-center justify-center gap-2 text-sm uppercase tracking-widest hover:bg-retro-green hover:text-retro-bg"
             >
               <Candy size={14} /> Rare Candy x{state.extras.rare_candy} — level up {selected.name}
             </button>
           )}
        </div>

        <div className="space-y-4">
           {/* Journey */}
           {onJourney && journey && journey.location && (
             <div className="border border-retro-green/60 bg-retro-dark p-4 space-y-3 box-glow">
               <p className="flex items-center gap-2 uppercase tracking-widest text-sm">
                 <Compass size={16} /> {journey.location.name}
                 <span className="opacity-50 text-[10px]">{journey.location.kind === 'town' ? 'TOWN' : 'ROUTE'}</span>
               </p>
               <p className="text-xs opacity-70">{journey.location.desc}</p>
               <p className="text-xs">🎯 {journey.objective}</p>
               <p className="text-[11px] opacity-60 uppercase tracking-widest">
                 Badges {journey.badge_count ?? journey.badges.length}/8{journey.complete ? ' · Champion' : ''}
               </p>

               {(journey.regions ?? []).filter((r) => r.unlocked && r.journey).length > 1 && (
                 <div className="flex flex-wrap gap-1.5" role="group" aria-label="Region">
                   {(journey.regions ?? []).filter((r) => r.unlocked && r.journey).map((r) => (
                     <button
                       key={r.id}
                       disabled={r.current || journeyBusy}
                       onClick={() => journeyDo(() => actions.journeyRegion(r.id))}
                       className={`px-2.5 py-1 text-[11px] uppercase border ${r.current ? 'bg-retro-green text-retro-bg border-retro-green' : 'border-retro-green/40 hover:bg-retro-green/10'}`}
                     >
                       {r.id}
                     </button>
                   ))}
                 </div>
               )}

               {journey.challenges.filter((c) => !c.cleared).map((c) => (
                 <button
                   key={c.id}
                   onClick={() => journeyDo(() => actions.startTrainer(c.id), true)}
                   disabled={!c.available || journeyBusy}
                   title={c.reason ?? undefined}
                   className="w-full border border-retro-green/70 py-2 px-3 text-left flex items-center justify-between gap-2 text-sm uppercase tracking-wide hover:bg-retro-green hover:text-retro-bg disabled:opacity-40 disabled:pointer-events-none"
                 >
                   <span className="flex items-center gap-2 min-w-0 truncate"><Swords size={14} /> {c.name} <span className="opacity-60 normal-case text-xs truncate">{c.title}</span></span>
                   <span className="shrink-0 text-xs opacity-70">{c.available ? `Lv.${c.top_level}` : <Lock size={12} />}</span>
                 </button>
               ))}
               {journey.pending && <p className="text-[11px] text-retro-alert">A trainer battle is in progress — challenge again to continue it.</p>}

               {journey.location.heal && (
                 <button
                   onClick={() => journeyDo(() => actions.journeyHeal())}
                   disabled={journeyBusy}
                   className="w-full border border-retro-green/50 py-2 flex items-center justify-center gap-2 text-sm uppercase tracking-widest hover:bg-retro-green hover:text-retro-bg disabled:opacity-40"
                 >
                   <HeartPulse size={14} /> Heal team ({journey.location.heal})
                 </button>
               )}

               <div className="grid grid-cols-2 gap-2">
                 {journey.exits.map((e) => (
                   <button
                     key={e.id}
                     onClick={() => travelTo(e)}
                     disabled={journeyBusy}
                     onContextMenu={(ev) => ev.preventDefault()}
                     title={e.reason ?? undefined}
                     className={`border-2 px-2 py-2 text-xs uppercase tracking-wide flex items-center justify-between gap-1 min-w-0 ${
                       e.locked ? 'border-retro-green/20 opacity-50' : 'border-retro-green/50 hover:bg-retro-green hover:text-retro-bg'
                     }`}
                   >
                     <span className="truncate">{e.name}</span>
                     {e.locked ? <Lock size={12} className="shrink-0" /> : <ArrowRight size={12} className="shrink-0" />}
                   </button>
                 ))}
               </div>
               {journey.exits.some((e) => e.locked && e.reason) && (
                 <p className="text-[10px] opacity-60">{journey.exits.filter((e) => e.locked && e.reason).map((e) => `${e.name}: ${e.reason}`).join(' · ')}</p>
               )}
             </div>
           )}


           {scene && (
             <Cutscene kind={scene.kind} region={scene.region} title={scene.title}
               line={scene.kind === 'route' ? 'You set out along the path…' : 'You arrive in town.'} onDone={() => setScene(null)} />
           )}

           {/* Daily boss */}
           {serverAvailable && boss && (
             <div className="border border-retro-alert/50 bg-retro-dark p-3 space-y-2">
               <p className="flex items-center gap-2 uppercase tracking-widest text-retro-alert text-sm">
                 <Skull size={16} /> Daily Boss
               </p>
               <p className="text-lg uppercase">{boss.name} <span className="opacity-70 text-sm">Lv.{boss.level}</span></p>
               <p className="text-xs opacity-70">
                 {boss.ability ? `Ability: ${boss.ability} · ` : ''}Reward up to {boss.coin_reward} credits + {boss.xp_reward} XP
               </p>
               <button
                 onClick={handleBoss}
                 disabled={boss.claimed_today || bossBusy || !state.party.some((m) => m.hp > 0)}
                 className="w-full border-2 border-retro-alert/70 py-2 uppercase tracking-widest text-sm hover:bg-retro-alert hover:text-retro-bg disabled:opacity-30 disabled:pointer-events-none"
               >
                 {boss.claimed_today ? 'Defeated today — back at 00:00 UTC' : bossBusy ? 'Engaging...' : 'Challenge'}
               </button>
             </div>
           )}

           {/* Battle Gym */}
           {serverAvailable && gym && (
             <div className="border border-retro-green/50 bg-retro-dark p-4 space-y-2">
               <p className="flex items-center gap-2 uppercase tracking-widest text-sm">
                 <Landmark size={16} /> Battle Gym
               </p>
               <p className="text-xs opacity-70">
                 Best floor {gym.best} · {gym.bp} BP
                 {gym.in_run ? ` · Run in progress (floor ${gym.floor})` : ''}
               </p>
               <p className="text-sm">
                 {gym.next_is_leader && gym.leader
                   ? `Next: ${gym.leader.gym} Gym Leader ${gym.leader.name} (Lv.${gym.next_level})`
                   : `Next: Floor ${gym.next_floor} trainer (Lv.${gym.next_level})`}
               </p>
               <button
                 onClick={handleGym}
                 disabled={gymBusy || !state.party.some((m) => m.hp > 0)}
                 className="w-full border border-retro-green/60 py-2 uppercase tracking-widest text-sm hover:bg-retro-green hover:text-retro-bg disabled:opacity-30 disabled:pointer-events-none"
               >
                 {gymBusy ? 'Entering...' : gym.in_run ? 'Resume Run' : 'Enter Gym'}
               </button>
             </div>
           )}


           {/* Secondary tools stay folded away until needed */}
           {serverAvailable && (
             <details className="border border-retro-green/30">
               <summary className="cursor-pointer px-3 py-2 uppercase text-xs tracking-widest hover:bg-retro-green/10">Care Center — heal &amp; rest</summary>
               <div className="p-2"><CareCenter /></div>
             </details>
           )}
           {serverAvailable && (
             <details className="border border-retro-green/30">
               <summary className="cursor-pointer px-3 py-2 uppercase text-xs tracking-widest hover:bg-retro-green/10">Duels &amp; Trades</summary>
               <div className="p-2"><DuelsAndTrades /></div>
             </details>
           )}
        </div>
      </div>
    </div>
  );
}
