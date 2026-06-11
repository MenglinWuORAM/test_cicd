# 流水线搭建 / 迁移指南（oram-main）

这是把"docstring 选择测试"CI/CD 流水线搭到真实仓库（例如生产用的 `oram-main`）
时的操作手册。demo 用来验证机制；这份文件是你把它搬到正式仓库时**照着做**的清单。

> TL;DR —— 最初 bootstrap 的折腾，绝大部分是**一次性的**（往一个已上保护的仓库强行
> 安装）或**已经修掉、固化进这些文件里的 bug**。一次干净的迁移就是：适配布局旋钮 →
> 在 `dev` 和 `main` 上铺一个干净基线 → 每个场景各跑一次 → **之后**再锁分支、勾必需
> 检查。从此日常就只是 `feature → PR → dev → PR → main`，不用再碰 ruleset。

---

## 1. 前置条件（runner）

流水线面向**自托管 Windows runner + 本地 Docker daemon**。无外部镜像仓库、无任何仓库
secret（只用 GitHub 自动注入的 `GITHUB_TOKEN`）。

- [ ] 自托管 runner 在线并已注册到本仓库。
- [ ] runner 上 **Docker** daemon 正在运行；从 runner 的 shell 能执行 `docker build` /
      `docker run`。
- [ ] 所有 workflow 都用 `defaults.run.shell: powershell`。**不要**依赖 `bash` ——
      在 Windows runner 上 `shell: bash` 会解析到 WSL 的 `bash.exe`，没装 WSL 发行版时
      报 `execvpe(/bin/bash) failed`。全程用 PowerShell 就彻底绕开。
- [ ] GitHub 套餐：私有库上**带 required reviewers / status checks 的 rulesets 需要
      Team 或 Enterprise**。

---

## 2. 布局契约 & 要改的旋钮

选择脚本（`scripts/select_tests.py`）写死了少量布局假设。逐条对照真实仓库；不一致的
地方改脚本。

| 假设（在 `select_tests.py` 里）| 在哪 | 你的仓库不同就这样改 |
|---|---|---|
| 源码在 `src/` 下 | `select_target_tests`，前缀 `src/` | 如果包直接在仓库根（`quant_core/...`，没有 `src/`），前缀判断必须对上——否则**改了源码却被静默地一个都不选**。|
| 镜像是 `tests/unit/<pkg>/test_<name>.py` | `mirror_for`（`["tests","unit",...]`）| 如果你的镜像在 `tests/<pkg>/`，就去掉 `"unit"`。|
| 工具在 `scripts/` 下 | 前缀 `scripts/` | 工具目录若叫 `tools/`、`bin/` 等就改。|
| 改动的测试在 `tests/` 下 | 前缀 `tests/` | 一般没问题；确认一下。|
| `Tests:` 条目以 `test.` 开头 | `resolve_dotted`（`test` → `tests`）| 约定：所有点分条目以 `test.` 开头并映射到 `tests/`。|
| 仓库根在脚本往上两级 | `REPO_ROOT` | 只要脚本还在 `<root>/scripts/select_tests.py` 就成立。|

封闭式（hermetic）测试套件（`tests/tooling/`）会构建**自己的**沙箱仓库，所以无论真实
布局如何它都照过。只有当你**改了契约本身**时，才需要动 `tests/tooling/conftest.py` 里的
`STANDARD_REPO`。

> `tests/tooling/conftest.py` 通过 `importlib` 按路径加载脚本（因为 `scripts/` 不是可
> import 的包）。那里唯一的旋钮是从 conftest 到仓库根的相对深度 `("..", "..")`——挪文件
> 时记得同步。

---

## 3. 要适配的 config

- **`pyproject.toml` 的 dev 依赖**必须用 setuptools/PEP 621 语法，不是 Poetry：
  ```toml
  [project.optional-dependencies]
  dev = ["pytest>=8.0", "pytest-cov", "pytest-sugar"]
  ```
  `[tool.poetry.group.dev.dependencies]` 这种块会被 setuptools **静默忽略**，导致
  `pip install -e ".[dev]"` 一个测试依赖都装不上。
- **覆盖率路径映射**——让容器内产出的 `coverage.xml` 和 runner 上 `git diff` 的路径对齐：
  ```toml
  [tool.coverage.run]
  relative_files = true
  [tool.coverage.paths]
  source = ["src/", "/app/src/", "*/src/"]
  ```
  外加测试镜像里的 **editable 安装**（`pip install -e ".[dev]"`），让包解析到 `/app/src`
  而不是 site-packages。
- **`ci.yml` 里的 `--cov` 目标**必须写真实的包根（如 `--cov=src --cov=scripts`）。
  只改 scripts 的 PR 也需要 `--cov` 包含 `scripts`，否则它的改动行算 0%、门会红。

