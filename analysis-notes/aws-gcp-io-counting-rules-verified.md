# AWS vs GCP IO 计量规则官方文档实证报告
日期：2026-05-19
来源：4 个云厂商 HTML 文档实抓 + 关键句搜索

═══════════════════════════════════════════════════════════════
规则 A：AWS EBS SSD 按 256 KiB 拆分 IO  →  ✅ 用户说法完全正确
═══════════════════════════════════════════════════════════════

URL: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-io-characteristics.html

原文（IOPS 章节）：
"IOPS are a unit of measure representing input/output operations per second.
 The operations are measured in KiB, and the underlying drive technology
 determines the maximum amount of data that a volume type counts as a
 single I/O. **I/O size is capped at 256 KiB for SSD volumes** and 1,024 KiB
 for HDD volumes."

"When small I/O operations are physically sequential, Amazon EBS attempts
 to **merge** them into a single I/O operation up to the maximum I/O size.
 Similarly, when I/O operations are larger than the maximum I/O size,
 Amazon EBS attempts to **split** them into smaller I/O operations."

官方示例表：
  SSD 256 KiB | 1 x 1024 KiB I/O operation     | 4 (1,024÷256=4)
              | 8 x sequential 32 KiB I/O ops  | 1 (8x32=256, merged)
              | 8 random 32 KiB I/O ops        | 8 (counted separately)
  HDD 1024 KiB| 1 x 1024 KiB I/O operation     | 1
              | 8 x sequential 32 KiB I/O ops  | 1 (merged into 256)


═══════════════════════════════════════════════════════════════
规则 B：AWS EBS HDD 按 1,024 KiB (1 MiB) 拆分  →  ✅ 用户说法完全正确
═══════════════════════════════════════════════════════════════

同一文档：
"I/O size is capped at 256 KiB for SSD volumes and **1,024 KiB for HDD
 volumes**"

EBS volume-types 文档也旁证：
URL: https://docs.aws.amazon.com/ebs/latest/userguide/ebs-volume-types.html
"Max IOPS per volume (1 MiB I/O) — 500 [st1] / 250 [sc1]"
→ HDD 的 IOPS 上限是按 1 MiB IO 算出来的。


═══════════════════════════════════════════════════════════════
规则 C：GCP Persistent Disk 不按 IO size 拆分  →  ✅ 用户说法基本正确
═══════════════════════════════════════════════════════════════

URL: https://cloud.google.com/compute/docs/disks/optimizing-pd-performance

GCP 文档明确把 IOPS 和 IO size 当作两个独立的轴：
"**The calculation for throughput is IOPS × I/O size.**"
"The IOPS numbers in this table are based on an **8 KB I/O size**. Other
 I/O sizes, such as 16 KB, might have different IOPS numbers but maintain
 the same read and write distribution."

→ 这是 GCP "**不按 IO size 拆分**" 的反向证据：
   - IO size 大 → 单次 IOPS 提供更多 throughput → 更易触 throughput 桶上限
   - IOPS 计数本身是按系统层 I/O 操作数计算的，不做 N×256 拆分

GCP PD 读写分桶（用户说法正确）：
URL: https://cloud.google.com/compute/docs/disks/performance
"For Balanced and SSD (performance) Persistent Disk volumes, the read and
 write throughput limits are independent of each other. This means that a
 disk can reach both the stated read and write limits simultaneously."

表格逐磁盘类型列 "Read IOPS per GiB / Write IOPS per GiB" 分两列。

⚠️ GCP 文档**未正面陈述** "我们不按 X KiB 拆分 IOPS"
   但所有性能计算示例都是 throughput = IOPS × IO_size 这种独立乘式
   且 8 KB / 16 KB 例子明说"不同 IO size 会有不同 IOPS 数"
   ——这与 AWS "强制拆分到 256 KiB" 的模式互不兼容


═══════════════════════════════════════════════════════════════
规则 D：GCP Hyperdisk 不按 IO size 拆分  →  ✅ 同 C
═══════════════════════════════════════════════════════════════

