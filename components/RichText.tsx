import type { ReactNode } from 'react';
import {
  Backpack, Book, Bug, CircleDot, Compass, Flame, Handshake, Heart, Link2, Map as MapIcon, MessageCircle, ScrollText,
  Shield, ShoppingBag, Sparkles, Star, Swords, Trophy, Users, Zap,
} from 'lucide-react';
import { parseRich, type Inline, type RichIcon } from '@/lib/richText';

const ICON: Record<RichIcon, React.ComponentType<{ size?: number; className?: string }>> = {
  book: Book, map: MapIcon, sword: Swords, ball: CircleDot, backpack: Backpack, users: Users, star: Star, scroll: ScrollText,
  shield: Shield, bug: Bug, link: Link2, sparkles: Sparkles, shopping: ShoppingBag, handshake: Handshake, message: MessageCircle,
  trophy: Trophy, heart: Heart, compass: Compass, flame: Flame, zap: Zap,
};

export function IconByName({ name, size = 16, className }: { name: string; size?: number; className?: string }) {
  const Icon = ICON[name as RichIcon] ?? Book;
  return <Icon size={size} className={className} />;
}

function inline(nodes: Inline[]): ReactNode[] {
  return nodes.map((n, i) => {
    switch (n.t) {
      case 'bold': return <strong key={i}>{n.v}</strong>;
      case 'italic': return <em key={i}>{n.v}</em>;
      case 'icon': return <IconByName key={i} name={n.name} size={14} className="inline align-text-bottom mx-0.5" />;
      case 'link':
        return <a key={i} href={n.href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:opacity-80">{n.label}</a>;
      default: return n.v;
    }
  });
}

const lines = (rows: Inline[][]): ReactNode[] =>
  rows.flatMap((row, i) => (i ? [<br key={`br${i}`} />, ...inline(row)] : inline(row)));

/** Renders the guide's mini markup. Everything goes through React elements, never raw HTML. */
export function RichText({ source, className = '' }: { source: string; className?: string }) {
  return (
    <div className={`space-y-2 text-sm leading-relaxed ${className}`}>
      {parseRich(source).map((b, i) => {
        switch (b.t) {
          case 'h': return <h3 key={i} className="uppercase tracking-wide text-xs opacity-80 pt-1">{inline(b.inlines)}</h3>;
          case 'ul': return <ul key={i} className="list-disc pl-5 space-y-0.5">{b.items.map((it, j) => <li key={j}>{inline(it)}</li>)}</ul>;
          case 'note': return <blockquote key={i} className="border-l-2 border-retro-green pl-3 py-1 bg-retro-green/10">{lines(b.lines)}</blockquote>;
          default: return <p key={i}>{lines(b.lines)}</p>;
        }
      })}
    </div>
  );
}
