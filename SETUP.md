# Setting up / migrating this pipeline (oram-main)

This is the operator's guide for standing the docstring-selection CI/CD pipeline
up in a real repository (e.g. the production `oram-main`). The demo proves the
mechanics; this file is what you actually follow when moving it onto a live repo.

> TL;DR — most of the friction in the original bootstrap was **one-time** (force
> installing onto an already-protected repo) or **bugs that are now fixed and
> baked into these files**. A clean migration is: adapt the layout knobs → seed
> a clean baseline on `dev` and `main` → run each scenario once → *then* lock the
> branches and require the checks. Day-to-day after that is just
> `feature → PR → dev → PR → main`, no ruleset toggling.

---

## 1. Prerequisites (the runner)

The pipeline targets a **self-hosted Windows runner with a local Docker daemon**.
No external registry, no repository secrets (only the auto-injected
`GITHUB_TOKEN`).

- [ ] Self-hosted runner online and registered to the repo.
- [ ] **Docker** daemon running on the runner; `docker build` / `docker run` work
      from the runner's shell.
- [ ] Every workflow uses `defaults.run.shell: powershell`. Do **not** rely on
      `bash` — on a Windows runner `shell: bash` resolves to WSL's `bash.exe`,
      which fails with `execvpe(/bin/bash) failed` when no WSL distro is
      installed. Staying on PowerShell side-steps this entirely.
- [ ] GitHub plan: **repository rulesets with required reviewers / status checks
      need Team or Enterprise** on private repos.

---

## 2. Layout contract & the knobs to change

The selection script (`scripts/select_tests.py`) hard-codes a small number of
layout assumptions. Confirm each against the real repo; change the script where
they differ.

| Assumption (in `select_tests.py`) | Where | Change if your repo differs |
|---|---|---|
| Source lives under `src/` | `select_target_tests`, prefix `src/` | If the package is at the repo root (`quant_core/...`, no `src/`), the prefix check must match — otherwise **changed source is silently never selected**. |
| Mirror is `tests/unit/<pkg>/test_<name>.py` | `mirror_for` (`["tests","unit",...]`) | Drop `"unit"` if your mirrors live at `tests/<pkg>/`. |
| Tooling lives under `scripts/` | prefix `scripts/` | Change if your tooling dir is `tools/`, `bin/`, etc. |
| Changed tests live under `tests/` | prefix `tests/` | Usually fine; confirm. |
| `Tests:` entries start with `test.` | `resolve_dotted` (`test` → `tests`) | Convention: all dotted entries begin `test.` and map to `tests/`. |
| Repo root is two levels up from the script | `REPO_ROOT` | Holds as long as the script stays at `<root>/scripts/select_tests.py`. |

The hermetic test suite (`tests/tooling/`) builds its **own** sandbox repo, so it
keeps passing regardless of the real layout. Only touch
`tests/tooling/conftest.py`'s `STANDARD_REPO` if you change the contract itself.

> `tests/tooling/conftest.py` loads the script by path via `importlib` (because
> `scripts/` is not an importable package). The only knob there is the relative
> depth `("..", "..")` from the conftest to the repo root — keep it in sync if
> you move the file.

---

## 3. Config to adapt

- **`pyproject.toml` dev deps** must use setuptools/PEP 621 syntax, not Poetry:
  ```toml
  [project.optional-dependencies]
  dev = ["pytest>=8.0", "pytest-cov", "pytest-sugar"]
  ```
  A `[tool.poetry.group.dev.dependencies]` block is **silently ignored** by
  setuptools, so `pip install -e ".[dev]"` would install no test deps.
- **Coverage path mapping** — so `coverage.xml` (produced inside the container)
  lines up with `git diff` paths on the runner:
  ```toml
  [tool.coverage.run]
  relative_files = true
  [tool.coverage.paths]
  source = ["src/", "/app/src/", "*/src/"]
  ```
  Plus an **editable install** in the test image (`pip install -e ".[dev]"`) so
  the package resolves to `/app/src` rather than site-packages.
- **`--cov` targets** in `ci.yml` must name the real package roots
  (e.g. `--cov=src --cov=scripts`). A scripts-only change still needs `--cov`
  to include `scripts`, or its changed lines count as 0% and fail the gate.

---

## 4. First-time landing order (do it clean)

