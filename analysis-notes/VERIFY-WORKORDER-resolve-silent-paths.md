# 核实工单: registry resolve 静默断链面全核 (进 S2 前置)

> 2026-05-31 落盘。触发: 用户要求"扩大代码分析范围,确认无误判无遗漏再进 S2"。
> 背景: 我上次"亲读 registry"只读了 DISK_FIELD_PREFIX 字典(L30-32),**漏了 resolve body L127 的
> `.get(provider, "standard")` fallback**(已被用户落盘改为 normalized)。这证明我的核实不彻底——
> 只读 SSOT 不读 resolve helper body = token-level skill 明确警告的 under-count。
> 故进 S2 前必须把所有 reader 的 resolve 调用 + 各自 fallback/silent-zero 面亲读一遍。
>
> ⚠️ **本工单未完成前不进 S2**。当前会话已多次上下文压缩(脏),应 /new 干净会话执行本工单。

## 已确认事实 (E1, 本次亲读)
- ✅ `utils/csv_schema_registry.py` L30-32 DISK_FIELD_PREFIX 三云=normalized
- ✅ `utils/csv_schema_registry.py` L127 resolve fallback = `.get(provider,"normalized")` (已落盘,原 standard)
- ✅ `utils/csv_schema_registry.py` resolve body: logical_name 未注册硬 raise KeyError(不静默)
- ✅ config/csv_schema_registry.sh L66-68 = normalized; 对称测试 5/5 绿
- ✅ T 阶段 5 处撒谎注释已清(§5.8)

## 待亲读函数体清单 (resolve helper + fallback 面, 逐个读 body 不 grep 抽样)

### Python reader (113处/10文件) — 重点读 resolve 调用处的"拿空怎么办"
- [ ] visualization/disk_chart_generator.py (76处最多) — resolve 拿到列名后, 若列不存在/为空, 是否静默归零?
      读 _recalculate_disk_* (token-level skill 记录: ebs_chart 自己重算覆写列=计算逻辑双源)
- [ ] visualization/device_manager.py (25处) — _disk_iops_suffix/_disk_throughput_suffix 来源,
      provider_aware_suffix_map 解析失败时行为
