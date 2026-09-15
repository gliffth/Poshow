import type {Metadata, Viewport} from 'next';
import { VT323, Press_Start_2P } from 'next/font/google';
import './globals.css'; // Global styles
import { GameProvider } from '@/store/GameContext';
import { ThemeSync } from '@/components/terminal/ThemeSync';

const vt323 = VT323({
  weight: '400',
  subsets: ['latin'],
  variable: '--font-retro',
});

const pressStart = Press_Start_2P({
  weight: '400',
  subsets: ['latin'],
  variable: '--font-pixel-family',
});

export const metadata: Metadata = {
  title: 'Poshow',
  description: 'A retro Pokémon battler',
};

// width=device-width + viewport-fit=cover: the app needs to render correctly
// inside notches/rounded corners on phones, and userScalable=false prevents
// accidental pinch-zoom from breaking the fixed game layout during play.
export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: 'cover',
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="en" data-theme="weathered" className={`${vt323.variable} ${pressStart.variable}`}>
      {/* h-dvh, not h-screen — 100vh doesn't track a mobile browser's address
          bar showing/hiding or update on orientation change, which is
          exactly what caused the overlap on phones. h-dvh does. */}
      <body suppressHydrationWarning className="font-retro h-dvh overflow-hidden bg-retro-bg text-retro-green relative selection:bg-retro-green selection:text-retro-bg">
        <GameProvider>
          <ThemeSync />
          <div className="absolute inset-0 z-0">
            {children}
          </div>
        </GameProvider>
      </body>
    </html>
  );
}