The painful part of the demo was installing the pipeline onto branches that were
already protected and out of sync. Avoid that:

1. **Seed one baseline.** Get `dev` and `main` to the **same** commit that
   contains the full pipeline (workflows, Dockerfile, `scripts/`, `tests/`,
   `pyproject.toml`). Do this *before* turning on branch protection, or via one
   initial PR.
   - ⚠️ Don't update only `main` and forget `dev` (or vice-versa). A stale base
     branch makes every later PR diff against ancient history and pulls
     unrelated files into selection.
2. **Run each scenario once** (see §6) so each job reports a status at least
   once. Scheduled (`eod.yml`) workflows only run from the **default branch**, so
   the pipeline must live on `main` for the nightly to ever fire.
3. **Then** add the rulesets and **require the status checks** — a check only
   appears in the "Require status checks" picker *after* it has run once.
   Require per base branch the job that actually runs there:
   - `dev` → require `selective-tests`
   - `main` → require `guard-main`, `integration-tests`
   - Never require a check on a base where its `if:` makes it skip, or PRs hang
     on "waiting for status".

---

## 5. Daily flow (after setup)

```
feature branch ──PR──▶ dev ──PR──▶ main
```

- **PR → dev**: `selective-tests` runs only the implied tests + a 50%
  diff-coverage gate on changed lines.
- **push dev** (merge): `version-update` bumps the `vX.Y.Z` tag **only if a
  commit since the last tag is `feat:`/`fix:`/breaking** (this repo sets
  `default_bump: false`). No tests. See §7.
- **PR → main** (must come from `dev`): `guard-main` + `integration-tests`.
- **push main** (merge): `deploy` builds/tags the prod image locally;
  `shadow-test` runs the full suite alongside (non-gating).
- **nightly**: `eod.yml` runs the full suite on `dev` and `main`.

No ruleset toggling in normal operation — everything goes through PRs.

---

## 6. How to test it (validation walkthrough)

Run these in order — later scenarios depend on earlier ones (e.g. deploy needs a
tag to exist). Each is a small branch + PR; the **commands** are run locally, the
**merge / Run-workflow** steps are on the GitHub web UI (no `gh` required). When
opening a PR, **double-check the base branch** — GitHub defaults to `main`.

Quick map of what each trigger exercises:

| # | Trigger | Job(s) | Expect |
|---|---|---|---|
| 1 / 1b / 1c | PR → **dev** | `selective-tests` | selection + 50% diff-coverage gate, red→green |
| 2 | merge → push **dev** | `version-update` | tag bump only on `feat:`/`fix:` (else none) |
| 3 | PR → **main** from non-`dev` | `guard-main` | **rejected** |
| 4 | PR → **main** from `dev` | `guard-main` + `integration-tests` | guard passes, integration runs |
| 5 | merge → push **main** | `deploy` + `shadow-test` | builds/tags prod image; shadow runs alongside |
| 6 | Actions → Run workflow | `eod.yml` | full suite on `dev` and `main` |

### Scenario 1 — PR → dev: selection + coverage gate (red → green)

**1a. Selection + green gate.** Make a *covered* change to a `src` file that has
a `Tests:` block (here `add.py`, which declares `test_combo`):

```bash
git checkout -b demo/sel-cov dev
# edit src/quant_core/add.py: change add()'s body to something still tested
git commit -am "demo: covered change to add()"
git push -u origin demo/sel-cov
```

Open a **PR → dev**. Expect the `Select tests` step to print both the mirror and
the declared test:

```
Selected: tests/unit/quant_core/test_add.py tests/unit/quant_core/test_combo.py
```

The changed lines are covered → diff coverage 100% → **gate green**, integration
absent.

**1b. Red gate.** Add an *untested* function and push to the same branch:

```bash
# add e.g. def add_many(values): ...  (no test for it)
git commit -am "demo: untested function to drop diff coverage"
git push
```

The PR re-runs. Only the new function's body lines changed and nothing covers
them → **gate red**, e.g.:

```
src/quant_core/add.py (20.0%): Missing lines 20-23
Failure. Coverage is below 50%.
```

> The gate measures **only the changed lines**, not the whole repo. A well-tested
> `add()` can't rescue an untested `add_many()`.

