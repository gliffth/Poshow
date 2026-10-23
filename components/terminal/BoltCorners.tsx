interface BoltCornersProps {
  size?: number; // px, in case of tighter panels
}

// four screw-head corners for that bolted-metal look, parent needs relative ⚙
export function BoltCorners({ size = 10 }: BoltCornersProps) {
  const style = { width: size, height: size };
  const corners = [
    'top-1 left-1',
    'top-1 right-1',
    'bottom-1 left-1',
    'bottom-1 right-1',
  ];

  return (
    <>
      {corners.map((pos) => (
        <div
          key={pos}
          className={`bolt-icon absolute ${pos} rounded-full pointer-events-none`}
          style={style}
        />
      ))}
    </>
  );
}
