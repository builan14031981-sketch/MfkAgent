import { useState, useCallback, useMemo } from "react";
import type { Message, useMessages } from "@/hooks/useMessages";
import type { ToolCall } from "@/components/ToolCallCard";
import type { ReasoningEffort } from "@/components/ChatInput";

type SendMessageStream = ReturnType<typeof useMessages>["sendMessageStream"];
type AppendMessage = ReturnType<typeof useMessages>["appendMessage"];

export interface UseChatStreamParams {
  chatId: number | null;
  sendMessageStream: SendMessageStream;
  appendMessage: AppendMessage;
  refetch: () => Promise<void>;
}

export interface SendStreamOptions {
  /** 模型 id；缺省回退默认模型 */
  modelId?: string | null;
  personalityLevel?: number;
  reasoningEffort?: ReasoningEffort;
  /** 是否乐观追加用户消息到本地列表（重试/重新生成时已有消息，置 false） */
  appendUserMessage?: boolean;
  /** 发送前对消息做变换（如拼接项目文件上下文）；返回原始值则不拼 */
  buildContent?: (content: string) => Promise<string> | string;
}

/**
 * 聊天流式发送统一管线：
 * 收敛 chat 页 handleSend / autoSend / runSendForUser 三份重复的
 * isSending + streaming 状态机 + 乐观消息 + 错误/完成处理的逻辑。
 *
 * 工具卡片：以 Map<tool_call_id, ToolCall> 维护生命周期（pending/running/success/failed），
 * 避免旧 name+path 去重导致的重复命令折叠问题。对外暴露数组供渲染。
 */
export function useChatStream({
  chatId,
  sendMessageStream,
  appendMessage,
  refetch,
}: UseChatStreamParams) {
  const [isSending, setIsSending] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [streamingThinking, setStreamingThinking] = useState("");
  const [toolCallsMap, setToolCallsMap] = useState<Map<string, ToolCall>>(new Map());
  const [streamingError, setStreamingError] = useState<string | null>(null);

  const streamingToolCalls = useMemo(() => Array.from(toolCallsMap.values()), [toolCallsMap]);

  const resetStreaming = useCallback(() => {
    setStreamingContent("");
    setStreamingThinking("");
    setToolCallsMap(new Map());
    setStreamingError(null);
  }, []);

  const sendStream = useCallback(
    async (content: string, options: SendStreamOptions = {}) => {
      if (!chatId) throw new Error("No chat selected");
      const { modelId, personalityLevel, reasoningEffort, appendUserMessage = true, buildContent } = options;

      setIsSending(true);
      resetStreaming();

      // 乐观更新：先追加用户消息到本地列表（无需等待服务端）
      if (appendUserMessage) {
        const tempUserMsg: Message = {
          id: Date.now(),
          chat_id: chatId,
          role: "user",
          content,
          created_at: new Date().toISOString(),
        };
        appendMessage(tempUserMsg);
      }

      const finalContent = buildContent ? await buildContent(content) : content;

      const appendAssistant = (
        final: string,
        toolCalls: ToolCall[],
        finalThinking: string
      ) => {
        setStreamingContent("");
        setStreamingThinking("");
        setToolCallsMap(new Map());
        setStreamingError(null);
        const aiMsg: Message = {
          id: Date.now(),
          chat_id: chatId,
          role: "assistant",
          content: final,
          thinking: finalThinking || undefined,
          tool_calls: toolCalls.length > 0 ? toolCalls : undefined,
          created_at: new Date().toISOString(),
        };
        appendMessage(aiMsg);
        // 后台静默同步真实 ID（不触发 loading，不驱动滚动）
        refetch().catch(() => { /* 静默失败 */ });
      };

      try {
        await sendMessageStream(
          finalContent,
          modelId || "mimo-v2.5-pro",
          (chunk) => setStreamingContent((prev) => prev + chunk),
          () => {
            setToolCallsMap(new Map());
            setIsSending(false);
          },
          (error) => {
            resetStreaming();
            setIsSending(false);
            setStreamingError(error);
          },
          personalityLevel,
          reasoningEffort,
          (thinking) => setStreamingThinking((prev) => prev + thinking),
          // onToolStart：以 tool_call_id 为键插入 running 卡片
          (toolStart) => {
            setToolCallsMap((prev) => {
              const next = new Map(prev);
              next.set(toolStart.tool_call_id, {
                tool: toolStart.tool,
                name: toolStart.tool,
                input: toolStart.input ?? {},
                arguments: toolStart.input ?? {},
                status: "running",
                tool_call_id: toolStart.tool_call_id,
              });
              return next;
            });
          },
          // onToolOutput：Phase A 后端不发射，占位（长命令流式输出时启用）
          () => {},
          // onToolResult：按 id 定位更新为终态
          (toolResult) => {
            const id = toolResult.tool_call_id;
            if (!id) return;
            setToolCallsMap((prev) => {
              const next = new Map(prev);
              const prevCard = next.get(id) ?? {};
              next.set(id, {
                ...prevCard,
                tool: toolResult.tool ?? prevCard.tool,
                name: toolResult.tool ?? prevCard.tool,
                success: toolResult.success,
                status: toolResult.success ? "success" : "failed",
                result: toolResult.result,
                duration_ms: toolResult.duration_ms,
                error: toolResult.error,
                tool_call_id: id,
              });
              return next;
            });
          },
          // onToolCallsBatch：汇总数据合并补齐（含 result），与实时卡片保持一致
          (batch) => {
            setToolCallsMap((prev) => {
              const next = new Map(prev);
              for (const c of batch) {
                if (!c.tool_call_id) continue;
                next.set(c.tool_call_id, { ...(next.get(c.tool_call_id) ?? {}), ...c });
              }
              return next;
            });
          },
          appendAssistant
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        resetStreaming();
        setIsSending(false);
        setStreamingError(msg);
      }
    },
    [chatId, sendMessageStream, appendMessage, refetch, resetStreaming]
  );

  return {
    isSending,
    streamingContent,
    streamingThinking,
    streamingToolCalls,
    streamingError,
    sendStream,
  };
}
