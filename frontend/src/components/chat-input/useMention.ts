import { useState, useCallback, useRef } from "react";
import type { Agent } from "@/hooks/useAgents";

export interface MentionState {
  isOpen: boolean;
  query: string;
  matchIndex: number; // '@' 字符在输入框中的位置
  selectedIndex: number;
}

export function useMention(
  value: string,
  onChange: (val: string) => void,
  textareaRef: React.RefObject<HTMLTextAreaElement | null>,
  candidates: Agent[]
) {
  const [mentionState, setMentionState] = useState<MentionState>({
    isOpen: false,
    query: "",
    matchIndex: -1,
    selectedIndex: 0,
  });

  // 根据当前输入的 query 过滤候选 Agent（按姓名、id、简介匹配）
  const filteredCandidates = candidates.filter((agent) => {
    if (!mentionState.query) return true;
    const q = mentionState.query.toLowerCase();
    const nameMatch = agent.name?.toLowerCase().includes(q);
    const idMatch = agent.id?.toLowerCase().includes(q);
    const descMatch = agent.description?.toLowerCase().includes(q);
    return nameMatch || idMatch || descMatch;
  });

  // 监听输入框变化或光标移动，检测是否处于 @mention 输入状态
  const checkMentionTrigger = useCallback(
    (text: string, cursorPos: number) => {
      if (cursorPos <= 0) {
        setMentionState((prev) => (prev.isOpen ? { ...prev, isOpen: false } : prev));
        return;
      }

      // 提取光标前的一小段文本（最多向前查找 30 个字符）
      const textBeforeCursor = text.slice(0, cursorPos);
      const lastAtIndex = textBeforeCursor.lastIndexOf("@");

      if (lastAtIndex === -1) {
        setMentionState((prev) => (prev.isOpen ? { ...prev, isOpen: false } : prev));
        return;
      }

      // 检查 @ 前面是否是合法边界（开头、空格或换行）
      if (lastAtIndex > 0) {
        const charBeforeAt = textBeforeCursor[lastAtIndex - 1];
        if (!/[\s\n,，.。:：]/.test(charBeforeAt)) {
          setMentionState((prev) => (prev.isOpen ? { ...prev, isOpen: false } : prev));
          return;
        }
      }

      // 提取 @ 与光标之间的字符作为 query
      const query = textBeforeCursor.slice(lastAtIndex + 1);

      // 如果 query 中包含了空格或换行，说明用户已经打完或跳出了 mention
      if (/[\s\n]/.test(query)) {
        setMentionState((prev) => (prev.isOpen ? { ...prev, isOpen: false } : prev));
        return;
      }

      setMentionState({
        isOpen: true,
        query,
        matchIndex: lastAtIndex,
        selectedIndex: 0,
      });
    },
    []
  );

  // 确认插入选中的 Agent
  const insertMention = useCallback(
    (agent: Agent) => {
      const textarea = textareaRef.current;
      if (!textarea || mentionState.matchIndex === -1) return;

      const beforeAt = value.slice(0, mentionState.matchIndex);
      const afterCursor = value.slice(textarea.selectionEnd || textarea.value.length);
      const mentionText = `@${agent.name} `;
      const newValue = `${beforeAt}${mentionText}${afterCursor}`;

      onChange(newValue);
      setMentionState({
        isOpen: false,
        query: "",
        matchIndex: -1,
        selectedIndex: 0,
      });

      // 恢复光标位置在插入的 @Agent 后面
      requestAnimationFrame(() => {
        if (textarea) {
          const newCursorPos = beforeAt.length + mentionText.length;
          textarea.focus();
          textarea.setSelectionRange(newCursorPos, newCursorPos);
        }
      });
    },
    [mentionState.matchIndex, value, onChange, textareaRef]
  );

  // 键盘导航处理（供 textarea onKeyDown 拦截）
  const handleMentionKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>): boolean => {
      if (!mentionState.isOpen || filteredCandidates.length === 0) {
        return false;
      }

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMentionState((prev) => ({
          ...prev,
          selectedIndex: (prev.selectedIndex + 1) % filteredCandidates.length,
        }));
        return true;
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        setMentionState((prev) => ({
          ...prev,
          selectedIndex:
            (prev.selectedIndex - 1 + filteredCandidates.length) %
            filteredCandidates.length,
        }));
        return true;
      }

      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        const selectedAgent = filteredCandidates[mentionState.selectedIndex];
        if (selectedAgent) {
          insertMention(selectedAgent);
        }
        return true;
      }

      if (e.key === "Escape") {
        e.preventDefault();
        setMentionState((prev) => ({ ...prev, isOpen: false }));
        return true;
      }

      return false;
    },
    [mentionState.isOpen, mentionState.selectedIndex, filteredCandidates, insertMention]
  );

  return {
    mentionState,
    filteredCandidates,
    checkMentionTrigger,
    insertMention,
    handleMentionKeyDown,
    closeMention: () => setMentionState((prev) => ({ ...prev, isOpen: false })),
  };
}
