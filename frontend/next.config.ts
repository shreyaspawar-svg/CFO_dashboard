import type { NextConfig } from "next";

// Proxy /api/* to the FastAPI backend server-side, so the browser only
// ever talks to this same origin. Avoids CORS entirely, and matters in
// some sandboxed/CI environments where a browser process can be
// restricted to a single allow-listed port while curl/server-side fetch
// is not.
const BACKEND_URL = process.env.BACKEND_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // The dev-mode indicator badge overlapped KPI card text at some
  // viewports in the Phase 3 review screenshots (frontend/screenshots/).
  devIndicators: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
