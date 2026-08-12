/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useCallback } from "react";
import { apiGet, apiPost } from "@/lib/api";

export interface SkillInfo {
  id: string;
  name: string;
  category: string;
  description: string;
  version: string;
  tags: string[];
  installed: boolean;
}

/** Skill 市场（内置 15 个 Skill）：浏览 + 安装 + 卸载 */
export function useSkills() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSkills = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiGet<{ skills: SkillInfo[] }>("/api/skills/builtin");
      setSkills(data.skills || []);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSkills();
  }, [fetchSkills]);

  async function installSkill(skillId: string) {
    await apiPost(`/api/skills/install`, { skill_id: skillId });
    await fetchSkills();
  }

  async function uninstallSkill(skillId: string) {
    await apiPost(`/api/skills/uninstall`, { skill_id: skillId });
    await fetchSkills();
  }

  return { skills, loading, error, installSkill, uninstallSkill, refetch: fetchSkills };
}
