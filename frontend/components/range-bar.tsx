import { formatRange } from "@/lib/format";

export function RangeBar({
  low,
  high,
  current,
  label,
}: {
  low: number | null | undefined;
  high: number | null | undefined;
  current: number | null | undefined;
  label: string;
}) {
  const hasData =
    low !== null && low !== undefined && high !== null && high !== undefined && high > low;
  const position =
    hasData && current !== null && current !== undefined
      ? Math.min(100, Math.max(0, ((current - low) / (high - low)) * 100))
      : null;

  return (
    <div className="min-w-0">
      <div className="mb-1 flex items-center justify-between text-xs text-muted">
        <span>{label}</span>
        <span className="tabular-nums-fixed">{formatRange(low, high)}</span>
      </div>
      <div className="relative h-1.5 w-full rounded-full bg-surface-raised">
        {position !== null && (
          <span
            className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-accent"
            style={{ left: `${position}%` }}
            aria-hidden
          />
        )}
      </div>
    </div>
  );
}
