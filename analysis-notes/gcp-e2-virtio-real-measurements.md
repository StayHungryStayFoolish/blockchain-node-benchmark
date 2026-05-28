# GCP e2-standard-4 真机实测数据 (2026-05-28)

**测试目标**: 验证 CORRECTED_PLAN §CP-2.5 设计中对 `gcp_virtio` variant 的字段假设是否准确, 为 CP-1~CP-2.5 实施提供真实数据样本。

**测试环境**:
- Project: `claude-ttft-test`
- Instance: `instance-20260429-041108` @ `us-central1-f`
- Machine type: `e2-standard-4` (Intel/AMD 自动选, 4 vCPU / 16 GB)
- OS: Debian 6.1.0-47-cloud-amd64
- Disks: 3 块 PERSISTENT (50G boot pd-balanced + 500G pd-ssd + 100G pd-ssd)
- NIC: ens4 (单网卡, 4 RX queue + 4 TX queue, 对应 4 vCPU)

---

## Q1: NIC driver 实测

### Q1a: 驱动识别

```bash
$ sudo ethtool -i ens4
driver: virtio_net
version: 1.0.0
firmware-version:
expansion-rom-version:
bus-info: 0000:00:04.0
supports-statistics: yes
supports-test: no
```

**结论**:
- e2-standard-4 driver = `virtio_net` ← 印证 CORRECTED_PLAN L3152 对 e2 系列的 gcp_virtio 定位
- `detect_nic_driver()` 实测命中 "virtio" 分支, `CLOUD_PROVIDER_VARIANT="gcp_virtio"` 派发正确
- e2 是 GCP **唯一 only VirtIO-Net** 在售机型族 (官方 cloud.google.com/compute/docs/networking/using-gvnic 矩阵, 2026 年仍 GA 无 deprecation 公告)

### Q1b: virtio_net counter 字段集 (57 行全量)

```bash
$ sudo ethtool -S ens4 | head -60
NIC statistics:
     rx_queue_0_packets: 811737
     rx_queue_0_bytes: 3419737586
     rx_queue_0_drops: 0
     rx_queue_0_xdp_packets: 0
     rx_queue_0_xdp_tx: 0
     rx_queue_0_xdp_redirects: 0
     rx_queue_0_xdp_drops: 0
     rx_queue_0_kicks: 25
     rx_queue_1_packets: 498649
     ... (rx_queue_1 ~ rx_queue_3 同字段)
     tx_queue_0_packets: 475268
     tx_queue_0_bytes: 283000460
     tx_queue_0_xdp_tx: 0
     tx_queue_0_xdp_tx_drops: 0
     tx_queue_0_kicks: 8
     tx_queue_0_tx_timeouts: 0
     tx_queue_1_packets: 524417
     ... (tx_queue_1 ~ tx_queue_3 同字段)
```

### Q1c: 字段命名规则 (与 CORRECTED_PLAN L3416 不一致, 需校正)

| CORRECTED_PLAN L3416 写法 | 实测真实字段 | 修正方向 |
|---|---|---|
| `virtio_rx_drops` | `rx_queue_{N}_drops` (per-queue) | 采集层必须 sum across N queues 输出 `virtio_rx_drops_sum` |
| `virtio_tx_tx_timeouts` | `tx_queue_{N}_tx_timeouts` (per-queue) | 同上, sum 后输出 `virtio_tx_timeouts_sum` |
| `virtio_per_queue_rx_drops_sum` | 需自行 awk 聚合 | 实现路径已确定 |

**virtio_net per-queue 字段全集** (RX + TX 两类):

RX (每 queue 8 字段):
- `rx_queue_{N}_packets` — packet count
- `rx_queue_{N}_bytes` — throughput byte
- `rx_queue_{N}_drops` — drop counter (饱和信号源)
- `rx_queue_{N}_xdp_packets` / `xdp_tx` / `xdp_redirects` / `xdp_drops` — XDP 路径 (通常 0)
- `rx_queue_{N}_kicks` — virtio kick 次数 (debugging)

TX (每 queue 6 字段):
- `tx_queue_{N}_packets` — packet count
- `tx_queue_{N}_bytes` — throughput byte
- `tx_queue_{N}_xdp_tx` / `xdp_tx_drops` — XDP 路径
- `tx_queue_{N}_kicks` — virtio kick 次数
- `tx_queue_{N}_tx_timeouts` — TX timeout (网络栈卡顿信号)

**没有顶层全局聚合字段**: 与 AWS ENA 直接暴露 `bw_in_allowance_exceeded` 等顶层字段不同, virtio_net 全部走 per-queue, 采集层必须自行 sum。

### Q1d: queue 数 = vCPU 数 (动态发现)

```bash
$ ls /sys/class/net/ens4/queues/  # 实测 4 个 RX + 4 个 TX (e2-standard-4 是 4 vCPU)
rx-0  rx-1  rx-2  rx-3  tx-0  tx-1  tx-2  tx-3
```

