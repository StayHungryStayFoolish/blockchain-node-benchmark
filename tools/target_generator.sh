#!/bin/bash

# =====================================================================
# Vegeta 测试目标生成器
# 用于生成 Vegeta 压力测试所需的 JSON 目标文件
# =====================================================================

# 加载配置文件
source "$(dirname "${BASH_SOURCE[0]}")/../config/config.sh"

# 初始化变量
ACCOUNTS_FILE=""
OUTPUT_FILE=""
RPC_MODE="single"
RPC_METHODS=("getAccountInfo")

# 帮助信息
show_help() {
    echo "Vegeta Test Target Generator"
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help                 Show this help message"
    echo "  -a, --accounts-file FILE   Input accounts file (default: ${ACCOUNTS_OUTPUT_FILE})"
    echo "  -o, --output FILE          Output targets file (auto-selected based on mode)"
    echo "  --rpc-mode MODE            RPC mode: single, mixed (default: single)"
    echo "  --rpc-url URL              RPC endpoint URL"
    echo "  --output-single FILE       Single method targets output file"
    echo "  --output-mixed FILE        Mixed method targets output file"
    echo "  -v, --verbose              Enable verbose output"
    echo ""
    echo "RPC modes:"
    echo "  single: Generate targets with a single RPC method (getAccountInfo)"
    echo "  mixed: Generate targets with multiple RPC methods (excluding getProgramAccounts)"
    echo ""
}

# 参数解析
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0  # --help 应该直接退出整个脚本
                ;;
            -a|--accounts-file)
                ACCOUNTS_FILE="$2"
                shift 2
                ;;
            -o|--output)
                OUTPUT_FILE="$2"
                shift 2
                ;;
            --rpc-mode)
                RPC_MODE="$2"
                shift 2
                ;;
            --rpc-url)
                # RPC URL 参数处理 (如果需要)
                shift 2
                ;;
            --output-single)
                SINGLE_METHOD_TARGETS_FILE="$2"
                shift 2
                ;;
            --output-mixed)
                MIXED_METHOD_TARGETS_FILE="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                return 1
                ;;
        esac
    done
    
    # 设置默认值
    ACCOUNTS_FILE=${ACCOUNTS_FILE:-"$ACCOUNTS_OUTPUT_FILE"}
    
    # 根据RPC模式设置输出文件
    if [[ "$RPC_MODE" == "single" ]]; then
        OUTPUT_FILE=${OUTPUT_FILE:-"$SINGLE_METHOD_TARGETS_FILE"}
    elif [[ "$RPC_MODE" == "mixed" ]]; then
        OUTPUT_FILE=${OUTPUT_FILE:-"$MIXED_METHOD_TARGETS_FILE"}
        # 设置混合 RPC 方法 (5种核心方法)
        RPC_METHODS=(
            "getAccountInfo"
            "getMultipleAccounts"
            "getBalance"
            "getTokenAccountBalance"
            "getRecentBlockhash"
        )
    else
        echo "Error: Invalid RPC mode: $RPC_MODE"
        show_help
        return 1
    fi
}

# 检查依赖
check_dependencies() {
    if ! command -v jq &> /dev/null; then
        echo "Error: jq is not installed"
        return 1
    fi
}

# 检查输入文件
check_input_file() {
    if [[ ! -f "$ACCOUNTS_FILE" ]]; then
        echo "Error: Accounts file not found: $ACCOUNTS_FILE"
        return 1
    fi
    
    # 检查文件是否为空
    if [[ ! -s "$ACCOUNTS_FILE" ]]; then
        echo "Error: Accounts file is empty: $ACCOUNTS_FILE"
        return 1
    fi
}

# 生成 getAccountInfo 方法的 JSON
generate_get_account_info_json() {
    local address="$1"
    local rpc_url="$LOCAL_RPC_URL"
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           --arg addr "$address" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getAccountInfo\",\"params\":[\"" + $addr + "\"]}" | @base64)
           }'
}

# 生成 getBalance 方法的 JSON
generate_get_balance_json() {
    local address="$1"
    local rpc_url="$LOCAL_RPC_URL"
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           --arg addr "$address" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getBalance\",\"params\":[\"" + $addr + "\"]}" | @base64)
           }'
}

# 生成 getBlockHeight 方法的 JSON
generate_get_block_height_json() {
    local rpc_url="$LOCAL_RPC_URL"
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getBlockHeight\"}" | @base64)
           }'
}

# 生成 getBlockTime 方法的 JSON
generate_get_block_time_json() {
    local slot=$(( RANDOM % 1000 + 1000000 ))
    local rpc_url="$LOCAL_RPC_URL"
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           --arg slot "$slot" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getBlockTime\",\"params\":[" + $slot + "]}" | @base64)
           }'
}

# 生成 getEpochInfo 方法的 JSON
generate_get_epoch_info_json() {
    local rpc_url="$LOCAL_RPC_URL"
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getEpochInfo\"}" | @base64)
           }'
}

# 生成 getHealth 方法的 JSON
generate_get_health_json() {
    local rpc_url="$LOCAL_RPC_URL"
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getHealth\"}" | @base64)
           }'
}

# 生成 getSlot 方法的 JSON
generate_get_slot_json() {
    local rpc_url="$LOCAL_RPC_URL"
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getSlot\"}" | @base64)
           }'
}

