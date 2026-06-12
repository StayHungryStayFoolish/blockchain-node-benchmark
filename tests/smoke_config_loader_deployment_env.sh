#!/bin/bash
# Smoke test: source full config_loader.sh and print resolved deployment envs
set -e
cd "$(dirname "$0")/.."
export BLOCKCHAIN_NODE=solana
source config/config_loader.sh > /tmp/cfg_load.log 2>&1
echo "EXIT=0 (source succeeded)"
echo "DEPLOYMENT_MODE=$DEPLOYMENT_MODE"
echo "DEPLOYMENT_MODE_SOURCE=$DEPLOYMENT_MODE_SOURCE"
echo "DEPLOYMENT_PLATFORM=$DEPLOYMENT_PLATFORM"
echo "HOST_PROC=$HOST_PROC"
echo "HOST_SYS=$HOST_SYS"
echo "CGROUP_VERSION=$CGROUP_VERSION"
echo "CGROUP_ROOT=$CGROUP_ROOT"