**实现含义**: `monitoring/network/gcp_virtio.sh` 不能硬编码 queue 数, 必须 `ls /sys/class/net/$IFACE/queues/ | grep ^rx- | wc -l` 动态发现。

### Q1e: gcp_virtio CSV header 字段集 (校正后)

```bash
# generate_network_csv_header() for gcp_virtio
generate_network_csv_header() {
    echo "timestamp,interface,rx_bytes,tx_bytes,rx_packets,tx_packets,\
virtio_rx_drops_sum,virtio_tx_timeouts_sum,virtio_xdp_drops_sum,virtio_xdp_tx_drops_sum,\
virtio_rx_kicks_sum,virtio_tx_kicks_sum,network_saturation_signal"
}

# saturation_signal 判定: virtio_rx_drops_sum > 0 OR virtio_tx_timeouts_sum > 0
# (virtio 没有 AWS ENA 那种显式 allowance_exceeded counter, 用 drops/timeouts 间接判定)
```

---

## Q2: 磁盘设备名 + 配置

### Q2a: lsblk + by-id 软链

```
$ lsblk -o NAME,SIZE,TYPE,MOUNTPOINT
NAME     SIZE TYPE MOUNTPOINT
sda       50G disk
├─sda1  49.9G part /
├─sda14    3M part
└─sda15  124M part /boot/efi
sdb      500G disk /mnt/disk500g
sdc      100G disk /mnt/disk100g

$ ls -l /dev/disk/by-id/google-*
google-disk-100g          -> sdc
google-disk-500g          -> sdb
google-persistent-disk-0  -> sda    # boot disk 命名特例
google-persistent-disk-0-part1   -> sda1
google-persistent-disk-0-part14  -> sda14
google-persistent-disk-0-part15  -> sda15
```

**设备名规则** (跨 AWS / GCP 对照):

| 维度 | AWS NVMe | GCP PD |
|---|---|---|
| 稳定标识 | `/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_vol-XXXX` | `/dev/disk/by-id/google-{deviceName}` |
| 设备节点 | `/dev/nvme{N}n1` (顺序不稳定) | `/dev/sd{a,b,c,...}` (顺序按挂载序) |
| boot disk 命名 | `/dev/nvme0n1` | `/dev/disk/by-id/google-persistent-disk-0` (硬编码 deviceName) |
| 非 boot disk 命名 | `/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_vol-XXXX` | `/dev/disk/by-id/google-{用户定义 deviceName}` (创建时指定) |

### Q2b: cloud_provider getter `get_data_device()` 实现指引

```bash
get_data_device() {
    # 用户 framework 一般通过 DATA_VOL_TYPE 配置选择数据盘 (如 500G ssd 跑链)
    # GCP 实现: 根据用户配置的 deviceName 反查 by-id 软链
    # AWS 实现: 根据 volume-id 反查 by-id 软链
    case "$PLATFORM" in
        gcp)
            local devname="${GCP_DATA_DEVICE_NAME:-disk-500g}"  # user_config
            readlink -f "/dev/disk/by-id/google-${devname}"  # → /dev/sdb
            ;;
        aws)
            local volid="${AWS_DATA_VOLUME_ID}"
            readlink -f "/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${volid}"
            ;;
    esac
}
```

---

## Q3: metadata API (替代 gcloud describe, 无需额外权限)

### Q3a: machine-type

```bash
$ curl -sf -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/machine-type
projects/531966061769/machineTypes/e2-standard-4
```

→ 后处理 `awk -F/ '{print $NF}'` 拿 `e2-standard-4`

### Q3b: 全部磁盘列表 + 类型

```bash
$ curl -sf -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/disks/0/?recursive=true
{"deviceName":"persistent-disk-0","index":0,"interface":"SCSI","mode":"READ_WRITE","type":"PERSISTENT-BALANCED"}

$ curl -sf ... /instance/disks/1/?recursive=true
{"deviceName":"disk-500g","index":1,"interface":"SCSI","mode":"READ_WRITE","type":"PERSISTENT-SSD"}

$ curl -sf ... /instance/disks/2/?recursive=true
{"deviceName":"disk-100g","index":2,"interface":"SCSI","mode":"READ_WRITE","type":"PERSISTENT-SSD"}
```

### Q3c: metadata `type` → CORRECTED_PLAN disk_type 映射表

| metadata `type` 值 | CORRECTED_PLAN disk_type | AWS 对应 |
|---|---|---|
| `PERSISTENT-STANDARD` | `pd-standard` | st1/sc1 |
| `PERSISTENT-BALANCED` | `pd-balanced` | gp3 (类似定位) |
| `PERSISTENT-SSD` | `pd-ssd` | gp3 / io2 |
| `PERSISTENT-EXTREME` | `pd-extreme` | io2 (高 IOPS) |
| `PERSISTENT-HYPERDISK-*` | `hyperdisk-extreme` / `hyperdisk-balanced` / `hyperdisk-throughput` | io2 (extreme) / gp3 (balanced/throughput) |
| `SCRATCH` | `local-ssd` | instance store |

