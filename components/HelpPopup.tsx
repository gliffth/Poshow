"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { HelpCircle } from 'lucide-react';

const OPEN_EVENT = 'poshow-help-open';
const WIDTH = 256;
const GAP = 8;

interface HelpPopupProps {
  id: string;
  label: string;
  children: ReactNode;
  pulse?: boolean;
  onOpen?: () => void;
  className?: string;
}

/** A small "?" button with a popover. Tap or click to open; tap outside, scroll or Esc to close. One open at a time. */
export function HelpPopup({ id, label, children, pulse = false, onOpen, className = '' }: HelpPopupProps) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);
  const btn = useRef<HTMLButtonElement>(null);
  const card = useRef<HTMLDivElement>(null);

  const close = useCallback(() => setOpen(false), []);

  useLayoutEffect(() => {
    if (!open || !btn.current) return;
    const r = btn.current.getBoundingClientRect();
    const width = Math.min(WIDTH, window.innerWidth - GAP * 2);
    const left = Math.max(GAP, Math.min(r.left + r.width / 2 - width / 2, window.innerWidth - width - GAP));
    const height = card.current?.offsetHeight ?? 96;
    const below = r.bottom + GAP;
    const top = below + height > window.innerHeight - GAP ? Math.max(GAP, r.top - GAP - height) : below;
    setPos({ top, left, width });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close(); };
    const onDown = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!card.current?.contains(t) && !btn.current?.contains(t)) close();
    };
    const onOther = (e: Event) => { if ((e as CustomEvent<string>).detail !== id) close(); };
    window.addEventListener('keydown', onKey);
    window.addEventListener('pointerdown', onDown);
    window.addEventListener('scroll', close, true);
    window.addEventListener('resize', close);
    window.addEventListener(OPEN_EVENT, onOther);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('pointerdown', onDown);
      window.removeEventListener('scroll', close, true);
      window.removeEventListener('resize', close);
      window.removeEventListener(OPEN_EVENT, onOther);
    };
  }, [open, id, close]);

  function toggle() {
    if (open) { close(); return; }
    window.dispatchEvent(new CustomEvent(OPEN_EVENT, { detail: id }));
    setPos(null);
    setOpen(true);
    onOpen?.();
  }

  return (
    <>
      <button
        ref={btn}
        type="button"
        onClick={toggle}
        aria-label={label}
        aria-expanded={open}
        className={`inline-flex items-center justify-center align-middle opacity-60 hover:opacity-100 focus-visible:opacity-100 ${pulse ? 'animate-pulse opacity-100' : ''} ${className}`}
      >
        <HelpCircle size={14} />
      </button>
      {open && (
        <div
          ref={card}
          role="dialog"
          aria-label={label}
          style={{ position: 'fixed', top: pos?.top ?? -9999, left: pos?.left ?? 0, width: pos?.width ?? WIDTH, visibility: pos ? 'visible' : 'hidden' }}
          className="z-50 border-2 border-retro-green bg-retro-dark p-3 text-sm normal-case tracking-normal leading-snug shadow-lg"
        >
          {children}
        </div>
      )}
    </>
  );
}
