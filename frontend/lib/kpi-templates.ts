/**
 * Headline KPI cards per business-model template (PLAN.md §2). Mirrors
 * backend/app/metrics/templates.py's KPI_DEFINITIONS exactly -- keep the
 * two in sync if either changes. `available: false` entries are metrics
 * this free data source can't provide (credit cost, GNPA/NNPA, AUM
 * growth, P/EV, solvency ratio): still shown as a card, but always "Not
 * in free data source", never a fabricated number.
 */

export type Template = "bank" | "nbfc" | "insurance" | "exchange" | "general";

export interface KpiDef {
  key: string;
  label: string;
  available: boolean;
  /** How to format the value -- most ratios are percentages; a few are multiples. */
  format: "percent" | "multiple" | "crore" | "days";
}

const KPI_DEFINITIONS: Record<Template, KpiDef[]> = {
  bank: [
    { key: "nii_growth", label: "NII growth", available: true, format: "percent" },
    { key: "nim", label: "NIM (derived)", available: true, format: "percent" },
    { key: "cost_to_income", label: "Cost-to-income", available: true, format: "percent" },
    { key: "roa", label: "ROA", available: true, format: "percent" },
    { key: "roe", label: "ROE", available: true, format: "percent" },
    { key: "pb", label: "P/B", available: true, format: "multiple" },
    { key: "advances_deposits_growth", label: "Advances & deposits growth", available: false, format: "percent" },
    { key: "credit_cost", label: "Credit cost", available: false, format: "percent" },
    { key: "gnpa_nnpa", label: "GNPA/NNPA", available: false, format: "percent" },
  ],
  nbfc: [
    { key: "aum_growth", label: "AUM/loan growth", available: false, format: "percent" },
    { key: "nim", label: "NIM (derived)", available: true, format: "percent" },
    { key: "roa", label: "ROA", available: true, format: "percent" },
    { key: "roe", label: "ROE", available: true, format: "percent" },
    { key: "pb", label: "P/B", available: true, format: "multiple" },
    { key: "debt_to_equity", label: "D/E", available: true, format: "multiple" },
  ],
  insurance: [
    { key: "premium_growth", label: "Premium growth", available: true, format: "percent" },
    { key: "p_ev", label: "P/EV", available: false, format: "multiple" },
    { key: "roe", label: "ROE", available: true, format: "percent" },
    { key: "solvency_ratio", label: "Solvency", available: false, format: "percent" },
    { key: "pb", label: "P/B", available: true, format: "multiple" },
  ],
  exchange: [
    { key: "revenue_growth", label: "Revenue growth", available: true, format: "percent" },
    { key: "ebitda_margin", label: "EBITDA margin", available: true, format: "percent" },
    { key: "pat_margin", label: "PAT margin", available: true, format: "percent" },
    { key: "roe", label: "ROE", available: true, format: "percent" },
    { key: "pe", label: "P/E", available: true, format: "multiple" },
  ],
  general: [
    { key: "revenue_growth", label: "Revenue growth", available: true, format: "percent" },
    { key: "ebitda_growth", label: "EBITDA growth", available: true, format: "percent" },
    { key: "pat_growth", label: "PAT growth", available: true, format: "percent" },
    { key: "ebitda_margin", label: "EBITDA margin", available: true, format: "percent" },
    { key: "roce", label: "ROCE", available: true, format: "percent" },
    { key: "roe", label: "ROE", available: true, format: "percent" },
    { key: "debt_to_equity", label: "D/E", available: true, format: "multiple" },
    { key: "interest_coverage", label: "Interest coverage", available: true, format: "multiple" },
    { key: "cash_conversion_cycle", label: "Working-capital days", available: true, format: "days" },
    { key: "fcf", label: "FCF", available: true, format: "crore" },
    { key: "ev_ebitda", label: "EV/EBITDA", available: true, format: "multiple" },
    { key: "pe", label: "P/E", available: true, format: "multiple" },
  ],
};

export function headlineKpis(template: string): KpiDef[] {
  return KPI_DEFINITIONS[template as Template] ?? KPI_DEFINITIONS.general;
}
