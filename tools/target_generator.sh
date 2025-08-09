#!/bin/bash

# =====================================================================
# 通用 Vegeta 测试目标生成器 - 多区块链支持版
# 支持基于 fetch_active_accounts.py 生成的地址文件
# =====================================================================

# 加载配置文件
if ! source "$(dirname "${BASH_SOURCE[0]}")/../config/config_loader.sh" 2>/dev/null; then
    echo "❌ 错误: 配置文件加载失败" >&2
    exit 1
fi

# 兜底：若方法串为空，现算一遍（避免上游未初始化）
if [[ -z "${CURRENT_RPC_METHODS_STRING:-}" ]]; then
    CURRENT_RPC_METHODS_STRING="$(get_current_rpc_methods)"
    IFS=',' read -ra CURRENT_RPC_METHODS_ARRAY <<< "$CURRENT_RPC_METHODS_STRING"
fi

# 初始化变量（保持向后兼容）
VERBOSE=${VERBOSE:-false}

# 帮助信息
show_help() {
    echo "通用 Vegeta 测试目标生成器 - 多区块链支持版"
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help                 显示帮助信息"
    echo "  -a, --accounts-file FILE   输入账户文件 (默认: ${ACCOUNTS_OUTPUT_FILE})"
    echo "  -o, --output FILE          输出目标文件 (根据模式自动选择)"
    echo "  --rpc-mode MODE            RPC模式: single, mixed (默认: $RPC_MODE)"
    echo "  --rpc-url URL              RPC端点URL (默认: $LOCAL_RPC_URL)"
    echo "  --output-single FILE       单一方法目标输出文件"
    echo "  --output-mixed FILE        混合方法目标输出文件"
    echo "  -v, --verbose              启用详细输出"
    echo ""
    echo "支持的区块链: solana, ethereum, bsc, base, polygon, scroll, starknet, sui"
    echo "当前区块链: $BLOCKCHAIN_NODE"
    echo "RPC模式:"
    echo "  single: 使用单一RPC方法生成目标"
    echo "  mixed: 使用多种RPC方法生成目标"
    echo ""
}

# 精确的 RPC JSON 生成函数 - 完全基于 JSON-RPC-API-List.md
generate_rpc_json() {
    local method="$1"
    local address="$2"
    local rpc_url="$LOCAL_RPC_URL"

    # 获取方法参数格式
    local param_format="${RPC_METHOD_PARAM_FORMATS[$method]}"
    local params_json=""

    case "$param_format" in
        "no_params")
            params_json="[]"
            ;;
        "single_address")
            params_json="[\"$address\"]"
            ;;
        "address_latest")
            # EVM兼容链格式: ["address", "latest"]
            params_json="[\"$address\", \"latest\"]"
            ;;
        "latest_address")
            # StarkNet格式: ["latest", "address"]
            params_json="[\"latest\", \"$address\"]"
            ;;
        "address_storage_latest")
            # eth_getStorageAt格式: ["address", "0x0", "latest"]
            params_json="[\"$address\", \"0x0\", \"latest\"]"
            ;;
        "address_key_latest")
            # starknet_getStorageAt格式: ["address", "0x1", "latest"]
            params_json="[\"$address\", \"0x1\", \"latest\"]"
            ;;
        "address_with_options")
            # sui_getObject格式: ["address", options]
            params_json="[\"$address\", {\"showType\": true, \"showContent\": true, \"showDisplay\": false}]"
            ;;
        *)
            # 默认使用单地址参数
            echo "⚠️ 警告: 未知参数格式 $param_format for method $method，使用默认格式" >&2
            params_json="[\"$address\"]"
            ;;
    esac

    # 生成 JSON RPC 请求体
    local request_body="{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$method\",\"params\":$params_json}"

    # 生成 Vegeta 目标 JSON
    jq -nc --arg method "POST" \
           --arg url "$rpc_url" \
           --arg body "$request_body" \
           '{
             method: $method,
             url: $url,
             header: {"Content-Type": ["application/json"]},
             body: ($body | @base64)
           }'
}

# 参数解析（保持现有接口兼容）
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -a|--accounts-file)
                ACCOUNTS_OUTPUT_FILE="$2"
                shift 2
                ;;
            -o|--output)
                USER_OUTPUT_FILE="$2"
                shift 2
                ;;
            --rpc-mode)
                RPC_MODE="$2"
                # 重新计算RPC方法列表
                CURRENT_RPC_METHODS_STRING=$(get_current_rpc_methods)
                IFS=',' read -ra CURRENT_RPC_METHODS_ARRAY <<< "$CURRENT_RPC_METHODS_STRING"
                shift 2
                ;;
            --rpc-url)
                LOCAL_RPC_URL="$2"
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
                echo "未知选项: $1" >&2
                shift
                ;;
        esac
    done

    # 根据RPC模式设置当前输出文件
    if [[ "$RPC_MODE" == "single" ]]; then
        CURRENT_OUTPUT_FILE="$SINGLE_METHOD_TARGETS_FILE"
    elif [[ "$RPC_MODE" == "mixed" ]]; then
        CURRENT_OUTPUT_FILE="$MIXED_METHOD_TARGETS_FILE"
    else
        echo "❌ 错误: 无效的RPC模式: $RPC_MODE" >&2
        show_help
        return 1
    fi

    # 如果用户通过 -o 指定了输出文件，覆盖默认设置
    if [[ -n "${USER_OUTPUT_FILE:-}" ]]; then
        CURRENT_OUTPUT_FILE="$USER_OUTPUT_FILE"
    fi
}

