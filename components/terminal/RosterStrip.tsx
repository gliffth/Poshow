import Image from 'next/image';
import { Monster } from '@/lib/types';
import { getTypeAccent } from '@/lib/gameData';
import { BoltCorners } from './BoltCorners';

interface RosterStripProps {
  party: Monster[];
  selectedUid?: string;
  onSelect: (uid: string) => void;
}

// photo-ID thumbnails in a row — tap one to bring it into the viewport above ᓚ₍⑅^..^₎♡
export function RosterStrip({ party, selectedUid, onSelect }: RosterStripProps) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 custom-scrollbar">
      {party.map((m) => {
        const accent = getTypeAccent(m.types[0]);
        const isFainted = m.hp <= 0;
        const isSelected = m.uid === selectedUid;

        return (
          <button
            key={m.uid}
            onClick={() => onSelect(m.uid)}
            className={`relative flex-shrink-0 w-16 bg-retro-dark border-2 text-left transition-colors ${
              isSelected ? 'border-retro-green box-glow' : 'border-retro-green/30 hover:border-retro-green/60'
            } ${isFainted ? 'opacity-40 grayscale' : ''}`}
          >
            <BoltCorners size={5} />
            <div
              className="relative w-full aspect-square border-b-2 border-retro-green/30 bg-retro-bg"
              style={{ boxShadow: 'inset 0 0 8px rgba(var(--shadow-rgb), 0.5)' }}
            >
              <Image
                src={m.portraitUrl}
                alt={m.name}
                fill
                className="object-contain [image-rendering:pixelated] p-1"
                unoptimized
                referrerPolicy="no-referrer"
              />
              <span
                className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: accent }}
                title={m.types.join(' / ')}
              />
            </div>
            <div className="px-1 py-0.5">
              <p className="text-[8px] uppercase tracking-wide truncate leading-tight">{m.name}</p>
              <p className="text-[8px] opacity-60 leading-tight">Lv.{m.level}</p>
            </div>
          </button>
        );
      })}
    </div>
  );
}
