# 答辩PPT 内容 JSON 结构与红线约束（Schema）

`generate_content` 必须只输出如下结构的 JSON（不要输出多余解释文字，只输出 JSON）：

```json
{
  "title": "论文题目（用于封面与文件名）",
  "discipline": "gongke|liberal|science|medical|art_design",
  "duration_min": 10,
  "slides": [
    {
      "role": "cover|section|background|status|method|result|innovation|conclusion|literature|theory|analysis|data|concept|process|works|summary|closing",
      "layout": "cover|section|bullets|two_column|image_right|closing",
      "title": "本页标题（≤18字）",
      "bullets": ["要点1（≤150字/页，全页正文合计≤150字）", "要点2", "要点3"],
      "note": "页脚/备注（可空）",
      "source_refs": ["P3-2", "P5-1"]
    }
  ]
}
```

## 红线（强制，违反即判不合格）
1. **每页正文合计 ≤ 150 个汉字**（含 bullets 全部文字）。
2. **每页要点 ≤ 3 条**（bullets 数组长度 ≤ 3）。
3. **每条数据/专有名词必须带 `source_refs`**：引用源文档标记，格式 `P<页码>-<段号>`（与 read_doc 输出一致）。无出处的数字一律不得出现；若文档确实没有，标注 `"source_refs": ["待补充"]` 并在 bullets 里写"待用户提供"。
4. **禁止编造**：所有内容必须来自用户文档，不得凭空生成数据、结论或引用。
5. **页数必须匹配时长**：5分钟≈9页、10分钟≈13页、15分钟≈16页、20分钟≈20页（允许±1）。封面/章节页/结尾页计入总页数。
6. **封面页** `role=cover` 必须存在且为首页；**结尾页** `role=closing`（致谢/请批评指正）必须为末页。
7. 语言：短句、要点化、口语化可上台讲述；避免大段文字堆砌。

## 页面类型（layout）说明
- `cover`：封面，仅 title + 副标题（学校/专业/姓名/导师可空占位）。
- `section`：章节分隔页，标题为该章名，无 bullets。
- `bullets`：标题 + ≤3 要点。
- `two_column`：标题 + 左右两栏要点（左"问题/输入"，右"做法/输出"），每栏≤3行。
- `image_right`：标题 + 左侧≤3要点 + 右侧图片占位（有素材图时填，无则占位）。
- `closing`：致谢页。
