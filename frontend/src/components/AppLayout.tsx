"use client";

import { useState, useMemo } from "react";
import { usePathname } from "next/navigation";
import { Sidebar } from "./Sidebar";
import { SettingsPanel } from "./panels/SettingsPanel";
import { MemoryPanel } from "./panels/MemoryPanel";

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const pathname = usePathname();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isMemoryOpen, setIsMemoryOpen] = useState(false);

  // 从URL解析当前chatId
  const currentChatId = useMemo(() => {
    const match = pathname.match(/^\/chat\/(\d+)$/);
    return match ? Number(match[1]) : null;
  }, [pathname]);

  return (
    <div style={{
      display: "flex",
      height: "100vh",
      background: "var(--bg-level-2)",
    }}>
      {/* 左侧 Sidebar - 固定存在 */}
      <Sidebar
        currentChatId={currentChatId}
        onSettingsClick={() => setIsSettingsOpen(true)}
        onMemoryClick={() => setIsMemoryOpen(true)}
      />

      {/* 面板 - 全局覆盖 */}
      <SettingsPanel isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
      <MemoryPanel isOpen={isMemoryOpen} onClose={() => setIsMemoryOpen(false)} />

      {/* 右侧主内容区 */}
      <main style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
      }}>
        {children}
      </main>
    </div>
  );
}
