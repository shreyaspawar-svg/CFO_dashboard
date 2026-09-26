import { Suspense } from "react";
import { DashboardShell } from "@/components/dashboard-shell";

export default function Home() {
  return (
    <Suspense fallback={null}>
      <DashboardShell />
    </Suspense>
  );
}
