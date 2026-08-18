interface TTCRingProps { ttc: number | null; size?: number }

export function TTCRing({ ttc, size = 72 }: TTCRingProps) {
  const maxTTC = 8;
  const valid = ttc !== null && isFinite(ttc);
  const pct = valid ? Math.min(1, (ttc as number) / maxTTC) : 1;
  const r = size * 0.4;
  const cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  const dash = pct * circ;
  const color = pct < 0.25 ? '#ef4444' : pct < 0.5 ? '#f97316' : pct < 0.75 ? '#facc15' : '#22d3ee';
  const label = valid ? `${(ttc as number).toFixed(1)}s` : '—';

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#374151" strokeWidth={6} />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth={6}
          strokeDasharray={`${dash} ${circ}`} strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`}
          style={{ transition: 'stroke-dasharray 0.3s, stroke 0.3s' }} />
        <text x={cx} y={cy + 4} textAnchor="middle" fill={color}
          fontSize={size < 60 ? 10 : 13} fontFamily="monospace" fontWeight="bold">
          {label}
        </text>
      </svg>
      <span className="text-[10px] text-gray-500 font-mono">TTC</span>
    </div>
  );
}
