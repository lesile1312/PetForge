import type { NextConfig } from "next";

const apiOrigin = (process.env.PETFORGE_API_ORIGIN ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const runtimeMode = process.env.PETFORGE_RUNTIME_MODE
  ?? (process.env.NODE_ENV === "development" ? "local" : "package");

const nextConfig: NextConfig = {
  experimental: { proxyTimeout: 900000 },
  transpilePackages: ["@petforge/pet-schema"],
  env: {
    NEXT_PUBLIC_PETFORGE_RUNTIME_MODE: runtimeMode,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};

export default nextConfig;
