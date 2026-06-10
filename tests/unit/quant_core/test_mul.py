"""Mirror test for ``quant_core.mul``."""
from quant_core.mul import mul


def test_mul_positive():
    assert mul(2, 3) == 6


def test_mul_by_zero():
    assert mul(123, 0) == 0
