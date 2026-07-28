/** @type {import('next').NextConfig} */
const nextConfig = {
  // 禁用静态导出（开发模式）
  // output: 'export',
  
  // 禁用图片优化（静态导出需要）
  images: {
    unoptimized: true,
  },
  
  // 严格模式
  reactStrictMode: true,
}

module.exports = nextConfig
