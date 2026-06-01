# ebs / ena / baseline 命名治理 — 代码事实审计与改名决策

> 方法: token-level 精读 config 权威源 + provider 抽象层归属铁证 + git diff 实证既有改动。
> 每条结论带 E1(file:line 引用)/E2(grep统计)证据。本文件取代旧 EBS-NEUTRALIZATION-spec-A.md
> (旧文件把 baseline 误判为"卷额定上限同义冲突",概念错误,作废)。
> 审计日期: 2026-05-30。
> **2026-05-30 更新**: §三 B4 待决项已由用户拍板定案 → 见 `decisions/ADR-0002-five-layer-disk-metric-naming.md`。
> 五层语义命名 total/normalized/provisioned/THRESHOLD/baseline_io_kib 已锁定;
> 本文 §三/§五"待决"段作废,以 ADR-0002 为准。下方 baseline 四语义判定(§一.3)仍有效。

---

## 一、三个词的归属判定(代码事实)

### 1. ebs = AWS 专属术语 → 通用磁盘逻辑应改 disk

**E1 铁证 — provider 抽象层已把 ebs 隔离为仅 AWS label:**
```
config/providers/aws_provider.sh:39   get_bottleneck_label() { echo "EBS"; }
config/providers/gcp_provider.sh:39   get_bottleneck_label() { echo "Disk"; }  # GCP 用通用语义
config/providers/other_provider.sh:37 get_bottleneck_label() { echo "Disk"; }
```

**结论**: 框架作者意图明确 —— AWS 磁盘 label = "EBS"(AWS 块存储产品名),GCP/Other = "Disk"(通用)。
核心代码里写死的 `ebs_util`/`ebs_latency`/`check_ebs_bottleneck` 等**通用磁盘逻辑**,
是框架早期 AWS-only 时代的命名残留(那时所有磁盘都是 EBS,拿 ebs 当通用磁盘词)。
框架已多云化,这些名**名不副实 → 改 disk**。

**E2 规模**: 核心代码 ebs 共 683 处 / 31 文件。

### 2. ena = AWS 专属网卡驱动 → 保留不改

**E1 铁证:**
```
config/providers/aws_provider.sh:31   get_nic_driver() { echo "ena"; }   # AWS Elastic Network Adapter
config/providers/gcp_provider.sh:32   get_nic_driver() { echo "gve"; }   # GCP gVNIC
config/providers/other_provider.sh:30 get_nic_driver() { echo "none"; }
config/providers/gcp_provider.sh:33   get_nic_allowance_fields() { echo ""; }  # GCP gVNIC 无 allowance 概念
```

**结论**: ena = AWS Elastic Network Adapter,是 AWS 专属硬件驱动名。
ena_* 限速计数器(bw_in_allowance_exceeded 等)是 AWS ENA 独有(GCP gVNIC 无此概念)。
**ena 全部保留,绝不改 disk/generic**。与 ebs 判定相反。

**E2 规模**: 核心代码 ena 共 664 处 / 20 文件 —— 全部保留。

### 3. baseline = 多语义词,绝不能全局替换(共 4 种独立语义)

**E1 逐语义铁证:**

