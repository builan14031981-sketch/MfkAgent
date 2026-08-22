import type { SVGProps } from "react";

export type AgentIconScheme = "A" | "B" | "C";

/**
 * Agent 图标统一 SVG 底座。
 * 硬性规范：viewBox 24 / fill none / stroke currentColor
 *           / strokeWidth 1.5 / round 端点与拐角。
 * 用 1em 尺寸，方便外层用 fontSize 精确控制像素大小（16/20/24px）。
 */
export function Svg({
  children,
  title,
  ...props
}: SVGProps<SVGSVGElement> & { title?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      width="1em"
      height="1em"
      aria-hidden={title ? undefined : true}
      {...props}
    >
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  );
}