# RPC method DSL 重构 — 自主执行续命 Prompt(上下文压缩后必读)

> 用户 2026-06-03 离场休息, 要求我自主执行全部代码更新。压缩后读本文件继续, **严禁为快投工减料**。

## ⛔ 开局强制(每次压缩后/接手必做, 不可跳)
1. 加载 skill: `blockchain-node-benchmark-architecture`(读 §4.5-4.8 + §4.6 已沉淀的调用链结论)、`token-level-careful-edit`、`parallel-entry-trap`、`no-deferred-bugs`、`test-driven-development`
2. 读 memory(MEMORY.md/USER.md 系统注入, 权威)。关键: phantom铁律(禁正文打 call:/invoke 标签当文本, 只走真 tool_call); commit 用 write_file 写 /tmp/msg.txt 再 git commit -F(禁 terminal 内联多行/heredoc/printf); python3 -c 内联会触发 BLOCKED(解析JSON用curl存文件+read_file)
3. 读沉淀文档(本任务事实地基, 全部 token-level 精读完成):
   - `analysis-notes/rpc-method-abstraction-design.md` §4(param_spec DSL)/§5(response_spec DSL)/§6.2(实施计划S0-S3.7)/§6.5(schema定稿+缺口落点+不留债约束) ← **代码更新的主依据**
   - `analysis-notes/rpc-method-refactor-fulllink-analysis.md` §0-105(全链路逐行分析, 行号落点)
   - `analysis-notes/block-height-sync-method-measurement.md`(36链块高method实测+五档sync_strategy+§98 sui/aptos官方文档确认)
4. 读 task list(todo工具): 26项, 找 in_progress/下一个 pending 继续

## 🎯 任务北极星(不可漂移)
声明式 DSL 让使用者**零代码配置任意 RPC method**(NS-1/NS-3 从"零代码加链"延伸到"零代码加method")。核心: **不留技术债 + 调用链不断裂 + 严格满足需求 + 更优雅更统一**。

## 执行纪律(用户强制, 每个功能点都遵守)
- **token-level**: 改前逐行 read_file 目标+caller+downstream reader 全文; grep 只锚入口, 命中行≠精读; "没读的不准判边缘/正交/死代码"
- **每次只更新一个功能点**, 改完立即更新 task 状态(completed), 落盘+commit, 再下一个
- **不留债**(§6.5.5 六条硬约束): ①字段名全保留(csv_registry单源, mainnet_block_height改名否决) ②block_height_diff=最硬契约(required无兜底)列名不变 ③配置债收敛单源 ④build_vegeta_target接口签名四处联动改 ⑤fallback fail-fast禁静默退化 ⑥D5 Shell不forkPython
- **L1+L2+L3 三层**: 每个功能点至少 L1单测; 阶段性 L2模块集成; 全部完成后 L3整框架e2e(fake-node在GCE/GKE真机)
- **commit铁律**: write_file写/tmp/msg.txt → git commit -F(分支 feat/architecture-docs)
- **真机环境就绪**(用户确认): GCE/GKE 都在, L3-gce/L3-gke 能跑

## 功能点执行顺序(task list, 按依赖排)
S0(前置工具链, in_progress) → A1/A2/A3(输入供给) → B1→B2→B3→B4→B5(参数DSL) → C1-C7(响应链+归因) → D1→D2→D3→D4(块高归一) → E1(出图统一) → FN(fake-node同步, 依赖B4/D1) → final-selfcheck → L3-gce → L3-gke

