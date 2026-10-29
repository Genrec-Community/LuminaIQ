import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Served as static files in front of the Lumina IQ app (frontend/scripts/merge-website.mjs)
  output: 'export',
  trailingSlash: true,
  poweredByHeader: false,
};

export default nextConfig;