---

## 4. 首次落地顺序（一次做干净）

demo 里最痛的部分，就是往**已经上了保护、又彼此不同步**的分支上装流水线。避开它：

1. **铺一个基线。** 把 `dev` 和 `main` 拉到**同一个**包含完整流水线（workflows、
   Dockerfile、`scripts/`、`tests/`、`pyproject.toml`）的 commit。在**开启分支保护之前**
   做，或者通过一个初始 PR 做。
   - ⚠️ 别只更新 `main` 忘了 `dev`（反之亦然）。一个过时的 base 分支会让之后每个 PR 都
     对着远古历史做 diff，把无关文件卷进选择。
2. **每个场景各跑一次**（见 §6），让每个 job 至少上报一次状态。定时（`eod.yml`）
   workflow **只从默认分支跑**，所以流水线必须在 `main` 上，夜间任务才会触发。
3. **然后**再加 rulesets、**勾必需的 status check**——一个 check 只有**跑过一次之后**才会
   出现在 "Require status checks" 的选择框里。按 base 分支各 require 它真正会跑的 job：
   - `dev` → require `selective-tests`
   - `main` → require `guard-main`、`integration-tests`
   - 绝不要在某个 base 上 require 一个会被 `if:` 跳过的 check，否则 PR 会卡在
     "waiting for status"。

---

## 5. 日常流程（搭好之后）

```
feature branch ──PR──▶ dev ──PR──▶ main
```

- **PR → dev**：`selective-tests` 只跑改动隐含的测试 + 对改动行的 50% diff-coverage 门。
- **push dev**（合并）：**仅当上次 tag 以来有 `feat:`/`fix:`/breaking 的 commit 时**，
  `version-update` 才打新 `vX.Y.Z` tag（本仓库设了 `default_bump: false`）。不跑测试。见 §7。
- **PR → main**（必须来自 `dev`）：`guard-main` + `integration-tests`。
- **push main**（合并）：`deploy` 在本地 build/tag prod 镜像；`shadow-test` 在旁边跑全量
  （不 gate）。
- **夜间**：`eod.yml` 在 `dev` 和 `main` 上各跑一次全量。

正常运行**不碰 ruleset**——一切走 PR。

---

## 6. 怎么测（验收 walkthrough）

按顺序跑——后面的场景依赖前面的（比如 deploy 需要已经有 tag）。每个都是一条小分支 + PR；
**命令**在本地跑，**合并 / Run-workflow** 在 GitHub 网页点（不需要 `gh`）。开 PR 时
**务必核对 base 分支**——GitHub 默认是 `main`。

各触发分别验什么，速查：

| # | 触发 | Job | 预期 |
|---|---|---|---|
| 1 / 1b / 1c | PR → **dev** | `selective-tests` | 选择 + 50% diff-coverage 门，红→绿 |
| 2 | merge → push **dev** | `version-update` | 仅 `feat:`/`fix:` 才打 tag（否则不打）|
| 3 | PR → **main**（非 `dev`）| `guard-main` | **被拒** |
| 4 | PR → **main**（来自 `dev`）| `guard-main` + `integration-tests` | guard 过，integration 跑 |
| 5 | merge → push **main** | `deploy` + `shadow-test` | build/tag prod 镜像；shadow 旁路跑 |
| 6 | Actions → Run workflow | `eod.yml` | `dev`、`main` 上各跑全量 |

### 场景 1 —— PR → dev：选择 + 覆盖率门（红 → 绿）

**1a. 选择 + 绿门。** 对一个带 `Tests:` 块的 `src` 文件做**有覆盖的**改动（这里是
`add.py`，它声明了 `test_combo`）：

```bash
git checkout -b demo/sel-cov dev
# 改 src/quant_core/add.py：把 add() 的函数体改成仍被测试覆盖的写法
git commit -am "demo: covered change to add()"
git push -u origin demo/sel-cov
```

开一个 **PR → dev**。预期 `Select tests` 步同时打印镜像和声明的测试：

```
Selected: tests/unit/quant_core/test_add.py tests/unit/quant_core/test_combo.py
```

改动行被覆盖 → diff 覆盖率 100% → **门绿**，integration 不出现。

**1b. 红门。** 加一个**没测试**的函数，推到同一条分支：

```bash
# 加比如 def add_many(values): ...（不给它写测试）
git commit -am "demo: untested function to drop diff coverage"
git push
```

PR 重跑。只有新函数的函数体行变了、又没人覆盖它们 → **门红**，例如：

```
src/quant_core/add.py (20.0%): Missing lines 20-23
Failure. Coverage is below 50%.
```

