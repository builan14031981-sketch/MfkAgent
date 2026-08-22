def fib(n):
    """返回第 n 个斐波那契数（n 从 1 开始，fib(1)=1, fib(2)=1）"""
    if n < 1:
        raise ValueError("n 必须大于等于 1")
    if n == 1 or n == 2:
        return 1
    a, b = 1, 1
    for _ in range(3, n + 1):
        a, b = b, a + b
    return b


if __name__ == '__main__':
    print("前 10 个斐波那契数：")
    for i in range(1, 11):
        print(f"fib({i}) = {fib(i)}")
