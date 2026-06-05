#!/usr/bin/env python3
"""
ci/check_fixture_coverage.py — fixture 覆盖一致性门(S0 交付 / F2 核对部分)

背景: fake-node handler 是 byte passthrough, 任一 config 配置的 method 缺 fixture →
       fake-node mixed 打到它即 `no fixture wired` 报错。所以"config method ↔ fixture 文件"
       必须 100% 一致, 加新 method 漏 fixture 要在 CI 就拦住, 不能等 fake-node 跑崩。

为什么固化双转换规则(2026-06-05, 之前人工核对连错4次的根因):
  method 名 → fixture 文件名有【两套】规则, 凭印象猜正向必错。实证双规则:
    ① method 带 HTTP 动词前缀(含空格, 如 `GET /v2/x`)→ 空格→_ 且 /→_  得 `GET__v2_x`(双下划线)
    ② method 以 / 开头无动词(如 `/status`)→ /→_ 去前导_  得 `status`
  核对必反向(读真实 fixture vs config), 但本脚本固化了正向规则供 CI 自动判定 —
  规则一旦写错会误报, 故脚本同时打印缺失项的【期望文件名】便于人工反查。

mock 豁免: MOCK_MANIFEST.md 记录的公开 endpoint 测不到、按官方文档 mock 的 method,
           这些 fixture 已生成, 同样要在; 本脚本不区分 mock/实测, 只校验文件存在。

退出码: 0 = 184/184 全覆盖; 1 = 有缺口(打印链+method+期望文件名)
"""
import json, glob, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAINS = os.path.join(REPO, "config", "chains")
FIXDIR = os.path.join(REPO, "tools", "fake-node", "fixtures")


def fixture_name(method: str) -> str:
    """固化双转换规则(实证 2026-06-05)。method 名 → fixture 文件 basename(不含 .json)。"""
    if " " in method:           # 带 HTTP 动词前缀: GET /v2/x → GET__v2_x
        return method.replace(" ", "_").replace("/", "_")
    return method.replace("/", "_").lstrip("_")  # /status → status ; eth_x / system_account 原样


def collect_config_methods():
    """每链 config 配置的所有 method(single + mixed_weighted), 返回 {chain: set(methods)}。"""
    out = {}
    for f in sorted(glob.glob(os.path.join(CHAINS, "*.json"))):
        chain = os.path.basename(f)[:-5]
        d = json.load(open(f))
        rm = d.get("rpc_methods", {})
        methods = set()
        if rm.get("single"):
            methods.add(rm["single"])
        for m in rm.get("mixed_weighted", []):
            if m.get("method"):
                methods.add(m["method"])
        out[chain] = methods
    return out


def collect_fixtures(chain: str):
    """该链 fixtures 目录里真实存在的响应 fixture basename 集合(排除 .request.json)。"""
    d = os.path.join(FIXDIR, chain)
    if not os.path.isdir(d):
        return set()
    return {fn[:-5] for fn in os.listdir(d)
            if fn.endswith(".json") and not fn.endswith(".request.json")}


def main():
    cfg = collect_config_methods()
    total = 0
    covered = 0
    gaps = []  # (chain, method, expected_file)
    for chain, methods in cfg.items():
        files = collect_fixtures(chain)
        for m in methods:
            total += 1
            if fixture_name(m) in files:
                covered += 1
            else:
                gaps.append((chain, m, fixture_name(m) + ".json"))

    print(f"=== fixture 覆盖门: {covered}/{total} ===")
    if gaps:
        print(f"  ❌ {len(gaps)} 个 method 缺 fixture:")
        for chain, m, exp in gaps:
            print(f"     {chain}: method='{m}' → 期望 fixtures/{chain}/{exp}")
        print("  修复: 补 fixture(真机实测落盘 或 按官方文档 mock + 记 MOCK_MANIFEST.md)")
        print("  提示: 若你确信 fixture 已存在, 检查文件名是否符合双转换规则(见本脚本 fixture_name)")
        return 1
    print(f"  ✅ {total} 个 config method 全有 fixture(fake-node mixed 不会报 no-fixture)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
