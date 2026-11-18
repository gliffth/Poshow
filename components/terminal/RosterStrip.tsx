import Image from 'next/image';
import { Monster } from '@/lib/types';
import { getTypeAccent } from '@/lib/gameData';

interface RosterStripProps {
  party: Monster[];
  selectedUid?: string;
  onSelect: (uid: string) => void;
  /** fixed number of slots to draw (empty ones are dashed placeholders); omit to show only the Pokémon */
  slots?: number;
}

// Your party at a glance: six slots in one row, each with a sprite, level and HP bar. Tap one to inspect it.
export function RosterStrip({ party, selectedUid, onSelect, slots }: RosterStripProps) {
  const empty = Math.max(0, (slots ?? party.length) - party.length);
  return (
    <div className="grid grid-cols-6 gap-1.5" role="list" aria-label="Party">
      {party.map((m) => {
        const accent = getTypeAccent(m.types[0]);
        const isFainted = m.hp <= 0;
        const isSelected = m.uid === selectedUid;
        const pct = Math.max(0, Math.min(100, (m.hp / Math.max(1, m.maxHp)) * 100));

        return (
          <button
            key={m.uid}
            role="listitem"
            onClick={() => onSelect(m.uid)}
            title={`${m.name} Lv.${m.level} — ${m.hp}/${m.maxHp} HP`}
            className={`relative min-w-0 bg-retro-dark text-left transition-colors ${
              isSelected ? 'border-2 border-retro-green' : 'border border-retro-green/30 hover:border-retro-green/70'
            } ${isFainted ? 'opacity-40 grayscale' : ''}`}
          >
            <div className="relative w-full aspect-square bg-retro-bg">
              <Image
                src={m.portraitUrl}
                alt={m.name}
                fill
                className="object-contain [image-rendering:pixelated] p-0.5"
                unoptimized
                referrerPolicy="no-referrer"
              />
              <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full" style={{ backgroundColor: accent }} />
            </div>
            <div className="h-1 bg-retro-green/15">
              <div className={`h-full ${pct < 25 ? 'bg-retro-alert' : 'bg-retro-green'}`} style={{ width: `${pct}%` }} />
            </div>
            <p className="text-[9px] leading-tight px-0.5 py-0.5 truncate opacity-80">Lv.{m.level}</p>
          </button>
        );
      })}
      {Array.from({ length: empty }).map((_, i) => (
        <div key={`empty-${i}`} aria-hidden className="aspect-square border border-dashed border-retro-green/20" />
      ))}
    </div>
  );
}