**关键**: GCP metadata API **无需 IAM 权限**, 任何在 GCE 内的 process 都能查 (区别于 `gcloud compute disks describe` 需要 SA 有 compute.disks.get 权限)。所以 `utils/cloud_provider.py` 的 `get_disk_type()` 实现首选走 metadata API。

### Q3d: 关键 metadata endpoint 速查表

| 数据 | endpoint |
|---|---|
| 机型 | `/computeMetadata/v1/instance/machine-type` |
| project ID | `/computeMetadata/v1/project/project-id` |
| zone | `/computeMetadata/v1/instance/zone` |
| 所有磁盘 (递归) | `/computeMetadata/v1/instance/disks/?recursive=true&alt=json` |
| 单盘 | `/computeMetadata/v1/instance/disks/{i}/?recursive=true` |
| 所有 NIC (递归) | `/computeMetadata/v1/instance/network-interfaces/?recursive=true&alt=json` |
| NIC nicType (gVNIC/VirtIO) | `/computeMetadata/v1/instance/network-interfaces/0/nic-type` (实测 e2 此字段为空, 默认 VIRTIO_NET) |

---

## Q4: iostat 字段 (跨平台一致, 无需 provider 分支)

```
Device  r/s  rkB/s  rrqm/s  %rrqm  r_await  rareq-sz  w/s  wkB/s  wrqm/s  %wrqm  w_await  wareq-sz  d/s  dkB/s  drqm/s  %drqm  d_await  dareq-sz  f/s  f_await  aqu-sz  %util
sda     0.39 23.70  0.05    10.61  0.84     61.37     4.74 78.27  1.68    26.16  3.23     16.53     0.04 172.73 0.00    0.00   0.49     4117.49  1.50 0.08     0.02    0.17
sdb     0.00 0.01   0.00    0.00   30.11    8.41      0.00 0.00   0.00    16.67  4.60     4.80      0.01 1028.36 0.00   0.00   0.54     128992.25 0.00 0.00    0.00    0.00
sdc     0.00 0.01   0.00    0.00   5.22     14.74     0.00 0.00   0.00    16.67  4.20     4.80      0.00 204.95  0.00   0.00   0.56     128927.40 0.00 0.00    0.00    0.00
```

**结论**: iostat 字段格式 100% 来自 Linux util-linux, 与云厂商无关。`monitoring/iostat_collector.sh` 不需要 GCP/AWS 分支, 当前 AWS 硬编码字段名实测**完全可以直接复用**(只需把变量名从 `EBS_*` 改为通用 `DISK_*` 或保留 EBS 别名)。

---

## CP-2.5 实施直接产出 (来自本次实测)

1. **`config/cloud_provider.sh::detect_nic_driver`** 实测产出 `virtio` 分支 → `CLOUD_PROVIDER_VARIANT=gcp_virtio` ✅
2. **`monitoring/network/gcp_virtio.sh`** 字段集**校正**:
   - 实现 per-queue 聚合 (sum across `rx_queue_{0..N-1}_drops` 等)
   - 输出 6 个 sum 字段而非 CORRECTED_PLAN L3416 中的 3 个单字段
3. **`utils/cloud_provider.py::get_disk_type`** 实现路径:metadata API `/instance/disks/{i}/?recursive=true` 取 `type`, 用 Q3c 映射表
4. **`config/cloud_provider.sh::get_data_device`** 实现路径:`readlink -f /dev/disk/by-id/google-${deviceName}`, deviceName 来自 metadata 或 user_config
5. **`monitoring/iostat_collector.sh`** 无需修改云厂商分支 (但需去 EBS 硬编码命名)

---

## 与 CORRECTED_PLAN 的需校正点(总览)

| CORRECTED_PLAN 位置 | 原文 | 实测校正 |
|---|---|---|
| L3098 `generate_network_csv_header GCP` | `gvnic_tx_drops,gvnic_rx_no_buffer,gvnic_tx_timeout` | 仅适用于 gcp_gvnic; gcp_virtio 需另起字段集 (Q1e) |
| L3416 字段示例 | `virtio_rx_drops, virtio_tx_tx_timeouts, virtio_per_queue_rx_drops_sum` | 命名 OK, 但实现路径是**采集层 sum across queue**, 不是 ethtool 直出 |
| (新增) 队列数 | 文档未提 | 实测 = vCPU 数, 动态发现, 不可硬编码 |
| (新增) metadata API 调用 | 文档未提 | 实测无需 IAM, 是 disk_type getter 的最优实现 |

---

## 测试可复现性

任何时候要重测 (instance 永远不删, 见 USER profile):
```bash
gcloud compute ssh instance-20260429-041108 \
    --project=claude-ttft-test \
    --zone=us-central1-f \
    --tunnel-through-iap \
    --command='<上述 4 节 Q1~Q4 命令>'
```

实测时间: 2026-05-28, 数据采集耗时约 60 秒 (含 IAP tunnel 建连)。