# 生成 getVersion 方法的 JSON
generate_get_version_json() {
    local rpc_url="$LOCAL_RPC_URL"
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getVersion\"}" | @base64)
           }'
}

# 生成 getMultipleAccounts 方法的 JSON
generate_get_multiple_accounts_json() {
    local addresses="$1"  # 传入多个地址，用逗号分隔
    local rpc_url="$LOCAL_RPC_URL"
    
    # 将地址字符串转换为JSON数组
    local accounts_array=$(echo "$addresses" | tr ',' '\n' | head -4 | jq -R . | jq -s .)
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           --argjson accounts "$accounts_array" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getMultipleAccounts\",\"params\":[" + ($accounts | tostring) + "]}" | @base64)
           }'
}

# 生成 getTokenAccountBalance 方法的 JSON
generate_get_token_account_balance_json() {
    local address="$1"
    local rpc_url="$LOCAL_RPC_URL"
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           --arg addr "$address" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getTokenAccountBalance\",\"params\":[\"" + $addr + "\"]}" | @base64)
           }'
}

# 生成 getRecentBlockhash 方法的 JSON
generate_get_recent_blockhash_json() {
    local rpc_url="$LOCAL_RPC_URL"
    
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ("{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"getRecentBlockhash\"}" | @base64)
           }'
}

# 生成测试目标
generate_targets() {
    echo "Generating Vegeta test targets..."
    echo "Input accounts file: $ACCOUNTS_FILE"
    echo "Output targets file: $OUTPUT_FILE"
    echo "RPC mode: $RPC_MODE"
    
    # 创建输出目录
    mkdir -p "$(dirname "$OUTPUT_FILE")"
    
    # 清空输出文件
    > "$OUTPUT_FILE"
    
    # 读取账户列表
    local accounts=()
    while IFS= read -r address; do
        [[ -z "$address" ]] && continue
        accounts+=("$address")
    done < "$ACCOUNTS_FILE"
    
    # 检查是否有账户
    if [[ ${#accounts[@]} -eq 0 ]]; then
        echo "Error: No valid accounts found in $ACCOUNTS_FILE"
        return 1
    fi
    
    echo "Found ${#accounts[@]} accounts"
    
    # 生成目标
    local count=0
    local total_targets=0
    
    if [[ "$RPC_MODE" == "single" ]]; then
        # 单一 RPC 方法模式
        for address in "${accounts[@]}"; do
            generate_get_account_info_json "$address" >> "$OUTPUT_FILE"
            ((count++))
            
            # 显示进度
            if [[ "$VERBOSE" == "true" && $((count % 100)) -eq 0 ]]; then
                echo "Generated $count targets..."
            fi
        done
        total_targets=$count
    else
        # 混合 RPC 方法模式
        local method_count=${#RPC_METHODS[@]}
        local account_index=0
        
        for address in "${accounts[@]}"; do
            # 根据账户索引选择 RPC 方法
            local method_index=$((account_index % method_count))
            local method=${RPC_METHODS[$method_index]}
            
            case "$method" in
                "getAccountInfo")
                    generate_get_account_info_json "$address" >> "$OUTPUT_FILE"
                    ;;
                "getMultipleAccounts")
                    # 为getMultipleAccounts生成多个地址
                    local multi_addresses=""
                    local start_idx=$account_index
                    for ((i=0; i<4 && start_idx+i<${#accounts[@]}; i++)); do
                        if [[ $i -gt 0 ]]; then
                            multi_addresses+=","
                        fi
                        multi_addresses+="${accounts[$((start_idx + i))]}"
                    done
                    generate_get_multiple_accounts_json "$multi_addresses" >> "$OUTPUT_FILE"
                    ;;
                "getBalance")
                    generate_get_balance_json "$address" >> "$OUTPUT_FILE"
                    ;;
                "getTokenAccountBalance")
                    # 对于getTokenAccountBalance，我们使用相同的地址
                    # 在实际环境中，这可能会返回错误，但可以测试RPC响应能力
                    generate_get_token_account_balance_json "$address" >> "$OUTPUT_FILE"
                    ;;
                "getRecentBlockhash")
                    generate_get_recent_blockhash_json >> "$OUTPUT_FILE"
                    ;;
            esac
            
            ((count++))
            ((account_index++))
            
            # 显示进度
            if [[ "$VERBOSE" == "true" && $((count % 100)) -eq 0 ]]; then
                echo "Generated $count targets..."
            fi
        done
        total_targets=$count
    fi
    
    echo "Generated $total_targets targets in $OUTPUT_FILE"
    
    # 验证生成的 JSON
    if [[ "$VERBOSE" == "true" ]]; then
        echo "Validating first target:"
        head -n 1 "$OUTPUT_FILE" | jq '.'
        
        echo "Validating body decode:"
        head -n 1 "$OUTPUT_FILE" | jq -r '.body' | base64 -d | jq '.'
        
        echo "Total targets: $(wc -l < "$OUTPUT_FILE")"
    fi
}

# 主函数
main() {
    # 检查依赖
    if ! check_dependencies; then
        exit 1
    fi
    
    # 解析参数
    parse_args "$@"
    
    # 检查输入文件
    if ! check_input_file; then
        exit 1
    fi
    
    # 生成测试目标
    if ! generate_targets; then
        exit 1
    fi
}

# 执行主函数
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
