"""Mirror test for ``quant_core.helpers``."""
import pytest

from quant_core.helpers import clamp


def test_clamp_within():
    assert clamp(5, 0, 10) == 5


def test_clamp_below():
    assert clamp(-3, 0, 10) == 0


def test_clamp_above():
    assert clamp(99, 0, 10) == 10


def test_clamp_bad_bounds():
    with pytest.raises(ValueError):
        clamp(1, 10, 0)