| # | baseline 语义 | E1 证据 | 该怎么处理 |
|---|---|---|---|
| B1 | **利用率判定基准线**(用户澄清的原始语义) | internal_config.sh:26 `HIGH level: Uses above baseline thresholds (90%, 50ms)`;:27 `CRITICAL: Baseline threshold + 5%` | **保留** baseline 概念。注意:此语义变量名实为 `BOTTLENECK_DISK_*_THRESHOLD`,baseline 仅在注释里描述,非变量名 |
| B2 | **卷预配额定能力**(VOL_MAX 原始 iops/throughput,做分母算利用率) | bottleneck_detector `baseline_iops=${DATA_VOL_MAX_IOPS}` (git diff 已改) | **→ provisioned**(符合云厂商术语,中立)。我已改对 |
| B3 | **各云 IO size 换算基准**(block size) | aws_provider.sh:23 `get_baseline_io_kib(){echo "16"}`;gcp=4;other=0;system_config.sh:53 `AWS_EBS_BASELINE_IO_SIZE_KIB=16` | **保留** baseline(这是 IO 块大小基准,各云通用概念,不是 ebs 也不是 provisioned) |
| B4 | **GCP CSV 物理列名前缀** | gcp_provider.sh:37 `get_disk_field_prefix(){echo "baseline"}` | 见 §三 待决(与方案甲 standard 冲突) |
| B5 | **链模板/区块/测试基准**(完全无关磁盘) | normalize_chain_templates.py 28处 `baseline 7-key format`;config/chains/*.json `baseline_sha` | **绝不动**(blockchain 术语) |

**E2 规模**: 核心代码 baseline 共 196 处,其中 normalize_chain_templates.py(28)+chains json = B5 无关项,
真正涉及磁盘的是 B1/B2/B3/B4。

---

## 二、我之前改动的复核(git diff 实证)

**VERIFIED(E3 git diff)**:
- B2 卷额定能力 baseline_iops→provisioned_iops:**改对了**(bottleneck_detector.sh / device_manager 属性名 / chart 属性名)
- 字典键 `thresholds['data_baseline_iops']` 两端保留键名只改属性名:**不断链**(device_manager 生产 L317 + chart 消费 L67 键名都还是 data_baseline_iops)

**我之前的概念错误(已纠正)**:
- 旧 spec-A 把 baseline 误判为"卷额定上限的同义冲突词"。
- 真相:baseline 本义是 B1(判定基准线),历史上把 B2(卷额定能力)误命名成 baseline_iops 造成名不副实。
- 正确终态:B1 保留 baseline,B2 改 provisioned,B3 保留 baseline(IO size 基准),二者不冲突。

---

## 三、B4 已定案(2026-05-30 用户拍板,详见 ADR-0002)

> 🔴 **2026-05-31 核实更新**: 下方"冲突现状"快照(provider 层 gcp=baseline/aws=aws_standard)**已过时**。
> registry 层 + provider 层三处 get_disk_field_prefix 均已改为 `normalized`(2026-05-31 本会话落地,
> 见 EXEC-TRACKER 顶部修正)。B4 定案(normalized)正确且已执行,下方快照仅留作历史对照。

**冲突(E1+E2 实证):两套并存** 〔已解决:两套均已统一 normalized〕
- registry 层(旧方案甲): utils/csv_schema_registry.py L29-33 `DISK_FIELD_PREFIX={'aws':'standard','gcp':'standard','other':'standard'}`
- provider 层(更旧): gcp_provider.sh:37 `get_disk_field_prefix(){echo "baseline"}`;aws_provider.sh:37 `echo "aws_standard"`

**定案**: 层2(折算值)物理前缀三云统一 → **`normalized`**(非 standard、非 baseline、非 aws_standard)。
- 继承 ADR-0001"中立化"原则(物理名不编码云厂商,provider 由 cloud_provider 列承载)。
- 推翻 ADR-0001"用 standard 这个词"(太泛易误读),改 `normalized`(精确表达"折算到统一可比口径")。
- 否决 `provisioned`(与 AWS/GCP 官方术语冲突,provisioned 专指层3 配置上限,见 ADR-0002 层2 选词理由)。
- 三云全部对齐 normalized:registry + gcp_provider.sh:37(baseline→normalized)+ aws_provider.sh:37(aws_standard→normalized)。

---

## 四、改名清单(B4 决策后执行)

### 改(ebs→disk,通用磁盘逻辑)
- 变量/函数/JSON键: ebs_util→disk_util, ebs_latency→disk_latency, check_ebs_bottleneck→check_disk_bottleneck 等
- 已完成(本会话): config 配置变量 BOTTLENECK_EBS_*→DISK_* (64处);bottleneck_detector.sh 全量;跨文件JSON键(130处)
- 待做: report_generator.py(305) / performance_visualizer(60) / 各 chart / analysis / tools/ebs_*.sh
- 文件改名: ebs_converter.sh→disk_converter.sh, ebs_bottleneck_detector.sh→disk_bottleneck_detector.sh,
  ebs_analyzer.sh→disk_analyzer.sh, ebs_chart_generator.py→disk_chart_generator.py,
  cpu_ebs_correlation_analyzer.py→cpu_disk_correlation_analyzer.py(+全引用同步)

### 保留(真 AWS 专属)
- ena 全部(网卡驱动 + allowance 计数器 + aws_ena.sh + ena_field_accessor.py)
- aws_provider.sh 内 EBS label / get_doc_url ebs/ SSD ceil(256) 计量规则
- utils/ebs_converter.sh 内 AWS EBS 官方换算逻辑(文件改名 disk_converter 但内部 AWS 规则保留)
- B1 baseline 判定基准线概念 / B3 get_baseline_io_kib IO size 基准 / B5 链模板 baseline

### 已改对(不动)
- B2 卷额定能力 baseline_iops→provisioned_iops

---

## 五、决策已闭环(无待决项)

**B4 已定**(2026-05-30 用户拍板): 层2 物理前缀三云统一 `normalized`,详见 ADR-0002。
本框架五层语义命名全部锁定,无方向性待决项,可直接执行 §四 改名 + ADR-0002 交叉改名清单。
