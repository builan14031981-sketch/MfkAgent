/**
 * settingsSearchIndex —— 设置项只读搜索索引（供 SettingsPanel 搜索框消费）
 *
 * 设计说明：
 * - 仅用于"导航级搜索"：过滤左侧 7 个 tab + 显示命中字段计数，不侵入字段渲染。
 * - 字段 label 与 zh-CN.json 文案对齐；aliases 补充英文/别名关键词，便于中英混合搜索。
 * - 新增设置项时在此登记一行即可让该设置可被搜索到。
 */
export interface SettingSearchField {
  key: string;
  label: string;
  aliases?: string[];
}

export interface SettingSearchEntry {
  section: string;
  fields: SettingSearchField[];
}

export const SETTINGS_SEARCH_INDEX: SettingSearchEntry[] = [
  {
    section: "general",
    fields: [
      { key: "theme", label: "主题", aliases: ["theme", "深色", "浅色", "system"] },
      { key: "visual_theme", label: "视觉主题", aliases: ["visual theme", "石墨"] },
      { key: "language", label: "语言", aliases: ["language", "英文", "中文"] },
      { key: "font", label: "字体", aliases: ["font", "字号", "字体大小"] },
      { key: "accent", label: "强调色", aliases: ["accent color"] },
      { key: "hero_theme", label: "首页启动主题", aliases: ["hero", "首页"] },
      { key: "greeting", label: "首页台词", aliases: ["greeting", "欢迎语"] },
      { key: "browser_homepage", label: "浏览器主页", aliases: ["browser homepage", "浏览器", "网页", "主页"] },
    ],
  },
  {
    section: "model",
    fields: [
      { key: "default_model", label: "默认模型", aliases: ["default model", "model"] },
      { key: "default_reasoning_effort", label: "默认推理程度", aliases: ["reasoning", "推理"] },
      { key: "show_reasoning", label: "显示思考过程", aliases: ["show reasoning", "思考过程", "thinking"] },
      { key: "providers", label: "模型提供商", aliases: ["provider", "API Key", "api key"] },
      { key: "api_base", label: "API Base", aliases: ["base url", "端点覆盖", "baseurl"] },
      { key: "enabled_models", label: "模型候选池", aliases: ["enabled models", "已加入候选池"] },
      { key: "fetch_remote", label: "一键拉取官方模型", aliases: ["fetch", "拉取", "官方模型"] },
      { key: "test_connection", label: "测试连接", aliases: ["test", "连通性"] },
      { key: "custom_model", label: "自定义模型", aliases: ["custom", "第三方"] },
      { key: "vision", label: "备用识图模型", aliases: ["vision", "识图", "图片"] },
      { key: "tattoo", label: "生图模型", aliases: ["image gen", "生图", "图像生成", "tattoo"] },
      { key: "temperature", label: "温度", aliases: ["temperature"] },
      { key: "max_tokens", label: "最大 Token", aliases: ["max tokens", "token"] },
    ],
  },
  {
    section: "ai",
    fields: [
      { key: "default_agent", label: "默认 Agent", aliases: ["agent", "智能体"] },
      { key: "default_personality", label: "默认人格", aliases: ["personality", "人格"] },
      { key: "memory", label: "长期记忆", aliases: ["memory", "记忆"] },
      { key: "sub_agent", label: "子代理", aliases: ["subagent", "子代理"] },
      { key: "reasoning", label: "推理强度", aliases: ["reasoning"] },
    ],
  },
  {
    section: "security",
    fields: [
      { key: "matrix", label: "审批矩阵", aliases: ["matrix", "审批规则"] },
      { key: "audit", label: "审计日志", aliases: ["audit", "审计"] },
      { key: "logs", label: "应用日志", aliases: ["logs", "日志"] },
      { key: "status", label: "运行状态", aliases: ["status", "状态"] },
      { key: "guardrails", label: "护栏与命令风险", aliases: ["guardrail", "命令风险"] },
    ],
  },
  {
    section: "extensions",
    fields: [
      { key: "skills", label: "技能", aliases: ["skill", "技能"] },
      { key: "plugins", label: "插件", aliases: ["plugin"] },
    ],
  },
  {
    section: "archive",
    fields: [
      { key: "archive_dir", label: "归档文件夹", aliases: ["archive dir", "导出", "备份"] },
      { key: "archive_list", label: "归档列表", aliases: ["archive list", "恢复"] },
    ],
  },
  {
    section: "about",
    fields: [
      { key: "version", label: "版本", aliases: ["version", "关于"] },
    ],
  },
  {
    section: "shortcuts",
    fields: [
      { key: "shortcuts", label: "快捷键", aliases: ["shortcut", "快捷键", "keyboard", "键位", "hotkey"] },
    ],
  },
];