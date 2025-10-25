# Blockchain Testing Features

## Overview

The framework provides flexible blockchain testing capabilities with support for multiple blockchain nodes and two distinct RPC testing modes: **Single** and **Mixed**. This design enables both focused performance analysis and realistic workload simulation.

## RPC Testing Modes

### Mode Comparison

| Feature | Single Mode | Mixed Mode |
|---------|-------------|------------|
| **RPC Methods** | One method | Multiple methods |
| **Test Focus** | Specific operation | Realistic workload |
| **Execution Speed** | Faster | Slower |
| **Use Case** | Performance profiling | Production simulation |
| **Complexity** | Simple | Complex |
| **Results** | Focused metrics | Comprehensive profile |

### Single Mode

**Purpose:** Test one RPC method repeatedly to measure its specific performance characteristics.

**Configuration:**
```bash
# In user_config.sh or environment variable
RPC_MODE="single"
```

**Behavior:**
- Generates load using a single RPC method
- All requests use the same method
- Measures method-specific performance
- Faster test execution
- Clearer bottleneck identification

**Example Test Flow:**
```
QPS 1000: getBlockHeight × 1000 requests/sec
QPS 2000: getBlockHeight × 2000 requests/sec
QPS 3000: getBlockHeight × 3000 requests/sec
...
```

**Use Cases:**
- Performance profiling of specific RPC methods
- Identifying method-specific bottlenecks
- Comparing performance across different methods
- Quick performance verification

**Advantages:**
- ✅ Clear performance attribution
- ✅ Faster test execution
- ✅ Easier result interpretation
- ✅ Focused optimization guidance

**Limitations:**
- ❌ Not representative of production workload
- ❌ May miss interaction effects between methods
- ❌ Single point of failure testing

### Mixed Mode

**Purpose:** Test multiple RPC methods simultaneously to simulate realistic production workloads.

**Configuration:**
```bash
# In user_config.sh or environment variable
RPC_MODE="mixed"
```

**Behavior:**
- Generates load using multiple RPC methods
- Requests distributed across methods
- Simulates real-world usage patterns
- Comprehensive performance profile
- Identifies interaction effects

**Example Test Flow:**
```
QPS 1000: 
  - getBlockHeight × 400 requests/sec (40%)
  - getBalance × 300 requests/sec (30%)
  - getTransaction × 200 requests/sec (20%)
  - sendTransaction × 100 requests/sec (10%)

QPS 2000:
  - getBlockHeight × 800 requests/sec (40%)
  - getBalance × 600 requests/sec (30%)
  - ...
```

**Use Cases:**
- Production environment simulation
- Comprehensive performance testing
- Identifying interaction bottlenecks
- Capacity planning
- SLA validation

**Advantages:**
- ✅ Realistic workload simulation
- ✅ Identifies interaction effects
- ✅ Better production prediction
- ✅ Comprehensive performance profile

**Limitations:**
- ❌ Slower test execution
- ❌ More complex result interpretation
- ❌ Harder to isolate specific issues

## Blockchain Node Support

### Supported Blockchains

The framework is designed to support multiple blockchain nodes with minimal configuration:

```bash
# Solana (default)
BLOCKCHAIN_NODE="solana"

# Ethereum
BLOCKCHAIN_NODE="ethereum"

# Other blockchains (extensible)
BLOCKCHAIN_NODE="polygon"
BLOCKCHAIN_NODE="avalanche"
```

### Blockchain Configuration

#### 1. Node Type Configuration

```bash
# In user_config.sh
BLOCKCHAIN_NODE="solana"  # Automatically converted to lowercase
```

**Supported Values:**
- `solana` - Solana blockchain
- `ethereum` - Ethereum blockchain
- Custom blockchain names (requires RPC method configuration)

#### 2. Process Name Configuration

```bash
# In user_config.sh
BLOCKCHAIN_PROCESS_NAMES=(
    "blockchain"
    "validator"
    "node.service"
)
```

**Purpose:**
- Identify blockchain processes for monitoring
- Calculate blockchain-specific resource usage
- Separate blockchain from monitoring overhead

**Customization:**
```bash
# For Ethereum
BLOCKCHAIN_PROCESS_NAMES=(
    "geth"
    "ethereum"
)

# For custom blockchain
BLOCKCHAIN_PROCESS_NAMES=(
    "custom-node"
    "custom-validator"
)
```

#### 3. RPC Endpoint Configuration

