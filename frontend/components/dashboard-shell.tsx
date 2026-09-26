"use client";

import { useSelection } from "@/hooks/use-selection";
import { TopBar } from "@/components/top-bar";
import { CompanyHeader } from "@/components/company-header";
import { KpiRow } from "@/components/kpi-row";
import { TabsShell } from "@/components/tabs-shell";
import { ErrorBoundary } from "@/components/error-boundary";
import { CompanyHeaderSkeleton, KpiRowSkeleton, TabsShellSkeleton } from "@/components/skeletons";

export function DashboardShell() {
  const { isLoading, currentSectorName, currentCompany } = useSelection();

  return (
    <div className="flex min-h-screen flex-col">
      <ErrorBoundary region="top bar">
        <TopBar />
      </ErrorBoundary>

      <main className="mx-auto w-full max-w-6xl flex-1 space-y-4 px-4 py-4 sm:px-6">
        {isLoading || !currentCompany || !currentSectorName ? (
          <>
            <CompanyHeaderSkeleton />
            <KpiRowSkeleton />
            <TabsShellSkeleton />
          </>
        ) : (
          <>
            <ErrorBoundary region="company header">
              <CompanyHeader company={currentCompany} sectorName={currentSectorName} />
            </ErrorBoundary>
            <ErrorBoundary region="KPI row">
              <KpiRow symbol={currentCompany.symbol} template={currentCompany.template} />
            </ErrorBoundary>
            <ErrorBoundary region="tabs">
              <TabsShell />
            </ErrorBoundary>
          </>
        )}
      </main>
    </div>
  );
}
