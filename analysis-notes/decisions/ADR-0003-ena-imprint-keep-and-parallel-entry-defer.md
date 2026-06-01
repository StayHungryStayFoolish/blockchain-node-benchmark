# ADR-0003: ENA 网络监控烙印保留 + 新旧并行入口暂不清理

## 状态
Accepted (2026-05-31, 用户拍板「C + KEEP」)

与 ADR-0001/0002(disk 字段中立化)**不冲突, 互补**: disk 段是"假烙印真通用"(EBS 名指通用磁盘逻辑)→
中立化; ENA 段是"真烙印真专属"(ENA = AWS 弹性网络适配器, 语义确属 AWS)→ 按 D2 保留 ena_。
两者方向相反但同一原则: **命名以语义真实性为准, 不为了"看起来中立"而抹掉真实的厂商专属语义。**

## 背景

2026-05-31 对全量产出文件做中立化审计(见 `analysis-notes/OUTPUT-FILES-INVENTORY-2026-05-31.md`),
ENA 烙印簇 5 个产出文件原拟按"方向2 (ena_→network_ 去烙印)"改名。但执行前按 token-level
纪律做 writer↔reader 全仓对账, 炸出两个关键事实, 使该问题从"改名"升级为"架构决策":

### 事实1: 网络监控三套实现已并存 (parallel-entry-trap)
| 实现 | 文件 | 产出 CSV | 派发状态 | 性质 |
|---|---|---|---|---|
| 旧 (AWS legacy) | `monitoring/ena_network_monitor.sh` | `ena_network_${TS}.csv` | coordinator:35 `["ena_network"]` 仍注册 | AWS-only legacy |
| 新 (Y+ 架构) | `monitoring/network_monitor.sh` + `monitoring/network/{aws_ena,gcp_gvnic,gcp_virtio,other_none,interface}.sh` | `network_${TS}.csv` | coordinator:36 `["network"]` 已注册 | 平台感知 driver 分流, 已中立 |
| provider getter | aws_provider.sh:34 → `ena_network_monitor` / gcp_provider.sh:34 → `gvnic_network_monitor` | — | getter 仍指旧的 | 派发名 |

代码自证据(注释):
- `monitoring/network/aws_ena.sh:3` "AWS ENA 实现 (driver=ena, 替代原 ena_network_monitor.sh)"
- `network_monitor.sh:5` "Replaces AWS-only ena_network_monitor.sh with platform-aware Y+ architecture"
- `network_monitor.sh:10` "Old ena_network_monitor.sh continues to coexist for AWS legacy compatibility"
- `network_monitor.sh:47` "Output CSV path — uses 'network_' prefix (not 'ena_network_') to distinguish from legacy"

即中立化已做一半: 新架构产出已是 `network_*.csv`; 旧 ena legacy 仍 coexist 未下线, getter 仍指旧的。

### 事实2: 3 张 ENA PNG 是真 ENA 专属指标 (非误命名)
- `ena_limitation_trends.png` / `ena_connection_capacity.png` / `ena_comprehensive_status.png`
- advanced_chart_generator.py 生成, 内容 = ENA allowance 限额 (PPS / 带宽 / 连接跟踪上限)
- i18n 文案本身写 "AWS ENA network limitation" (report_generator.py:547) — 内容确属 AWS ENA
- 与 `aws_ebs_baseline_stats` (假烙印真通用, 已中立化为 "Disk Baseline...") **性质相反**: 此处真专属

## 决策

### D1 (KEEP): ENA 专属产出物保留 ena_ 前缀, 不中立化
以下 5 个产出文件**保留 ena_ 命名**, 因其语义确属 AWS ENA(GCP 用 gVNIC/virtio, 无 ENA allowance 概念):
1. `ena_network_${TS}.csv` (legacy CSV)
2. `ena_baseline.json` (bottleneck_detector.sh:537, ENA allowance 基线)
3. `ena_limitation_trends.png`
4. `ena_connection_capacity.png`
5. `ena_comprehensive_status.png`
6. `ena_network_monitor.log` (legacy 日志)

理由: ENA = Elastic Network Adapter = AWS 专属硬件/驱动概念。其 allowance 限额(PPS/带宽/conntrack)
是 AWS 实例独有的可观测指标, GCP gVNIC/virtio 无对应概念。给它中立化为 `network_*` 反而抹掉真实语义,
让 AWS 用户看不出"这是 ENA 网卡限额监控"。符合 ADR-0002 同一原则(命名以语义真实性为准)。

### D2 (C, 暂不清理): ena_network legacy 入口 parallel-entry 暂不动
`ena_network_monitor.sh` 这个 AWS legacy 入口**本轮不下线、不改 getter**, 与新 `network_monitor.sh`
继续 coexist。理由:
- 切新架构(改 aws_provider.sh:34 getter 指 network_monitor + 从 coordinator 下线 legacy)**会动 AWS 生产路径**
- 需先验证"AWS 实例下 network_monitor.sh (走 monitoring/network/aws_ena.sh driver) 能完全替代
  ena_network_monitor.sh 的采集能力", 该验证需 AWS 真机 / fake-node AWS variant, 本阶段未做
- 撞 memory "破坏性操作铁律"(动生产路径前必验) + skill parallel-entry-trap(不自决)
→ 留到架构层 parallel-entry 统一清理时, 连同 disk 侧 legacy 入口一并做(需 L3 AWS 验收护航)

## 撤销线 (满足任一 → 重开本 ADR)
- **D1 撤销**: 若未来 GCP/Azure 也引入等价的"网卡 allowance 限额"可观测概念, 且需要跨云统一这套图表 →
  届时考虑把 ENA 限额抽象为 `nic_allowance_*` 通用层(provider 子类各自填充), 此时才中立化命名。
  触发动作: 出现第 2 个云的 allowance 监控需求。
- **D2 撤销**: 当 (a) AWS 真机 / fake-node aws_ena variant 验证 network_monitor.sh 采集 == ena_network_monitor.sh
  字节对齐, 且 (b) 进入架构层 parallel-entry 统一清理阶段 → 下线 ena_network_monitor.sh legacy 入口,
  aws_provider.sh:34 getter 改指 network_monitor (driver 分流), legacy CSV/log 自然消失。
  触发动作: AWS L3 验收通过 + parallel-entry 清理排期。

## 关联
- `analysis-notes/OUTPUT-FILES-INVENTORY-2026-05-31.md` — 全量产出文件清单 × 需求 × 烙印总表(本 ADR 的证据底座)
- ADR-0002 — disk 五层命名(中立化方向, 与本 ADR D1 KEEP 方向相反但同原则)
- skill `blockchain-node-benchmark-architecture` §4#5 / §5 parallel-entry-trap
- skill `parallel-entry-trap`