## 各功能点落点速查(行号已token-level坐实, §6.5.4)
| 功能点 | 落点 | 关键 |
|---|---|---|
| S0 | fake-node fixture补全 + e2e method构造验证harness(F2) + adapter_family自动生成(F1, normalize_chain_templates.py) | L3地基先建 |
| A1 | fetch_active_accounts.py create_adapter L673 | 补bitcoin UTXO(无account) |
| A2 | fetch L729用→L818弃 | 保留tx_hash入池 |
| A3 | target_generator.sh L220-225 | 多池按param_spec.source分桶 |
| B1 | chain template param_spec(扩展param_formats/_meta.rest_paths) | §4.2 schema |
| B2 | 6 adapter _build_params | list/dict/path/delegate+auth, 消占位污染 |
| B3 | base.py L34 + cli.py L70/106 + target_generator TSV + _build_params | 单address槽→inputs:dict 四处联动 |
| B4 | target_generator.sh L260 | mixed_weighted加权(非round-robin均权) |
| B5 | cli.py L55 / jsonrpc.py L97 / 各adapter default | fail-fast禁静默[address] |
| C1 | chain template response_spec(复用network_field_registry语义映射) | §5.2 schema |
| C2 | proxy handler + 各adapter id=1(8处) + rest无id + batch | request_id关联键 |
| C3 | tools/proxy/internal/proxy/handler.go:77 __unmatched__ | 三端同源method为键 |
| C4 | analysis/per_method_attribution.py L62-68 + visualization/per_method_charts.py L241(只画cpu) | 补mem/EBS/Net四维 |
| C5 | per_method_attribution.py 读 proxy_self.csv | 减proxy基线(Q4-10/ADR-0004) |
| C6 | per_method_attribution.py L98 默认mem_used_mb→mem_used | report_generator L4308已显式兜默认仍错 |
| C7 | cosmos-hub/polkadot协议错配, 复用hedera_dual委派+rest.py | S3.7 |
| D1 | chain template扩展_meta.health_probe(五档sync_strategy) | §6.2.3已schema定稿 |
| D2 | common_functions.sh get_block_height(8链case) + chain_adapters parse_block_height/health_check | 收编单源, Shell读声明 |
| D3 | common_functions.sh | 不打MAINNET_RPC_URL, 本地自查 |
| D4 | config/internal_config.sh L59 + analysis/rpc_deep_analyzer.py L35 | DIFF_THRESHOLD=50/SYNC_THRESHOLD=20双源合一(py os.getenv读) |
| E1 | visualization/per_method_charts.py | SVG→matplotlib UnifiedChartStyle |
| FN | tools/fake-node/handlers/*.go validate(6处rpc_methods.mixed→mixed_weighted) + fixture补全(record_all_184) | Handle()passthrough不改 |

## 4个declarative范式(DSL复用不新造, 防parallel-entry)
1. rest `_meta.rest_paths`(path+body模板, _tx_hashes/_addresses数组=非account输入)
2. hedera_dual委派路由(_is_jsonrpc_method正则按method分协议)
3. network provider约定式文件名路由({variant}.sh免dispatch表)
4. network_field_registry字段→语义映射(response_spec样板)

## 2治理缺口(进S0必带)
- F1 adapter_family无自动生成(normalize只产adapter_required)→ normalize补自动判定+CI校验必填
- F2 e2e黑盒探活不验method构造→ S0补 method×chain build-target断言(address进body/url+param顺序)

## 7真缺口(行号坐实)
#2 fetch无UTXO adapter / #3 tx_hash丢弃 / #8 per_method_charts L241只画cpu / #9 weight L260取模均权 / #10 单account池 / #11 proxy_self.csv死数据 / mem_used列名 attribution L98

## 块高调用链(D1-D4必须保护的契约)
block_height_monitor(唯一调get_block_height)→3内存文件(cache.json/node_health.cache/time_exceeded.flag)+CSV→unified_monitor tail+cut块高6字段进主performance CSV→8 consumer(bottleneck场景C/5 Python reader/csv_registry单源)。
**块高功能链**: 本地vs网络高度→block_height_diff→monitor持续超时→time_exceeded.flag→bottleneck_detector场景C=Node_Unhealthy。**L3必验: 构造节点落后断言flag写入+场景C触发**。

## 完成定义
26项task全completed → final-selfcheck(token-level回验每个落点+不留债+差集) → L3-gce(fake-node整框架e2e出图+块高场景C) → L3-gke(+k8s采集) 全过 → 给用户审/报告。

## 自查触发(用户元问句=探针, 默认我没做到)
"实测了么/grep还是精读/遵守要求了么/分析完了么/确定完了么" → 立即(a)实测重验(b)按文件×读取状态清单证覆盖率(c)回业务目的对照。绝不嘴上认错继续挖/凭"挖出东西"自证。
