"use client";

import { useMemo, useState } from "react";
import type { Message } from "@/hooks/useMessages";
import { MessageList } from "@/components/MessageList";
import { MessageOutline } from "@/components/MessageOutline";

/** 轮数（每轮 = 1 条用户消息 + 1 条 AI 回复）档位 */
const TURN_OPTIONS = [10, 50, 100, 200, 500];

const SHORT_QUESTIONS = [
  "如何优化 React 渲染性能？",
  "解释一下 JavaScript 事件循环。",
  "帮我重构这个有问题的函数。",
  "什么是闭包？举几个实际例子。",
  "数据库索引应该怎么建才合理？",
  "CSS 里 flex 和 grid 怎么选？",
  "什么是防抖和节流？",
  "http 缓存策略有哪些？",
];

const CODE_REPLY = `## 完整实现

需要分几步来做这件事，下面是完整的实现思路与代码。

### 第一步：定义接口

\`\`\`ts
interface PageItem<T> {
  id: number;
  data: T;
  next: PageItem<T> | null;
}

interface PagedListProps<T> {
  items: T[];
  pageSize: number;
  renderItem: (item: T, index: number) => React.ReactNode;
}

function normalizePage<T>(items: T[], pageSize: number): PageItem<T>[] {
  return items.map((data, index) => ({
    id: index,
    data,
    next: index + 1 < items.length ? null : null,
  }));
}
\`\`\`

### 第二步：接入渲染

这里是实现要点：

1. 使用 \`useMemo\` 缓存派生数据，避免无谓重算；
2. 滚动监听用 \`throttle\` 限制触发频率；
3. 骨架屏用 CSS 动画填充空白区域；
4. 虚拟化只渲染可视区 + 少量缓冲区的条目；
5. 删除操作走不可变更新，保证引用稳定。

### 第三步：边界情况

- 空列表时展示占位文案；
- 滚动到顶部时停止加载；
- 数据源变更时重置分页状态；
- 窗口 resize 时重新计算可视高度。

## 小结

以上就是完整方案，核心是「分页 + 虚拟化 + 节流」三件套。如果还有疑问，可以继续追问。

\`\`\`bash
# 运行方式
npm run dev
\`\`\``;

const HEADING_REPLY = `## 回答

这里是一个带结构的回复，包含标题、列表和强调。

### 为什么这样做

1. 第一点：保持代码简洁，职责单一；
2. 第二点：优先使用组合而非继承；
3. 第三点：所有文案走 locales，方便国际化。

> 提醒：注意边界条件与空值处理。

### 什么时候不该用

- 性能瓶颈尚未证实时不提前优化；
- 状态复杂度不高时优先 useState；
- 组件树过深时才考虑拆分。`;

const SHORT_REPLY = "好的，这个方案是可行的。建议先从最小可运行版本开始，再逐步补边界处理。有问题随时继续问。";

/** 超长用户消息：多段文字 + 列表 + 代码，压大纲预览截断与整页渲染 */
const LONG_QUESTION = `这是一个超长的测试问题，用来验证对话大纲在超长对话场景下的表现，同时压测预览文本的截断逻辑。

背景说明：我们在做一个 AI 桌面应用，聊天页面右侧需要有一个对话大纲悬浮导航，把所有用户消息按顺序列出来，点击可以跳转并高亮。

需求细节：
- 收起态是一个竖排圆点胶囊，悬停展开；
- 展开态每行显示编号和问题预览，超长内容省略号截断；
- 点击后平滑滚动到对应消息，并做短暂高亮闪烁；
- 在几百上千轮的长对话中，展开列表和滚动都不能卡顿。

为了凑够长度，这里再补一段补充说明：\`scrollIntoView\` 会找到最近的滚动祖先，配合 \`behavior: 'smooth'\` 与 \`block: 'center'\` 即可实现居中平滑滚动，高亮则可以用 Web Animations API 的 \`el.animate\` 直接做，不需要往业务组件里塞状态。

代码示例：

\`\`\`ts
el.scrollIntoView({ behavior: "smooth", block: "center" });
el.animate(
  [{ backgroundColor: "rgba(76, 154, 255, 0.16)" }, { backgroundColor: "rgba(76, 154, 255, 0)" }],
  { duration: 1600, easing: "ease-out" }
);
\`\`\`

最后再说一遍：这是一个纯前端假数据的压测消息，没有调用任何 AI 接口。`;