# 检查依赖
check_dependencies() {
    if ! command -v jq &> /dev/null; then
        echo "❌ 错误: jq 未安装" >&2
        return 1
    fi
}

# 检查必需的配置变量
check_required_variables() {
    local required_vars=(
        "ACCOUNTS_OUTPUT_FILE"
        "SINGLE_METHOD_TARGETS_FILE"
        "MIXED_METHOD_TARGETS_FILE"
        "LOCAL_RPC_URL"
        "BLOCKCHAIN_NODE"
        "CURRENT_RPC_METHODS_STRING"
    )

    local missing_vars=()
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            missing_vars+=("$var")
        fi
    done

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        echo "❌ 错误: 必需的变量未设置:" >&2
        for var in "${missing_vars[@]}"; do
            echo "  - $var" >&2
        done
        echo "请确保 config_loader.sh 正确加载" >&2
        return 1
    fi

    return 0
}

# 检查输入文件
check_input_file() {
    if [[ ! -f "$ACCOUNTS_OUTPUT_FILE" ]]; then
        echo "❌ 错误: 账户文件不存在: $ACCOUNTS_OUTPUT_FILE" >&2
        return 1
    fi

    # 检查文件是否为空
    if [[ ! -s "$ACCOUNTS_OUTPUT_FILE" ]]; then
        echo "❌ 错误: 账户文件为空: $ACCOUNTS_OUTPUT_FILE" >&2
        return 1
    fi
}

# 生成测试目标 - 使用配置化的方法列表
generate_targets() {
    echo "🎯 生成Vegeta测试目标..." >&2
    echo "   区块链类型: $BLOCKCHAIN_NODE" >&2
    echo "   RPC模式: $RPC_MODE" >&2
    echo "   RPC方法: $CURRENT_RPC_METHODS_STRING" >&2
    echo "   输入文件: $ACCOUNTS_OUTPUT_FILE" >&2
    echo "   输出文件: $CURRENT_OUTPUT_FILE" >&2

    # 创建输出目录
    mkdir -p "$(dirname "$CURRENT_OUTPUT_FILE")"

    # 清空输出文件
    > "$CURRENT_OUTPUT_FILE"

    # 读取账户列表
    local accounts=()
    while IFS= read -r address; do
        [[ -z "$address" ]] && continue
        accounts+=("$address")
    done < "$ACCOUNTS_OUTPUT_FILE"

    if [[ ${#accounts[@]} -eq 0 ]]; then
        echo "❌ 错误: 账户文件为空或不存在有效地址" >&2
        return 1
    fi

    echo "✅ 读取到 ${#accounts[@]} 个账户" >&2

    # 生成目标
    local count=0

    if [[ "$RPC_MODE" == "single" ]]; then
        # 单一方法模式
        local method="${CURRENT_RPC_METHODS_ARRAY[0]}"
        echo "📝 使用单一方法: $method" >&2

        for address in "${accounts[@]}"; do
            generate_rpc_json "$method" "$address" >> "$CURRENT_OUTPUT_FILE"
            ((count++))

            if [[ "$VERBOSE" == "true" && $((count % 100)) -eq 0 ]]; then
                echo "   已生成 $count 个目标..." >&2
            fi
        done
    else
        # 混合方法模式
        local method_count=${#CURRENT_RPC_METHODS_ARRAY[@]}
        local account_index=0

        echo "📝 使用混合方法: ${CURRENT_RPC_METHODS_ARRAY[*]}" >&2

        for address in "${accounts[@]}"; do
            local method_index=$((account_index % method_count))
            local method="${CURRENT_RPC_METHODS_ARRAY[$method_index]}"

            generate_rpc_json "$method" "$address" >> "$CURRENT_OUTPUT_FILE"

            ((count++))
            ((account_index++))

            if [[ "$VERBOSE" == "true" && $((count % 100)) -eq 0 ]]; then
                echo "   已生成 $count 个目标 (当前方法: $method)..." >&2
            fi
        done
    fi

    echo "✅ 成功生成 $count 个测试目标" >&2

    # 验证生成的JSON
    if [[ "$VERBOSE" == "true" ]]; then
        echo "🔍 验证第一个目标:" >&2
        head -n 1 "$CURRENT_OUTPUT_FILE" | jq '.' 2>/dev/null || echo "   JSON格式验证失败" >&2

        echo "🔍 验证请求体:" >&2
        head -n 1 "$CURRENT_OUTPUT_FILE" | jq -r '.body' 2>/dev/null | base64 -d 2>/dev/null | jq '.' 2>/dev/null || echo "   请求体解码失败" >&2

        echo "📊 总目标数: $(wc -l < "$CURRENT_OUTPUT_FILE")" >&2
    fi
}

# 主函数
main() {
    # 检查依赖
    if ! check_dependencies; then
        exit 1
    fi

    # 检查必需的配置变量
    if ! check_required_variables; then
        exit 1
    fi

    # 解析参数
    parse_args "$@"

    # 再次兜底：确保方法串/数组就绪
    if [[ -z "${CURRENT_RPC_METHODS_STRING:-}" ]]; then
        CURRENT_RPC_METHODS_STRING="$(get_current_rpc_methods)"
    fi
    IFS=',' read -ra CURRENT_RPC_METHODS_ARRAY <<< "$CURRENT_RPC_METHODS_STRING"

    # 可选DEBUG输出
    [[ "${CFG_DEBUG:-}" == "1" ]] && { echo "=== DEBUG TG: methods=($CURRENT_RPC_METHODS_STRING)" >&2; }

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