"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { VisualThemeProvider } from "@/lib/visual-theme";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <ThemeProvider
      attribute="data-theme"
      defaultTheme="dark"
      enableSystem={false}
      themes={["dark", "light"]}
    >
      <VisualThemeProvider>
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      </VisualThemeProvider>
    </ThemeProvider>
  );
}
