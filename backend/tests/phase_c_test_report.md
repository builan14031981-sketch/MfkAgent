# MfkAgent Tool Runtime Phase C 测试报告

- 时间: 2026-08-09 23:41:07
- 临时工作目录: `C:\Users\Asus\AppData\Local\Temp\mfk_phaseC_2ixo8lpg`
- 测试模式: 单元级 (normalizer) + FastAPI TestClient + 脚本化 LLM

## 结果总览

| # | 用例 | 结果 | 耗时 |
|---|------|------|------|
| 1 | Normalizer 单元用例 | ✅ PASS | 0ms |
| 2 | 集成: XML invoke 归一化执行 | ✅ PASS | 1390ms |
| 3 | 集成: 纯文本调用归一化执行 | ✅ PASS | 1094ms |
| 4 | 集成: 解析失败回馈重生成 | ✅ PASS | 891ms |
| 5 | 非流式审批明确拒绝 | ❌ FAIL | 0ms |

**通过率: 4/5**

### 1. Normalizer 单元用例

- cases: [('invoke+JSON', True), ('invoke+json围栏', True), ('tool_call+name+arguments', True), ('文本块状', True), ('文本行内', True), ('未知工具→issue', True), ('write_file非JSON→issue', True), ('空工具名→issue', True), ('无调用→空结果', True), ('多调用混合', True)]

### 2. 集成: XML invoke 归一化执行

- case: xml_invoke
- executed: True
- chat_id: 1

### 3. 集成: 纯文本调用归一化执行

- case: text_call
- executed: True
- chat_id: 2

### 4. 集成: 解析失败回馈重生成

- case: parse_fail
- no_execution: True
- chat_id: 3

### 5. 非流式审批明确拒绝

- 说明: LLM 轮次溢出：调用了第 2 轮

> 失败: LLM 轮次溢出：调用了第 2 轮

## 结论

❌ **1 项未通过**，详见上方明细。
