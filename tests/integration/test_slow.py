"""Integration test.

This is deliberately trivial (add + mul together) plus a ``time.sleep`` to
stand in for the cost of a real integration test. In a real repository this is
where you would spin up external services -- a database, a message broker, a
downstream HTTP API -- and assert that the pieces work together end to end.
Because it is slow and/or needs infrastructure, it never runs at PR-to-dev
time; it runs only on PR-to-main, on push-main (shadow), and nightly (EOD).
"""
import time

from quant_core.add import add
from quant_core.mul import mul


def test_pipeline_end_to_end():
    time.sleep(2)  # stand-in for real external-service latency
    # ((3 + 4) * 2) == 14
    assert mul(add(3, 4), 2) == 14