```bash
# In user_config.sh
LOCAL_RPC_URL="http://localhost:8899"  # Solana default

# For Ethereum
LOCAL_RPC_URL="http://localhost:8545"

# For custom blockchain
LOCAL_RPC_URL="http://localhost:PORT"
```

## RPC Method Configuration

### Configuration Structure

RPC methods are defined in `config/config_loader.sh` within the `UNIFIED_BLOCKCHAIN_CONFIG` variable:

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

### Method Weights

**Purpose:** Define the distribution of requests across methods in mixed mode.

**Example:**
```json
"method_weights": {
  "getBlockHeight": 0.4,    // 40% of requests
  "getBalance": 0.3,        // 30% of requests
  "getTransaction": 0.2,    // 20% of requests
  "getAccountInfo": 0.1     // 10% of requests
}
```

**Calculation:**
```bash
# At QPS 1000
getBlockHeight: 1000 × 0.4 = 400 requests/sec
getBalance: 1000 × 0.3 = 300 requests/sec
getTransaction: 1000 × 0.2 = 200 requests/sec
getAccountInfo: 1000 × 0.1 = 100 requests/sec
```

### Adding New Blockchain Support

#### Step 1: Add RPC Method Configuration

Edit `config/config_loader.sh` and add to `UNIFIED_BLOCKCHAIN_CONFIG`:

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

#### Step 2: Configure Node Settings

In `user_config.sh`:

```bash
BLOCKCHAIN_NODE="your_blockchain"
LOCAL_RPC_URL="http://localhost:YOUR_PORT"
BLOCKCHAIN_PROCESS_NAMES=(
    "your-node-process"
    "your-validator-process"
)
```

#### Step 3: Test Configuration

```bash
# Verify configuration
./blockchain_node_benchmark.sh --help

# Run quick test
./blockchain_node_benchmark.sh --quick
```

**That's it!** The framework automatically:
- Loads RPC method configuration
- Generates appropriate test targets
- Monitors blockchain processes
- Analyzes performance metrics

## Test Target Generation

### Target Generator

The `tools/target_generator.sh` script generates Vegeta test targets based on:
- Blockchain node type
- RPC mode (single/mixed)
- Method weights (mixed mode)
- Account data (if available)

### Single Mode Target Generation

```bash
# Generate targets for single mode
./tools/target_generator.sh --mode single --method getBlockHeight

# Output: targets_single.txt
POST http://localhost:8899
Content-Type: application/json

{"jsonrpc":"2.0","id":1,"method":"getBlockHeight"}

POST http://localhost:8899
Content-Type: application/json

{"jsonrpc":"2.0","id":2,"method":"getBlockHeight"}
...
```

### Mixed Mode Target Generation

```bash
# Generate targets for mixed mode
./tools/target_generator.sh --mode mixed

# Output: targets_mixed.txt (distributed by weights)
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

**Distribution:**
- 40% getBlockHeight
- 30% getBalance
- 20% getTransaction
- 10% getAccountInfo

## Performance Analysis by Mode

### Single Mode Analysis

**Metrics Collected:**
- Method-specific latency (p50, p95, p99)
- Method-specific success rate
- Method-specific throughput
- Resource usage per method

**Analysis Focus:**
- Identify method performance ceiling
- Detect method-specific bottlenecks
- Compare methods against each other
- Optimize specific method implementation

**Report Sections:**
- Method performance summary
- Latency distribution
- Resource consumption per method
- Bottleneck identification

### Mixed Mode Analysis

**Metrics Collected:**
- Overall system throughput
- Per-method latency distribution
- Method interaction effects
- Resource usage under mixed load

**Analysis Focus:**
- System capacity under realistic load
- Method interaction bottlenecks
- Resource contention analysis
- Production readiness assessment

**Report Sections:**
- Overall system performance
- Per-method breakdown
- Interaction analysis
- Capacity planning recommendations

## Best Practices

### Choosing the Right Mode

**Use Single Mode When:**
- ✅ Profiling specific RPC method performance
- ✅ Comparing different methods
- ✅ Debugging method-specific issues
- ✅ Quick performance verification
- ✅ Optimizing specific operations

**Use Mixed Mode When:**
- ✅ Simulating production workload
- ✅ Capacity planning
- ✅ SLA validation
- ✅ Identifying interaction bottlenecks
- ✅ Comprehensive performance testing

### Testing Strategy

**Recommended Approach:**

1. **Start with Single Mode:**
   ```bash
   # Test each critical method individually
   RPC_MODE="single" ./blockchain_node_benchmark.sh --quick
   ```

2. **Identify Weak Methods:**
   - Analyze single mode results
   - Identify methods with high latency or low throughput
   - Optimize weak methods

3. **Test with Mixed Mode:**
   ```bash
   # Test realistic workload
   RPC_MODE="mixed" ./blockchain_node_benchmark.sh --standard
   ```

4. **Validate Production Readiness:**
   ```bash
   # Intensive test with mixed mode
   RPC_MODE="mixed" ./blockchain_node_benchmark.sh --intensive
   ```

### Method Weight Tuning

**Analyze Production Traffic:**
```bash
# Example: Analyze production logs
grep "RPC method" production.log | \
  awk '{print $5}' | \
  sort | uniq -c | \
  awk '{print $2": "$1}'

