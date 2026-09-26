import { cn } from "@/lib/utils";

function Bone({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded bg-surface-raised", className)} />;
}

export function CompanyHeaderSkeleton() {
  return (
    <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center gap-3">
        <Bone className="h-8 w-8 rounded-full" />
        <div className="space-y-2">
          <Bone className="h-4 w-40" />
          <Bone className="h-3 w-24" />
        </div>
        <div className="ml-auto space-y-2 text-right">
          <Bone className="h-6 w-28" />
          <Bone className="h-3 w-20" />
        </div>
      </div>
      <Bone className="h-1.5 w-full" />
    </div>
  );
}

export function KpiRowSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="rounded-lg border border-border bg-surface p-3">
          <Bone className="h-3 w-16" />
          <Bone className="mt-2 h-5 w-20" />
        </div>
      ))}
    </div>
  );
}

export function TabsShellSkeleton() {
  return (
    <div className="space-y-3 rounded-lg border border-border bg-surface p-4">
      <Bone className="h-4 w-32" />
      <Bone className="h-32 w-full" />
    </div>
  );
}
