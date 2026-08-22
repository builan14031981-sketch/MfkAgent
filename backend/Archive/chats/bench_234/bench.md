# bench
Agent: coder
Project: coder_glm51_bench
Created: 2026-08-13 06:16:01.215802

---

**User** (2026-08-13 06:16:01.249194):
修复任务：项目 src/calc.py 中存在 bug，tests/test_calc.py 有一个测试失败。请定位根因并修复，修复后必须运行 pytest 验证全部通过，向用户汇报修改了哪些文件与验证结果。

**Assistant** (2026-08-13 06:16:37.870735):
修复完成，汇报如下：

## 根因分析

`src/calc.py` 的 `moving_average` 函数中有两处 off-by-one 错误：

1. **切片范围错误**：`values[i : i + window - 1]` 少取了 1 个元素，实际只取了 `window - 1` 个，导致均值计算错误。
2. **边界判断错误**：`if len(seg) < window: break` 配合上面的错误切片，导致第一次迭代就 break，返回空列表 `[]`。

## 修复内容

修改文件：`src/calc.py`

| 行 | 修复前 | 修复后 |
|---|---|---|
| 切片 | `values[i : i + window - 1]` | `values[i : i + window]` |
| 边界 | `if len(seg) < window: break` | `if i + window > len(values): break` |

## 验证结果

```
tests/test_calc.py::test_moving_average PASSED
tests/test_calc.py::test_max_window_sum   PASSED
2 passed in 0.05s
```

全部测试通过，`max_window_sum` 函数未受影响。

