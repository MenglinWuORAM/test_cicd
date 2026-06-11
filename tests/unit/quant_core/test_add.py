"""Mirror test for ``quant_core.add``."""
from quant_core.add import add, add_many


def test_add_positive():
    assert add(2, 3) == 5


def test_add_negative():
    assert add(-1, -1) == -2


def test_add_zero():
    assert add(0, 7) == 7


def test_add_many():
    assert add_many([1, 2, 3]) == 6
    assert add_many([]) == 0
