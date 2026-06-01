"""CSV Schema Registry (Python 侧) — 全 CSV 字段定义的单一事实源 (SSOT).

设计依据: analysis-notes/CSV-SCHEMA-ABSTRACTION-proposal.md §3
仿 network 范本 (utils/network_field_registry.py) 的 1:1 bash/python 对称模式扩展到全 CSV.

核心职责:
1. 定义每个逻辑字段: {logical_name, semantic_type, segment, provider_aware, physical_name_template}
2. resolve(logical_name, provider, device) -> 物理列名 (reader 用这个, 不认裸物理字段名)
3. 守护三大不变量 (首列 timestamp / 段顺序 / expected_column_count)

provider_aware 字段: 逻辑指标经 provider 规则折算后落 CSV (ADR-0002: 三云物理名统一 normalized),
但逻辑名恒定 -> reader 只认逻辑名, 字段物理名怎么改都不断链 (根治 CP-1 方案乙妥协).

S0 范围: 仅 disk 段 (21 字段 × {data,accounts}) 接入. 其余段后续波次扩展.
bash 对称实现见 config/csv_schema_registry.sh — 二者字段集必须 1:1 (test_csv_registry_symmetry 守护).
"""
from __future__ import annotations
from typing import Dict, List, Optional, Iterable
from dataclasses import dataclass


# disk_field_prefix 取值 — 方案甲(中立命名): 三云统一为 "normalized" (ADR-0002).
# 设计理由 (CSV-SCHEMA-ABSTRACTION-proposal.md §4.5):
#   物理名表达"是什么"(归一化后的 provider-adjusted IOPS), 不表达"来自哪个云".
#   provider 信息由独立的 cloud_provider 列承载 (与配置一致), 不污染指标名 => 架构中立、零厂商烙印.
#   provider 参数仍保留 (resolve 签名不变), 作为将来某云若需特殊命名的挂点; 当前三云同名.
#   AWS/GCP 数值语义差异(I/O size 拆分换算 vs passthrough)已被 disk_converter provider 分流吸收,
#   落 CSV 时同为"该云调整后的逻辑 IOPS" => 同一逻辑指标, 用同一中性名, 语义一致.
DISK_FIELD_PREFIX = {
    "aws": "normalized",
    "gcp": "normalized",
    "other": "normalized",
}

VALID_SEMANTIC_TYPES = {
    "rate", "throughput", "iops", "latency", "queue", "utilization",
    "ratio", "io_size", "iops_provider_adjusted", "throughput_provider_adjusted",
    "timestamp", "gauge", "unknown",
}

VALID_SEGMENTS = {
    "basic", "device", "network", "ena", "overhead",
    "block", "qps", "cgroup", "meta",
}


@dataclass(frozen=True)
class FieldDef:
    """单个逻辑字段定义.

    logical_name: 稳定逻辑名 (reader 只认这个; provider_aware 字段不含云厂商前缀)
    semantic_type: 语义类型 (用于 group_by_semantic 按语义取列)
    segment: 所属 CSV 段
    provider_aware: True = 物理名随 cloud_provider 变
    physical_template: 物理名模板. {prefix}=逻辑设备前缀(data/accounts), {dfp}=disk_field_prefix(provider 相关)
    """
    logical_name: str
    semantic_type: str
    segment: str
    provider_aware: bool
    physical_template: str


# ── 段顺序 (= CSV 列顺序 SSOT, 实证来源 monitoring/unified_monitor.sh:1940/1942 generate_csv_header) ──
# device/ena/cgroup 为动态段 (运行时按设备数/ENA开关/cgroup可用性变长), 不在静态 FieldDef 列表里,
# 由各自的 *_header 生成函数产出; 静态段则用 FieldDef 录入. SEGMENT_ORDER 定义段之间的拼接次序.
SEGMENT_ORDER = ["basic", "device", "network", "ena", "overhead", "block", "qps", "cgroup", "meta"]

# 动态段 (长度运行时可变, 不用 FieldDef 静态枚举; 由 writer 的生成函数 + registry 的 segment header 接口产出)
DYNAMIC_SEGMENTS = {"device", "ena"}


# ── basic 段 10 字段 (静态, 无 provider 分流) ──────────────────────────
# 实证来源: monitoring/unified_monitor.sh:1927 generate_csv_header basic_header
# 全部物理名固定 (= 逻辑名), provider_aware=False, physical_template 即字面量.
_BASIC_FIELDS: List[FieldDef] = [
    FieldDef("timestamp",   "timestamp",   "basic", False, "timestamp"),
    FieldDef("cpu_usage",   "gauge",       "basic", False, "cpu_usage"),
    FieldDef("cpu_usr",     "gauge",       "basic", False, "cpu_usr"),
    FieldDef("cpu_sys",     "gauge",       "basic", False, "cpu_sys"),
    FieldDef("cpu_iowait",  "gauge",       "basic", False, "cpu_iowait"),
    FieldDef("cpu_soft",    "gauge",       "basic", False, "cpu_soft"),
    FieldDef("cpu_idle",    "gauge",       "basic", False, "cpu_idle"),
    FieldDef("mem_used",    "gauge",       "basic", False, "mem_used"),
    FieldDef("mem_total",   "gauge",       "basic", False, "mem_total"),
    FieldDef("mem_usage",   "gauge",       "basic", False, "mem_usage"),
]


