// Short definitions for the "?" hints. Keep this list small: a hint is for a term a new player may not know.
export const GLOSSARY = {
  'trade-cable': { label: 'Trade Cable', text: 'A cable that makes a trade happen even when nobody is on the other end.' },
  'care-center': { label: 'Care Center', text: 'Nurse Joy will take it from here.' },
  'held-item': { label: 'Held item', text: 'Something a Pokémon carries into battle. Each one holds a single item.' },
  'storage': { label: 'Team and storage', text: 'Your team fights beside you. Every other Pokémon waits in storage until you swap it in.' },
  'dex-seen': { label: 'Seen and caught', text: 'Seen means you met it. Caught means it is yours.' },
  'exp-all': { label: 'EXP All', text: 'Shares the XP from a win across your whole team.' },
  'rare-candy': { label: 'Rare Candy', text: 'Lifts a Pokémon up one level.' },
  'daily-quest': { label: 'Daily quests', text: 'These start over each day. Claim what you earned before they reset.' },
  'cold-start': { label: 'Waking up', text: 'The server has been asleep. Give it a moment to wake.' },
} as const;

export type GlossaryId = keyof typeof GLOSSARY;
