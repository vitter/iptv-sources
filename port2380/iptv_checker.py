#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV IP:端口检测与替换工具
整合多个源的检测，支持并发测试
"""

import re
import random
import time
import requests
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ===== 配置区域 =====
# IP:端口源文件
IP_PORT_FILE = "fz.php"

# 测试URL与模板文件的映射关系
# 格式: {名称: {"test_path": 测试路径, "template": 模板文件, "output": 输出文件}}
SOURCE_CONFIG = {
    "sxg": {
        "test_path": "hw1live.rxip.sc96655.com.huan.tv/live/CCTV-1H265_4000.m3u8",
        "template": "dz-sxg.txt",
        "output": "sxg.txt"
    },
    "yh": {
        "test_path": "js-live-screenshot.gitv.tv/gitv_live/CCTV-1-HD/CCTV-1-HD.m3u8",
        "template": "dz-yh.txt",
        "output": "yh.txt"
    },
    "bjyd": {
        "test_path": "ywotttv.bj.chinamobile.com/PLTV/88888888/224/3221226933/1.m3u8",
        "template": "dz-bj.txt",
        "output": "bjyd.txt"
    },
    "hngd": {
        "test_path": "c3.cdn.hunancatv.com/live/CCTV1HD.m3u8",
        "template": "dz-hn.txt",
        "output": "hngd.txt"
    },
    "mobaibox": {
        "test_path": "tptvh.mobaibox.com/hwcdnbacksourceflag_223.110.243.244/PLTV/4/224/3221228287/1.m3u8",
        "template": "dz-mbh.txt",
        "output": "mbh.txt"
    }
}

# 检测配置
REQUEST_TIMEOUT = 10  # 请求超时时间（秒）
MAX_ATTEMPTS = 5000     # 最大尝试次数
DELAY_BETWEEN_TESTS = 0  # 测试间隔（秒）
MAX_WORKERS = 40       # 并发线程数

# ===== 核心功能 =====

def get_ip_port_list(filepath: str) -> List[str]:
    """
    读取IP:端口列表文件
    
    Args:
        filepath: IP:端口列表文件路径
        
    Returns:
        IP:端口列表
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取所有符合 IP:端口 格式的记录
        pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}\b'
        ip_port_list = re.findall(pattern, content)
        
        if not ip_port_list:
            print(f"❌ 错误：{filepath} 中未找到有效的IP:端口组合")
            return []
        
        return list(set(ip_port_list))  # 去重
        
    except FileNotFoundError:
        print(f"❌ 错误：找不到文件 {filepath}")
        return []
    except Exception as e:
        print(f"❌ 错误：读取文件失败 - {e}")
        return []


def check_ip_port_valid(ip: str, port: str, test_path: str) -> bool:
    """
    检测单个IP:端口是否有效
    
    Args:
        ip: IP地址
        port: 端口号
        test_path: 测试路径
        
    Returns:
        是否有效
    """
    test_url = f"http://{ip}:{port}/{test_path}"
    
    try:
        response = requests.get(
            test_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            verify=False
        )
        
        # 检查状态码和响应内容
        if response.status_code == 200 and len(response.text.strip()) > 0:
            return True
            
    except requests.exceptions.RequestException:
        pass
    
    return False


def test_ip_port_for_source(ip_port: str, source_name: str, test_path: str) -> tuple:
    """
    测试IP:端口对特定源的有效性
    
    Args:
        ip_port: IP:端口组合
        source_name: 源名称
        test_path: 测试路径
        
    Returns:
        (源名称, IP:端口, 是否有效)
    """
    ip, port = ip_port.split(':', 1)
    is_valid = check_ip_port_valid(ip, port, test_path)
    return (source_name, ip_port, is_valid)


