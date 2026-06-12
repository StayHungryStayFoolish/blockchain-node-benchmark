# GitHub PR Gates and Branch Protection

[中文](../zh/github-pr-gates.md) | [English](github-pr-gates.md)

This document describes how to protect `main` so external contributions cannot
be merged until automated checks and reviews pass.

## What Is Enforced by Repository Files

The repository includes:

- `.github/workflows/pr_gate.yml`: required PR CI checks.
- `.github/workflows/full_smoke.yml`: manual and weekly full smoke workflow.
- `.github/pull_request_template.md`: contributor validation checklist.
- `.github/CODEOWNERS`: review routing for critical paths.
- `.github/dependabot.yml`: dependency update automation.
- `CONTRIBUTING.md`: contributor workflow and local validation commands.

These files become active after they are pushed to GitHub.

## What Must Be Enabled in GitHub Settings

Repository files cannot fully protect the branch by themselves. Enable these
settings in GitHub:

1. Open the repository on GitHub.
2. Go to `Settings` -> `Branches`.
3. Add a branch protection rule for `main`.
4. Enable:
   - `Require a pull request before merging`
   - `Require approvals`
   - `Require review from Code Owners`
   - `Dismiss stale pull request approvals when new commits are pushed`
   - `Require status checks to pass before merging`
   - `Require branches to be up to date before merging`
   - `Require conversation resolution before merging`
   - `Do not allow bypassing the above settings`
   - `Restrict who can push to matching branches` if the repo has multiple maintainers
   - `Block force pushes`
   - `Block deletions`
5. Select these required status checks:
   - `repository hygiene and static contracts`
   - `chain templates, adapters, and fake-node fixtures`
   - `reports, attribution, and observability`
   - `monitoring lifecycle and runtime file contracts`
   - `Go module tests (tools/proxy)`
   - `Go module tests (tools/fake-node)`
   - `Docker and Kubernetes static checks`
   - `monitoring entry guard + self-test`

Also enable in `Settings` -> `Code security and analysis`:

- Secret scanning
- Push protection
- Dependabot alerts
- Dependabot security updates

## Optional GitHub CLI Setup

If the GitHub CLI is installed and authenticated, maintainers can inspect the
repository and configure protection from the terminal.

```bash
gh auth login
gh auth status
gh repo view --json nameWithOwner
```

After login, either use the GitHub UI above or apply branch protection with the
GitHub REST API. The UI is recommended first because required status-check
names are easiest to select after the first workflow run has completed.

## Merge Policy

Use squash merge for ordinary PRs. Require the PR title to follow Conventional
Commits because it becomes the final commit subject:

```text
type(scope): short summary
```

Allowed types are `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `ci`,
`build`, and `chore`. Examples:

```text
feat(fake-node): add fixture coverage validation
fix(monitoring): read sync health from runtime cache
docs(readme): clarify Kubernetes quick start
build(deps): update requests requirement
```

Intermediate commits should follow the same style when practical, but the PR
title is the enforced contract.

Do not merge when:

- PR CI is red.
- The PR changes monitored runtime files but no lifecycle test was run.
- The PR changes chain templates but fake-node coverage or chain adapter tests
  were not run.
- The PR adds new user-facing config without documentation.
- The PR includes secrets, private endpoints, local paths, generated result
  archives, or public-release marker violations.

For high-risk PRs that touch `blockchain_node_benchmark.sh`, `monitoring/`,
`tools/proxy/`, `tools/fake-node/`, `tools/benchmark_archiver.sh`, or runtime
path logic, run `.github/workflows/full_smoke.yml` before merge.
