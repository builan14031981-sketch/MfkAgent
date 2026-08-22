import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from calc import moving_average, max_window_sum


def test_moving_average():
    assert moving_average([1, 2, 3, 4, 5], 3) == [2.0, 3.0, 4.0]


def test_max_window_sum():
    assert max_window_sum([-2, 1, -3, 4, -1, 2, 1, -5, 4], 4) == 6
