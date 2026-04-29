import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  pageExtensions: ['ts', 'tsx', 'js', 'jsx'],

  images: {
    formats: ['image/avif', 'image/webp'],
    remotePatterns: [],
  },

  experimental: {
    optimizePackageImports: ['lucide-react', 'framer-motion'],
  },

  async rewrites() {
    // Proxy API calls in dev so the browser hits same-origin /api/* and we
    // don't have to deal with CORS preflight on every request. In prod the
    // frontend points directly at NEXT_PUBLIC_API_URL.
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    return [
      { source: '/api/:path*', destination: `${apiUrl}/:path*` },
    ]
  },
}

export default nextConfig
