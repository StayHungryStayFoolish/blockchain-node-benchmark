# 区块链测试特性

## 概述

框架提供灵活的区块链测试能力，支持多个区块链节点和两种不同的RPC测试模式：**单一**和**混合**。这种设计既支持专注的性能分析，也支持真实的工作负载模拟。

## RPC测试模式

### 模式对比

| 特性 | 单一模式 | 混合模式 |
|------|---------|---------|
| **RPC方法** | 一个方法 | 多个方法 |
| **测试重点** | 特定操作 | 真实工作负载 |
| **执行速度** | 更快 | 较慢 |
| **使用场景** | 性能分析 | 生产模拟 |
| **复杂度** | 简单 | 复杂 |
| **结果** | 专注指标 | 全面概况 |

### 单一模式

**目的：** 重复测试一个RPC方法以测量其特定性能特征。

**配置：**
```bash
# 在user_config.sh或环境变量中
RPC_MODE="single"
```

**行为：**
- 使用单个RPC方法生成负载
- 所有请求使用相同方法
- 测量方法特定性能
- 更快的测试执行
- 更清晰的瓶颈识别

**示例测试流程：**
```
QPS 1000: getBlockHeight × 1000 请求/秒
QPS 2000: getBlockHeight × 2000 请求/秒
QPS 3000: getBlockHeight × 3000 请求/秒
...
```

**使用场景：**
- 特定RPC方法的性能分析
- 识别方法特定瓶颈
- 比较不同方法的性能
- 快速性能验证

**优势：**
- ✅ 清晰的性能归因
- ✅ 更快的测试执行
- ✅ 更容易的结果解释
- ✅ 专注的优化指导

**限制：**
- ❌ 不代表生产工作负载
- ❌ 可能错过方法间的交互效应
- ❌ 单点故障测试

### 混合模式

**目的：** 同时测试多个RPC方法以模拟真实的生产工作负载。

**配置：**
```bash
# 在user_config.sh或环境变量中
RPC_MODE="mixed"
```

**行为：**
- 使用多个RPC方法生成负载
- 请求分布在各方法间
- 模拟真实世界使用模式
- 全面的性能概况
- 识别交互效应

**示例测试流程：**
```
QPS 1000: 
  - getBlockHeight × 400 请求/秒 (40%)
  - getBalance × 300 请求/秒 (30%)
  - getTransaction × 200 请求/秒 (20%)
  - sendTransaction × 100 请求/秒 (10%)

QPS 2000:
  - getBlockHeight × 800 请求/秒 (40%)
  - getBalance × 600 请求/秒 (30%)
  - ...
```

**使用场景：**
- 生产环境模拟
- 全面性能测试
- 识别交互瓶颈
- 容量规划
- SLA验证

**优势：**
- ✅ 真实工作负载模拟
- ✅ 识别交互效应
- ✅ 更好的生产预测
- ✅ 全面的性能概况

**限制：**
- ❌ 较慢的测试执行
- ❌ 更复杂的结果解释
- ❌ 更难隔离特定问题

## 区块链节点支持

### 支持的区块链

框架设计为支持多个区块链节点，配置最少：

```bash
# Solana（默认）
BLOCKCHAIN_NODE="solana"

# Ethereum
BLOCKCHAIN_NODE="ethereum"

# 其他区块链（可扩展）
BLOCKCHAIN_NODE="polygon"
BLOCKCHAIN_NODE="avalanche"
```

### 区块链配置

#### 1. 节点类型配置

```bash
# 在user_config.sh中
BLOCKCHAIN_NODE="solana"  # 自动转换为小写
```

**支持的值：**
- `solana` - Solana区块链
- `ethereum` - Ethereum区块链
- 自定义区块链名称（需要RPC方法配置）

#### 2. 进程名称配置

```bash
# 在user_config.sh中
BLOCKCHAIN_PROCESS_NAMES=(
    "blockchain"
    "validator"
    "node.service"
)
```

**目的：**
- 识别区块链进程进行监控
- 计算区块链特定资源使用
- 分离区块链和监控开销

