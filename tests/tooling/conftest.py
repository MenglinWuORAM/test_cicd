import importlib.util
import os

import pytest

# Load the script under test by path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_spec = importlib.util.spec_from_file_location(
    "select_tests", os.path.join(_ROOT, "scripts", "select_tests.py")
)
select_tests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(select_tests)

SelectionError = select_tests.SelectionError

TEST_STUB = "def test_stub():\n    pass\n"


def _module_with_tests(*entries):
    """Source module whose docstring declares the given dotted ``Tests:`` entries."""
    lines = ['"""Widget.', "", "Tests:"]
    lines += [f"    {e}" for e in entries]
    lines += ['"""', "", "def f():", "    return 1"]
    return "\n".join(lines) + "\n"


def _module_no_tests():
    """Source module with a docstring but no ``Tests:`` block."""
    return '"""Widget without a Tests block."""\n\ndef f():\n    return 1\n'


# One shared repository layout for tests.
STANDARD_REPO = {
    # src modules
    "src/widget/alpha.py": _module_with_tests("test.unit.widget.test_combo"),  # mirror + declared
    "src/widget/beta.py": _module_with_tests(),                                # empty Tests: block
    "src/widget/gamma.py": _module_no_tests(),                                 # no block at all
    "src/widget/delta.py": _module_with_tests("test.unit.widget.test_combo.test_both"),  # node id, no mirror
    "src/widget/bad.py": _module_with_tests("test.unit.widget.test_nope"),     # points at a missing target
    "src/widget/sec.py": (                                                      # Tests: glued to next section
        '"""Widget.\n'
        "\n"
        "Tests:\n"
        "    test.unit.widget.test_combo\n"
        "Returns:\n"
        "    int\n"
        '"""\n\n'
        "def f():\n    return 1\n"
    ),
    # to test only the column-0 one counts.
    "scripts/tool.py": (
        '"""Tooling.\n'
        "\n"
        "An indented example must NOT be matched:\n"
        "    Tests:\n"
        "        test.unit.widget.test_combo\n"
        "\n"
        "Tests:\n"
        "    test.tooling.test_tool\n"
        '"""\n'
    ),
    # tests:
    "tests/unit/widget/test_alpha.py": TEST_STUB,
    "tests/unit/widget/test_beta.py": TEST_STUB,
    "tests/unit/widget/test_gamma.py": TEST_STUB,
    "tests/unit/widget/test_combo.py": TEST_STUB,
    "tests/unit/widget/test_combo/keep.txt": "x",  # same-named dir, to prove file wins over dir
    "tests/tooling/test_tool.py": TEST_STUB,
}


def select(root, files):
    return select_tests.select_target_tests(files, root)


@pytest.fixture
def repo(tmp_path):
    """Materialise STANDARD_REPO under tmp_path and return the repo root (str)."""
    for relpath, content in STANDARD_REPO.items():
        p = tmp_path / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return str(tmp_path)