def find_valid_ip_ports_concurrent(ip_port_list: List[str]) -> Dict[str, List[str]]:
    """
    并发测试IP:端口对所有源的有效性（每个IP测试所有源，收集所有有效IP）
    
    Args:
        ip_port_list: IP:端口列表
        
    Returns:
        {源名称: [有效的IP:端口列表]} 字典
    """
    print(f"\n📋 找到 {len(ip_port_list)} 个IP:端口组合")
    print(f"🔍 开始并发测试 {len(SOURCE_CONFIG)} 个源...\n")
    
    # 结果字典 - 改为列表，保存所有有效IP
    from threading import Lock
    results = {name: [] for name in SOURCE_CONFIG.keys()}
    results_lock = Lock()
    
    # 随机打乱列表
    random.shuffle(ip_port_list)
    
    # 限制测试数量
    test_list = ip_port_list[:MAX_ATTEMPTS]
    
    print(f"📝 将测试所有 {len(test_list)} 个IP:端口组合（每个IP测试所有源）\n")
    
    # 创建测试任务 - 每个IP测试所有源
    total_tests = len(test_list) * len(SOURCE_CONFIG)
    completed_tests = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for idx, ip_port in enumerate(test_list, 1):
            # 为当前IP创建针对所有源的任务
            futures = {}
            for source_name, config in SOURCE_CONFIG.items():
                future = executor.submit(
                    test_ip_port_for_source,
                    ip_port,
                    source_name,
                    config["test_path"]
                )
                futures[future] = source_name
            
            # 等待当前IP的所有测试完成
            for future in as_completed(futures):
                completed_tests += 1
                source_name, test_ip_port, is_valid = future.result()
                
                if is_valid:
                    with results_lock:
                        if test_ip_port not in results[source_name]:
                            results[source_name].append(test_ip_port)
                            print(f"✅ [{source_name}] 找到有效IP:端口: {test_ip_port} (第{len(results[source_name])}个)")
            
            # 进度提示
            with results_lock:
                total_found = sum(len(v) for v in results.values())
            print(f"📊 进度: IP {idx}/{len(test_list)}, 总测试 {completed_tests}/{total_tests}, 共找到 {total_found} 个有效组合")
            
            time.sleep(DELAY_BETWEEN_TESTS)
    
    return results


def replace_ip_port_in_template(template_file: str, new_ip_port: str) -> str:
    """
    替换模板文件中的IP:端口
    
    Args:
        template_file: 模板文件路径
        new_ip_port: 新的IP:端口
        
    Returns:
        替换后的内容
    """
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换所有IP:端口组合
        pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}\b'
        replaced_content = re.sub(pattern, new_ip_port, content)
        
        return replaced_content
        
    except FileNotFoundError:
        print(f"❌ 错误：找不到模板文件 {template_file}")
        return None
    except Exception as e:
        print(f"❌ 错误：读取模板文件失败 - {e}")
        return None


def generate_output_files(valid_ip_ports: Dict[str, List[str]]) -> None:
    """
    根据有效IP:端口生成输出文件（追加所有有效IP）
    
    Args:
        valid_ip_ports: {源名称: [有效的IP:端口列表]} 字典
    """
    print(f"\n📝 开始生成输出文件...\n")
    
    # 用于记录每个IP对应的源内容（IP -> 源列表）
    ip_to_sources = {}
    # 用于存储所有output内容
    all_output_contents = []
    
    for source_name, ip_port_list in valid_ip_ports.items():
        if not ip_port_list:
            print(f"⚠️  [{source_name}] 未找到有效IP:端口，跳过")
            continue
        
        config = SOURCE_CONFIG[source_name]
        template_file = config["template"]
        output_file = config["output"]
        
        print(f"🔄 [{source_name}] 处理 {len(ip_port_list)} 个有效IP:端口...")
        
        # 读取模板
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                template_content = f.read()
        except Exception as e:
            print(f"❌ [{source_name}] 读取模板失败: {e}")
            continue
        
        # 为每个有效IP生成内容并合并
        all_contents = []
        for ip_port in ip_port_list:
            # 替换IP:端口
            pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}:\d{1,5}\b'
            content = re.sub(pattern, ip_port, template_content)
            all_contents.append(content)
            
            # 记录IP对应的源内容（用于生成单个IP的聚合文件）
            if ip_port not in ip_to_sources:
                ip_to_sources[ip_port] = []
            ip_to_sources[ip_port].append({
                'source_name': source_name,
                'content': content
            })
        
        # 合并所有内容
        merged_content = '\n'.join(all_contents)
        
        # 写入输出文件
        try:
            # 如果文件存在且无写权限，先删除
            if Path(output_file).exists():
                try:
                    Path(output_file).unlink()
                except PermissionError:
                    print(f"⚠️  [{source_name}] 无法删除旧文件 {output_file}，尝试覆盖写入...")
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(merged_content)
            print(f"✅ [{source_name}] 生成成功: {output_file} (包含 {len(ip_port_list)} 个IP: {', '.join(ip_port_list)})")
            
            # 保存到all.txt的内容列表
            all_output_contents.append(merged_content)
            
        except PermissionError as e:
            print(f"❌ [{source_name}] 权限不足: {output_file} 可能由其他用户创建，请运行: sudo chown $USER:$USER {output_file}")
        except Exception as e:
            print(f"❌ [{source_name}] 写入文件失败: {e}")
    
    # 生成单个IP的聚合文件
    print(f"\n📝 生成单个IP的聚合文件...\n")
    for ip_port, sources in ip_to_sources.items():
        # 使用IP地址作为文件名（去掉端口）
        ip_only = ip_port.split(':')[0]
        ip_output_file = f"{ip_only}.txt"
        
        # 合并该IP在所有源的内容
        ip_contents = [src['content'] for src in sources]
        ip_merged_content = '\n'.join(ip_contents)
        
        try:
            with open(ip_output_file, 'w', encoding='utf-8') as f:
                f.write(ip_merged_content)
            
            source_names = [src['source_name'] for src in sources]
            print(f"✅ 生成IP聚合文件: {ip_output_file} (包含源: {', '.join(source_names)})")
        except Exception as e:
            print(f"❌ 生成IP聚合文件失败 {ip_output_file}: {e}")
    
    # 生成all.txt总汇总文件
    if all_output_contents:
        print(f"\n📝 生成总汇总文件...\n")
        try:
            all_merged_content = '\n'.join(all_output_contents)
            with open('all.txt', 'w', encoding='utf-8') as f:
                f.write(all_merged_content)
            print(f"✅ 生成总汇总文件: all.txt (包含所有 {len(all_output_contents)} 个源的内容)")
        except Exception as e:
            print(f"❌ 生成总汇总文件失败: {e}")


