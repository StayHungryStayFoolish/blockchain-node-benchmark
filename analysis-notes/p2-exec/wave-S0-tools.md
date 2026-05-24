# Wave S0-tools — L3 前置工具链(N1a 精简版)

**baseline**: `ffbeeee`
**完成时间**: 2026-05-24
**决策依据**: 用户回 **N1a**(精简版,跟 wave 走的渐进式 mock 扩展)

## 决策摘要

| 议题 | 选项 | 决策 | 反转条件 |
|------|------|------|----------|
| S0-tools 范围 | N1a 精简 / N1b 全 28 handler / N1c 跳过 | **N1a** | 若 S2-a 发现 5+ 共享 handler 可压成 1 通用 dispatcher,回头重构 S0 |
| 新链 handler 实现时机 | S0 一把梭 / wave 增量 | **wave 增量**(跟 S2 wave 走) | 若 wave 内开发链 handler 工程量超估 2x,回头折回 S0 |
| 未知 chain 默认行为 | 静默 echo / 报错拒绝 | **报错拒绝**(opt-in `MOCK_ALLOW_UNKNOWN=1`) | — |

## 4 个自动停手点(全部生效)

1. **mock 启动 exit≠0** → step 1 PASS(8/8 启动 OK)
2. **baseline snapshot diff≠0** → step 2 PASS(8/8 round-trip DIFF=0)
3. **8 链 matrix 非 0 退出** → step 3 PASS(`ONLY=ethereum` rc=0 + 既有 8 链 smoke rc=0)
4. **兜底 handler 返非合法 JSON** → step 4 PASS(curl 实测合法 JSON-RPC envelope)

## 执行步骤

### Step 1: 验证现有 mock 可启动 + 8 链 curl(2 秒)

8/8 PASS:

```
✅ solana       port=18900  result=1779588689
✅ ethereum     port=18900  result=0x8d6dd31
✅ bsc          port=18900  result=0x8d6dd31
✅ base         port=18900  result=0x8d6dd31
✅ polygon      port=18900  result=0x8d6dd31
✅ scroll       port=18900  result=0x8d6dd31
✅ starknet     port=18900  result=148299057
✅ sui          port=18900  result=148299057
```

**结论**:现有 `tools/mock_rpc_server.py` 8 链 sentinel method 全过,无需任何修补。

### Step 2: baseline 8 链 snapshot(0.2 秒)

从 `config/config_loader.sh:408-652` 的 `UNIFIED_BLOCKCHAIN_CONFIG` heredoc(顶层 key = `blockchains`,**非** `chains`,首版误判已纠正)抽取 8 链 baseline,落盘 `tests/snapshots/baseline_8chains/*.json`。

Round-trip 验证(snapshot vs `config/chains/<chain>.json` 去掉 `_meta`):

```
✅ solana       snap=1181B  round_trip=DIFF=0
✅ ethereum     snap=922B   round_trip=DIFF=0
✅ bsc          snap=917B   round_trip=DIFF=0
✅ base         snap=918B   round_trip=DIFF=0
✅ scroll       snap=920B   round_trip=DIFF=0
✅ polygon      snap=921B   round_trip=DIFF=0
✅ starknet     snap=905B   round_trip=DIFF=0
✅ sui          snap=1092B  round_trip=DIFF=0
```

**结论**:8/8 字节级一致,可作为 S1.2 拆 8 链后回归的金标准。

### Step 3: e2e harness 接 `config/chains/*.json`

**改造点 1**(零破坏)— `tools/e2e_smoke.sh` 加可选 `CHAIN_CONFIG` 环境变量:

- 未传时行为不变(与既有 8 链 matrix 100% 兼容)
- 传时 gate 校验:文件存在 + `.chain_type` 字段可读;不一致即 fail

**改造点 2**(新文件)— `tools/e2e_smoke_chain_matrix.sh`:

