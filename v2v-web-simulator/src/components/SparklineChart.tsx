interface SparklineProps { data: number[]; color?: string; label?: string; unit?: string }

export function SparklineChart({ data, color = "#22d3ee", label = "", unit = "" }: SparklineProps) {
  if (data.length < 2) return null;
  const w = 130, h = 36;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = Math.max(max - min, 0.1);
  const pts = data.map((v, i) =>
    `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * h}`
  ).join(' ');
  const last = data[data.length - 1];
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex justify-between text-[10px] font-mono text-gray-500">
        <span>{label}</span>
        <span style={{ color }}>{last.toFixed(1)}{unit}</span>
      </div>
      <svg width={w} height={h} className="rounded bg-gray-900/60">
        <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
      </svg>
    </div>
  );
}