# ── disk 段 21 字段 (S0 接入) ──────────────────────────────────────────
# 实证来源: monitoring/iostat_collector.sh:144 generate_device_header
# 21 字段中仅 2 个 provider_aware (normalized_iops / normalized_throughput_mibs),
# 其余 19 个物理名固定 (不随云变).
_DISK_FIELDS: List[FieldDef] = [
    FieldDef("disk_r_s",                       "rate",        "device", False, "{prefix}_r_s"),
    FieldDef("disk_w_s",                       "rate",        "device", False, "{prefix}_w_s"),
    FieldDef("disk_rkb_s",                     "throughput",  "device", False, "{prefix}_rkb_s"),
    FieldDef("disk_wkb_s",                     "throughput",  "device", False, "{prefix}_wkb_s"),
    FieldDef("disk_r_await",                   "latency",     "device", False, "{prefix}_r_await"),
    FieldDef("disk_w_await",                   "latency",     "device", False, "{prefix}_w_await"),
    FieldDef("disk_avg_await",                 "latency",     "device", False, "{prefix}_avg_await"),
    FieldDef("disk_aqu_sz",                    "queue",       "device", False, "{prefix}_aqu_sz"),
    FieldDef("disk_util",                      "utilization", "device", False, "{prefix}_util"),
    FieldDef("disk_rrqm_s",                    "rate",        "device", False, "{prefix}_rrqm_s"),
    FieldDef("disk_wrqm_s",                    "rate",        "device", False, "{prefix}_wrqm_s"),
    FieldDef("disk_rrqm_pct",                  "ratio",       "device", False, "{prefix}_rrqm_pct"),
    FieldDef("disk_wrqm_pct",                  "ratio",       "device", False, "{prefix}_wrqm_pct"),
    FieldDef("disk_rareq_sz",                  "io_size",     "device", False, "{prefix}_rareq_sz"),
    FieldDef("disk_wareq_sz",                  "io_size",     "device", False, "{prefix}_wareq_sz"),
    FieldDef("disk_total_iops",                "iops",        "device", False, "{prefix}_total_iops"),
    FieldDef("disk_iops_provider_adjusted",    "iops_provider_adjusted",       "device", True,  "{prefix}_{dfp}_iops"),
    FieldDef("disk_read_throughput_mibs",      "throughput",  "device", False, "{prefix}_read_throughput_mibs"),
    FieldDef("disk_write_throughput_mibs",     "throughput",  "device", False, "{prefix}_write_throughput_mibs"),
    FieldDef("disk_total_throughput_mibs",     "throughput",  "device", False, "{prefix}_total_throughput_mibs"),
    FieldDef("disk_throughput_provider_adjusted", "throughput_provider_adjusted", "device", True, "{prefix}_{dfp}_throughput_mibs"),
]


# ── network 段 10 字段 (静态, 通用网卡指标, 无 provider 分流) ────────────
# 实证来源: monitoring/unified_monitor.sh:1938 generate_csv_header network_header
# 全部物理名固定 (= 逻辑名). 注: 这是 unified CSV 的通用 net 段, 与 ENA/gvnic 平台专属段无关
# (后者是动态段 ena/独立 Y+ 架构 CSV).
_NETWORK_FIELDS: List[FieldDef] = [
    FieldDef("net_interface",    "gauge",      "network", False, "net_interface"),
    FieldDef("net_rx_mbps",      "throughput", "network", False, "net_rx_mbps"),
    FieldDef("net_tx_mbps",      "throughput", "network", False, "net_tx_mbps"),
    FieldDef("net_total_mbps",   "throughput", "network", False, "net_total_mbps"),
    FieldDef("net_rx_gbps",      "throughput", "network", False, "net_rx_gbps"),
    FieldDef("net_tx_gbps",      "throughput", "network", False, "net_tx_gbps"),
    FieldDef("net_total_gbps",   "throughput", "network", False, "net_total_gbps"),
    FieldDef("net_rx_pps",       "rate",       "network", False, "net_rx_pps"),
    FieldDef("net_tx_pps",       "rate",       "network", False, "net_tx_pps"),
    FieldDef("net_total_pps",    "rate",       "network", False, "net_total_pps"),
]


# ── overhead 段 2 字段 (监控自身开销, 静态) ───────────────────────────
# 实证来源: monitoring/unified_monitor.sh:1939 overhead_header
_OVERHEAD_FIELDS: List[FieldDef] = [
    FieldDef("monitoring_iops_per_sec",            "iops",       "overhead", False, "monitoring_iops_per_sec"),
    FieldDef("monitoring_throughput_mibs_per_sec", "throughput", "overhead", False, "monitoring_throughput_mibs_per_sec"),
]


