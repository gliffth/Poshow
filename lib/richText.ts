// Mini markup for the guide: ## heading, - list, > note, **bold**, *italic*, [label](https://…), :icon:.
// It only ever produces data; the renderer builds elements from it, so no HTML is ever injected.

export const RICH_ICONS = [
  'book', 'map', 'sword', 'ball', 'backpack', 'users', 'star', 'scroll', 'shield', 'bug', 'link', 'sparkles',
  'shopping', 'handshake', 'message', 'trophy', 'heart', 'compass', 'flame', 'zap',
] as const;
export type RichIcon = (typeof RICH_ICONS)[number];

export type Inline =
  | { t: 'text' | 'bold' | 'italic'; v: string }
  | { t: 'link'; label: string; href: string }
  | { t: 'icon'; name: RichIcon };

export type Block =
  | { t: 'h'; inlines: Inline[] }
  | { t: 'p'; lines: Inline[][] }
  | { t: 'ul'; items: Inline[][] }
  | { t: 'note'; lines: Inline[][] };

const TOKEN = /(\*\*(?!\s)[^*\n]*[^*\s]\*\*|\*(?!\s)[^*\n]*[^*\s]\*|\[[^\]\n]+\]\([^)\n]*\)|:[a-z]+:)/g;

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  for (const part of text.split(TOKEN)) {
    if (!part) continue;
    let m: RegExpMatchArray | null;
    if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
      out.push({ t: 'bold', v: part.slice(2, -2) });
    } else if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      out.push({ t: 'italic', v: part.slice(1, -1) });
    } else if ((m = part.match(/^\[([^\]]+)\]\(([^)]*)\)$/))) {
      const href = m[2].trim();
      out.push(href.startsWith('https://') ? { t: 'link', label: m[1], href } : { t: 'text', v: m[1] });
    } else if ((m = part.match(/^:([a-z]+):$/)) && (RICH_ICONS as readonly string[]).includes(m[1])) {
      out.push({ t: 'icon', name: m[1] as RichIcon });
    } else {
      out.push({ t: 'text', v: part });
    }
  }
  return out;
}

export function parseRich(source: string): Block[] {
  const blocks: Block[] = [];
  for (const chunk of source.replace(/\r\n?/g, '\n').split(/\n{2,}/)) {
    const lines = chunk.split('\n').filter((l) => l.trim() !== '');
    let i = 0;
    while (i < lines.length) {
      const line = lines[i];
      if (line.startsWith('## ')) {
        blocks.push({ t: 'h', inlines: parseInline(line.slice(3).trim()) });
        i++;
      } else if (line.startsWith('- ')) {
        const items: Inline[][] = [];
        while (i < lines.length && lines[i].startsWith('- ')) items.push(parseInline(lines[i++].slice(2).trim()));
        blocks.push({ t: 'ul', items });
      } else if (line.startsWith('>')) {
        const quoted: Inline[][] = [];
        while (i < lines.length && lines[i].startsWith('>')) quoted.push(parseInline(lines[i++].replace(/^>\s?/, '').trim()));
        blocks.push({ t: 'note', lines: quoted });
      } else {
        const para: Inline[][] = [];
        while (i < lines.length && !/^(## |- |>)/.test(lines[i])) para.push(parseInline(lines[i++].trim()));
        blocks.push({ t: 'p', lines: para });
      }
    }
  }
  return blocks;
}
