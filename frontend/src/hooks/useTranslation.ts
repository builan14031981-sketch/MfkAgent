/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { useSettings } from "./useSettings";

import zhCN from "@/locales/zh-CN.json";
import enUS from "@/locales/en-US.json";

const locales: Record<string, typeof zhCN> = {
  "zh-CN": zhCN,
  "en-US": enUS,
};

function getNestedValue(obj: Record<string, unknown>, path: string): string {
  const keys = path.split(".");
  let current: unknown = obj;
  for (const key of keys) {
    if (current && typeof current === "object" && key in current) {
      current = (current as Record<string, unknown>)[key];
    } else {
      return path;
    }
  }
  return typeof current === "string" ? current : path;
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

      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          value = value.replace(`{${k}}`, v);
        });
      }

      return value;
    },
    [locale]
  );

  return { t, locale };
}
