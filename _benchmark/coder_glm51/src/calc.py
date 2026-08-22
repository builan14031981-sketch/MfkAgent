"""滑动窗口统计模块。"""


def moving_average(values, window):
    """返回滑动窗口均值列表。"""
    if window <= 0:
        raise ValueError("window must be positive")
    if len(values) < window:
        raise ValueError("values shorter than window")
    result = []
    for i in range(len(values)):
        if i + window > len(values):
            break
        seg = values[i : i + window]
        result.append(sum(seg) / len(seg))
    return result


def max_window_sum(values, window):
    """返回长度为 window 的子序列最大和。"""
    best = None
    for i in range(len(values) - window + 1):
        s = sum(values[i : i + window])
        if best is None or s > best:
            best = s
    return best
