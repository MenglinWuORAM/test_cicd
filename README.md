# selection-demo

A small, immediately runnable CI/CD demo for a **self-hosted Windows runner**
with a **local Docker daemon**. There is no external registry and no repository
secret anywhere — images are built and kept on the local server's daemon, and
the only token used (`GITHUB_TOKEN` for tagging) is the one GitHub Actions
injects automatically.

The application code is deliberately trivial (`add`, `mul`, `clamp`). All the
weight is in the pipeline, the **docstring-based test selection** script, and
the **diff-coverage gate**.

---

## What the pipeline does (the four+one scenarios)

| Trigger | Workflow / job | Behaviour |
|---|---|---|
| **PR → dev** | `ci.yml` · `selective-tests` | Run only the tests a change implies (mirror + declared cross-cutting), then a **diff-coverage gate at 50%** on the changed lines. Integration never runs here. |
| **push dev** | `ci.yml` · `version-bump` | No tests. Bump the `vX.Y.Z` tag (patch by default). |
| **PR → main** | `ci.yml` · `guard-main-source` + `integration-full` | Reject unless the source branch is `dev`; otherwise run `tests/integration`. |
| **push main** | `deploy.yml` · `deploy` + `shadow-test` | Build the **prod** image locally, tag `<devVersion>-<shortSha>` and `latest`. A full shadow suite runs **alongside** deploy and does **not** gate it. |
| **nightly (EOD)** | `eod.yml` | Scheduled full unit + integration run on `dev`. |

### Why no semantic-conflict test on push-dev
Two PRs that each pass selective tests in isolation can still break `dev` once
both land (each only ran its own slice). The defense is **not** more YAML — it
is the branch-protection checkbox **"Require branches to be up to date before
merging"**, which forces a PR to re-test against the latest `dev` before it can
merge. The nightly EOD run is the backstop.

---

## The selection contract

**Mirror rule:** `src/quant_core/xxx.py` ⇄ `tests/unit/quant_core/test_xxx.py`.
The script adds the mirror **automatically** whenever it exists on disk.

**`Tests:` docstring block** declares *only* cross-cutting tests beyond the
mirror, in dotted form:

```python
"""Addition.

Tests:
    test.unit.quant_core.test_combo
"""
```

**Dotted-path resolution:** split on dots; map segments to directories under
the repo root (leading `test` → `tests/`); the first segment that matches
`<seg>.py` in the current directory ends the path part; any remaining segments
become pytest `::` node ids. For example
`test.unit.quant_core.test_combo.test_both` →
`tests/unit/quant_core/test_combo.py::test_both`.

**Hard rules:**
* A resolved target that is **not on disk** → the script **exits non-zero**. An
  annotation typo is a bug to fix now, not something to fall back from.
* **No full fallback.** `helpers.py` has no `Tests:` block, so a change to it
  selects *only* its mirror. This is deliberate: discipline plus the coverage
  gate keep changes honest about what they touch.
* Infra / docs / config changes contribute **nothing** at PR level.

Extraction is **AST-based** (`ast.get_docstring`), never regex over raw source.
The pure classifier `classify()` lives in `scripts/select_tests.py` and is
unit-tested in `tests/unit/quant_core/test_select.py`.

---

## Coverage path technicality (why it actually works)

`pytest` runs **inside** the container (`/app`) but `diff-cover` runs **on the
runner** against the checkout. Two things make the paths line up:

1. The test image installs the package **editable** (`pip install -e`), so
   `quant_core` resolves to `/app/src` rather than site-packages.
2. `pyproject.toml` sets `[tool.coverage.run] relative_files = true` (plus a
   `[tool.coverage.paths]` mapping), so `coverage.xml` records
   `src/quant_core/add.py` — exactly the path `git diff` reports.

The volume mount uses **`$(pwd -W)`** (e.g. `C:/Users/.../repo`) rather than
`$PWD`, because Git Bash would otherwise mangle the path Docker Desktop needs.

> Verified locally: container `coverage.xml` contained
> `filename="src/quant_core/add.py"`, and `diff-cover` matched it against the
> `dev` branch with no `--src-roots` tweaking.

---

## Run it locally (verified)

```bash
# full suite in the test image (what shadow/integration/EOD run)
docker build --target test -t selection-demo:test .
docker run --rm selection-demo:test pytest          # 21 passed (py3.12)

# selection script against a base ref (three-dot diff)
python scripts/select_tests.py origin/dev           # prints targets or NONE

# prod image sanity
docker build --target prod -t selection-demo:prod .
docker run --rm selection-demo:prod                 # "prod image ok: quant_core"
```

