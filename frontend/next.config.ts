import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 禁用图片优化（静态导出需要）
  images: {
    unoptimized: true,
  },

  // 严格模式
  reactStrictMode: true,
};

export default nextConfig;
