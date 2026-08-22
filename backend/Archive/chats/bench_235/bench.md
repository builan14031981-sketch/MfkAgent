# bench
Agent: coder
Project: coder_glm51_bench
Created: 2026-08-13 06:16:48.757702

---

**User** (2026-08-13 06:16:48.783726):
只读任务：请阅读 src/calc.py 与 tests/test_calc.py，定位为什么 test_moving_average 失败，说明根因。这是只读分析，禁止修改任何文件。

**Assistant** (2026-08-13 06:17:31.472288):
根因定位完成，以下是分析结果：

---

## `test_moving_average` 失败根因

`moving_average` 函数中有 **两个 bug**，都出在切片逻辑上：

### Bug 1：切片少取了一个元素

```python
# 源码（第 10 行）
seg = values[i : i + window - 1]   # ❌ 切了 window-1 个元素
```

当 `window=3` 时，`values[0:2]` 只取到索引 0、1（2 个元素），而不是期望的 3 个。

**正确写法应为：**
```python
seg = values[i : i + window]       # ✅ 切 window 个元素
```

### Bug 2：中断条件用了错误的长度判断

```python
# 源码（第 11-12 行）
if len(seg) < window:              # ❌ seg 永远只有 window-1 个元素，第一轮就会 break
    break
```

由于 Bug 1 导致 `seg` 始终只有 `window-1` 个元素，`len(seg) < window` 在第一次循环就为 `True`，直接 `break`。结果列表最多只有 1 个元素（且均值也是错的）。

**正确写法应为：**
```python
if i + window > len(values):       # ✅ 判断剩余元素是否够一个窗口
    break
```

### 实际执行效果（以测试用例为例）

输入 `values=[1,2,3,4,5], window=3`：

| 步骤 | i | seg (实际) | len(seg) | window | 判断 | 结果 |
|------|---|-----------|----------|--------|------|------|
| 1 | 0 | [1,2] | 2 | 3 | 2<3 → break | 均值 1.5 被追加后退出 |

函数返回 `[1.5]`，而测试期望 `[2.0, 3.0, 4.0]`，断言失败。

---

**总结**：核心问题是切片 `values[i:i+window-1]` 少取了 1 个元素，连带导致后续的 `len(seg) < window` 判断逻辑也失效。修复两处即可：切片改为 `i+window`，中断条件改为 `i + window > len(values)`。

> 本任务为只读分析，未修改任何文件。

