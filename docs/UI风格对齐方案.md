# MfkAgent UI 风格对齐方案

> 参考目标：小米 MiMo Code（https://mimo.xiaomi.com/coder）
> 核心原则：**克制、有质感、暖白基调、黑白为主、微动效加分**

---

## 一、当前状态 vs 目标状态 总览

| 维度 | 当前 | 目标（MiMo 启发） |
|------|------|-------------------|
| **色彩** | 18 个主题，默认 studio-graphite（灰白+近黑） | 保持黑白+暖白，但暖白更暖一点 |
| **字体** | Geist Sans + Noto Sans SC | 同一套字体即可，调整字重/字号层次 |
| **间距** | 组件内间距偏紧（6px/10px） | 适度放松，呼吸感 |
| **圆角** | 多样（4px/8px/12px/16px/20px/24px/9999px） | 收敛到 3-4 种，多用圆角保持柔和 |
| **动效** | 大量 Hero 动画（18+ 主题） | 克制，减少表演性动画，增加实用性微动效 |
| **鼠标动效** | 无 | 半透明圆点跟随鼠标 cursor |
| **边框** | 1px solid 为主 | 更细更淡，hover 时才有存在感 |
| **按钮** | 多种 inline 样式，hover 不一致 | 统一按钮规范，hover 微上移+变暗 |
| **组件风格** | 偏工程化，inline 样式多 | 统一 Token 引用，减少 inline 样式 |

---

## 二、具体改动方案（按优先级排列）

### P0 — 高优先级（核心体验）

#### 1. 暖白背景微调（默认主题）

**当前（studio-graphite）：**
```css
--mf-bg-app: #ffffff;        /* 纯白 */
--mf-bg-surface: #f6f6f8;   /* 冷灰 */
```

**改为：**
```css
--mf-bg-app: #fcfaf8;       /* 暖白（MiMo 同款） */
--mf-bg-surface: #f5f2ee;   /* 暖灰表面 */
--mf-bg-card: #f8f6f3;      /* 暖灰卡片 */
--mf-bg-elevated: #efece8;  /* 暖灰抬升层 */
```

**效果：** 整个界面从"冷白工具"变为"暖白质感"，视觉上更柔和、更"像小米"。

#### 2. 侧边栏/面板间距放松

**当前：** 侧边栏 padding: 8px 12px，行高 padding: 5px 10px

**改为：** 整体增加 2-4px 呼吸空间

- 侧边栏列表项：`padding: 8px 12px` → `padding: 10px 14px`
- 分组标题：增加上下间距
- 面板内容区：`padding: 16px` → `padding: 20px 24px`

#### 3. 统一按钮规范（减少 inline 样式）

当前 Sidebar.tsx 中几乎所有按钮都在用 `onMouseEnter/onMouseLeave` 做 inline hover 样式，导致：
- 代码冗余
- 不一致
- 难以维护

**方案：** 在 globals.css 里定义 3 种按钮 class，逐步替换 inline 样式

```css
.sb-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--mf-motion-fast), color var(--mf-motion-fast);
}
.sb-btn:hover {
  background: var(--bg-level-3);
}
.sb-btn:active {
  background: var(--bg-level-4);
}
```

#### 4. 减少 Hero 动画噪音

**当前：** 18 个 Hero 主题，大量动画（CRT 扫描线、粒子漂浮、Matrix 数字雨、Glitch 抖动等）

**建议：** 保留 3-4 个高质量、克制的主题（如 AppleMinimal、WabiSabi、Editorial），其余移入实验区或归档。不需要"表演性"动画，只需要"安静地展示产品"。

---

### P1 — 中优先级（细节质感）

#### 5. 鼠标跟随动效（Cursor Follower）

一个极简的半透明圆点，跟随鼠标移动，不影响交互：

```css
.cursor-follower {
  position: fixed;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--mf-accent);
  opacity: 0.25;
  pointer-events: none;
  transform: translate(-50%, -50%);
  transition: width 0.15s ease, height 0.15s ease, opacity 0.15s ease;
  z-index: 99999;
}
.cursor-follower.is-hovering {
  width: 20px;
  height: 20px;
  opacity: 0.10;
}
```

