#!/bin/bash

# 自动下载并处理 UDPXY 代理地址列表
# 从 https://tv1288.xyz/ip.php 下载，提取 IP:端口 格式的行，然后批量测试

echo "========================================"
echo "UDPXY 代理自动下载与测试工具"
echo "========================================"

# 配置参数
DOWNLOAD_URL="https://tv1288.xyz/ip.php"
IP_FILE="ip.txt"
TEMP_FILE="ip_temp.html"

# 检查udpxysourcemake.py是否存在
if [ ! -f "udpxysourcemake.py" ]; then
    echo "错误: udpxysourcemake.py 脚本不存在！"
    exit 1
fi

# 步骤1: 下载页面内容
echo "步骤 1/3: 正在从 $DOWNLOAD_URL 下载代理列表..."
if curl -s -o "$TEMP_FILE" "$DOWNLOAD_URL"; then
    echo "✓ 下载完成"
else
    echo "✗ 下载失败！请检查网络连接或URL是否正确"
    exit 1
fi

# 步骤2: 提取 IP:端口 格式的行
echo "步骤 2/3: 正在提取 IP:端口 格式的地址..."

# 使用 grep 匹配 IP:端口 格式
# 匹配规则：数字.数字.数字.数字:数字
grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]+' "$TEMP_FILE" | sort -u > "$IP_FILE"

# 检查是否成功提取到地址
if [ ! -s "$IP_FILE" ]; then
    echo "✗ 未能提取到有效的IP地址！"
    echo "原始文件内容预览："
    head -20 "$TEMP_FILE"
    rm -f "$TEMP_FILE"
    exit 1
fi

# 统计提取到的地址数量
extracted_count=$(wc -l < "$IP_FILE")
echo "✓ 成功提取 $extracted_count 个代理地址"

# 清理临时文件
rm -f "$TEMP_FILE"

# 步骤3: 批量测试代理
echo "步骤 3/3: 开始批量测试代理..."
echo "代理设置: http://127.0.0.1:10808"
echo "========================================"
echo

# 计数器
total_lines=$extracted_count
processed_lines=0
success_count=0
failed_count=0

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
    if python3 udpxysourcemake.py "$ip_port" --proxy http://127.0.0.1:10808 --test-count 5 --max-workers 5; then
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
echo "下载地址: $DOWNLOAD_URL"
echo "提取IP数量: $extracted_count"
echo "实际处理: $processed_lines"
echo "成功处理: $success_count"
echo "失败处理: $failed_count"
echo "成功率: $([ $processed_lines -gt 0 ] && echo "scale=2; $success_count * 100 / $processed_lines" | bc -l || echo "0")%"
echo "========================================"
echo
echo "提示: IP地址列表已保存到 $IP_FILE 文件中"
