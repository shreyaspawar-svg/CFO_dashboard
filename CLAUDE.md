# Project: NIFTY 50 CFO Dashboard
- Always read PLAN.md first; implement only the phase requested.
- Backend: Python 3.12, FastAPI, Pydantic v2, yfinance. Frontend: Next.js 15 App Router, TS strict, Tailwind, shadcn/ui, ECharts, TanStack Query, Zustand.
- Money in ₹ crore internally; format with Indian digit grouping in the UI. Fiscal year = Apr–Mar, label "FY24".
- Missing data is null, never 0. Surface warnings to the UI.
- All ratio logic lives in backend/app/metrics as pure, tested functions. No financial maths in React components.
- Every API response includes source, as_of, warnings[].
- Run tests before declaring a task done. Summarise changes and open questions at the end of each phase.