---

## Live demo script

### 0. Setup (one-time)
```bash
git checkout -b dev && git push -u origin dev
```
Configure branch protection **manually** (this is intentionally *not* in YAML):
* **dev** → require a PR **and** ✅ **Require branches to be up to date before
  merging**. *This checkbox is the semantic-conflict defense.*
* **main** → require a PR (from `dev`), require approval, require status checks.

### 1. Selection + mirror
Edit the implementation of `add()`, open a **PR → dev**. The `selective-tests`
log shows the mirror `test_add` **and** the declared `test_combo` selected; the
coverage gate evaluates only the changed lines; integration is absent.

> Verified: `select_tests.py` on an `add.py` change prints
> `tests/unit/quant_core/test_add.py tests/unit/quant_core/test_combo.py`.

### 2. Coverage gate red → green
Add a new **untested** function to `add.py`, PR → dev. `diff-cover` reports the
changed lines under 50% and the gate goes **red**.

> Verified: an untested function drove diff coverage to **33%** and `diff-cover`
> exited non-zero at `--fail-under=50`. A covered one-line change measured
> **100%** and passed.

Add a test that covers the new function — the gate goes **green**.

### 3. Discipline (no fallback)
Edit `helpers.py` (which has no annotation), PR → dev. Only `test_helpers` (its
mirror) runs. Cross-cutting impact is deliberately **not** chased here — the
up-to-date rule and the EOD run catch any drift.

> Verified: a `helpers.py` change selects only
> `tests/unit/quant_core/test_helpers.py`.

### 4. Annotation typo
Point a `Tests:` entry at a nonexistent dotted path, PR → dev. The job fails
fast with the script's error. Revert.

> Verified: the script printed
> `select_tests: Tests: entry 'test.unit.quant_core.test_nonexistent' does not
> resolve to a file on disk … Fix the annotation.` and **exited 1**.

### 5. Version bump
Merge a PR. Watch the **push** run on `dev`: no tests, a new `vX.Y.Z` tag
appears (patch bump via `mathieudutour/github-tag-action`).

### 6. Main guard
Open a **PR → main from a feature branch** — `guard-main-source` rejects it
("PRs to main must come from dev"). From **dev**, `integration-full` runs
`tests/integration`.

### 7. Deploy + shadow
Merge to `main`. `deploy.yml` resolves the version from the `dev` tag
(`git describe`), builds the **prod** image, and tags it on the local daemon:
```
selection-demo:vX.Y.Z-<sha7>
selection-demo:latest
```
Verify with `docker images`. `shadow-test` (full unit + integration) runs
alongside and does **not** gate the deploy.

> Verified: prod image builds and its sanity CMD prints `prod image ok`; the
> PowerShell tag math yields `<version>-<sha7>` (e.g. `v1.4.2-abc1234`).

### 8. Rollback runbook (documented; demonstrate verbally)
If the shadow suite is **red** after a deploy:
1. `git revert` the merge commit on `main` (which triggers a fresh deploy), and
2. retag `latest` locally to the previous good image:
   ```powershell
   docker tag selection-demo:vPREV-<sha7> selection-demo:latest
   ```
> Note: consumers that pin an exact version tag (`selection-demo:vX.Y.Z-<sha7>`)
> never see a bad `latest`, which makes the retag step unnecessary for them.

---

## Layout

```
selection-demo/
├── README.md
├── pyproject.toml                 # setuptools, static 0.0.1, dev deps, coverage paths
├── Dockerfile                     # base → test → prod
├── .dockerignore / .gitignore
├── scripts/select_tests.py        # stdlib-only selection script (pure classify())
├── .github/workflows/
│   ├── ci.yml                     # scenarios 1, 2, 3
│   ├── deploy.yml                 # scenario 4 (deploy + shadow)
│   └── eod.yml                    # scenario 5 (nightly)
├── src/quant_core/
│   ├── add.py                     # Tests: block → test_combo (cross-cutting)
│   ├── mul.py                     # Tests: block present but EMPTY
│   └── helpers.py                 # NO Tests: block (discipline demo)
└── tests/
    ├── unit/quant_core/           # mirrors + test_combo + test_select
    └── integration/test_slow.py   # add+mul, time.sleep(2); real repos: external services
```
