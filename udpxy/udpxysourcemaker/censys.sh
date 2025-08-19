#!/bin/bash
# filepath: extract_ips.sh

input_file="$1"
output_file="$2"

if [ $# -ne 2 ]; then
    echo "用法: $0 <输入文件> <输出文件>"
    exit 1
fi

awk '/^Host$/{print prev} {prev=$0}' "$input_file" > "$output_file"

echo "已提取IP地址到 $output_file"