- **自动扫描** `config/chains/*.json`(零写死),36 链全覆盖
- 支持 `ONLY_CHAINS=a,b,c`/`SKIP_CHAINS=x,y`/`BASE_PORT=29000` 过滤
- 每链独立 log:`/tmp/e2e_smoke_chain_matrix/<chain>.log`
- 自带尾部 6 行日志(自调试)
- 默认串行(GCE 共享资源 3 原则);可 `PARALLEL=1` 切并行

**验证**:

```
=== Test A: bash -n syntax ===
  ✅ tools/e2e_smoke.sh                rc=0
  ✅ tools/e2e_smoke_chain_matrix.sh   rc=0

=== Test B: ONLY=__never_match__ 干跑(期望 exit=2)===
  rc=2  stderr=ERROR: filter left 0 chains

=== Test C: ONLY=ethereum 单链真跑(带 CHAIN_CONFIG gate)===
  rc=0  PASS (CHAIN_CONFIG gate 命中,chain_type=evm)
```

**保留原 `tools/e2e_smoke_8chain_matrix.sh`**(写死 8 链版)作为 S1.2 回归基准——不删,新版与旧版并存,符合 v1.4.4 老测保护规则。

### Step 4: 兜底 handler(unknown chain → echo)

**双层 gate 设计**(防止"未知链静默装成 ethereum"这种 parallel-entry-trap 变体):

1. **dispatch 路径**:`MOCK_ALLOW_UNKNOWN=1` 时,未知 chain → `handle_unknown()` 返 `{"_mock_echo": true, "_method": <m>, "_params": <p>}`
2. **启动路径**:`main()` 启动时若 `--chain` 不在 `CHAIN_HANDLERS` 且 env 未设,**直接 exit=2 拒启**(fail-fast)
3. **默认行为不变**:未设 env 时 `dispatch` 仍返 -32601,既有所有测试 0 副作用

`handle_unknown` 返回的 `_mock_echo: true` 是**显式不通过语义验证的标记**——任何下游 assert 看到这字段就必须当"liveness OK, semantics not validated"处理,绝不能据此声明"通过"。

**验证**:

```
=== L1 unittest (tests/test_mock_rpc_unknown_echo.py) — 4/4 PASS ===
  test_default_unknown_chain_rejected       ... ok
  test_env_set_unknown_chain_echoes         ... ok
  test_handle_unknown_shape                 ... ok
  test_known_chain_not_affected_by_gate     ... ok

=== L2 实测 ===
  ✅ 启动 gate: --chain bitcoin (no env) → exit=2 + 提示
  ✅ MOCK_ALLOW_UNKNOWN=1 + --chain bitcoin → curl getblockcount
     返回 {"_mock_echo":true,"_method":"getblockcount","_params":[]}

=== 回归 ===
  ✅ tests/smoke_mock_rpc_8chains.sh        8/8 PASS
  ✅ tests/test_mock_rpc_chain_forward.py   4/4 PASS
```

## 落盘清单

| 文件 | 性质 | 字节 |
|------|------|------|
| `tools/e2e_smoke.sh` | 改造(+27 行 / -2 行) | 6017 |
| `tools/e2e_smoke_chain_matrix.sh` | 新增 | 5401 |
| `tools/mock_rpc_server.py` | 改造(+30 行 / -1 行) | 31855 |
| `tests/test_mock_rpc_unknown_echo.py` | 新增 L1 测 | 2609 |
| `tests/snapshots/baseline_8chains/*.json` × 8 | 新增 snapshot | 7776 合计 |

## E1/E5 自检

- **E1 完整度**:S0-tools 5 步全 PASS,无 defer,无 skip。
- **E5 反例**:`MOCK_ALLOW_UNKNOWN=1` 时 echo 的语义"对不对"是**已知不验证**(`_mock_echo:true` 显式标记),下游必须用真 endpoint fixture 校验语义,不能拿 echo 当通过。

## 下一步(S1.1)

拆 8 链 baseline 出 `config/chains/*.json`(已完成—— `_meta` 标 `source:"baseline-heredoc"` 而非 `"research-md"`)+ 改 `config/config_loader.sh` heredoc 改 loader 读 `config/chains/*.json`。S1.2 回归用 step 2 落盘的 snapshot 做 diff=0 闸门。
