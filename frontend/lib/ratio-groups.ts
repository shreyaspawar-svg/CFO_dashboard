import type { KpiDef, Template } from "@/lib/kpi-templates";

export interface RatioGroup {
  label: string;
  ratios: KpiDef[];
}

/** Template-aware ratio card groups for the Ratios tab (PLAN.md §4.3 item
 * 1) -- a superset, organised, of the single-row KPI list in
 * `kpi-templates.ts`. `available: false` entries render as "—" with "Not
 * in free data source", same convention as the KPI row. */
const RATIO_GROUPS: Record<Template, RatioGroup[]> = {
  general: [
    {
      label: "Profitability",
      ratios: [
        { key: "gross_margin", label: "Gross margin", available: true, format: "percent" },
        { key: "ebitda_margin", label: "EBITDA margin", available: true, format: "percent" },
        { key: "ebit_margin", label: "EBIT margin", available: true, format: "percent" },
        { key: "pat_margin", label: "PAT margin", available: true, format: "percent" },
      ],
    },
    {
      label: "Returns",
      ratios: [
        { key: "roe", label: "ROE", available: true, format: "percent" },
        { key: "roce", label: "ROCE", available: true, format: "percent" },
        { key: "roic", label: "ROIC", available: true, format: "percent" },
        { key: "roa", label: "ROA", available: true, format: "percent" },
      ],
    },
    {
      label: "Leverage",
      ratios: [
        { key: "debt_to_equity", label: "D/E", available: true, format: "multiple" },
        { key: "net_debt_to_ebitda", label: "Net debt/EBITDA", available: true, format: "multiple" },
        { key: "interest_coverage", label: "Interest coverage", available: true, format: "multiple" },
        { key: "debt_to_assets", label: "Debt/Assets", available: true, format: "multiple" },
      ],
    },
    {
      label: "Liquidity",
      ratios: [
        { key: "current_ratio", label: "Current ratio", available: true, format: "multiple" },
        { key: "quick_ratio", label: "Quick ratio", available: true, format: "multiple" },
        { key: "cash_ratio", label: "Cash ratio", available: true, format: "multiple" },
      ],
    },
    {
      label: "Efficiency",
      ratios: [
        { key: "asset_turnover", label: "Asset turnover", available: true, format: "multiple" },
        { key: "inventory_days", label: "Inventory days", available: true, format: "days" },
        { key: "debtor_days", label: "Debtor days", available: true, format: "days" },
        { key: "payable_days", label: "Payable days", available: true, format: "days" },
        { key: "cash_conversion_cycle", label: "Cash conversion cycle", available: true, format: "days" },
      ],
    },
    {
      label: "Cash flow",
      ratios: [
        { key: "fcf_margin", label: "FCF margin", available: true, format: "percent" },
        { key: "cfo_to_pat", label: "CFO/PAT", available: true, format: "multiple" },
        { key: "capex_intensity", label: "Capex intensity", available: true, format: "percent" },
      ],
    },
  ],
  exchange: [
    {
      label: "Profitability",
      ratios: [
        { key: "ebitda_margin", label: "EBITDA margin", available: true, format: "percent" },
        { key: "pat_margin", label: "PAT margin", available: true, format: "percent" },
      ],
    },
    {
      label: "Returns",
      ratios: [
        { key: "roe", label: "ROE", available: true, format: "percent" },
        { key: "roce", label: "ROCE", available: true, format: "percent" },
      ],
    },
    {
      label: "Leverage",
      ratios: [
        { key: "debt_to_equity", label: "D/E", available: true, format: "multiple" },
        { key: "interest_coverage", label: "Interest coverage", available: true, format: "multiple" },
      ],
    },
    {
      label: "Liquidity",
      ratios: [{ key: "current_ratio", label: "Current ratio", available: true, format: "multiple" }],
    },
    {
      label: "Efficiency",
      ratios: [{ key: "asset_turnover", label: "Asset turnover", available: true, format: "multiple" }],
    },
  ],
  bank: [
    {
      label: "Profitability & returns",
      ratios: [
        { key: "nim", label: "NIM (derived)", available: true, format: "percent" },
        { key: "cost_to_income", label: "Cost-to-income", available: true, format: "percent" },
        { key: "roa", label: "ROA", available: true, format: "percent" },
        { key: "roe", label: "ROE", available: true, format: "percent" },
      ],
    },
    {
      label: "Growth",
      ratios: [
        { key: "nii_growth", label: "NII growth", available: true, format: "percent" },
        { key: "pat_growth", label: "PAT growth", available: true, format: "percent" },
      ],
    },
    {
      label: "Valuation",
      ratios: [{ key: "pb", label: "P/B", available: true, format: "multiple" }],
    },
    {
      label: "Not in free data source",
      ratios: [
        { key: "gnpa", label: "GNPA", available: false, format: "percent" },
        { key: "nnpa", label: "NNPA", available: false, format: "percent" },
        { key: "casa", label: "CASA", available: false, format: "percent" },
        { key: "credit_cost", label: "Credit cost", available: false, format: "percent" },
      ],
    },
  ],
  nbfc: [
    {
      label: "Profitability & returns",
      ratios: [
        { key: "nim", label: "NIM (derived)", available: true, format: "percent" },
        { key: "cost_to_income", label: "Cost-to-income", available: true, format: "percent" },
        { key: "roa", label: "ROA", available: true, format: "percent" },
        { key: "roe", label: "ROE", available: true, format: "percent" },
      ],
    },
    {
      label: "Growth",
      ratios: [
        { key: "nii_growth", label: "NII growth", available: true, format: "percent" },
        { key: "pat_growth", label: "PAT growth", available: true, format: "percent" },
      ],
    },
    {
      label: "Valuation",
      ratios: [{ key: "pb", label: "P/B", available: true, format: "multiple" }],
    },
  ],
  insurance: [
    {
      label: "Growth & profitability",
      ratios: [
        { key: "premium_growth", label: "Premium growth", available: true, format: "percent" },
        { key: "pat_margin", label: "PAT margin", available: true, format: "percent" },
        { key: "roe", label: "ROE", available: true, format: "percent" },
      ],
    },
    {
      label: "Valuation",
      ratios: [{ key: "pb", label: "P/B", available: true, format: "multiple" }],
    },
    {
      label: "Not in free data source",
      ratios: [
        { key: "p_ev", label: "P/EV", available: false, format: "multiple" },
        { key: "solvency_ratio", label: "Solvency", available: false, format: "percent" },
      ],
    },
  ],
};

export function ratioGroupsFor(template: string): RatioGroup[] {
  return RATIO_GROUPS[template as Template] ?? RATIO_GROUPS.general;
}
