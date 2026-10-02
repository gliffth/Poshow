"use client";

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { useGame } from '@/store/GameContext';
import { Monster } from '@/lib/types';
import { getRoutes, RouteInfo } from '@/lib/apiClient';
import { getTypeAccent } from '@/lib/gameData';
import { Radar, Navigation } from 'lucide-react';
import { BoltCorners } from './terminal/BoltCorners';

interface ScoutScreenProps {
  onEncounter: () => void;
  onCancel: () => void;
}

// same three species WILD_POOL/WILD_SPECIES_POOL give the lowest weight —
// flagging them here is cosmetic only, the actual rarity lives server-side
const RARE_SPECIES = new Set(['bulbasaur', 'charmander', 'squirtle']);

export function ScoutScreen({ onEncounter, onCancel }: ScoutScreenProps) {
  const { actions, serverAvailable, journey } = useGame();
  const onJourney = journey?.mode === 'journey';
  const [candidates, setCandidates] = useState<Monster[]>([]);
  const [loading, setLoading] = useState(true);
  const [engaging, setEngaging] = useState(false);
  const [error, setError] = useState('');
  const [routes, setRoutes] = useState<RouteInfo[]>([]);
  // '' = the original "wild grass" mix, scaled to your lead Pokemon
  const [routeId, setRouteId] = useState('');

  // route list is optional garnish — if it fails the scan still works with the default mix
  useEffect(() => {
    if (!serverAvailable) return;
    let cancelled = false;
    getRoutes()
      .then((r) => { if (!cancelled) setRoutes(r.routes); })
      .catch(() => { /* leave the picker empty */ });
    return () => { cancelled = true; };
  }, [serverAvailable]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!serverAvailable) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError('');
      const found = await actions.scoutArea(routeId || undefined);
      if (cancelled) return;
      if (found.length === 0) setError("Couldn't scan the area — try again.");
      setCandidates(found);
      setLoading(false);
    }
    load();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverAvailable, routeId]);

  async function handleEngage(target: Monster) {
    if (engaging) return;
    setEngaging(true);
    try {
      await actions.scanArea({ species: target.speciesId, level: target.level });
      onEncounter();
    } finally {
      setEngaging(false);
    }
  }

  async function handleInstantScan() {
    if (engaging) return;
    setEngaging(true);
    try {
      await actions.scanArea();
      onEncounter();
    } finally {
      setEngaging(false);
    }
  }

  if (!serverAvailable) {
    return (
      <div className="w-full max-w-2xl mx-auto h-full flex flex-col items-center justify-center gap-4 p-6 text-center">
        <Radar size={40} className="opacity-40" />
        <p className="opacity-70">Scouting needs a server connection — offline mode scans instantly instead.</p>
        <button
          onClick={handleInstantScan}
          disabled={engaging}
          className="border-2 border-retro-green px-6 py-2 hover:bg-retro-green hover:text-retro-bg uppercase tracking-widest disabled:opacity-50"
        >
          {engaging ? 'Scanning...' : 'Scan Anyway'}
        </button>
        <button onClick={onCancel} className="text-sm opacity-60 underline">Back</button>
      </div>
    );
  }

  return (
    <div className="w-full max-w-5xl mx-auto h-full flex flex-col p-3 sm:p-6 lg:p-12 overflow-y-auto custom-scrollbar">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-end gap-4 mb-6 sm:mb-8 border-b-2 border-retro-green pb-4">
        <div className="min-w-0">
          <h1 className="font-pixel text-base sm:text-lg lg:text-xl leading-relaxed mb-2 flex items-center gap-2">
            <Radar size={22} className={loading ? 'animate-spin' : ''} /> Area Scan
          </h1>
          <p className="text-retro-green/70 text-sm">Pick a target to engage</p>
        </div>
        <button
          onClick={onCancel}
          className="border-2 border-retro-green/50 hover:border-retro-green px-4 sm:px-6 py-2 uppercase tracking-wide text-sm shrink-0"
        >
          Retreat
        </button>
      </div>

      {routes.length > 0 && !onJourney && (
        <label className="mb-4 flex flex-col gap-1 text-xs uppercase tracking-widest text-retro-green/70">
          Location
          <select
            value={routeId}
            onChange={(e) => setRouteId(e.target.value)}
            disabled={loading || engaging}
            className="bg-retro-dark border-2 border-retro-green/50 px-3 py-2 text-sm text-retro-green normal-case tracking-normal disabled:opacity-50"
          >
            <option value="">Wild Grass (scaled to your team)</option>
            {routes.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name} — Lv {r.min_level}-{r.max_level}
              </option>
            ))}
          </select>
        </label>
      )}

      {error && (
        <div className="mb-4 border-2 border-retro-alert p-3 text-sm text-retro-alert bg-retro-alert/10">{error}</div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6">
        {loading
          ? Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="border-2 border-retro-green/20 p-6 flex items-center justify-center min-h-[220px] bezel-inverted">
                <Radar className="opacity-20 animate-spin" size={40} />
              </div>
            ))
          : candidates.map((mon) => {
              const accent = getTypeAccent(mon.types[0]);
              const rare = RARE_SPECIES.has(mon.speciesId);
              return (
                <button
                  key={mon.uid}
                  disabled={engaging}
                  onClick={() => handleEngage(mon)}
                  className="group relative border-2 border-retro-green/40 bg-retro-dark hover:border-retro-green bezel transition-colors p-4 sm:p-6 flex flex-col items-center gap-3 disabled:opacity-50"
                >
                  <BoltCorners size={8} />
                  {rare && (
                    <span className="absolute top-2 left-2 text-[8px] uppercase bg-retro-green text-retro-bg px-1 tracking-widest">
                      Rare Signal
                    </span>
                  )}
                  <span className="absolute top-2 right-2 text-xs border-2 border-retro-green/30 px-1">
                    Lv.{mon.level}
                  </span>

                  <div className="h-24 w-24 sm:h-32 sm:w-32 relative mt-4 bezel-inverted border-2 border-retro-green/30 bg-retro-bg">
                    <Image
                      src={mon.portraitUrl}
                      alt={mon.name}
                      fill
                      unoptimized
                      referrerPolicy="no-referrer"
                      className="object-contain [image-rendering:pixelated] p-2"
                    />
                  </div>

                  <div className="text-center w-full pt-3 border-t-2 border-retro-green/20">
                    <p className="font-pixel text-[10px] sm:text-xs leading-relaxed mb-2 truncate">{mon.name}</p>
                    <div className="flex gap-1 justify-center flex-wrap">
                      {mon.types.map((t) => (
                        <span
                          key={t}
                          className="text-[9px] uppercase tracking-widest border px-1"
                          style={{ borderColor: accent, color: accent }}
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center gap-1 text-xs uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity">
                    <Navigation size={12} /> Engage
                  </div>
                </button>
              );
            })}
      </div>
    </div>
  );
}
