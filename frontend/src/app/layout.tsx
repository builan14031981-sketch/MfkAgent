import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import "../styles/tokens.css";
/* 字体本地化（2026-08-11）：原 next/font/google 构建期需联网下载字体，
   离线/网络抖动时构建直接崩。现改为：
   - 单文件 Latin 字体（Geist/Geist Mono/VT323）→ next/font/local + public/fonts/
   - unicode-range 分片字体（Noto Sans SC/IBM Plex Sans/像素主题字体）
     → fontsource CSS 直引（npm 包自带 @font-face + 分片，构建零网络）
   所有 --font-* CSS 变量名保持不变，主题/组件引用零改动。 */
import "@fontsource-variable/noto-sans-sc";
import "@fontsource-variable/ibm-plex-sans";
import "@fontsource/press-start-2p/latin.css";
import "@fontsource/dotgothic16";
import "@xterm/xterm/css/xterm.css";
import "./terminal.css";
import { Providers } from "@/components/providers";
import { AppLayout } from "@/components/AppLayout";

/* Geist 可变字体（latin 单文件，wght 100-900） */
const geistSans = localFont({
  src: "../../public/fonts/geist-latin.woff2",
  variable: "--font-geist-sans",
  weight: "100 900",
});

const geistMono = localFont({
  src: "../../public/fonts/geist-mono-latin.woff2",
  variable: "--font-geist-mono",
  weight: "100 900",
});

/* VT323：静态单字重 latin 单文件（family 定义由 next/font/local 输出） */
const vt323 = localFont({
  src: "../../public/fonts/vt323-latin.woff2",
  variable: "--font-pixel-vt",
  weight: "400",
});

/* fontsource 字体的 CSS 变量定义在 globals.css :root（变量名与原 next/font 一致）：
   --font-noto-sans-sc → 'Noto Sans SC Variable'
   --font-ibm-plex-sans → 'IBM Plex Sans Variable'
   --font-pixel-8bit → 'Press Start 2P'（latin 子集）
   --font-pixel-dot → 'DotGothic16' */

export const metadata: Metadata = {
  title: "MfkAgent - 智能Agent平台",
  description: "一个人人都能创建、使用和管理AI助手的智能工作空间",
};

/* 安卓端 M1：移动视口与键盘行为。
   - viewportFit: cover 配合 safe-area-inset（输入框底部避让）
   - interactiveWidget: resizes-content 让软键盘顶起内容而非遮挡（Android WebView/Chrome 108+） */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${geistSans.variable} ${geistMono.variable} ${vt323.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        {/* 2026-08-11 首帧主题守卫 v2（修重启闪黑 FOUC）：
            原生内联 script 放置于 head 内，早于任何 body 内容解析/绘制：读 localStorage 缓存（lib/theme.ts 写入，格式 {t,m}）
            立即应用上次主题；无缓存/解析失败静默回默认 studio-graphite（石墨）。 */}
        {/* ⚠️ dangerouslySetInnerHTML 安全说明：
            内容为硬编码常量（FOUC 防护脚本），绝不包含用户输入或动态数据。 */}
        <script
          suppressHydrationWarning
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var c=window.localStorage.getItem("mfk-visual-theme");if(!c)return;var p=JSON.parse(c);if(p&&typeof p.t==="string"&&(p.m==="light"||p.m==="dark")){var r=document.documentElement;r.setAttribute("data-theme",p.t);r.classList.remove("light","dark");r.classList.add(p.m);}}catch(e){}})();`,
          }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        <Providers>
          <AppLayout>
            {children}
          </AppLayout>
        </Providers>
      </body>
    </html>
  );
}