**自定义：**
```bash
# 对于Ethereum
BLOCKCHAIN_PROCESS_NAMES=(
    "geth"
    "ethereum"
)

# 对于自定义区块链
BLOCKCHAIN_PROCESS_NAMES=(
    "custom-node"
    "custom-validator"
)
```

#### 3. RPC端点配置

```bash
# 在user_config.sh中
LOCAL_RPC_URL="http://localhost:8899"  # Solana默认

# 对于Ethereum
LOCAL_RPC_URL="http://localhost:8545"

# 对于自定义区块链
LOCAL_RPC_URL="http://localhost:PORT"
```

## RPC方法配置

### 配置结构

RPC方法在 `config/config_loader.sh` 的 `UNIFIED_BLOCKCHAIN_CONFIG` 变量中定义：

```json
{
  "solana": {
    "rpc_methods": {
      "single": "getBlockHeight",
      "mixed": "getBlockHeight,getBalance,getTransaction,getAccountInfo"
    },
    "method_weights": {
      "getBlockHeight": 0.4,
      "getBalance": 0.3,
      "getTransaction": 0.2,
      "getAccountInfo": 0.1
    }
  },
  "ethereum": {
    "rpc_methods": {
      "single": "eth_blockNumber",
      "mixed": "eth_blockNumber,eth_getBalance,eth_getTransactionByHash"
    },
    "method_weights": {
      "eth_blockNumber": 0.5,
      "eth_getBalance": 0.3,
      "eth_getTransactionByHash": 0.2
    }
  }
}
```

### 方法权重

**目的：** 定义混合模式下请求在方法间的分布。

**示例：**
```json
"method_weights": {
  "getBlockHeight": 0.4,    // 40%的请求
  "getBalance": 0.3,        // 30%的请求
  "getTransaction": 0.2,    // 20%的请求
  "getAccountInfo": 0.1     // 10%的请求
}
```

**计算：**
```bash
# 在QPS 1000时
getBlockHeight: 1000 × 0.4 = 400 请求/秒
getBalance: 1000 × 0.3 = 300 请求/秒
getTransaction: 1000 × 0.2 = 200 请求/秒
getAccountInfo: 1000 × 0.1 = 100 请求/秒
```

### 添加新区块链支持

#### 步骤1：添加RPC方法配置

编辑 `config/config_loader.sh` 并添加到 `UNIFIED_BLOCKCHAIN_CONFIG`：

```json
{
  "your_blockchain": {
    "rpc_methods": {
      "single": "your_single_method",
      "mixed": "method1,method2,method3"
    },
    "method_weights": {
      "method1": 0.5,
      "method2": 0.3,
      "method3": 0.2
    }
  }
}
```

#### 步骤2：配置节点设置

在 `user_config.sh` 中：

```bash
BLOCKCHAIN_NODE="your_blockchain"
LOCAL_RPC_URL="http://localhost:YOUR_PORT"
BLOCKCHAIN_PROCESS_NAMES=(
    "your-node-process"
    "your-validator-process"
)
```

#### 步骤3：测试配置

```bash
# 验证配置
./blockchain_node_benchmark.sh --help

# 运行快速测试
./blockchain_node_benchmark.sh --quick
```

**就这样！** 框架自动：
- 加载RPC方法配置
- 生成适当的测试目标
- 监控区块链进程
- 分析性能指标

## 测试目标生成

### 目标生成器

`tools/target_generator.sh` 脚本基于以下内容生成Vegeta测试目标：
- 区块链节点类型
- RPC模式（单一/混合）
- 方法权重（混合模式）
- 账户数据（如果可用）

### 单一模式目标生成

```bash
# 为单一模式生成目标
./tools/target_generator.sh --mode single --method getBlockHeight

# 输出：targets_single.txt
POST http://localhost:8899
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"getBlockHeight"}

POST http://localhost:8899
Content-Type: application/json

{"jsonrpc":"2.0","id":2,"method":"getBlockHeight"}
...
```

### 混合模式目标生成

