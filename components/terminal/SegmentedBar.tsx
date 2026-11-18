import { ReactNode } from 'react';

interface SegmentedBarProps {
  value: number;
  max: number;
  segments?: number;
  label?: ReactNode;
  showNumbers?: boolean;
  alertBelow?: number; // fraction (0-1) under which the bar turns alert-colored
  height?: 'sm' | 'md';
  /** per-type hex accent, overrides the default ink fill */
  accentColor?: string;
}

export function SegmentedBar({
  value, max, segments = 10, label, showNumbers = true, alertBelow = 0.25, height = 'md', accentColor,
}: SegmentedBarProps) {
  const percent = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const filled = Math.round(percent * segments);
  const isAlert = percent < alertBelow;
  const barHeight = height === 'sm' ? 'h-2' : 'h-3';

  return (
    <div>
      {(label || showNumbers) && (
        <div className="flex justify-between text-sm mb-1">
          {label ? <span className="flex items-center gap-1">{label}</span> : <span />}
          {showNumbers && <span>{value} / {max}</span>}
        </div>
      )}
      <div className={`flex gap-[2px] ${barHeight}`}>
        {Array.from({ length: segments }).map((_, i) => {
          const isFilled = i < filled;
          const useAccent = isFilled && accentColor && !isAlert;
          return (
            <div
              key={i}
              className={`flex-1 transition-colors duration-300 ${
                isFilled
                  ? (isAlert ? 'bg-retro-alert box-glow-alert' : (useAccent ? '' : 'bg-retro-green box-glow'))
                  : 'bg-retro-green/10'
              }`}
              style={useAccent ? { backgroundColor: accentColor, boxShadow: `0 0 8px ${accentColor}66` } : undefined}
            />
          );
        })}
      </div>
    </div>
  );
}
