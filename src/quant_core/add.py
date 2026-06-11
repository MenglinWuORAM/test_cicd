"""Addition.

This module carries a cross-cutting ``Tests:`` block: besides its own mirror
(``test_add``, added automatically), a change here also exercises
``test_combo`` because that test uses ``add`` together with ``mul``.

Tests:
    test.unit.quant_core.test_combo
"""


def add(a, b):
    """Return the sum of ``a`` and ``b``."""
    result = a + b
    return result


def add_many(values):
    """Return the running sum of ``values``."""
    total = 0
    for v in values:
        total = add(total, v)
    return total
