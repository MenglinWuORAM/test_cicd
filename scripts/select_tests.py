#!/usr/bin/env python3
"""
Select pytest targets from a git diff using the mirror + docstring contract.
Usage: python scripts/select_tests.py <git-base-ref>

It runs ``git diff --name-only <base>...HEAD``, classifies the changed files, and prints the
resulting pytest targets space-separated on stdout; or the literal ``NONE`` if nothing is selected.

The selection contract
----------------------
* Mirror rule: ``src/quant_core/xxx.py`` <-> ``tests/unit/quant_core/test_xxx.py``, selected automatically.
* ``Tests:`` docstring block declares ONLY cross-cutting tests beyond the
  mirror, in dotted form, e.g.:
      Tests:
          test.unit.quant_core.backtest_framework.backtester.backtester
* Tooling under ``scripts/`` has its own tests with the same ``Tests:`` block.
* An unannotated source file selects only its mirror. Other infra / docs / config changes contribute nothing.

Tests:
    test.tooling.test_select
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class SelectionError(Exception):
    pass


def changed_files(base_ref, repo_root=REPO_ROOT):
    out = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=repo_root,
        text=True,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def mirror_for(src_path):
    """mirror the src to its corresponding test"""
    parts = src_path.split("/")
    middle = parts[1:-1]  # drop leading "src" and the filename
    fname = parts[-1]
    if not fname.startswith("test_"):
        fname = "test_" + fname
    return "/".join(["tests", "unit", *middle, fname])


def get_tests_docstring(abs_path):
    """Return the dotted ``Tests:`` entries from a module docstring.

    The block is the indented lines under a column-0 ``Tests:`` header;
    it ends at the first blank or dedented line.
    """
    with open(abs_path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    doc = ast.get_docstring(tree)
    if not doc:
        return []
    entries = []
    in_block = False
    for line in doc.splitlines():
        if not in_block:
            if line.strip() == "Tests:" and not line[:1].isspace():
                in_block = True
            continue
        if not line.strip():
            break  
        if not line[:1].isspace():
            break  # a dedented line next section header ends the block
        entries.append(line.strip())
    return entries


def resolve_dotted(dotted, repo_root):
    """Parse the entry of a test block to a pytest target path."""
    segments = dotted.split(".")
    cur = repo_root
    file_rel = None
    node_ids = []
    for idx, seg in enumerate(segments):
        name = "tests" if (idx == 0 and seg == "test") else seg
        candidate = os.path.join(cur, name + ".py")
        if os.path.isfile(candidate):
            file_rel = os.path.relpath(candidate, repo_root).replace(os.sep, "/")
            node_ids = segments[idx + 1:]  # leftover segments are pytest node ids
            break
        cur = os.path.join(cur, name)
    if file_rel is None:
        raise SelectionError(
            f"Tests: entry {dotted!r} does not resolve to a file on disk "
            f"(looked under {repo_root}). Fix the annotation."
        )
    return file_rel + "".join(f"::{n}" for n in node_ids)


def _add_docstring_targets(targets, abs_path, repo_root):
    if os.path.isfile(abs_path):
        for dotted in get_tests_docstring(abs_path):
            targets.add(resolve_dotted(dotted, repo_root))


def select_target_tests(files, repo_root):
    """Find all the target tests implied by the changed files."""
    targets = set()
    for raw in files:
        path = raw.replace("\\", "/")
        if path.startswith("tests/") and path.endswith(".py"):   # A changed test file selects itself
            if os.path.isfile(os.path.join(repo_root, path)):
                targets.add(path)
            continue
        if path.startswith("src/") and path.endswith(".py"):
            mirror = mirror_for(path)
            if os.path.isfile(os.path.join(repo_root, mirror)):
                targets.add(mirror)
            _add_docstring_targets(targets, os.path.join(repo_root, path), repo_root)
            continue
        if path.startswith("scripts/") and path.endswith(".py"):
            _add_docstring_targets(targets, os.path.join(repo_root, path), repo_root)
            continue
    return sorted(targets)

def main(argv):
    if len(argv) != 2:
        print("usage: select_tests.py <git-base-ref>", file=sys.stderr)
        return 2
    files = changed_files(argv[1])
    try:
        targets = select_target_tests(files, REPO_ROOT)
    except SelectionError as exc:
        print(f"select_tests: {exc}", file=sys.stderr)
        return 1
    print(" ".join(targets) if targets else "NONE")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