**1c. Back to green.** Add a test that calls the new function, push again → the
changed lines get covered → diff coverage ≥ 50% → **gate green**.

### Scenario 2 — push dev: conditional version bump

Merge the green PR into `dev`. The push triggers `version-update`. Because this
repo sets `default_bump: false`, a tag is created **only if** a commit since the
last tag is `feat:`/`fix:`/breaking. With only `demo:`/`chore:` commits you'll
see:

```
Analysis of N commits complete: no release
```

and **no new tag** — the job still passes. (Live gotcha we hit: a `feat:` written
in the **PR title** did *not* bump under merge-commit strategy, because the merge
commit's *subject* is `Merge pull request #N…` and the PR title landed in the
*body*. See §7.) To actually cut a version, land a commit whose **subject** is
`feat:`/`fix:`.

### Scenario 3 — PR → main from a non-dev branch: guard rejects

```bash
git checkout -b feature/guard-demo origin/main
# any trivial change, e.g. add a throwaway file
git commit -am "demo: trivial change"
git push -u origin feature/guard-demo
```

Open a **PR → main** (base = `main`). `guard-main` runs and **fails** with
"PRs to main must come from dev"; `integration-tests` is skipped (it `needs:
guard-main`). Close the PR and delete the branch afterward.

### Scenario 4 — PR → main from dev: guard passes + integration

Open a **PR `dev → main`**. `head_ref == dev` → `guard-main` passes →
`integration-tests` runs `tests/integration` in the test image.

### Scenario 5 — push main: deploy + shadow

Merge the `dev → main` PR. The push to `main` triggers `deploy.yml`:

- `deploy` resolves the version via `git describe --tags --match "v*"`, builds
  the **prod** image, and tags it `oram-main:<version>-<sha7>` + `oram-main:latest`
  on the local daemon (verify with `docker images`).
- `shadow-test` runs the full suite **alongside**, non-gating.

> Deploy needs a `v*` tag to already exist (from scenario 2 or a manual
> `git tag v0.0.1`), or it fails with "No version tag reachable".

### Scenario 6 — EOD nightly (manual trigger)

Don't wait for the 23:00 UTC cron — **Actions → EOD-test → Run workflow**
(`workflow_dispatch`). The matrix `[dev, main]` with `fail-fast: false` runs two
independent jobs, each building `oram-main:eod_test-<branch>` and running the
**full** suite. Both should be green. The cron fires the same workflow nightly.

### Seeding the required status checks

A check is only selectable in the ruleset UI **after it has reported once**.
Scenarios 1 and 4 above produce the first runs of `selective-tests`,
`guard-main`, and `integration-tests` — once they have, go back and require them
per §4 step 3.

---

## 7. Versioning: what drives the tag bump

The `version-update` job (`mathieudutour/github-tag-action`) decides
patch/minor/major from **commit messages** (Conventional Commits) between the
last tag and HEAD — **not** the PR title or PR description directly.

- `feat:` → minor · `fix:` → patch · `BREAKING CHANGE:` footer → major ·
  anything else → `default_bump` (defaults to patch).
- ⚠️ **The `feat!:` `!` shorthand is NOT documented as supported.** The only
  documented major trigger is a `BREAKING CHANGE:` footer in the commit body.
  Don't rely on `!` — verify empirically, or make it deterministic with
  `custom_release_rules` (e.g. `custom_release_rules: feat:minor,fix:patch,breaking:major`).
- ⚠️ Pre-1.0 (`0.x.y`) handling of breaking changes is undocumented; if a fresh
  repo starts at `0.x`, test whether a breaking change goes to `1.0.0` or only
  bumps minor before relying on it.
- It parses the commit **subject** (first line). The PR description body never
  drives it (except a `BREAKING CHANGE:` footer → major).
- **The PR title only matters under "Squash and merge"**, because GitHub turns
  the PR title into the squash commit's subject. Under "Create a merge commit"
  or "Rebase and merge", the **branch commit messages** are parsed and the PR
  title is irrelevant.

**Pick one convention and enforce it:**
1. **Squash merge** + Conventional-Commit **PR titles** (recommended; cleanest
   history, single source of truth). Optionally add a PR-title lint check.
2. **Merge / rebase** + Conventional-Commit **commit messages**.

