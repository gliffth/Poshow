// procedural retro SFX via Web Audio, no audio files needed ⤙•

let ctx: AudioContext | null = null;
let enabled = true;

function getCtx(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  if (!ctx) {
    const AudioCtor = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtor) return null;
    ctx = new AudioCtor();
  }
  // Browsers suspend the context until a user gesture resumes it.
  if (ctx.state === 'suspended') {
    ctx.resume().catch(() => {});
  }
  return ctx;
}

export function setSoundEnabled(value: boolean) {
  enabled = value;
}

export function isSoundEnabled(): boolean {
  return enabled;
}

interface ToneOpts {
  freq: number;
  duration: number;
  type?: OscillatorType;
  volume?: number;
  glideTo?: number;
  delay?: number;
}

function tone({ freq, duration, type = 'square', volume = 0.06, glideTo, delay = 0 }: ToneOpts) {
  if (!enabled) return;
  const audioCtx = getCtx();
  if (!audioCtx) return;

  const start = audioCtx.currentTime + delay;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, start);
  if (glideTo) {
    osc.frequency.linearRampToValueAtTime(glideTo, start + duration);
  }
  gain.gain.setValueAtTime(volume, start);
  gain.gain.exponentialRampToValueAtTime(0.001, start + duration);
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start(start);
  osc.stop(start + duration + 0.02);
}

export const sfx = {
  menuMove: () => tone({ freq: 320, duration: 0.05, type: 'square', volume: 0.04 }),
  menuSelect: () => tone({ freq: 520, duration: 0.08, type: 'square', volume: 0.06 }),
  menuBack: () => tone({ freq: 220, duration: 0.07, type: 'square', volume: 0.05 }),
  moveUsed: () => tone({ freq: 200, duration: 0.12, type: 'sawtooth', volume: 0.07, glideTo: 90 }),
  hit: () => tone({ freq: 140, duration: 0.1, type: 'square', volume: 0.09, glideTo: 60 }),
  superEffective: () => {
    tone({ freq: 660, duration: 0.08, volume: 0.07 });
    tone({ freq: 880, duration: 0.1, volume: 0.07, delay: 0.08 });
  },
  faint: () => tone({ freq: 300, duration: 0.4, type: 'sawtooth', volume: 0.08, glideTo: 40 }),
  catchSuccess: () => {
    tone({ freq: 440, duration: 0.09, volume: 0.07 });
    tone({ freq: 660, duration: 0.09, volume: 0.07, delay: 0.1 });
    tone({ freq: 880, duration: 0.15, volume: 0.07, delay: 0.2 });
  },
  catchFail: () => tone({ freq: 200, duration: 0.2, type: 'sawtooth', volume: 0.07, glideTo: 100 }),
  levelUp: () => {
    tone({ freq: 523, duration: 0.08, volume: 0.07 });
    tone({ freq: 659, duration: 0.08, volume: 0.07, delay: 0.09 });
    tone({ freq: 784, duration: 0.08, volume: 0.07, delay: 0.18 });
    tone({ freq: 1046, duration: 0.18, volume: 0.07, delay: 0.27 });
  },
  coin: () => tone({ freq: 988, duration: 0.06, volume: 0.05, glideTo: 1318 }),
  error: () => tone({ freq: 150, duration: 0.15, type: 'square', volume: 0.06 }),
};
