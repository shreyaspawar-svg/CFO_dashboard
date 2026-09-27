"use client";

import type { EChartsOption } from "echarts";
import { useTheme } from "next-themes";
import { useEvents } from "@/lib/queries";
import { ChartCard } from "@/components/charts/chart-card";
import { chartThemeFor } from "@/lib/chart-theme";

export function ShareholdingEventsTab({ symbol }: { symbol: string; template: string }) {
  const { data: events, isLoading } = useEvents(symbol);
  const { resolvedTheme } = useTheme();
  const theme = chartThemeFor(resolvedTheme);

  if (isLoading || !events) {
    return <div className="h-80 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  const dividendOption: EChartsOption | null =
    events.dividends.length > 0
      ? {
          grid: { left: 56, right: 56, top: 40, bottom: 60 },
          legend: { top: 0, left: "center", data: ["Dividend/share", "Approx. yield"] },
          xAxis: {
            type: "category",
            data: events.dividends.map((d) => d.date),
            axisLabel: { color: theme.muted, rotate: 45 },
          },
          yAxis: [
            { type: "value", name: "₹/share", axisLabel: { color: theme.muted } },
            { type: "value", name: "%", axisLabel: { color: theme.muted }, splitLine: { show: false } },
          ],
          series: [
            { name: "Dividend/share", type: "bar", data: events.dividends.map((d) => d.amount) },
            { name: "Approx. yield", type: "line", yAxisIndex: 1, data: events.dividends.map((d) => d.yield_pct ?? null) },
          ],
        }
      : null;

  return (
    <div className="space-y-4">
      {dividendOption ? (
        <ChartCard
          title="Dividend history"
          subtitle="Yield is an approximation: amount / current price, not the price on the payment date"
          option={dividendOption}
          height={300}
          csv={{
            filename: `${symbol}_dividends.csv`,
            headers: ["Date", "Amount", "Approx yield %"],
            rows: events.dividends.map((d) => [d.date, d.amount, d.yield_pct ?? null]),
          }}
        />
      ) : (
        <p className="text-sm text-muted">No dividend history available.</p>
      )}

      <div className="rounded-lg border border-border bg-surface p-4">
        <h3 className="mb-2 text-sm font-medium">Splits & bonuses</h3>
        {events.splits.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {events.splits.map((s) => (
              <li key={s.date} className="flex justify-between border-b border-border/50 py-1">
                <span>{s.date}</span>
                <span className="tabular-nums-fixed">
                  {s.numerator}:{s.denominator}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">No splits/bonuses on record.</p>
        )}
      </div>

      <div className="rounded-lg border border-border bg-surface p-4">
        <h3 className="mb-2 text-sm font-medium">Next earnings date</h3>
        <p className="text-sm text-muted">
          {events.next_earnings_date ?? "Not available from free sources (requires a Yahoo crumb this app doesn't rely on)"}
        </p>
      </div>

      <div className="rounded-lg border border-border bg-surface p-4">
        <h3 className="mb-2 text-sm font-medium">Shareholding pattern (promoter / FII / DII / public)</h3>
        {events.shareholding ? (
          <pre className="overflow-x-auto text-xs">{JSON.stringify(events.shareholding, null, 2)}</pre>
        ) : (
          <p className="text-sm text-muted">Not available from free sources (NSE blocks this deployment&apos;s IP).</p>
        )}
      </div>

      <div className="rounded-lg border border-border bg-surface p-4">
        <h3 className="mb-2 text-sm font-medium">News</h3>
        {events.news.length > 0 ? (
          <ul className="space-y-2 text-sm">
            {events.news.slice(0, 10).map((n, i) => {
              const item = n as { title?: string; link?: string; publisher?: string };
              return (
                <li key={i} className="border-b border-border/50 pb-2">
                  {item.link ? (
                    <a href={item.link} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                      {item.title ?? "Untitled"}
                    </a>
                  ) : (
                    <span>{item.title ?? "Untitled"}</span>
                  )}
                  {item.publisher && <span className="ml-2 text-xs text-muted">{item.publisher}</span>}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-sm text-muted">No recent news available.</p>
        )}
      </div>
    </div>
  );
}
