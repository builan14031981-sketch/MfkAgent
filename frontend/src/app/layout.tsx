import type { Metadata } from "next";
import { Geist, Geist_Mono, Noto_Sans_SC, IBM_Plex_Sans, Press_Start_2P, VT323, DotGothic16 } from "next/font/google";
import "./globals.css";
import "../styles/tokens.css";
import { Providers } from "@/components/providers";
import { AppLayout } from "@/components/AppLayout";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const notoSansSC = Noto_Sans_SC({
  variable: "--font-noto-sans-sc",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

const ibmPlexSans = IBM_Plex_Sans({
  variable: "--font-ibm-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

/* 像素风主题字体（纯新增，供 hero 像素主题引用） */
const pressStart2P = Press_Start_2P({
  variable: "--font-pixel-8bit",
  weight: "400",
  subsets: ["latin"],
});

const vt323 = VT323({
  variable: "--font-pixel-vt",
  weight: "400",
  subsets: ["latin"],
});

const dotGothic16 = DotGothic16({
  variable: "--font-pixel-dot",
  weight: "400",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MfkAgent - 智能Agent平台",
  description: "一个人人都能创建、使用和管理AI助手的智能工作空间",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${geistSans.variable} ${geistMono.variable} ${notoSansSC.variable} ${ibmPlexSans.variable} ${pressStart2P.variable} ${vt323.variable} ${dotGothic16.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        {/* 2026-08-11 首帧主题守卫 v2（修重启闪黑 FOUC）：
            原生内联 script（不用 next/script beforeInteractive——dev 下其注入首帧 HTML
            时机不可靠，脚本晚于首帧执行导致仍闪黑）。body 首位同步执行，
            早于任何 body 内容解析/绘制：读 localStorage 缓存（lib/theme.ts 写入，格式 {t,m}）
            立即应用上次主题；无缓存/解析失败静默回默认 obsidian。缓存格式改动需同步本脚本。 */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var c=window.localStorage.getItem("mfk-visual-theme");if(!c)return;var p=JSON.parse(c);if(p&&typeof p.t==="string"&&(p.m==="light"||p.m==="dark")){var r=document.documentElement;r.setAttribute("data-theme",p.t);r.classList.remove("light","dark");r.classList.add(p.m);}}catch(e){}})();`,
          }}
        />
        <Providers>
          <AppLayout>
            {children}
          </AppLayout>
        </Providers>
      </body>
    </html>
  );
}
