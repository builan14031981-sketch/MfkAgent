# bench
Agent: coder
Project: coder_glm51_bench
Created: 2026-08-13 06:23:33.590418

---

**User** (2026-08-13 06:23:33.615583):
修复任务：项目 src/calc.py 中存在 bug，tests/test_calc.py 有一个测试失败。请定位根因并修复，修复后必须运行 pytest 验证全部通过，向用户汇报修改了哪些文件与验证结果。

**Assistant** (2026-08-13 06:24:11.577482):
修复完成，汇报如下：

## 根因分析

`src/calc.py` 中 `moving_average` 函数存在两个 bug：

1. **切片范围错误**：`values[i : i + window - 1]` 少取了一个元素，应为 `values[i : i + window]`。例如 `window=3` 时，切片只取了 2 个元素，导致均值计算错误。
2. **循环范围错误**：`range(len(values))` 遍历了所有索引，但靠后的索引无法凑齐完整窗口。应为 `range(len(values) - window + 1)`。

这两个 bug 叠加导致函数返回空列表 `[]`，测试断言 `== [2.0, 3.0, 4.0]` 失败。

## 修改文件

仅修改 `src/calc.py`，改动两行：

| 行 | 修改前 | 修改后 |
|---|---|---|
| 切片 | `values[i : i + window - 1]` | `values[i : i + window]` |
| 循环 | `range(len(values))` | `range(len(values) - window + 1)` |

同时移除了因切片范围错误而引入的冗余 `if len(seg) < window: break` 判断。

## 验证结果

```
tests/test_calc.py::test_moving_average PASSED
tests/test_calc.py::test_max_window_sum  PASSED
2 passed in 0.05s
```

