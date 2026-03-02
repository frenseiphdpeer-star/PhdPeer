/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Granular chunking for better caching in production
  output: "standalone",

  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "recharts",
      "@xyflow/react",
      "@radix-ui/react-accordion",
      "@radix-ui/react-avatar",
      "@radix-ui/react-dialog",
      "@radix-ui/react-dropdown-menu",
      "@radix-ui/react-label",
      "@radix-ui/react-progress",
      "@radix-ui/react-separator",
      "@radix-ui/react-switch",
    ],
  },

  images: {
    formats: ["image/avif", "image/webp"],
  },

  // Headers for security + caching
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
      {
        source: "/(.*)\\.(js|css|woff|woff2)",
        headers: [
          {
            key: "Cache-Control",
            value: "public, max-age=31536000, immutable",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
