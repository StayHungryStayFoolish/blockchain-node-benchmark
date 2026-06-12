## Summary

- What changed:
- Why it changed:

## PR Title

Use a Conventional Commit title because squash merge uses the PR title as the
final commit subject.

Examples:

```text
feat(fake-node): add fixture coverage validation
fix(monitoring): read sync health from runtime cache
docs(readme): clarify Kubernetes quick start
```

## Affected Areas

Check every area touched by this PR:

- [ ] Chain template or RPC method configuration
- [ ] fake-node fixture or fixture recording
- [ ] RPC proxy / per-method attribution
- [ ] Monitoring lifecycle or runtime files
- [ ] Sync health / block-height logic
- [ ] Analysis, charts, or HTML report
- [ ] Kubernetes or observability deployment
- [ ] Documentation only

## Validation

Paste the commands you ran and the result:

```text

```

Minimum expectations:

- Chain/RPC changes: run chain template, adapter, mixed-weighted, sync-health, and fake-node coverage tests.
- Proxy changes: run Go proxy tests and per-method attribution/report tests.
- Monitoring changes: run monitoring lifecycle and runtime contract tests on Linux or Docker.
- Report changes: generate synthetic report/chart tests.
- Entry-point changes: run the full fake-node lifecycle smoke before merge.

## Compatibility Notes

- New user-facing configuration variables:
- File schema changes:
- Backward-incompatible behavior:
- Security or secret-handling impact:

## Checklist

- [ ] PR CI is green.
- [ ] No secrets, private RPC URLs, API keys, or local machine paths were added.
- [ ] Public repo marker check passes.
- [ ] Documentation was updated when behavior changed.
- [ ] New chain/RPC methods include fake-node fixture coverage or an explicit reason.
