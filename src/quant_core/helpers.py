"""Small numeric helpers.

NOTE: there is deliberately NO ``Tests:`` block in this module. A change to
``helpers.py`` therefore selects only its mirror (``test_helpers``). Chasing
cross-cutting impact here is intentionally left undone -- the "branches must be
up to date" rule plus the nightly EOD full run are what catch any drift. This
is the discipline demo: under-annotated code is allowed, and the diff-coverage
gate is what keeps a change honest about what it actually touched.
"""


def clamp(x, lo, hi):
    """Clamp ``x`` into the inclusive range ``[lo, hi]``."""
    if lo > hi:
        raise ValueError("lo must be <= hi")
    return max(lo, min(x, hi))