> 门只衡量**改动的行**，不是整个仓库。`add()` 测得再好也救不了没测试的 `add_many()`。

**1c. 回到绿。** 加一个调用新函数的测试，再次 push → 改动行被覆盖 → diff 覆盖率 ≥ 50% →
**门绿**。

### 场景 2 —— push dev：条件式版本 bump

把绿 PR 合进 `dev`。push 触发 `version-update`。因为本仓库设了 `default_bump: false`，
**仅当**上次 tag 以来有 `feat:`/`fix:`/breaking 的 commit 才打 tag。如果只有
`demo:`/`chore:` 的 commit，你会看到：

```
Analysis of N commits complete: no release
```

并且**不打新 tag**——job 仍然通过。（实测踩到的坑：写在 **PR title** 里的 `feat:` 在
merge-commit 策略下**没有**触发 bump，因为 merge 提交的 *subject* 是
`Merge pull request #N…`，PR title 落到了 *正文*。见 §7。）想真正发版，让某个 commit 的
**subject** 是 `feat:`/`fix:`。

### 场景 3 —— PR → main 从非 dev 分支：guard 拒绝

```bash
git checkout -b feature/guard-demo origin/main
# 任意琐碎改动，比如加个一次性文件
git commit -am "demo: trivial change"
git push -u origin feature/guard-demo
```

开一个 **PR → main**（base = `main`）。`guard-main` 跑并**失败**，提示
"PRs to main must come from dev"；`integration-tests` 被跳过（它 `needs: guard-main`）。
验完 close PR、删分支。

### 场景 4 —— PR → main 从 dev：guard 放行 + integration

开一个 **PR `dev → main`**。`head_ref == dev` → `guard-main` 通过 → `integration-tests`
在测试镜像里跑 `tests/integration`。

### 场景 5 —— push main：deploy + shadow

合并 `dev → main` 的 PR。push 到 `main` 触发 `deploy.yml`：

- `deploy` 用 `git describe --tags --match "v*"` 解析版本，build **prod** 镜像，在本地
  daemon 上打 `oram-main:<version>-<sha7>` + `oram-main:latest`（`docker images` 验证）。
- `shadow-test` 在**旁边**跑全量，不 gate。

> deploy 需要已经存在 `v*` tag（来自场景 2，或手动 `git tag v0.0.1`），否则会报
> "No version tag reachable"。

### 场景 6 —— EOD 夜间（手动触发）

别等 23:00 UTC 的 cron —— **Actions → EOD-test → Run workflow**（`workflow_dispatch`）。
matrix `[dev, main]` + `fail-fast: false` → 两个独立 job，各自 build
`oram-main:eod_test-<branch>` 并跑**全量**套件。两个都应该绿。cron 到点会触发同一个
workflow。

### 把必需 status check 激活出来

一个 check 只有**上报过一次之后**才能在 ruleset UI 里被选。上面的场景 1 和 4 会产生
`selective-tests`、`guard-main`、`integration-tests` 的首次运行——跑过之后，回去按
§4 第 3 步把它们 require 上。

---

## 7. 版本：什么决定 tag bump

`version-update` job（`mathieudutour/github-tag-action`）从上次 tag 到 HEAD 之间的
**commit message**（Conventional Commits）决定 patch/minor/major ——**不是** PR title 或
PR description 直接决定。

- `feat:` → minor · `fix:` → patch · `BREAKING CHANGE:` footer → major ·
  其它 → `default_bump`（默认 patch）。
- ⚠️ **`feat!:` 的 `!` 简写文档里没说支持。** 唯一有文档背书的 major 触发是 commit 正文
  里的 `BREAKING CHANGE:` footer。别依赖 `!`——要么实测，要么用 `custom_release_rules`
  写死（如 `custom_release_rules: feat:minor,fix:patch,breaking:major`）。
- ⚠️ 1.0 以下（`0.x.y`）的 breaking change 怎么处理没有文档；如果新仓库从 `0.x` 起步，
  先实测 breaking 是跳到 `1.0.0` 还是只 bump minor，再依赖它。
- 它解析 commit 的 **subject（第一行）**。PR description 正文永远不决定它（除非
  `BREAKING CHANGE:` footer → major）。
- **PR title 只在 "Squash and merge" 下才算数**，因为 GitHub 会把 PR title 变成 squash
  提交的 subject。用 "Create a merge commit" 或 "Rebase and merge" 时，解析的是**分支
  commit message**，PR title 无关。

**选一种约定并强制执行：**
1. **Squash merge** + 规范的 **PR title**（推荐；历史最干净、单一来源）。可选加个 PR-title
   lint 检查。
2. **Merge / rebase** + 规范的 **commit message**。

