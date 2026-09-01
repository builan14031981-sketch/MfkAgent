"use client";

/**
 * /pair — 连接手机（PC 端配对页，安卓端 M1）
 *
 * 设置内的「连接手机」走 SettingsPanel 内联渲染（activeSection === "pair"，见 PairSection）；
 * 本路由保留作设置外的直达入口（如侧边栏直接进入），页面外壳在此，内容复用 PairSection。
 */
import { PairSection } from "@/components/panels/PairSection";

export default function PairPage() {
  return (
    <div style={{
      height: "100%",
      overflowY: "auto",
      padding: "24px clamp(16px, 4vw, 48px)",
      background: "var(--bg-level-2)",
      color: "var(--text-level-2)",
    }}>
      <div style={{ maxWidth: 960, margin: "0 auto" }}>
        <PairSection />
      </div>
    </div>
  );
}