> Config note: this repo sets **`default_bump: false`**, so a merge with no
> `feat:`/`fix:`/breaking commit produces **no tag** (the version "freezes" until
> a qualifying commit lands). The input is `default_bump` — an earlier
> `default_update: patch` was a typo that the action silently ignored (it only
> "worked" because the built-in default is already patch). With `false`,
> Conventional-Commit discipline is mandatory or the version never moves.

---

## 8. Conventions to lock in

### GitHub repo settings

> Note: this repo is governed by **Rulesets** (Settings → Rules → Rulesets), the
> newer system — *not* the classic "Branches" protection. Direct pushes here are
> blocked by a ruleset ("Changes must be made through a pull request"). Editing
> the wrong page (Branches) won't lift it.

- **Ruleset for `dev`:**
  - Require a pull request before merging.
  - Require status check **`selective-tests`**.
  - ✅ **Require branches to be up to date before merging** — this checkbox is the
    semantic-conflict defense: it forces a PR to re-run against the latest `dev`
    before it can merge (two PRs that each pass in isolation can still break
    `dev`). The nightly EOD run is the backstop.
- **Ruleset for `main`:**
  - Require a pull request (from `dev`; `guard-main` also enforces this in CI).
  - Require status checks **`guard-main`** and **`integration-tests`**.
  - Require at least 1 approval (and/or required reviewers).
- **Bootstrap only:** to seed the first baseline you may temporarily set the
  ruleset to `Disabled` or add yourself to its **Bypass list**. Re-enable / remove
  the bypass once the pipeline is in and validated. In steady state you never
  direct-push protected branches.
- **Merge strategy (Settings → General → Pull Requests):** pick **one** and
  disable the others so versioning is deterministic. **Recommended: Squash and
  merge only** — the PR title becomes the commit subject that drives the version
  bump (see §7).
- **Actions:** `version-update` needs `permissions: contents: write` (already set
  in the job). Only the auto-injected `GITHUB_TOKEN` is used — no PAT, no secret.
- **Default branch must be `main`** — scheduled workflows (`eod.yml`) only run
  from the default branch.
- **Optional approval gate:** add a `production` **Environment** with required
  reviewers and reference it from the `deploy` job (`environment: production`) if
  you want a manual click before deploy. (Requires Team/Enterprise on private
  repos.)

### Commit / PR conventions

- **Conventional Commits** on the line that becomes the commit **subject**:
  - `feat:` → minor · `fix:` → patch · `BREAKING CHANGE:` footer → major.
  - `chore:` / `docs:` / `refactor:` / `test:` / `demo:` → **no version bump**
    (this repo uses `default_bump: false`, so non-feat/fix merges freeze the
    version).
  - The type must be on the **first line**. With **squash merge** that line is the
    **PR title** → enforce Conventional-Commit PR titles (optionally add a
    PR-title lint action). With merge/rebase it's the **branch commit subjects**.
- **`Tests:` annotation discipline** — when you rename a test file, update any
  dotted `Tests:` entry that points at it; an unresolved entry is a hard error by
  design (this bit us once after a rename).
- **Branch naming** — `feature/*` for work targeting `dev`; throwaway demo/spike
  branches can be deleted right after their PR.
- **Workflow shell** — keep `run:` commands single-line (no backtick
  continuation) and brace env vars (`${env:VAR}`); see §9.

---

## 9. Gotcha quick-reference (learned the hard way)

- **PowerShell: one line.** Don't split a command with the backtick (`` ` ``)
  continuation — under YAML + CRLF on the runner it breaks and drops trailing
  args (a multi-line `docker build` lost its `.` build context). Keep commands
  on one line.
- **`${env:VAR}` with braces.** Bare `$env:IMAGE_NAME:latest` mis-parses: the
  colon and `latest` get swallowed into the variable name, yielding an empty
  string. Always brace it: `"${env:IMAGE_NAME}:latest"`.
- **Rename a test file → update its annotation.** The selection script's own
  `Tests:` block is a real annotation; renaming `test_x.py` without updating the
  dotted entry makes it fail to resolve (hard error, by design).
- **Sync *both* `dev` and `main`** when seeding/bootstrapping. A forgotten
  `origin/dev` makes PR diffs explode.
- **Scheduled workflows run from the default branch only** — `eod.yml` must be on
  `main`.
- **Required checks must run once before they're selectable** in the ruleset UI.
