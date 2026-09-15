import { Monster } from '@/lib/types';
import { Shield, Skull, Zap, Droplets, Snowflake, Activity, Utensils, Heart, Plus, Syringe } from 'lucide-react';
import Image from 'next/image';
import { SegmentedBar } from './terminal/SegmentedBar';
import { BoltCorners } from './terminal/BoltCorners';
import { getTypeAccent } from '@/lib/gameData';

interface StatCardProps {
  monster: Monster;
  isOpponent?: boolean;
  showXp?: boolean;
  onFeed?: () => void;
  onHeal?: (item: 'potion' | 'superpotion') => void;
  potionCount?: number;
  superpotionCount?: number;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  psn: <Skull size={16} className="text-retro-green text-glow" />,
  brn: <Droplets size={16} className="text-retro-green text-glow" />,
  par: <Zap size={16} className="text-retro-green text-glow" />,
  slp: <span className="text-xs">ZZZ</span>,
  frz: <Snowflake size={16} className="text-retro-green text-glow" />,
};

export function StatCard({ monster, isOpponent = false, showXp = false, onFeed, onHeal, potionCount = 0, superpotionCount = 0 }: StatCardProps) {
  const isLowHp = monster.hp / monster.maxHp < 0.25;
  const isFainted = monster.hp <= 0;
  const accent = getTypeAccent(monster.types[0]);

  return (
    <div
      className={`relative border-2 p-4 rounded-sm bg-retro-dark ${isLowHp ? 'border-retro-alert' : 'border-retro-green'} ${isFainted ? 'opacity-50 grayscale' : ''}`}
      style={{
        boxShadow: [
          'inset 2px 2px 0px rgba(var(--highlight-rgb), 0.15)',
          'inset -2px -2px 0px rgba(var(--shadow-rgb), 0.5)',
          'inset 4px 4px 0px rgba(var(--highlight-rgb), 0.06)',
          'inset -4px -4px 0px rgba(var(--shadow-rgb), 0.3)',
          !isLowHp ? `3px 3px 0 ${accent}55` : '',
        ].filter(Boolean).join(', '),
      }}
    >
      <BoltCorners />

      {/* Header: Name and Level */}
      <div className="flex justify-between items-center gap-2 mb-3 border-b-2 border-retro-green/30 pb-2">
        <div className="min-w-0 flex-1">
          <h3 className="font-pixel text-xs sm:text-sm leading-relaxed tracking-wide truncate">{monster.name}</h3>
          <p className="text-xs uppercase tracking-widest opacity-70 mt-1 truncate" style={{ color: accent }}>
            {monster.types.join(' / ')}
          </p>
        </div>
        <div className="flex items-center gap-1 text-retro-green/80 shrink-0">
          <Activity size={14} />
          <span className="text-base sm:text-lg">LV.{monster.level}</span>
        </div>
      </div>

      <div className="flex gap-3 sm:gap-4">
        {/* Portrait — framed like a viewport, not a plain photo box */}
        <div
          className={`relative w-16 h-16 sm:w-24 sm:h-24 border-2 bezel-inverted ${isLowHp ? 'border-retro-alert' : 'border-retro-green'} p-1 bg-retro-bg flex-shrink-0`}
        >
           <Image
             src={monster.portraitUrl}
             alt={monster.name}
             fill
             className={`object-contain [image-rendering:pixelated] ${isOpponent ? '' : 'scale-x-[-1]'} filter contrast-110 saturate-150 ${isLowHp ? 'grayscale-[40%]' : ''}`}
             referrerPolicy="no-referrer"
             unoptimized
           />
           {isFainted && (
             <div className="absolute inset-0 z-20 flex items-center justify-center bg-retro-bg/70">
               <Skull size={28} className="text-retro-alert" />
             </div>
           )}
        </div>

        {/* Stats & HP */}
        <div className="flex-1 min-w-0 flex flex-col justify-between">
          <div className="space-y-2">
            <SegmentedBar
              value={monster.hp}
              max={monster.maxHp}
              label={<><Heart size={12}/> HP</>}
              accentColor={accent}
            />

            {showXp && (
              <SegmentedBar
                value={monster.xp}
                max={monster.xpToNext}
                height="sm"
                showNumbers={false}
                alertBelow={-1}
                label={<span className="text-xs opacity-70">XP</span>}
              />
            )}

            {/* Minor Stats Icons Row */}
            <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-retro-green/70">
               <div className="flex items-center gap-1" title="Hunger">
                 <Utensils size={14} />
                 <span className="text-sm">{monster.hunger}/{monster.maxHunger}</span>
               </div>
               {onFeed && monster.hunger < monster.maxHunger && (
                 <button
                   onClick={(e) => { e.stopPropagation(); onFeed(); }}
                   className="text-xs border-2 border-retro-green/50 px-2 py-0.5 hover:bg-retro-green hover:text-retro-bg transition-colors flex items-center gap-1"
                 >
                   <Plus size={10} /> FEED
                 </button>
               )}
            </div>

            {onHeal && monster.hp < monster.maxHp && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs opacity-60 flex items-center gap-1"><Syringe size={12} /> Heal:</span>
                <button
                  onClick={(e) => { e.stopPropagation(); onHeal('potion'); }}
                  disabled={potionCount <= 0}
                  className="text-xs border-2 border-retro-green/50 px-2 py-0.5 hover:bg-retro-green hover:text-retro-bg transition-colors disabled:opacity-30 disabled:pointer-events-none"
                >
                  POTION x{potionCount}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onHeal('superpotion'); }}
                  disabled={superpotionCount <= 0}
                  className="text-xs border-2 border-retro-green/50 px-2 py-0.5 hover:bg-retro-green hover:text-retro-bg transition-colors disabled:opacity-30 disabled:pointer-events-none"
                >
                  SUPER x{superpotionCount}
                </button>
              </div>
            )}
          </div>

          {/* Status Effect Badges */}
          <div className="flex justify-end gap-2 mt-2">
            {monster.status !== 'none' && (
              <div className="border-2 border-retro-green/50 p-1 flex items-center justify-center bg-retro-green/10">
                {STATUS_ICON[monster.status]}
              </div>
            )}
            <div className="border-2 border-retro-green/20 p-1 flex items-center justify-center opacity-30">
               <Shield size={16} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
