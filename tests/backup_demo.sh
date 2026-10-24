#!/usr/bin/env bash
# 复制两份 demo 章节，用于验证 L1 自动修复（不污染原 demo）
set -e
cd "$(dirname "$0")/.."
mkdir -p /tmp/nr-test
cp demo/章节/*.md /tmp/nr-test/
echo "已备份到 /tmp/nr-test"
