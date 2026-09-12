import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@toeic-pilot/shared"],
  // Byte header `X-Powered-By` không nói gì với người học, chỉ nói với scanner.
  poweredByHeader: false,
  async headers() {
    return [
      {
        // Tài sản petland là tệp tĩnh đổi chỉ khi deploy: sprite là tệp nhị phân
        // mới-thì-tên-mới, còn `map.json` được fetch lại ở MỖI lần mở panel
        // (`petland-map-source.ts`) — mặc định của Next là revalidate mỗi lần,
        // nghĩa là trình duyệt hỏi lại máy chủ một tệp không bao giờ đổi.
        source: "/pet/:path*",
        headers: [{ key: "Cache-Control", value: "public, max-age=3600" }],
      },
    ];
  },
};

export default nextConfig;
