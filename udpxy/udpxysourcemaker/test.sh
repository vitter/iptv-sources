#!/bin/bash

# 检查是否提供了IP文件参数
if [ $# -eq 0 ]; then
    echo "使用方法: $0 <ip_file>"
    echo "示例: $0 ip.txt"
    exit 1
fi

# 获取IP文件路径
IP_FILE="$1"

# 检查文件是否存在
if [ ! -f "$IP_FILE" ]; then
    echo "错误: 文件 '$IP_FILE' 不存在！"
    exit 1
fi

# 检查文件是否为空
if [ ! -s "$IP_FILE" ]; then
    echo "警告: 文件 '$IP_FILE' 为空！"
    exit 1
fi

# 检查udpxysourcemake.py是否存在
if [ ! -f "udpxysourcemake.py" ]; then
    echo "错误: udpxysourcemake.py 脚本不存在！"
    exit 1
fi

echo "开始处理文件: $IP_FILE"
echo "代理设置: http://127.0.0.1:10808"
echo "========================================"

# 计数器
total_lines=0
processed_lines=0
success_count=0
failed_count=0

# 获取总行数
total_lines=$(wc -l < "$IP_FILE")
echo "总计发现 $total_lines 个IP地址"
echo

# 逐行读取IP文件并执行命令
while IFS= read -r ip_port || [ -n "$ip_port" ]; do
    # 跳过空行和注释行
    if [[ -z "$ip_port" || "$ip_port" =~ ^[[:space:]]*# ]]; then
        continue
    fi
    
    # 移除行首行尾空白字符
    ip_port=$(echo "$ip_port" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    
    # 跳过处理后的空行
    if [[ -z "$ip_port" ]]; then
        continue
    fi
    
    processed_lines=$((processed_lines + 1))
    
    echo "[$processed_lines/$total_lines] 正在处理: $ip_port"
    
    # 执行python命令
    if python3 udpxysourcemake.py "$ip_port" --proxy http://127.0.0.1:10808 --test-count 3 --max-workers 3; then
        success_count=$((success_count + 1))
        echo "✓ 成功处理: $ip_port"
    else
        failed_count=$((failed_count + 1))
        echo "✗ 处理失败: $ip_port"
    fi
    
    echo "----------------------------------------"
    
done < "$IP_FILE"

# 输出统计结果
echo
echo "========================================"
echo "处理完成！统计结果:"
echo "总IP数量: $total_lines"
echo "实际处理: $processed_lines"
echo "成功处理: $success_count"
echo "失败处理: $failed_count"
echo "成功率: $([ $processed_lines -gt 0 ] && echo "scale=2; $success_count * 100 / $processed_lines" | bc -l || echo "0")%"
echo "========================================"