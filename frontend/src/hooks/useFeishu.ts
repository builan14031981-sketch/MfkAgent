"use client";
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost } from "@/lib/api";

/** 飞书连接状态 */
export interface FeishuTestResult {
  success: boolean;
  message: string;
  token_valid: boolean;
  has_bases: boolean;
}

/** 飞书当前配置（不返回完整 secret） */
export interface FeishuConfig {
  app_id: string;
  has_secret: boolean;
}

/** 飞书配置输入 */
export interface FeishuConfigInput {
  app_id: string;
  app_secret: string;
}

/** 飞书群聊 */
export interface FeishuChat {
  chat_id: string;
  name: string;
  description?: string;
}

/** 飞书配置管理 + 连接测试 */
export function useFeishu() {
  const [config, setConfig] = useState<FeishuConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<FeishuTestResult | null>(null);
  const [chats, setChats] = useState<FeishuChat[]>([]);
  const [chatError, setChatError] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);

  const fetchConfig = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiGet<FeishuConfig>("/api/feishu/config");
      setConfig(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "获取飞书配置失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  async function saveConfig(input: FeishuConfigInput) {
    try {
      setSaving(true);
      setError(null);
      await apiPost("/api/feishu/config", input);
      setConfig({ app_id: input.app_id, has_secret: Boolean(input.app_secret) });
      setTestResult(null);
      return true;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "保存飞书配置失败");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function testConnection(): Promise<boolean> {
    try {
      setTesting(true);
      setError(null);
      const result = await apiPost<FeishuTestResult>("/api/feishu/test", {});
      setTestResult(result);
      return result.success;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "测试连接失败");
      return false;
    } finally {
      setTesting(false);
    }
  }

  async function fetchChats(): Promise<FeishuChat[]> {
    try {
      setChatLoading(true);
      setChatError(null);
      const data = await apiGet<{ items: FeishuChat[] }>("/api/feishu/chats?page_size=50");
      const items = data?.items ?? [];
      setChats(items);
      return items;
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : "获取飞书群列表失败");
      setChats([]);
      return [];
    } finally {
      setChatLoading(false);
    }
  }

  async function sendTestMessage(receiveId: string, text: string): Promise<boolean> {
    try {
      await apiPost("/api/feishu/message", { receive_id: receiveId, text, receive_id_type: "chat_id" });
      return true;
    } catch (err: unknown) {
      setChatError(err instanceof Error ? err.message : "发送测试消息失败");
      return false;
    }
  }

  return {
    config,
    loading,
    saving,
    testing,
    error,
    testResult,
    chats,
    chatError,
    chatLoading,
    saveConfig,
    testConnection,
    fetchChats,
    sendTestMessage,
    setChatError,
    refetch: fetchConfig,
  };
}