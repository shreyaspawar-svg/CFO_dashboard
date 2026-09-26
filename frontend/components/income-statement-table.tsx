"use client";

import { useState } from "react";
import { formatCrore, formatPercent, formatRupees } from "@/lib/format";
import { computeSeriesCagr, type FinancialPeriodLite } from "@/lib/income-statement";

interface RowDef {
  key: string;
  label: string;
  core: boolean;
  isPerShare?: boolean;
}

const ROWS: RowDef[] = [
  { key: "revenue", label: "Revenue", core: true },
  { key: "cogs", label: "Cost of revenue", core: false },
  { key: "gross_profit", label: "Gross profit", core: false },
  { key: "ebitda", label: "EBITDA", core: true },
  { key: "ebit", label: "EBIT", core: false },
  { key: "operating_income", label: "Operating income", core: false },
  { key: "d_and_a", label: "Depreciation & amortisation", core: false },
  { key: "interest_expense", label: "Interest expense", core: false },
  { key: "pretax_income", label: "Pretax income", core: false },
  { key: "tax", label: "Tax", core: false },
  { key: "net_income", label: "Net income (PAT)", core: true },
  { key: "eps_diluted", label: "EPS (diluted)", core: true, isPerShare: true },
  { key: "eps_basic", label: "EPS (basic)", core: false, isPerShare: true },
  { key: "net_interest_income", label: "Net interest income", core: false },
  { key: "non_interest_income", label: "Non-interest income", core: false },
  { key: "non_interest_expense", label: "Non-interest expense", core: false },
  { key: "premiums_earned", label: "Premiums earned", core: false },
];

/** All mapped income-statement line items across every comparable period,
 * plus a CAGR column (PLAN.md §4.2). Collapsed to the core rows by
 * default -- expanding reveals every other mapped field, which is mostly
 * `null`/"—" for a template it doesn't apply to (never hidden, since a
 * bank's absent COGS is itself informative, not just clutter). */
export function IncomeStatementTable({
  periods,
  comparableFrom,
}: {
  periods: FinancialPeriodLite[];
  comparableFrom: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const rows = expanded ? ROWS : ROWS.filter((r) => r.core);
  const rowsWithData = rows.filter((r) => periods.some((p) => p.line_items[r.key] != null));

  if (periods.length === 0) {
    return <p className="text-sm text-muted">No comparable periods available.</p>;
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-medium">Income statement detail</h3>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="text-xs text-accent hover:underline"
        >
          {expanded ? "Show fewer rows" : "Show all line items"}
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted">
              <th className="py-1.5 pr-4 font-normal">Line item</th>
              {periods.map((p) => (
                <th key={p.period_end} className="py-1.5 px-2 text-right font-normal tabular-nums-fixed">
                  {p.fiscal_year}
                </th>
              ))}
              <th className="py-1.5 pl-2 text-right font-normal">CAGR</th>
            </tr>
          </thead>
          <tbody>
            {rowsWithData.length === 0 && (
              <tr>
                <td colSpan={periods.length + 2} className="py-3 text-center text-muted">
                  No data for the selected rows.
                </td>
              </tr>
            )}
            {rowsWithData.map((row) => {
              const cagr = computeSeriesCagr(periods, row.key, comparableFrom);
              const fmt = row.isPerShare ? formatRupees : formatCrore;
              return (
                <tr key={row.key} className="border-b border-border/50">
                  <td className="py-1.5 pr-4">{row.label}</td>
                  {periods.map((p) => (
                    <td key={p.period_end} className="py-1.5 px-2 text-right tabular-nums-fixed">
                      {fmt(p.line_items[row.key] ?? null)}
                    </td>
                  ))}
                  <td className="py-1.5 pl-2 text-right tabular-nums-fixed text-muted">{formatPercent(cagr, 1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