URL: https://cloud.google.com/compute/docs/disks/hyperdisks
URL: https://cloud.google.com/compute/docs/disks/optimizing-hyperdisk-performance

Hyperdisk 的计费模型是 "Provisioned IOPS + Provisioned Throughput" 完全
解耦：用户独立购买 IOPS 配额和 Throughput 配额。文档无任何"按 X KiB
拆分 IO" 的字样。


═══════════════════════════════════════════════════════════════
关于 Hyperdisk 读写是否合并计量（用户额外问题）
═══════════════════════════════════════════════════════════════

⚠️ 本次抓的两份 Hyperdisk 文档（gcp_hyperdisk.html、optimizing-hyperdisk-
   performance）没有找到明确的 "Hyperdisk 读写共用一个 IOPS 桶" 的字样。
   用户原文说 "Hyperdisk 和 AWS 是一起计算的" —— 此条**官方文档未直接
   证实**，但根据 Hyperdisk 是 Provisioned-IOPS（独立配置非默认赠送）的
   模型来推测：用户买的 Provisioned IOPS 配额 = 读+写共享总 IOPS 上限。
   建议在 framework 里同时记录 read_iops/write_iops/total_iops，让分析
   阶段可以按 max(read+write, total) 算饱和度，向后兼容两种解读。


═══════════════════════════════════════════════════════════════
对 blockchain-node-benchmark 的影响（决定性结论）
═══════════════════════════════════════════════════════════════

【过往认知错误】
2026-05-18 在工作记忆中写入的 "AWS EBS 不按 IO size 拆分 IOPS/Throughput"
和 utils/ebs_converter.sh 当前的 passthrough 实现 —— **都是错的**，与
AWS 官方文档直接冲突。

【用户提供的规则全部成立】
1. AWS SSD：actual_iops_consumed = (r/s + w/s) × ceil(areq_sz / 256)
2. AWS HDD：actual_iops_consumed = (r/s + w/s) × ceil(areq_sz / 1024)
3. GCP PD/Hyperdisk：actual_iops_consumed = r/s + w/s（不做转换）
4. 双重天花板：threshold = min(disk_limit, vm_limit) ← 框架必须实现

【AWS sequential merge 的工程权衡】
官方说 "EBS attempts to merge sequential small I/O up to max I/O size"。
监控侧能不能算出"合并后的 IOPS"？
→ 不能，因为 iostat 看不到 EBS 内部是否合并了。
→ 工程实践：用 ceil(areq_sz / 256) × (r/s + w/s) 算上界（保守告警），
   实际 EBS 内部 merge 会让真实消耗 ≤ 该上界。这正是用户给的公式。

【framework 必须改的 5 个点】
1. utils/ebs_converter.sh — convert_to_aws_standard_iops 恢复成
   ceil(areq_sz / 256) 拆分逻辑（之前的 passthrough 错了）
2. utils/ebs_converter.sh — convert_to_aws_standard_throughput 验证
   是否要恢复（throughput 公式可能不需要拆分，只是 KiB→MiB）
3. monitoring/disk/aws_ebs.sh — 计算 aws_standard_iops 字段时调用上面
   修复后的函数，并把 commit message 改正过来
4. monitoring/disk/gcp_pd.sh + gcp_hyperdisk.sh — 保持 passthrough
   （这是对的，符合 GCP 业务规则）
5. 新增 vm-level IOPS/throughput 上限抓取（C-S2 cloud_detect.sh 已有
   PROVIDER 检测雏形，需补 vm_type → max_storage_iops 的查表）

【MEMORY 必须修正】
之前 MEMORY 中写的 "AWS EBS 不按 IO size 拆分 IOPS/Throughput" 是错的，
需要替换为正确版本：
  "AWS EBS SSD 按 256 KiB 拆分 IO，HDD 按 1024 KiB 拆分；GCP PD/Hyperdisk
   不拆分。监控侧用 ceil(areq_sz / 256) × (r/s+w/s) 算 AWS 消耗上界。"