- [ ] visualization/report_generator.py (5处) — L1644/1794/1812 后缀精确匹配, 匹配不到怎么办
- [ ] monitoring/pod_device_mapper.py (1处)
- [ ] tools/chain_adapters/*, normalize_chain_templates, audit_rpc_methods (各1处, 大概率无关 disk, 确认即可)

### Bash reader (66处/11文件) — 重点读 jq //0 / echo "0" / CSV_FIELD_MAP[]:- 等静默归零
- [ ] monitoring/bottleneck_detector.sh (9处) — token-level skill 记录: 文件级 trap ERR→exit 0 吞错;
      CSV_FIELD_MAP[field]:- 查不到→空下标→默认0
- [ ] core/master_qps_executor.sh (7处) — skill 记录 L301-304 `_mqe_provider_field`: resolve 失败 col 空
      → echo "0" + jq //0 双层静默归零 (这是确认过的真静默面, 复核是否已修)
- [ ] monitoring/iostat_collector.sh (5处) — header 走 registry(L159) 但 data 行手工拼接(L129)?
      §5.3 结构性脆弱点: data 未纳入 registry, 靠人肉保序
- [ ] tools/framework_data_quality_checker.sh (4处) — §5.2/L80 整串等值; **这也是 S2 的目标文件**,
      读它时顺便为 S2 做准备
- [ ] tools/disk_bottleneck_detector.sh — skill 记录 CSV_FIELD_MAP:- →0 + ebs_bottleneck_detector trap exit 0
- [ ] config/providers/{aws,gcp,other}_provider.sh get_disk_field_prefix — 与 registry 是否仍两 getter 并存?
      (§5.6 fallback bug 已修, 但 provider 层 getter 本身值核实)

## 核实判定标准 (每个 resolve 点回答)
1. resolve 拿到的列名, 若该列在 CSV 不存在 / 值为空, reader 是 **硬失败** 还是 **静默归零/None**?
2. 有无"计算逻辑双源"(reader 自己重算 writer 已写好的折算值)?
3. 有无"错误吞没"机制(trap ERR→exit 0 / jq //0 / [[ -z ]] && echo 0)?
4. fallback 默认值是否 = normalized (与 writer 一致), 还是残留 standard/baseline?

## 验收铁律 (token-level skill, 改名后禁"跑通没报错"=通过)
- 多文件有错误吞没机制时, EXIT=0 完全不能当成功信号
- 必须额外验: reader 输出折算值非零 + 与 CSV 折算列一致 + bottleneck_status.json 值非 null

## 完成后
- 所有 resolve 点判定完, 无 active 静默断链 → 扶正 EXEC-TRACKER, 干净进 S2
- 发现 active 静默面 → 先修(no-deferred-bugs), 再进 S2

## ✅ 回验完成 (2026-05-31, 干净会话, read_file 亲读函数体, 非 grep 抽样)

> 注: 工单原记的旧函数名 (_recalculate_disk_standard 等用 ebs_ 前缀) 已随 ebs→disk 改名变更,
> 本轮按当前真实行号重新定位后亲读。10 薄弱点全覆盖。

### resolve helper body 全部干净 (返 None/[]/空, 不静默归零成数据值)
- [x] disk_chart_generator.py:130 `_resolve_disk_field` — registry resolve→正则匹配→无匹配返 None
- [x] disk_chart_generator.py:153 `_recalculate_disk_standard_metrics` — 计算逻辑双源【确认存在】,
      但 L163 `if all([...])` 守卫: resolve 返 None 则整段跳过, 不崩。判定 LATENT 设计债 (折算逻辑活在
      writer disk_converter.sh + 此 chart 两处), 非 active bug
- [x] device_manager.py:170/180 `_resolve_disk_suffix`/`_resolve_disk_field` — df None→None, 无匹配→None
- [x] device_manager.py:430-460 suffix_map 消费方 — `if actual_field:` 守卫, find 不到不建映射, 安全
- [x] report_generator.py:1639 `_resolve_disk_columns` — df None→[], 无匹配→空 list
- [x] bottleneck_detector.sh:72 `_bd_resolve` — registry 缺失→echo "", 上层 `[[ -n ]]` 守卫不自拼裸名
- [x] master_qps_executor.sh:292 `_mqe_provider_field` — col 空→echo 0 + jq //0 双层归零【active 静默面,
      已记录】, 但靠 registry+writer 同源保证 //0 仅在列真不存在时触发, provider 非法→other 兜底

### active 静默/吞错面 (确认仍在, 验收铁律照旧适用)
- [x] bottleneck_detector.sh:110-120 文件级 `trap ERR→exit 0` (handle_detector_error) — 最隐蔽吞错面,
      resolve 全空→pattern 全空→检测全 0→仍 exit 0。**L3 验收必查 bottleneck_status.json 值非 null,
      EXIT=0 绝不当通过**
- [x] master_qps_executor.sh:301-304 双层归零 — 同上, L3 验收必查折算值非零且==CSV 折算列

### 工单遗留疑虑消解
- [x] providers/{aws,gcp,other}_provider.sh get_disk_field_prefix — **三云全返 `normalized`** (aws:37/gcp:37/
      other:35), 三 getter 不再并存分歧。iostat_collector.sh:164-165 fallback 即便走 getter 覆盖也拿 normalized,
      与 registry/ADR-0002 完全一致。memory 记的"三方不一致 aws_standard/baseline"是旧态, 已统一
- [x] csv_schema_registry.py:127 resolve fallback — 已改 normalized (本工单 §E1-13 落盘), 与 .sh *) 分支对称

### 无关确认
- [x] pod_device_mapper.py — 全部 resolve 是 Pod volume→host device 映射 (by-id symlink), 零 disk 折算字段, 无关
- [x] framework_data_quality_checker.sh — 消费 monitoring_iops 等非 provider_aware 字段, 不直接读折算列, 无 active 断链

### 撒谎注释 (文档层, 待扶正, 非 active bug)
- [ ] framework_data_quality_checker.sh:354 注释残留旧"standard_iops/standard_throughput_mibs" (ADR-0002 前)
- [ ] (前轮已记) csv_schema_registry .py L60 / .sh L60 / report_generator L1628 fallback 注释仍写 "standard"

### 结论
**无 active 静默断链点** (新发现)。已知 active 静默面 (trap exit 0 / jq //0 双层) 均靠 registry+writer 同源
+ 守卫保护, 设计正确; 唯需在 L3 验收时强制"折算值非零 + ==CSV 列"而非"EXIT=0=通过"。
计算逻辑双源 (disk_chart_generator._recalculate) 是 LATENT 设计债, 不阻塞进 S2。
撒谎注释 4 处属文档层。→ **可干净进 S2**, 撒谎注释建议清理后进。
