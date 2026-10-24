/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/rovers",
        destination: "http://127.0.0.1:8000/api/rovers",
      },
      {
        source: "/api/moonbase",
        destination: "http://127.0.0.1:8000/api/moonbase",
      },
      {
        source: "/api/plan-route",
        destination: "http://127.0.0.1:8000/api/plan-route",
      },
      {
        source: "/api/save-run",
        destination: "http://127.0.0.1:8000/api/save-run",
      },
      {
        source: "/api/lunar-sites",
        destination: "http://127.0.0.1:8000/api/lunar-sites",
      },
      {
        source: "/api/lunar-sites/:path*",
        destination: "http://127.0.0.1:8000/api/lunar-sites/:path*",
      },
      {
        source: "/api/terrain-preview",
        destination: "http://127.0.0.1:8000/api/terrain-preview",
      },
      {
        source: "/api/validate-route",
        destination: "http://127.0.0.1:8000/api/validate-route",
      },
      {
        source: "/api/compare-routes",
        destination: "http://127.0.0.1:8000/api/compare-routes",
      },
      {
        source: "/api/upload-dem",
        destination: "http://127.0.0.1:8000/api/upload-dem",
      },
    ];
  },
};

module.exports = nextConfig;