JS：`requestAnimationFrame` 平滑跟随，鼠标悬停可交互元素时略微放大变淡。

#### 6. 边框克制化

**当前：** 侧边栏右侧 `1px solid var(--border-primary)` 始终可见

**建议：** 边框更细更淡，或者在 hover 时才更有存在感。参考 MiMo 的 `hero__divider` 只有 1px 的 `#f3f0ef`（几乎看不见）。

```css
--border-primary: #e8e5e0;  /* 从 #e4e5e9 改为暖色 */
```

#### 7. 圆角收敛

**当前：** 7 种圆角（4/8/12/16/20/24/9999）

**建议：** 收敛到 4 种：
- `--radius-xs: 4px` — 小元素（tag、badge）
- `--radius-md: 8px` — 按钮、卡片、输入框
- `--radius-lg: 12px` — 弹层、下拉菜单（MiMo 菜单用 12px）
- `--radius-full: 9999px` — 胶囊、头像

删除：`--radius-sm`, `--radius-xl`, `--radius-2xl`

#### 8. 消息气泡风格微调

**当前：** 用户气泡带 tint 色（方案B），AI 气泡无 tint

**建议：** 保持中性面（零色相噪音），气泡之间只靠背景深浅区分。参考 MiMo 的卡片都只有暖色背景，不用彩色 tint。

---

### P2 — 低优先级（细活）

#### 9. 排版字重收敛

**当前：** 多处使用 `font-weight: 650`（非标准值），`font-weight: 600`，`font-weight: 500` 混用

**建议：** 统一为 400（正文）、500（强调）、600（标题）三档

#### 10. 侧边栏 icon 大小统一

**当前：** 有 `--sidebar-icon-size: 14px` 和 `--sidebar-icon-size-sm: 12px` 两种

**建议：** 统一为 14px，收起时用 12px。减少大小跳跃。

#### 11. 过渡动画收敛

**当前：** `var(--transition-fast): 0.15s`，`var(--transition-normal): 0.2s`，`var(--transition-slow): 0.3s`，另有 `var(--mf-motion-fast): 0.12s`，`var(--mf-motion-base): 0.2s`，`var(--mf-motion-slow): 0.3s` 两套同名不同值

**建议：** 统一使用 `--mf-motion-*` 系列，删除 `--transition-*` 旧名

---

## 三、不修改的内容（保持现状）

| 内容 | 原因 |
|------|------|
| **黑白主题体系** | 用户明确要求保持黑白+暖白 |
| **18 个 Hero 主题** | 保留但只默认启用克制型，其余的移入实验区不删除 |
| **现有字体栈** | Geist + Noto Sans SC 已足够好 |
| **后端代码** | 前端 AI 红线，不碰 |
| **数据库/模型** | 前端 AI 红线，不碰 |

---

## 四、执行计划

1. **P0 改动** — 暖白背景 + 间距放松 + 按钮规范 + Hero 收敛
2. **P1 改动** — 鼠标动效 + 边框/圆角/气泡微调
3. **P2 改动** — 字重/icon/动画收敛

每步改动前都会备份，你确认后我再动手。

---

## 五、参考截图对比

### MiMo Code 设计特征提取：

| 特征 | 描述 |
|------|------|
| 背景色 | `#fcfaf8`（暖白） |
| 按钮 hover | 微上移 1px + 背景变深色 |
| 卡片 | 暖色背景（`#efebe3`, `#f6f1ea` 等），无边框 |
| 导航 | 极简，hover 下划线展开动画 |
| 字体 | Display 字体（Questrial）用于标题，Mincho 用于副标题 |
| 品质感 | 大量留白，克制使用颜色，信息层级清晰 |

### 我们的借鉴方向：

- **不抄袭颜色**，但借鉴"留白节奏"和"信息层级"
- **不抄袭字体**，但借鉴"标题有质感、正文清晰"的层次感
- **不抄袭布局**，但借鉴"克制使用动效、只做有用的事"的设计哲学