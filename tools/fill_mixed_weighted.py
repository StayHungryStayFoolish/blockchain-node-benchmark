#!/usr/bin/env python3
"""
W1.1 — chain template 批量填 mixed_weighted 字段 (Q4-14)

策略:把现有 rpc_methods.mixed (逗号分隔字符串) 转为 mixed_weighted (数组,
每个 method weight=1)。等权重 = 平均 = 与原 mixed 完全等价行为,
向后兼容(保留 mixed 字段不删除,见 spec §1.8 优先级规则)。

幂等:已有 mixed_weighted 的链跳过。
"""
import json
import sys
from pathlib import Path

CHAINS_DIR = Path(__file__).parent.parent / "config" / "chains"


def fill_chain(chain_file: Path) -> tuple[bool, str]:
    with open(chain_file) as f:
        d = json.load(f)

    rm = d.get("rpc_methods")
    if not rm:
        return False, "no rpc_methods"

    if "mixed_weighted" in rm:
        return False, "already has mixed_weighted"

    mixed = rm.get("mixed")
    if not mixed:
        return False, "no mixed field"

    methods = [m.strip() for m in mixed.split(",") if m.strip()]
    if not methods:
        return False, "mixed field is empty after split"

    rm["mixed_weighted"] = [
        {"method": m, "weight": 1} for m in methods
    ]

    with open(chain_file, "w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return True, f"filled ({len(methods)} methods, all weight=1)"


def main():
    chain_files = sorted(CHAINS_DIR.glob("*.json"))
    filled = 0
    skipped = 0
    errors = []
    for cf in chain_files:
        changed, reason = fill_chain(cf)
        if changed:
            filled += 1
            print(f"  ✓ {cf.name}: {reason}")
        else:
            if "already" in reason:
                skipped += 1
                print(f"  - {cf.name}: SKIP ({reason})")
            else:
                errors.append((cf.name, reason))
                print(f"  ✗ {cf.name}: ERROR ({reason})")

    print()
    print(f"Summary: filled={filled} skipped={skipped} errors={len(errors)} total={len(chain_files)}")
    if errors:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