# ── block 段 6 字段 (区块高度监控, 静态) ──────────────────────────────
# 实证来源: monitoring/unified_monitor.sh:1940 block_height_header
_BLOCK_FIELDS: List[FieldDef] = [
    FieldDef("local_block_height",   "gauge", "block", False, "local_block_height"),
    FieldDef("mainnet_block_height", "gauge", "block", False, "mainnet_block_height"),
    FieldDef("block_height_diff",    "gauge", "block", False, "block_height_diff"),
    FieldDef("local_health",         "gauge", "block", False, "local_health"),
    FieldDef("mainnet_health",       "gauge", "block", False, "mainnet_health"),
    FieldDef("data_loss",            "gauge", "block", False, "data_loss"),
]


# ── qps 段 3 字段 (QPS 测试指标, 静态) ────────────────────────────────
# 实证来源: monitoring/unified_monitor.sh:1941 qps_header
_QPS_FIELDS: List[FieldDef] = [
    FieldDef("current_qps",        "gauge", "qps", False, "current_qps"),
    FieldDef("rpc_latency_ms",     "latency", "qps", False, "rpc_latency_ms"),
    FieldDef("qps_data_available", "gauge", "qps", False, "qps_data_available"),
]


class CSVSchemaRegistry:
    """全 CSV schema 单一事实源. reader/writer 都向它要字段信息, 不各自硬编码."""

    # 全静态字段 (按 CSV 段顺序拼接; 动态段 device/ena 不在此, 由生成函数产出)
    _ALL_STATIC_FIELDS: List[FieldDef] = (
        _BASIC_FIELDS + _DISK_FIELDS + _NETWORK_FIELDS
        + _OVERHEAD_FIELDS + _BLOCK_FIELDS + _QPS_FIELDS
    )
    _FIELDS_BY_LOGICAL: Dict[str, FieldDef] = {f.logical_name: f for f in _ALL_STATIC_FIELDS}

    @classmethod
    def all_logical_names(cls) -> List[str]:
        return list(cls._FIELDS_BY_LOGICAL.keys())

    @classmethod
    def segment_logical_names(cls, segment: str) -> List[str]:
        """返回某静态段的逻辑名 (顺序 = FieldDef 录入序 = CSV 列序).

        动态段 (device/ena) 无静态 FieldDef, 返回 []; 调用方应改用 writer 的生成函数.
        """
        return [f.logical_name for f in cls._ALL_STATIC_FIELDS if f.segment == segment]

    @classmethod
    def segment_header(cls, segment: str, provider: str = "other",
                       device_prefix: str = "") -> str:
        """生成某静态段的 CSV header (逗号分隔物理列名).

        provider/device_prefix 仅对 provider_aware 字段有意义 (basic 等静态段忽略).
        动态段返回空串.
        """
        names = cls.segment_logical_names(segment)
        return ",".join(cls.resolve(ln, provider, device_prefix) for ln in names)

    @classmethod
    def get_field(cls, logical_name: str) -> Optional[FieldDef]:
        return cls._FIELDS_BY_LOGICAL.get(logical_name)

    @classmethod
    def get_semantic_type(cls, logical_name: str) -> str:
        f = cls._FIELDS_BY_LOGICAL.get(logical_name)
        return f.semantic_type if f else "unknown"

    @classmethod
    def resolve(cls, logical_name: str, provider: str, device_prefix: str) -> str:
        """逻辑名 -> 物理列名.

        device_prefix: 逻辑设备前缀, 'data' 或 'accounts' (含运行时设备名时调用方先拼好,
                       或传 'data_nvme1n1' 这类完整前缀均可 — 模板只做字符串替换).
        provider:      'aws'|'gcp'|'other', 决定 provider_aware 字段的 disk_field_prefix.

        Raises: KeyError 若 logical_name 未注册 (硬失败, 不静默 — 防 reader 用错逻辑名静默拿空).
        """
        f = cls._FIELDS_BY_LOGICAL.get(logical_name)
        if f is None:
            raise KeyError(
                f"unknown logical field: {logical_name!r} "
                f"(registered: {sorted(cls._FIELDS_BY_LOGICAL)})"
            )
        dfp = DISK_FIELD_PREFIX.get(provider, "normalized")
        return f.physical_template.format(prefix=device_prefix, dfp=dfp)

    @classmethod
    def group_by_semantic(cls, logical_names: Iterable[str]) -> Dict[str, List[str]]:
        groups: Dict[str, List[str]] = {}
        for ln in logical_names:
            groups.setdefault(cls.get_semantic_type(ln), []).append(ln)
        return groups

    @classmethod
    def provider_aware_fields(cls) -> List[str]:
        """返回所有 provider_aware 逻辑名 (物理名随云变的字段)."""
        return [f.logical_name for f in cls._FIELDS_BY_LOGICAL.values() if f.provider_aware]
