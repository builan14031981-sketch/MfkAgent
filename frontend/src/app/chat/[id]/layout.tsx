// 静态导出：动态路由需提供 generateStaticParams。
// Electron 桌面端真实聊天 ID 由本地后端动态生成，运行时通过 router.push 客户端跳转，
// 这里生成一个占位参数即可满足静态导出要求（真实 ID 走客户端路由，无需预生成）。
export function generateStaticParams() {
  return [{ id: "0" }];
}

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
