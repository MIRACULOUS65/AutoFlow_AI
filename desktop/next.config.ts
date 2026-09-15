import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === "production";

/**
 * In development the Next.js dev server serves the renderer and Electron loads
 * http://localhost:3000. For the packaged desktop app we produce a fully static
 * export so Electron can load the frontend from local files with no running
 * Next.js server required.
 */
const nextConfig: NextConfig = {
  // Static export only for production packaging; dev keeps normal dynamic
  // routing so runtime-created task ids resolve without static params.
  // `output: export` writes the static site to `out/` by default. Dev uses the
  // default `.next` working dir so the two never collide.
  ...(isProd ? { output: "export" as const } : {}),
  // Static export cannot optimize images on the fly.
  images: { unoptimized: true },
  // The packaged app serves `out/` through a custom `app://` protocol (see
  // electron/main.ts), so absolute `/_next/...` paths resolve correctly.
  trailingSlash: true,
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