# Output:
# getBlockHeight: 4000
# getBalance: 3000
# getTransaction: 2000
# getAccountInfo: 1000
```

**Calculate Weights:**
```bash
# Total: 10000 requests
# getBlockHeight: 4000/10000 = 0.4
# getBalance: 3000/10000 = 0.3
# getTransaction: 2000/10000 = 0.2
# getAccountInfo: 1000/10000 = 0.1
```

**Update Configuration:**
```json
"method_weights": {
  "getBlockHeight": 0.4,
  "getBalance": 0.3,
  "getTransaction": 0.2,
  "getAccountInfo": 0.1
}
```

## Advanced Features

### Dynamic Method Selection

The framework supports dynamic method selection based on:
- Available account data
- Transaction history
- Node capabilities

**Example:**
```bash
# If accounts.txt exists, use account-specific methods
if [[ -f "accounts.txt" ]]; then
    RPC_METHODS="getBalance,getAccountInfo"
else
    RPC_METHODS="getBlockHeight,getSlot"
fi
```

### Method Parameter Generation

**Static Parameters:**
```json
{"jsonrpc":"2.0","id":1,"method":"getBlockHeight"}
```

**Dynamic Parameters:**
```json
{"jsonrpc":"2.0","id":1,"method":"getBalance","params":["RANDOM_ACCOUNT"]}
```

**Account-Based Parameters:**
```json
{"jsonrpc":"2.0","id":1,"method":"getTransaction","params":["REAL_TX_HASH"]}
```

### Custom RPC Methods

**Add Custom Method:**

1. Edit `config/config_loader.sh` in `UNIFIED_BLOCKCHAIN_CONFIG`:
```json
"custom_method": {
  "weight": 0.1,
  "params": ["param1", "param2"]
}
```

2. Generate targets:
```bash
./tools/target_generator.sh --custom-method custom_method
```

## Troubleshooting

### Common Issues

#### 1. "RPC method not found"

**Cause:** Method not defined in `config/config_loader.sh`

**Solution:**
```bash
# Check configuration
grep -A 20 "\"${BLOCKCHAIN_NODE}\":" config/config_loader.sh | grep -A 5 "rpc_methods"

# Add missing method by editing config_loader.sh
vim config/config_loader.sh
```

#### 2. "Invalid method weights"

**Cause:** Weights don't sum to 1.0

**Solution:**
```bash
# Verify weights in config_loader.sh
grep -A 10 "method_weights" config/config_loader.sh

# Should sum to 1.0
```

#### 3. "Target generation failed"

**Cause:** Missing account data or invalid configuration

**Solution:**
```bash
# Check account file
ls -lh accounts.txt

# Regenerate targets
./tools/target_generator.sh --force-regenerate
```

## Summary

The framework's blockchain testing features provide:

✅ **Flexibility:** Single and mixed RPC modes  
✅ **Realism:** Production workload simulation  
✅ **Extensibility:** Easy blockchain addition  
✅ **Accuracy:** Weighted method distribution  
✅ **Simplicity:** Minimal configuration required  
✅ **Power:** Comprehensive performance analysis

**Key Capabilities:**
- Multi-blockchain support
- Dual testing modes (single/mixed)
- Configurable method weights
- Dynamic target generation
- Automatic process monitoring
- Comprehensive performance analysis

For more details:
- [Configuration Guide](./configuration-guide.md)
- [Architecture Overview](./architecture-overview.md)
- [Monitoring Mechanism](./monitoring-mechanism.md)
