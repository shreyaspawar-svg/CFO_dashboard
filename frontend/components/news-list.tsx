"use client";

import { useEvents } from "@/lib/queries";

interface NewsItem {
  title?: string;
  link?: string;
  publisher?: string;
  providerPublishTime?: number;
}

export function NewsList({ symbol }: { symbol: string }) {
  const { data: events, isLoading } = useEvents(symbol);

  if (isLoading || !events) {
    return <div className="h-32 animate-pulse rounded-lg border border-border bg-surface" />;
  }

  const items = (events.news as unknown as NewsItem[]).filter((n) => n.title);

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <h3 className="mb-3 text-sm font-medium">News</h3>
      {items.length === 0 ? (
        <p className="text-xs text-muted">No recent headlines from this data source.</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 8).map((item, i) => (
            <li key={i} className="text-sm">
              {item.link ? (
                <a
                  href={item.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-accent hover:underline"
                >
                  {item.title}
                </a>
              ) : (
                <span>{item.title}</span>
              )}
              {item.publisher && <span className="ml-1 text-xs text-muted">&middot; {item.publisher}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
