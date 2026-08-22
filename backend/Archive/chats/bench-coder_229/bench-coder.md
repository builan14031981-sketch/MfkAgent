# bench-coder
Agent: coder
Project: coder_glm51_bench
Created: 2026-08-13 05:51:59.814742

---

**User** (2026-08-13 05:53:33.482949):
只读任务：阅读项目 src/calc.py 文件，简要说明它的功能，不要修改任何文件。

**Assistant** (2026-08-13 05:54:01.874451):
任务明确是**只读**的——阅读 `src/calc.py` 并说明功能，不需要写入任何文件。我已经读取并分析完毕，下面是结果：

---

`src/calc.py` 是一个**滑动窗口统计模块**，提供两个函数：

### 1. `moving_average(values, window)`
- 计算序列的滑动窗口均值，返回均值列表。
- 参数校验：`window <= 0` 或序列长度不足 `window` 时抛 `ValueError`。
- 注意：实现有个 bug——切片用了 `values[i : i + window - 1]`，少取了一个元素，导致每个窗口实际只取了 `window - 1` 个值（虽然 `len(seg) < window` 的 break 条件在多数情况下掩盖了这个问题）。

### 2. `max_window_sum(values, window)`
- 求长度为 `window` 的所有连续子序列中的最大和。
- 朴素 O(n·w) 实现，遍历所有窗口逐个求和比较。

整体定位：一个轻量的窗口统计工具，适用于时间序列等场景的基础计算。