> Config 说明：本仓库设了 **`default_bump: false`**，所以一次没有 `feat:`/`fix:`/breaking
> commit 的合并**不打 tag**（版本"冻结"，直到出现合格 commit）。输入名是 `default_bump`
> ——早先写的 `default_update: patch` 是个 typo，被 action 静默忽略（只因为内置默认本就是
> patch 才"看起来生效"）。设成 `false` 后，Conventional-Commit 纪律变成硬要求，否则版本
> 永远不动。

---

## 8. 要锁定的规范

### GitHub 仓库设置

> 注意：本仓库用 **Rulesets**（Settings → Rules → Rulesets）这套较新的系统治理——**不是**
> 老的 "Branches" 保护。这里的直推被一条 ruleset 挡住（"Changes must be made through a
> pull request"）。改错页面（Branches）是放不开的。

- **`dev` 的 ruleset：**
  - 合并前必须经过 pull request。
  - require status check **`selective-tests`**。
  - ✅ **Require branches to be up to date before merging**——这个勾是语义冲突防线：它
    强制 PR 在能合并前对着最新的 `dev` 重跑一次（两个各自独立通过的 PR 合起来仍可能搞坏
    `dev`）。夜间 EOD 是兜底。
- **`main` 的 ruleset：**
  - 必须经过 pull request（来自 `dev`；`guard-main` 在 CI 里也强制这点）。
  - require status checks **`guard-main`** 和 **`integration-tests`**。
  - 至少 1 个 approval（和/或 required reviewers）。
- **仅 bootstrap 阶段：** 为了铺第一个基线，你可以临时把 ruleset 设成 `Disabled`，或把
  自己加进它的 **Bypass list**。流水线装好、验完后再 re-enable / 移除 bypass。稳定状态下
  你永远不直推受保护分支。
- **合并策略（Settings → General → Pull Requests）：** 选**一种**、禁掉其它，让版本号
  确定。**推荐：只留 Squash and merge**——PR title 会变成驱动版本 bump 的 commit subject
  （见 §7）。
- **Actions：** `version-update` 需要 `permissions: contents: write`（job 里已设）。只用
  自动注入的 `GITHUB_TOKEN`——无 PAT、无 secret。
- **默认分支必须是 `main`**——定时 workflow（`eod.yml`）只从默认分支跑。
- **可选审批闸：** 如果想在 deploy 前加一道人工点击，建一个带 required reviewers 的
  `production` **Environment**，并在 `deploy` job 里引用（`environment: production`）。
  （私有库需要 Team/Enterprise。）

### 提交 / PR 规范

- **Conventional Commits**，写在会变成 commit **subject** 的那一行：
  - `feat:` → minor · `fix:` → patch · `BREAKING CHANGE:` footer → major。
  - `chore:` / `docs:` / `refactor:` / `test:` / `demo:` → **不 bump 版本**（本仓库用
    `default_bump: false`，非 feat/fix 的合并会冻结版本）。
  - 类型必须在**第一行**。用 **squash merge** 时那一行就是 **PR title** → 强制规范的
    PR title（可选加 PR-title lint action）。用 merge/rebase 时是**分支的 commit subject**。
- **`Tests:` 注释纪律**——重命名测试文件时，更新所有指向它的点分 `Tests:` 条目；解析不到
  的条目按设计是硬报错（我们改名后被它咬过一次）。
- **分支命名**——`feature/*` 用于面向 `dev` 的开发；一次性 demo/spike 分支在它的 PR 之后
  即可删。
- **Workflow shell**——`run:` 命令保持单行（不用反引号续行）、环境变量加花括号
  （`${env:VAR}`）；见 §9。

---

## 9. 踩坑速查（用血换来的）

- **PowerShell：写一行。** 别用反引号（`` ` ``）续行拆命令——在 YAML + CRLF + runner 下它
  会断、把末尾参数丢掉（多行 `docker build` 丢了它的 `.` 构建上下文）。命令写一行。
- **`${env:VAR}` 加花括号。** 裸写 `$env:IMAGE_NAME:latest` 会解析错：冒号和 `latest` 被
  吞进变量名，得到空字符串。永远加花括号：`"${env:IMAGE_NAME}:latest"`。
- **重命名测试文件 → 更新它的注释。** 选择脚本自己的 `Tests:` 块就是个真注释；改了
  `test_x.py` 却不更新点分条目，会解析失败（按设计硬报错）。
- **`dev` 和 `main` **两个都**要同步**——铺基线/bootstrap 时漏了 `origin/dev`，PR diff 就会
  爆炸。
- **定时 workflow 只从默认分支跑**——`eod.yml` 必须在 `main` 上。
- **必需 check 要先跑过一次**才能在 ruleset UI 里被选。
