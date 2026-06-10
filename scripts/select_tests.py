#!/usr/bin/env python3
"""Select pytest targets from a git diff using the mirror + docstring contract.

Stateless, standard library only. Usage::

    python scripts/select_tests.py <git-base-ref>

It runs ``git diff --name-only <base>...HEAD`` (THREE dots: changes on HEAD
since it diverged from base), classifies the changed files, and prints the
resulting pytest targets space-separated on stdout -- or the literal ``NONE``
if nothing is selected.

The selection contract
----------------------
* Mirror rule: ``src/quant_core/xxx.py`` <-> ``tests/unit/quant_core/test_xxx.py``.
  Whenever the mirror exists on disk it is selected automatically.
* ``Tests:`` docstring block declares ONLY cross-cutting tests beyond the
  mirror, in dotted form, e.g.::

      Tests:
          test.unit.quant_core.test_combo

  Extraction is AST-based (``ast.get_docstring``), never regex over raw source.
* Dotted-path resolution: split on dots; map segments to directories under the
  repo root (leading ``test`` -> ``tests/``); the first segment that matches
  ``<seg>.py`` in the current directory ends the path part; any remaining
  segments become pytest ``::`` node ids.
* A resolved target that does not exist on disk is a hard error (exit 1): an
  annotation typo is a bug to fix now, not something to fall back from.
* There is NO full fallback. An unannotated source file selects only its
  mirror. Infra / docs / config changes contribute nothing.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SelectionError(Exception):
    """Raised when an annotation resolves to a target that is not on disk."""


def changed_files(base_ref, repo_root=REPO_ROOT):
    """Return files changed between ``base_ref`` and HEAD (three-dot diff)."""
    out = subprocess.check_output(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=repo_root,
        text=True,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def mirror_for(src_path):
    """Map ``src/<pkg>/xxx.py`` to its mirror ``tests/unit/<pkg>/test_xxx.py``."""
    parts = src_path.split("/")
    middle = parts[1:-1]  # drop leading "src" and the filename
    fname = parts[-1]
    if not fname.startswith("test_"):
        fname = "test_" + fname
    return "/".join(["tests", "unit", *middle, fname])


def tests_block_entries(abs_path):
    """Return the dotted ``Tests:`` entries from a module docstring (AST-based)."""
    with open(abs_path, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    doc = ast.get_docstring(tree)
    if not doc:
        return []
    entries = []
    in_block = False
    for line in doc.splitlines():
        stripped = line.strip()
        if not in_block:
            if stripped == "Tests:":
                in_block = True
            continue
        if not stripped:
            break  # a blank line ends the block
        entries.append(stripped)
    return entries


def resolve_dotted(dotted, repo_root):
    """Resolve a dotted ``Tests:`` entry to a pytest target path.

    Segments map to directories under ``repo_root``; the conventional leading
    ``test`` maps to the ``tests`` directory. The first segment whose
    ``<seg>.py`` exists in the current directory ends the path part; the rest
    become ``::`` node ids.
    """
    segments = dotted.split(".")
    cur = repo_root
    file_rel = None
    node_ids = []
    for idx, seg in enumerate(segments):
        name = "tests" if (idx == 0 and seg == "test") else seg
        candidate = os.path.join(cur, name + ".py")
        if os.path.isfile(candidate):
            file_rel = os.path.relpath(candidate, repo_root).replace(os.sep, "/")
            node_ids = segments[idx + 1:]
            break
        cur = os.path.join(cur, name)
    if file_rel is None:
        raise SelectionError(
            f"Tests: entry {dotted!r} does not resolve to a file on disk "
            f"(looked under {repo_root}). Fix the annotation."
        )
    return file_rel + "".join(f"::{n}" for n in node_ids)


def classify(files, repo_root):
    """Pure classification: changed files -> sorted list of pytest targets.

    Raises ``SelectionError`` if a docstring annotation resolves to a missing
    target.
    """
    targets = set()
    for raw in files:
        path = raw.replace("\\", "/")
        if path.startswith("tests/") and path.endswith(".py"):
            # A changed test file selects itself (if it still exists).
            if os.path.isfile(os.path.join(repo_root, path)):
                targets.add(path)
            continue
        if path.startswith("src/") and path.endswith(".py"):
            mirror = mirror_for(path)
            if os.path.isfile(os.path.join(repo_root, mirror)):
                targets.add(mirror)
            src_abs = os.path.join(repo_root, path)
            if os.path.isfile(src_abs):
                for dotted in tests_block_entries(src_abs):
                    targets.add(resolve_dotted(dotted, repo_root))
            continue
        # Everything else (infra, docs, configs) contributes nothing.
    return sorted(targets)


def main(argv):
    if len(argv) != 2:
        print("usage: select_tests.py <git-base-ref>", file=sys.stderr)
        return 2
    files = changed_files(argv[1])
    try:
        targets = classify(files, REPO_ROOT)
    except SelectionError as exc:
        print(f"select_tests: {exc}", file=sys.stderr)
        return 1
    print(" ".join(targets) if targets else "NONE")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
