"""Cross-cutting test: uses BOTH ``add`` and ``mul``.

There is no source file named ``combo.py`` -- this test has no mirror. It is
reached only because ``add.py`` (and could be ``mul.py``) names it in a
``Tests:`` block. That is the whole point of the docstring annotation: declare
the tests that the mirror rule alone would miss.
"""
from quant_core.add import add
from quant_core.mul import mul


def test_both():
    # (2 * 3) + 4 == 10
    assert add(mul(2, 3), 4) == 10


def test_distributes():
    assert mul(add(1, 2), 4) == 12