def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description='IPTV IP:端口检测与替换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认的fz.php作为IP源文件
  python iptv_checker.py
  
  # 指定自定义的IP源文件
  python iptv_checker.py -i custom_ips.txt
  
  # 使用短格式
  python iptv_checker.py -i guangdong_mobile.txt
        """
    )
    
    parser.add_argument(
        '-i', '--input',
        type=str,
        default=IP_PORT_FILE,
        help=f'IP:端口源文件路径 (默认: {IP_PORT_FILE})'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 IPTV IP:端口检测与替换工具")
    print("=" * 60)
    print(f"IP源文件: {args.input}")
    print("=" * 60)
    
    # 1. 读取IP:端口列表
    ip_port_list = get_ip_port_list(args.input)
    if not ip_port_list:
        return
    
    # 2. 并发测试所有源
    start_time = time.time()
    valid_ip_ports = find_valid_ip_ports_concurrent(ip_port_list)
    elapsed_time = time.time() - start_time
    
    # 3. 生成输出文件
    generate_output_files(valid_ip_ports)
    
    # 4. 输出统计信息
    print("\n" + "=" * 60)
    print("📊 统计信息:")
    print(f"   - 总耗时: {elapsed_time:.2f} 秒")
    print(f"   - 测试源: {len(SOURCE_CONFIG)} 个")
    found_count = sum(1 for v in valid_ip_ports.values() if v)
    total_valid_ips = sum(len(v) for v in valid_ip_ports.values())
    # 统计唯一IP数量
    unique_ips = set()
    for ip_list in valid_ip_ports.values():
        for ip_port in ip_list:
            unique_ips.add(ip_port.split(':')[0])
    print(f"   - 成功: {found_count}/{len(SOURCE_CONFIG)} 个源")
    print(f"   - 总计找到: {total_valid_ips} 个有效IP:端口组合")
    print(f"   - 唯一IP数: {len(unique_ips)} 个")
    for source_name, ip_list in valid_ip_ports.items():
        if ip_list:
            print(f"     • [{source_name}]: {len(ip_list)} 个")
    print("\n📄 生成的文件:")
    print(f"   - 源文件: {found_count} 个 ({', '.join([SOURCE_CONFIG[k]['output'] for k in valid_ip_ports.keys() if valid_ip_ports[k]])})")
    print(f"   - IP聚合文件: {len(unique_ips)} 个")
    print(f"   - 总汇总文件: all.txt")
    print("=" * 60)


if __name__ == "__main__":
    # 禁用SSL警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    main()
