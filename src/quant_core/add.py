"""Addition.

This module carries a cross-cutting ``Tests:`` block: besides its own mirror
(``test_add``, added automatically), a change here also exercises
``test_combo`` because that test uses ``add`` together with ``mul``.

Tests:
    test.unit.quant_core.test_combo
"""


def add(a, b):
    """Return the sum of ``a`` and ``b``."""
    return a + b
