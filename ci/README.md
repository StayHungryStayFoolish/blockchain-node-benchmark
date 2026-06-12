# CI Guards

This directory contains repository-level CI guard scripts.

These scripts are not benchmark runtime entrypoints and are not general-purpose
developer tools. They protect architecture boundaries that should stay true
across refactors.

## Guards

- `check_parallel_entry.sh`
  - Ensures monitoring helper modules remain wired into the main monitoring
    lifecycle.
  - Catches cases where a helper file exists but is no longer sourced or
    invoked by the expected caller.
  - Used by `.github/workflows/parallel_entry.yml`.

- `check_csv_registry_bypass.sh`
  - Ensures migrated readers do not bypass `CSVSchemaRegistry` by hardcoding
    provider-aware physical column names.
  - Keep allowlists narrow and only for files that define registry mappings or
    intentionally test them.

## Placement

`ci/` lives at repository root because these checks enforce cross-cutting
repository policy. Runtime scripts belong under `tools/`, `monitoring/`, or
`core/`; test cases belong under `tests/`.

## Local Usage

```bash
bash ci/check_parallel_entry.sh
bash ci/check_csv_registry_bypass.sh
```
