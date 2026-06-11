"""
ests for the selection script (``scripts/select_tests.py``).
Every case selects against the shared ``STANDARD_REPO`` 
"""
import pytest

from conftest import SelectionError, select

SELECT_CASES = [
    (["src/widget/alpha.py"], ["tests/unit/widget/test_alpha.py", "tests/unit/widget/test_combo.py"]),  # block -> mirror + declared
    (["src/widget/beta.py"], ["tests/unit/widget/test_beta.py"]),                                       # block -> mirror only
    (["src/widget/gamma.py"], ["tests/unit/widget/test_gamma.py"]),                                     # no block -> mirror only
    (["tests/unit/widget/test_combo.py"], ["tests/unit/widget/test_combo.py"]),                         # changed test selects itself
    (["src/widget/ghost.py", "tests/unit/widget/test_ghost.py"], []),                                   # deleted/absent files select nothing
    (["README.md", "Dockerfile", "pyproject.toml", "cfg/x.yaml"], []),                                  # infra and docs select nothing
    (["src/widget/alpha.py", "tests/unit/widget/test_combo.py"], ["tests/unit/widget/test_alpha.py", "tests/unit/widget/test_combo.py"]),  # dedup across changes
    (["src/widget/delta.py"], ["tests/unit/widget/test_combo.py::test_both"]),                          # file wins over same-named dir
    (["scripts/tool.py"], ["tests/tooling/test_tool.py"]),                                              # only column-0 Tests: 
    (["src/widget/sec.py"], ["tests/unit/widget/test_combo.py"]),                                       # Tests: block stops at glued next section
    (["src/widget/bad.py"], SelectionError),                                                            # missing target 
]


@pytest.mark.parametrize("changed, expected", SELECT_CASES)
def test_select(repo, changed, expected):
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            select(repo, changed)
    else:
        assert select(repo, changed) == expected
