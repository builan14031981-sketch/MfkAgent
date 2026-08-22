# 桌面通知触发策略设计（2026-08-13）

## 背景
- 用户要求：右下角 Toast 通知（任务完成 / 审批 / 抉择等场景）设计统一触发策略。
- 先决体验：通知持久化已实现（`timeoutType: "never"`，用户确认"不点不消失"）。
- 前端改动已获用户授权，前提：全量备份可回滚（见下方回滚）。

## 触发矩阵（最终版）
所有系统通知统一在 `useChatStream.ts` 中、以 `isUserAway()` 守卫触发。
`isUserAway` 判定：全局活跃会话不是本会话，或窗口不可见 / 失焦（任一成立）。
用户在场时界面卡片已有反馈，不重复弹系统通知。

| 场景 | 触发条件 | 音效 beep | persistent | chatId | 备注 |
|------|----------|-----------|-----------|--------|------|
| 长任务完成 | isUserAway | success | false（短显） | - | 正向结果，短提示即可 |
| 需要审批 | isUserAway | attention | true | targetChatId | 需用户操作，保持到交互 |
| AI 询问（抉择） | isUserAway | attention | true | targetChatId | 需用户操作，保持到交互 |
| 抉择超时预警（新增） | isUserAway 且即将超时 | attention | true | targetChatId | 后端 CHOICE_TIMEOUT=300s 自动采纳推荐项，超时前 30s 提醒 |
| 子任务完成 | isUserAway | success | false（短显） | - | 高频事件，短提示 |
| 子任务失败 | isUserAway | error | true | targetChatId | 需关注，保持到交互 |
| 流式出错 | isUserAway | error | true | targetChatId | 需关注，保持到交互 |

### 审批 vs 抉择超时语义（关键区分）
- 审批超时 300s（`APPROVAL_TIMEOUT`，approval.py）→ **自动拒绝**（安全方向）→ 不弹预警。
- 抉择超时 300s（`CHOICE_TIMEOUT`，choice.py）→ **自动采纳推荐项**（非安全方向）→ 超时前 30s 弹预警，提醒用户及时处理。

## 音效分级规范
`frontend/src/lib/notify.ts`，`BeepKind` 类型，Web Audio 合成（无需音频文件）：

| kind | 音色 | 场景 |
|------|------|------|
| info | 单声 880Hz A5 | 信息类（默认） |
| success | 上行双音 660→880 | 完成（正向感知） |
| error | 低沉 440Hz 长音 | 失败 / 出错 |
| attention | 急促三连 880×3 | 审批 / 抉择（需用户操作） |

- 3 秒节流防刷屏（beep 与 toast 同节流，保证音画同步）。
- `silent: true`：Electron 原生通知静默，音效统一由 Web Audio 播放，避免双音。

## 通知行为（Electron 主进程）
`frontend/electron/main.js` `show-notification` handler：
- `persistent: true` → `timeoutType: "never"`（保持显示直到用户交互）；否则 `"default"`（短显）。
- 点击通知 → 聚焦主窗口；带 `chatId` 时 `loadURL("/chat/{chatId}")` 跳转对应会话。

## 抉择超时预警实现（前端）
`useChatStream.ts` onUserChoice 回调：
- 每收到抉择，若用户离开，注册 `setTimeout`（300s−30s=270s 后触发）。
- 触发时检查该 choice 是否仍 pending（未 resolved）且用户仍离开 → 弹"即将自动采纳"通知。
- 定时器存于 `refs.choiceWarnTimers`（Map<choiceId, timer>），`streamStore.ts` 新增字段：
  - `resetStreaming` 统一清理；
  - `resolveChoice` 用户解决该抉择时清除对应定时器。

## 抉择卡片在场倒计时（UserChoiceCard）
- 待选择时：一行提示 + 后端 300s 剩余时间倒计时。
- 剩余 ≤30s 时：边框黄色高亮 + 文案"X 后自动采纳"。
- 已解决：仍为只读记录（V3.2 极简版），交互由底部 UserChoiceComposer 承担。

## 改动文件清单
- `frontend/src/lib/notify.ts`：BeepKind / playBeep / NotifyOptions(beep/beepEnabled/silent/persistent/chatId)
- `frontend/src/hooks/useChatStream.ts`：6 处通知点对齐矩阵 + 抉择超时预警定时器
- `frontend/src/lib/streamStore.ts`：StreamSessionRefs 增加 choiceWarnTimers
- `frontend/electron/main.js`：show-notification 支持 persistent/chatId + 点击跳转
- `frontend/electron/preload.js`：IPC 透传（实质未改）
- `frontend/src/types/electron.d.ts`：showNotification opts 扩展
- `frontend/src/components/UserChoiceCard.tsx`：在场倒计时

## 回滚
- 备份目录：`_backup/notify_design_0813_152458/`（7 文件，frontend 结构保留）
- 如需回滚：将该目录下文件复制回对应位置覆盖当前版本即可。
- 另：`_backup/notify_persist_pre/main.js` 为上一轮持久化改动前的 main.js。
- 前端类型检查：`cd frontend && npx tsc --noEmit`（通过）。
- 注意：lint 存在大量既存 React Compiler 规则报错（set-state-in-effect 等），与本次改动无关。

## 待验证
- [ ] Electron 重启后实测：短显（任务完成）自动消失 vs 持久（审批/抉择）不点不消失
- [ ] 点击通知跳转对应会话
- [ ] 抉择在场倒计时显示与 ≤30s 高亮
