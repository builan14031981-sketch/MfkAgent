import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 静态导出：仅生产构建（next build）启用，生成 out/ 目录供 Electron loadFile 加载。
  // 开发模式（next dev）不启用，否则动态路由 [id] 会被 generateStaticParams 约束，
  // 导致运行时生成的真实 chat id（如 /chat/5）因未预生成而报错。
  output: process.env.NODE_ENV === "production" ? "export" : undefined,

  // 禁用图片优化（静态导出需要）
  images: {
    unoptimized: true,
  },

  // 资源使用相对路径（./_next/...），保证 file:// 协议下 Electron 能正确加载
  // 不设置则生成 /_next/... 绝对路径，file:// 下会 404
  // 仅生产构建（next build / 静态导出）时设 "./"；开发模式（next dev）不设，
  // 否则 Next.js 16 的 next/font 会因 assetPrefix 非 "/" 开头报 500 错误
  //
  // 安卓端 M1（2026-08-29）：BUILD_TARGET=mobile 时改用绝对路径 —— Capacitor WebView
  // 以 https://localhost 为根加载，相对前缀在二级路由（如 /connect/）下会解析成
  // /connect/_next/... 导致 404 白屏（Electron 只从根加载不受影响，故保留 ./）
  assetPrefix:
    process.env.NODE_ENV === "production"
      ? process.env.BUILD_TARGET === "mobile"
        ? undefined
        : "./"
      : undefined,

  // 目录风格 URL（生成 index.html 而非 /about.html 的目录形式）
  trailingSlash: true,

  // 严格模式
  reactStrictMode: true,

  // 开发模式 API 代理：将 /api/* 请求转发到后端
  // 生产构建为静态导出，无需代理（Electron 直接调用后端）
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    const backendUrl = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8001";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
