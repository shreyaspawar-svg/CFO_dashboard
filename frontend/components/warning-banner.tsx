import { AlertTriangle } from "lucide-react";

export function WarningBanner({ notes }: { notes: string[] }) {
  if (notes.length === 0) return null;

  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border px-3 py-2 text-sm"
      style={{
        backgroundColor: "var(--warning-bg)",
        borderColor: "var(--warning-border)",
        color: "var(--warning-foreground)",
      }}
    >
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <div className="space-y-1">
        {notes.map((note, i) => (
          <p key={i}>{note}</p>
        ))}
      </div>
    </div>
  );
}
