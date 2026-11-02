import type { NextConfig } from "next";

/** Static export: the built UI in web/out is served by the Python runner
 * (single process). Dev mode uses `next dev` + NEXT_PUBLIC_NEXUS_URL. */
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
