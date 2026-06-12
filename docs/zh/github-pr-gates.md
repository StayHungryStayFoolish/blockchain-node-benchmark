# GitHub PR Gate 与分支保护

[中文](github-pr-gates.md) | [English](../en/github-pr-gates.md)

本文档说明如何保护 `main` 分支，确保外部贡献在自动检查和 code review 通过前
不能合并。

## 仓库文件已经提供的能力

仓库内包含：

- `.github/workflows/pr_gate.yml`：PR 必跑 CI。
- `.github/workflows/full_smoke.yml`：手动和每周 full smoke workflow。
- `.github/pull_request_template.md`：PR 验证清单。
- `.github/CODEOWNERS`：关键路径 review owner。
- `.github/dependabot.yml`：依赖更新自动化。
- `CONTRIBUTING.md`：贡献流程和本地验证命令。

这些文件 push 到 GitHub 后会自动生效。但仅靠仓库文件不能完全保护主分支，
还需要在 GitHub 设置中开启 branch protection。

## 需要在 GitHub 设置中开启的规则

在 GitHub 仓库页面：

1. 进入 `Settings` -> `Branches`。
2. 为 `main` 添加 branch protection rule。
3. 开启：
   - `Require a pull request before merging`
   - `Require approvals`
   - `Require review from Code Owners`
   - `Dismiss stale pull request approvals when new commits are pushed`
   - `Require status checks to pass before merging`
   - `Require branches to be up to date before merging`
   - `Require conversation resolution before merging`
   - `Do not allow bypassing the above settings`
   - 多维护者场景下开启 `Restrict who can push to matching branches`
   - 禁止 force push
   - 禁止删除 protected branch
4. 第一次 workflow 跑完后，选择 required status checks：
   - `repository hygiene and static contracts`
   - `chain templates, adapters, and fake-node fixtures`
   - `reports, attribution, and observability`
   - `monitoring lifecycle and runtime file contracts`
   - `Go module tests (tools/proxy)`
   - `Go module tests (tools/fake-node)`
   - `Docker and Kubernetes static checks`
   - `monitoring entry guard + self-test`

同时建议在 `Settings` -> `Code security and analysis` 开启：

- Secret scanning
- Push protection
- Dependabot alerts
- Dependabot security updates

## GitHub CLI

如果本机已安装并登录 `gh`，可以用 GitHub CLI 或 API 配置分支保护。
不过第一次建议先用 UI 设置，因为 required status check 名称需要等 workflow
至少跑过一次后最容易选择。

```bash
gh auth status
gh repo view --json nameWithOwner
```

## 合并策略

普通 PR 建议使用 squash merge。PR 标题必须遵循 Conventional Commits，因为它会成为最终 commit subject：

```text
type(scope): short summary
```

允许的 type 包括 `feat`、`fix`、`docs`、`test`、`refactor`、`perf`、`ci`、`chore`。
示例：

```text
feat(fake-node): add fixture coverage validation
fix(monitoring): read sync health from runtime cache
docs(readme): clarify Kubernetes quick start
```

PR 中间 commit 建议使用同样格式，但强制检查以 PR title 为准。

以下情况不要合并：

- PR CI 未通过。
- 修改 monitoring/runtime files 但没有跑 lifecycle 测试。
- 修改 chain templates 但没有跑 fake-node coverage 或 chain adapter 测试。
- 新增用户配置变量但没有更新文档。
- PR 包含 secrets、private endpoints、本地路径、生成的 benchmark 结果归档，
  或 public-release marker 违规。

高风险 PR 如果修改 `blockchain_node_benchmark.sh`、`monitoring/`、`tools/proxy/`、
`tools/fake-node/`、`tools/benchmark_archiver.sh` 或 runtime path 逻辑，合并前应
运行 `.github/workflows/full_smoke.yml`。