```bash
# 为混合模式生成目标
./tools/target_generator.sh --mode mixed

# 输出：targets_mixed.txt（按权重分布）
POST http://localhost:8899
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"getBlockHeight"}

POST http://localhost:8899
Content-Type: application/json

{"jsonrpc":"2.0","id":2,"method":"getBalance","params":["ADDRESS"]}

POST http://localhost:8899
Content-Type: application/json

{"jsonrpc":"2.0","id":3,"method":"getTransaction","params":["TX_HASH"]}
...
```

**分布：**
- 40% getBlockHeight
- 30% getBalance
- 20% getTransaction
- 10% getAccountInfo

## 最佳实践

### 选择正确的模式

**使用单一模式当：**
- ✅ 分析特定RPC方法性能
- ✅ 比较不同方法
- ✅ 调试方法特定问题
- ✅ 快速性能验证
- ✅ 优化特定操作

**使用混合模式当：**
- ✅ 模拟生产工作负载
- ✅ 容量规划
- ✅ SLA验证
- ✅ 识别交互瓶颈
- ✅ 全面性能测试

### 测试策略

**推荐方法：**

1. **从单一模式开始：**
   ```bash
   # 单独测试每个关键方法
   RPC_MODE="single" ./blockchain_node_benchmark.sh --quick
   ```

2. **识别弱方法：**
   - 分析单一模式结果
   - 识别高延迟或低吞吐量的方法
   - 优化弱方法

3. **使用混合模式测试：**
   ```bash
   # 测试真实工作负载
   RPC_MODE="mixed" ./blockchain_node_benchmark.sh --standard
   ```

4. **验证生产就绪性：**
   ```bash
   # 混合模式密集测试
   RPC_MODE="mixed" ./blockchain_node_benchmark.sh --intensive
   ```

### 方法权重调优

**分析生产流量：**
```bash
# 示例：分析生产日志
grep "RPC method" production.log | \
  awk '{print $5}' | \
  sort | uniq -c | \
  awk '{print $2": "$1}'

# 输出：
# getBlockHeight: 4000
# getBalance: 3000
# getTransaction: 2000
# getAccountInfo: 1000
```

**计算权重：**
```bash
# 总计：10000请求
# getBlockHeight: 4000/10000 = 0.4
# getBalance: 3000/10000 = 0.3
# getTransaction: 2000/10000 = 0.2
# getAccountInfo: 1000/10000 = 0.1
```

**更新配置：**
```json
"method_weights": {
  "getBlockHeight": 0.4,
  "getBalance": 0.3,
  "getTransaction": 0.2,
  "getAccountInfo": 0.1
}
```

## 故障排除

### 常见问题

#### 1. "RPC method not found"

**原因：** 方法未在 `config/config_loader.sh` 中定义

**解决方案：**
```bash
# 检查配置
grep -A 20 "\"${BLOCKCHAIN_NODE}\":" config/config_loader.sh | grep -A 5 "rpc_methods"

# 添加缺失的方法
vim config/config_loader.sh
```

#### 2. "Invalid method weights"

**原因：** 权重总和不等于1.0

**解决方案：**
```bash
# 验证权重
grep -A 10 "method_weights" config/config_loader.sh

# 应总和为 1.0
```

#### 3. "Target generation failed"

**原因：** 缺少账户数据或配置无效

**解决方案：**
```bash
# 检查账户文件
ls -lh accounts.txt

# 重新生成目标
./tools/target_generator.sh --force-regenerate
```

## 总结

框架的区块链测试特性提供：

✅ **灵活性：** 单一和混合RPC模式  
✅ **真实性：** 生产工作负载模拟  
✅ **可扩展性：** 轻松添加区块链  
✅ **准确性：** 加权方法分布  
✅ **简单性：** 最少配置要求  
✅ **强大：** 全面性能分析

**关键能力：**
- 多区块链支持
- 双测试模式（单一/混合）
- 可配置方法权重
- 动态目标生成
- 自动进程监控
- 全面性能分析

更多详情：
- [配置指南](./configuration-guide-zh.md)
- [架构概览](./architecture-overview-zh.md)
- [监控机制](./monitoring-mechanism-zh.md)
