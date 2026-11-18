"use client";

import { useGame } from '@/store/GameContext';
import { sceneUrl, regionSlideUrl, SceneKind } from '@/lib/apiClient';
import { usePrefs } from '@/lib/prefs';

const SLOT: Record<SceneKind, (region: string) => string> = {
  region: (r) => `region_${r}`,
  route: () => 'route',
  town: () => 'town',
  care: () => 'care_center',
  lab: () => 'starter_lab',
};

/**
 * One scene picture. Priority: an image the admin set for this slot -> the procedural pixel scene drawn by
 * the API (animated GIF, or a still when cutscenes are off).
 */
export function SceneImage({
  kind, region = 'kanto', slide = false, className = '', alt = '',
}: { kind: SceneKind; region?: string; slide?: boolean; className?: string; alt?: string }) {
  const { assets, avatar } = useGame();
  const [prefs] = usePrefs();
  const override = assets[SLOT[kind](region)];
  const src = override ?? (slide ? regionSlideUrl(region) : sceneUrl(kind, region, avatar, prefs.cutscenes));
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      className={`w-full h-full object-cover ${className}`}
      style={{ imageRendering: 'pixelated' }}
      draggable={false}
    />
  );
}
