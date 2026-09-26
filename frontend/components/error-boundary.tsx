"use client";

import { Component, type ReactNode } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  /** Label for what failed, shown in the fallback (e.g. "company header"). */
  region: string;
}

interface State {
  hasError: boolean;
}

/**
 * One data-fetching region failing shouldn't blank the whole page (task
 * 3.9) -- each major section (header, KPI row, each tab) gets its own
 * boundary so the rest of the dashboard keeps working.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error(`[${this.props.region}] failed to render:`, error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4 text-sm text-muted"
        >
          <span>Couldn&apos;t load {this.props.region}.</span>
          <Button variant="outline" size="sm" onClick={() => this.setState({ hasError: false })}>
            <RefreshCw size={14} /> Retry
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