/** 确定性生成假对话：turns 轮（user + assistant 交替），seed 偏移超长消息位置 */
function makeMessages(turns: number, seed: number): Message[] {
  const start = new Date("2026-01-01T00:00:00Z").getTime();
  const list: Message[] = [];
  for (let i = 1; i <= turns; i++) {
    const userContent =
      (i + seed) % 13 === 0
        ? LONG_QUESTION
        : `第 ${i} 个问题：${SHORT_QUESTIONS[i % SHORT_QUESTIONS.length]}`;
    const assistantContent = i % 3 === 0 ? CODE_REPLY : i % 3 === 1 ? HEADING_REPLY : SHORT_REPLY;
    list.push({
      id: i * 2 - 1,
      chat_id: 1,
      role: "user",
      content: userContent,
      created_at: new Date(start + i * 60000).toISOString(),
    });
    list.push({
      id: i * 2,
      chat_id: 1,
      role: "assistant",
      content: assistantContent,
      created_at: new Date(start + i * 60000 + 30000).toISOString(),
    });
  }
  return list;
}

const noop = () => {};

const TEST_AGENT = { id: "coder", name: "Coder" };

export default function OutlineTestPage() {
  const [turns, setTurns] = useState(200);
  const [seed, setSeed] = useState(0);
  const [lockOpen, setLockOpen] = useState(false);
  const [activeUserMessageId, setActiveUserMessageId] = useState<number | null>(null);

  const messages = useMemo(() => makeMessages(turns, seed), [turns, seed]);
  const userCount = messages.filter((m) => m.role === "user").length;

  return (
    <div style={{
      height: "100vh",
      display: "flex",
      flexDirection: "column",
      background: "var(--bg-level-2)",
      padding: "12px 16px",
      boxSizing: "border-box",
    }}>
      {/* 控制条 */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "12px",
        flexShrink: 0,
        marginBottom: "10px",
      }}>
        <h1 style={{ fontSize: "14px", fontWeight: 600, margin: 0, color: "var(--text-level-1)" }}>
          Outline Stress Test
        </h1>
        <select
          value={turns}
          onChange={(e) => setTurns(Number(e.target.value))}
          style={{
            padding: "4px 8px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)",
            color: "var(--text-level-2)",
            fontSize: "12px",
          }}
        >
          {TURN_OPTIONS.map((n) => (
            <option key={n} value={n}>{n} 轮</option>
          ))}
        </select>
        <button
          onClick={() => setSeed((s) => s + 1)}
          style={{
            padding: "4px 12px",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)",
            color: "var(--text-level-2)",
            cursor: "pointer",
            fontSize: "12px",
          }}
        >
          重新生成
        </button>
        <label style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          fontSize: "12px",
          color: "var(--text-level-2)",
          cursor: "pointer",
        }}>
          <input
            type="checkbox"
            checked={lockOpen}
            onChange={(e) => setLockOpen(e.target.checked)}
          />
          锁定展开大纲
        </label>
        <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>
          用户消息 {userCount} 条 / 总 {messages.length} 条
        </span>
      </div>

      {/* 复用真实聊天页布局：MessageList + MessageOutline */}
      <div style={{
        position: "relative",
        flex: 1,
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        border: "1px solid var(--border-primary)",
        borderRadius: "var(--radius-lg)",
        overflow: "hidden",
        background: "var(--bg-level-1)",
      }}>
        <MessageList
          messages={messages}
          streamingContent=""
          streamingToolCalls={[]}
          isStreaming={false}
          currentAgent={TEST_AGENT}
          onQuote={noop}
          onRegenerate={noop}
          onEdit={noop}
          onActiveUserMessageChange={setActiveUserMessageId}
        />
        <MessageOutline messages={messages} activeUserMessageId={activeUserMessageId} forceOpen={lockOpen} />
      </div>

      <div style={{
        marginTop: "8px",
        fontSize: "12px",
        color: "var(--text-level-3)",
        flexShrink: 0,
      }}>
        说明：纯前端假数据压测页，零 AI 调用。悬停右侧胶囊展开大纲，点击条目跳转并闪烁；锁定开关便于长时间观察超长列表渲染。
      </div>
    </div>
  );
}
