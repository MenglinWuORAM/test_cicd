"""Tests for the selection script itself.

``scripts/`` is not an installable package, so we load ``select_tests.py``
directly from disk by path and exercise its pure classification function and
its dotted-path resolver against the real repository layout.
"""
import importlib.util
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SCRIPT = os.path.join(ROOT, "scripts", "select_tests.py")

_spec = importlib.util.spec_from_file_location("select_tests", SCRIPT)
select_tests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(select_tests)


def classify(files):
    return select_tests.classify(files, ROOT)


def test_src_with_tests_block_adds_mirror_and_declared():
    # add.py has a Tests: block naming test_combo -> mirror + declared target.
    assert classify(["src/quant_core/add.py"]) == [
        "tests/unit/quant_core/test_add.py",
        "tests/unit/quant_core/test_combo.py",
    ]


def test_src_with_empty_tests_block_adds_only_mirror():
    # mul.py has an EMPTY Tests: block -> only its mirror.
    assert classify(["src/quant_core/mul.py"]) == [
        "tests/unit/quant_core/test_mul.py",
    ]


def test_src_without_tests_block_adds_only_mirror():
    # helpers.py has NO Tests: block (no fallback) -> only its mirror.
    assert classify(["src/quant_core/helpers.py"]) == [
        "tests/unit/quant_core/test_helpers.py",
    ]


def test_changed_test_file_selects_itself():
    assert classify(["tests/unit/quant_core/test_combo.py"]) == [
        "tests/unit/quant_core/test_combo.py",
    ]


def test_infra_and_docs_contribute_nothing():
    assert classify(["README.md", "Dockerfile", "pyproject.toml"]) == []


def test_dedup_across_multiple_changes():
    # Changing add.py and test_combo.py must not duplicate test_combo.
    assert classify(
        ["src/quant_core/add.py", "tests/unit/quant_core/test_combo.py"]
    ) == [
        "tests/unit/quant_core/test_add.py",
        "tests/unit/quant_core/test_combo.py",
    ]


def test_resolve_dotted_with_node_id():
    assert (
        select_tests.resolve_dotted("test.unit.quant_core.test_combo.test_both", ROOT)
        == "tests/unit/quant_core/test_combo.py::test_both"
    )


def test_resolve_dotted_file_only():
    assert (
        select_tests.resolve_dotted("test.unit.quant_core.test_combo", ROOT)
        == "tests/unit/quant_core/test_combo.py"
    )


def test_missing_target_is_hard_error():
    with pytest.raises(select_tests.SelectionError):
        select_tests.resolve_dotted("test.unit.quant_core.test_nope", ROOT)
