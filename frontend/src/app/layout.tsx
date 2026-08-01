import type { Metadata } from "next";
import { Geist, Geist_Mono, Noto_Sans_SC, IBM_Plex_Sans, Press_Start_2P, VT323, DotGothic16 } from "next/font/google";
import "./globals.css";
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
        <Providers>
          <AppLayout>
            {children}
          </AppLayout>
        </Providers>
      </body>
    </html>
  );
}
