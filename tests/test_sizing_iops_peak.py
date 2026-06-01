#!/usr/bin/env python3
"""test_sizing_iops_peak.py — Hyperdisk/Provisioned 共桶 sizing 峰值兜底单测.

验证 report_generator.ReportGenerator._sizing_iops_peak 的 Worst-Case Envelope:
max(峰值 total_adjusted, 峰值 r_s + 峰值 w_s)。

不依赖双盘真机 / 不跑整框架 —— 用合成 DataFrame 直接验逻辑。
覆盖:
  T1 错峰场景 (read 峰与 write 峰不同刻) → 兜底 > total 峰值, 真生效 (非 no-op)
  T2 同峰场景 (GCP passthrough 正常采样) → 兜底 == total 峰值
  T3 AWS 拆分盘 (adjusted 已放大) → max 自然退化为 adjusted
  T4 r_s/w_s 列缺失 (老 CSV) → 优雅退回 adjusted 峰值, 不报错
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from visualization.report_generator import ReportGenerator


def _mk_df(rows, provider='gcp'):
    """rows: list of dict; 自动补 cloud_provider 列供 _provider_from_df 识别."""
    df = pd.DataFrame(rows)
    df['cloud_provider'] = provider
    return df


def _peak(df, device, adjusted_col):
    # _sizing_iops_peak 是实例方法; 不需完整 __init__, 用 __new__ 造壳实例.
    rg = ReportGenerator.__new__(ReportGenerator)
    return rg._sizing_iops_peak(df, device, adjusted_col)


PASS = 0
FAIL = 0


def check(name, got, expected):
    global PASS, FAIL
    if abs(float(got) - float(expected)) < 1e-6:
        print(f"OK   [{name}] = {got}")
        PASS += 1
    else:
        print(f"FAIL [{name}] got {got}, expected {expected}")
        FAIL += 1


# ── T1: 错峰 (GCP passthrough, adjusted==total). read 峰=8000@t0, write 峰=7000@t1 ──
# 同刻 total: t0=8000+1000=9000, t1=2000+7000=9000 → total 峰=9000
# r 峰 + w 峰 = 8000 + 7000 = 15000 > 9000 → 兜底必须取 15000 (证明非 no-op)
df1 = _mk_df([
    {'data_sda_r_s': 8000, 'data_sda_w_s': 1000, 'data_sda_normalized_iops': 9000},
    {'data_sda_r_s': 2000, 'data_sda_w_s': 7000, 'data_sda_normalized_iops': 9000},
])
check("T1 错峰兜底生效 (r峰+w峰 > total峰)", _peak(df1, 'data', 'data_sda_normalized_iops'), 15000)

# ── T2: 同峰 (正常采样, read/write 同刻达峰) ──
# t0=5000+5000=10000(total), r峰=5000 w峰=5000 → r+w=10000 == total峰 → 兜底==total
df2 = _mk_df([
    {'data_sda_r_s': 5000, 'data_sda_w_s': 5000, 'data_sda_normalized_iops': 10000},
    {'data_sda_r_s': 1000, 'data_sda_w_s': 1000, 'data_sda_normalized_iops': 2000},
])
check("T2 同峰 (r+w == total)", _peak(df2, 'data', 'data_sda_normalized_iops'), 10000)

# ── T3: AWS 拆分盘 — adjusted 已放大 (ceil256), r_s/w_s 未拆 ──
# r峰=1000 w峰=1000 → r+w=2000; adjusted 峰=8000 (×4 拆分) → max 退化为 adjusted=8000
df3 = _mk_df([
    {'data_sda_r_s': 1000, 'data_sda_w_s': 1000, 'data_sda_normalized_iops': 8000},
], provider='aws')
check("T3 AWS拆分盘 max退化为adjusted", _peak(df3, 'data', 'data_sda_normalized_iops'), 8000)

# ── T4: r_s/w_s 列缺失 (老 CSV) → 优雅退回 adjusted 峰值 ──
df4 = _mk_df([
    {'data_sda_normalized_iops': 12000},
    {'data_sda_normalized_iops': 3000},
])
check("T4 r/w列缺失退回adjusted峰值", _peak(df4, 'data', 'data_sda_normalized_iops'), 12000)

# ── T5: accounts 设备前缀同样工作 ──
df5 = _mk_df([
    {'accounts_sdb_r_s': 6000, 'accounts_sdb_w_s': 1000, 'accounts_sdb_normalized_iops': 7000},
    {'accounts_sdb_r_s': 1000, 'accounts_sdb_w_s': 6000, 'accounts_sdb_normalized_iops': 7000},
])
check("T5 accounts错峰兜底", _peak(df5, 'accounts', 'accounts_sdb_normalized_iops'), 12000)

print()
if FAIL == 0:
    print(f"PASS sizing iops peak test ({PASS} checks)")
    sys.exit(0)
else:
    print(f"FAIL sizing iops peak test ({FAIL} failed / {PASS+FAIL} total)")
    sys.exit(1)
