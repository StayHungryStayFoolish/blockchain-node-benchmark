# S4.2 W3 — Per-Method Attribution Mock Report

These are **mock/fixture-driven** artifacts produced by the W3 analysis +
visualization layer. Real-data artifacts come later in S4.3 (solana e2e).

## What's here

- `per_method_qps_solana.svg`         — per-second QPS per method (line chart)
- `per_method_latency_solana.svg`     — per-second p99 latency per method
- `per_method_error_rate_solana.svg`  — per-second error rate per method
- `per_method_resource_solana.svg`    — per-second CPU% attribution (stacked area)
- `report_en.html` / `report_zh.html` — full bilingual HTML section, open in any
  browser

## How they were generated

Run `tests/test_per_method_report.py` — the `TestW36E2E` class regenerates
fixture CSV in tmp and produces equivalent artifacts. To reproduce exactly
these files, run the helper inline at the top of W3's e2e block in
`tests/test_per_method_report.py` with output directed at this folder.

Fixture details:
- 60-second window, fake solana node
- 3 methods: `getSlot` (100 req/s), `getBlock` (20 req/s), `getHealth` (5 req/s)
- Error spike at t=30 (20/100 getSlot calls returned 500 for 1 second)
- Monitor data: 40% CPU baseline, spikes to 60% at t=30

## Why fixture CSV is NOT committed

`fixture_proxy.csv` is ~430 KB and serves only as test data; it would bloat
git history. The generator function in `test_per_method_report.py` (`_run_lang`)
is self-contained — anyone can regenerate identical CSV + SVG + HTML by
running the test.
