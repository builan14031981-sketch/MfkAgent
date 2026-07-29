/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { useSettings } from "./useSettings";

import zhCN from "@/locales/zh-CN.json";
import enUS from "@/locales/en-US.json";

const locales: Record<string, typeof zhCN> = {
  "zh-CN": zhCN,
  "en-US": enUS,
};

function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  const keys = path.split(".");
  let current: unknown = obj;
  for (const key of keys) {
    if (current && typeof current === "object" && key in current) {
      current = (current as Record<string, unknown>)[key];
    } else {
      return path;
    }
  }
  return current;
}

export function useTranslation() {
  const { settings } = useSettings();
  const [locale, setLocale] = useState<string>("zh-CN");

  useEffect(() => {
    if (settings?.language) {
      setLocale(settings.language);
    }
  }, [settings?.language]);

  const t = useCallback(
    (key: string, params?: Record<string, string>): string => {
      const messages = locales[locale] || locales["zh-CN"];
      let value = getNestedValue(messages as Record<string, unknown>, key);

      // 如果值不是字符串，返回key路径
      if (typeof value !== "string") {
        return key;
      }

      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          value = (value as string).replace(`{${k}}`, v);
        });
      }

      return value as string;
    },
    [locale]
  );

  const tArray = useCallback(
    (key: string): string[] => {
      const messages = locales[locale] || locales["zh-CN"];
      const value = getNestedValue(messages as Record<string, unknown>, key);

      // 如果值是数组，返回数组
      if (Array.isArray(value)) {
        return value as string[];
      }

      // 如果值是字符串，返回单元素数组
      if (typeof value === "string") {
        return [value];
      }

      return [key];
    },
    [locale]
  );

  return { t, tArray, locale };
}
