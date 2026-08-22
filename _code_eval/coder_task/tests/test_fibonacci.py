from fibonacci import fib


def test_fib_1():
    assert fib(1) == 1


def test_fib_10():
    assert fib(10) == 55


def test_fib_20():
    assert fib(20) == 6765
