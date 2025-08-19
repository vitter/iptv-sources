#!/usr/bin/env python3
"""
Censys IP信息获取工具
从censys.txt文件读取IP地址，通过Censys平台获取UDPXY服务信息

项目主页: https://github.com/vitter/iptv-sources
问题反馈: https://github.com/vitter/iptv-sources/issues
"""

import os
import re
import csv
import json
import time
import requests
from pathlib import Path
from urllib.parse import urljoin
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_env_file(env_path=".env"):
    """加载环境变量文件"""
    config = {}
    if not os.path.exists(env_path):
        return config
        
    with open(env_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 支持多行字符串的正则模式
    patterns = [
        # 双引号包围的多行字符串
        r'([A-Z_]+)\s*=\s*"([^"]*(?:\\"[^"]*)*)"',
        # 单引号包围的多行字符串  
        r"([A-Z_]+)\s*=\s*'([^']*(?:\\'[^']*)*)'",
        # 无引号的单行字符串
        r'([A-Z_]+)\s*=\s*([^"\'\n\r]+)'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
        for key, value in matches:
            key = key.strip()
            value = value.strip()
            # 处理转义字符
            value = value.replace('\\"', '"').replace("\\'", "'")
            # 移除末尾的空白字符
            value = value.rstrip()
            config[key] = value
            # 同时设置到环境变量
            os.environ[key] = value
    
    return config


def extract_json_data(html_content):
    """从HTML内容中提取JSON数据"""
    try:
        # 首先尝试解析整个响应为JSON（如果是纯JSON响应）
        try:
            data = json.loads(html_content)
            if isinstance(data, dict) and ('host' in data or 'services' in data):
                return data
        except json.JSONDecodeError:
            pass
        
        # 查找包含端口信息的JSON数据
        # 通常在script标签或data属性中
        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__NUXT__\s*=\s*({.*?});',
            r'data-props="([^"]*)"',
            r'data-page="([^"]*)"',
            r'"host":\s*({.*?"services".*?})',  # 匹配包含host和services的完整对象
            r'({.*?"services":\s*\[.*?\].*?})',  # 匹配包含services数组的对象
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL)
            for match in matches:
                try:
                    # 如果是HTML编码的JSON，需要解码
                    if match.startswith('&quot;'):
                        match = match.replace('&quot;', '"').replace('&amp;', '&')
                    
                    data = json.loads(match)
                    # 检查是否包含我们需要的数据
                    if isinstance(data, dict) and ('services' in data or 'ports' in data or 'port' in data):
                        return data
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and ('port' in item or 'protocol' in item):
                                return {'services': data}
                except json.JSONDecodeError:
                    continue
        
        # 如果没有找到结构化JSON，尝试直接搜索端口信息
        # 改进的端口搜索模式
        port_patterns = [
            # 在JSON结构中搜索udpxy相关的端口
            r'"port":\s*(\d+)[^}]*"vendor":\s*"udpxy"',
            r'"vendor":\s*"udpxy"[^}]*"port":\s*(\d+)',
            r'"port":\s*(\d+)[^}]*"product":\s*"udpxy"',
            r'"product":\s*"udpxy"[^}]*"port":\s*(\d+)',
            # 查找Server头中的udpxy信息对应的端口
            r'"port":\s*(\d+)[^}]*"Server"[^}]*"udpxy',
            r'"Server"[^}]*"udpxy[^}]*"port":\s*(\d+)',
            # 通用模式
            r'udpxy.*?port["\s:]*(\d+)',
            r'(\d+).*?udpxy',
        ]
        
        ports = []
        for pattern in port_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
            for match in matches:
                try:
                    port = int(match)
                    if 1000 <= port <= 65535:  # 有效端口范围
                        ports.append(port)
                except ValueError:
                    continue
        
        if ports:
            return {'udpxy_ports': list(set(ports))}
            
    except Exception as e:
        logger.error(f"提取JSON数据时出错: {e}")
    
    return None


def extract_host_info(html_content):
    """从HTML内容中提取主机的详细信息"""
    info = {
        'dns': '',
        'country': '',
        'city': '',
        'province': '',
        'isp': ''
    }
    
    try:
        # 方法1: 从JSON数据中提取信息
        json_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.__NUXT__\s*=\s*({.*?});',
            r'data-props="([^"]*)"',
            r'({.*?"ip".*?"location".*?})',
            r'({.*?"dns".*?"location".*?})',
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL)
            for match in matches:
                try:
                    # 如果是HTML编码的JSON，需要解码
                    if match.startswith('&quot;'):
                        match = match.replace('&quot;', '"').replace('&amp;', '&')
                    
                    # 尝试解析JSON
                    data = json.loads(match)
                    
                    # 提取DNS信息
                    if not info['dns']:
                        if 'dns' in data and 'names' in data['dns']:
                            names = data['dns']['names']
                            if names and len(names) > 0:
                                info['dns'] = names[0]
                    
                    # 提取地理位置信息
                    if 'location' in data:
                        location = data['location']
                        if 'country' in location:
                            info['country'] = location['country']
                        if 'city' in location:
                            info['city'] = location['city']
                        if 'province' in location:
                            info['province'] = location['province']
                    
                    # 提取运营商信息
                    if 'whois' in data and 'network' in data['whois']:
                        network = data['whois']['network']
                        if 'name' in network:
                            info['isp'] = network['name']
                    
                except (json.JSONDecodeError, KeyError):
                    continue
        
        # 方法2: 如果JSON解析失败，使用正则表达式
        if not info['dns']:
            dns_patterns = [
                r'"dns":\s*\{[^}]*"names":\s*\[\s*"([^"]+)"',
                r'"forward_dns":[^}]*"([^"]+\.[a-zA-Z]{2,})"',
                r'"hostname":\s*"([^"]+)"'
            ]
            for pattern in dns_patterns:
                match = re.search(pattern, html_content)
                if match:
                    info['dns'] = match.group(1)
                    break
        
        if not info['country']:
            country_pattern = r'"country":\s*"([^"]+)"'
            match = re.search(country_pattern, html_content)
            if match:
                info['country'] = match.group(1)
        
        if not info['city']:
            city_pattern = r'"city":\s*"([^"]+)"'
            match = re.search(city_pattern, html_content)
            if match:
                info['city'] = match.group(1)
        
        if not info['province']:
            province_pattern = r'"province":\s*"([^"]+)"'
            match = re.search(province_pattern, html_content)
            if match:
                info['province'] = match.group(1)
        
        if not info['isp']:
            isp_patterns = [
                r'"whois":[^}]*"network":[^}]*"name":\s*"([^"]+)"',
                r'"network":[^}]*"name":\s*"([^"]+)"'
            ]
            for pattern in isp_patterns:
                match = re.search(pattern, html_content)
                if match:
                    info['isp'] = match.group(1)
                    break
        
        return info
        
    except Exception as e:
        logger.debug(f"提取主机信息时出错: {e}")
        return info


def extract_forward_dns(html_content):
    """从HTML内容中提取Forward DNS信息（兼容性函数）"""
    host_info = extract_host_info(html_content)
    return host_info['dns']


def extract_udpxy_info(html_content, ip):
    """从HTML内容中提取UDPXY相关信息"""
    udpxy_info = {
        'ports': [],
        'urls': [],
        'dns': '',
        'country': '',
        'city': '',
        'province': '',
        'isp': ''
    }
    
    try:
        # 提取主机详细信息
        host_info = extract_host_info(html_content)
        udpxy_info.update(host_info)
        
        # 提取JSON数据
        json_data = extract_json_data(html_content)
        
        if json_data:
            # 从JSON数据中提取端口信息
            services = []
            
            # 处理不同的JSON结构
            if 'host' in json_data and 'services' in json_data['host']:
                # Censys API的标准响应格式
                services = json_data['host']['services']
            elif 'services' in json_data:
                # 直接包含services的格式
                services = json_data['services']
            
            # 遍历所有服务
            for service in services:
                if isinstance(service, dict):
                    port = service.get('port')
                    software = service.get('software', [])
                    
                    # 检查是否是udpxy服务
                    for sw in software:
                        if isinstance(sw, dict) and (
                            sw.get('vendor', '').lower() == 'udpxy' or 
                            sw.get('product', '').lower() == 'udpxy'
                        ):
                            if port and port not in udpxy_info['ports']:
                                udpxy_info['ports'].append(port)
                                udpxy_info['urls'].append(f"http://{ip}:{port}")
                                logger.info(f"  从JSON中发现UDPXY服务: 端口 {port}")
                            break
            
            # 如果有udpxy_ports字段（从正则提取的）
            if 'udpxy_ports' in json_data:
                for port in json_data['udpxy_ports']:
                    if port not in udpxy_info['ports']:
                        udpxy_info['ports'].append(port)
                        udpxy_info['urls'].append(f"http://{ip}:{port}")
                        logger.info(f"  从正则表达式发现UDPXY服务: 端口 {port}")
        
        # 如果没有从JSON中找到，尝试直接从HTML中搜索
        if not udpxy_info['ports']:
            # 搜索udpxy相关的端口信息
            port_patterns = [
                r'udpxy.*?(\d{4,5})',
                r'(\d{4,5}).*?udpxy',
                r'"port":\s*(\d+).*?udpxy',
                r'udpxy.*?"port":\s*(\d+)',
            ]
            
            for pattern in port_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    port = int(match)
                    if 1000 <= port <= 65535 and port not in udpxy_info['ports']:
                        udpxy_info['ports'].append(port)
                        udpxy_info['urls'].append(f"http://{ip}:{port}")
        
        # 提取Forward DNS
        udpxy_info['dns'] = extract_forward_dns(html_content)
        
    except Exception as e:
        logger.error(f"提取UDPXY信息时出错: {e}")
    
    return udpxy_info


def fetch_censys_data(ip, session):
    """获取指定IP的Censys数据"""
    try:
        # 使用Censys平台的API端点（与浏览器访问相同的端点）
        url = f"https://platform.censys.io/hosts/{ip}?_data=routes/hosts.$id"
        
        # 添加更多随机化的头信息来绕过检测
        session.headers.update({
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
        })
        
        response = session.get(url, timeout=30)
        
        logger.info(f"请求状态码: {response.status_code} for IP {ip}")
        logger.info(f"响应头: {dict(response.headers)}")
        logger.info(f"响应前200字符: {response.text[:200]}")
        
        if response.status_code == 200:
            # 简单粗暴地只保留ASCII字符，忽略所有Unicode字符
            content = response.text
            # 只保留ASCII字符，其他字符用空格替换
            content = ''.join(char if ord(char) < 128 else ' ' for char in content)
            
            # 检查是否遇到Cloudflare挑战
            if "Just a moment" in content or "cf-mitigated" in str(response.headers):
                logger.warning(f"遇到Cloudflare防护 for IP {ip} - 需要更新cookie或增加延迟")
                return None
            
            logger.info(f"成功获取 {ip} 的数据，状态码: {response.status_code}")
            return content
            
        elif response.status_code == 403:
            logger.warning(f"访问被拒绝 (403) for IP {ip} - cookie可能过期")
            return None
        elif response.status_code == 429:
            logger.warning(f"请求限制 (429) for IP {ip} - 需要增加延迟")
            # 对于429错误，额外等待更长时间
            retry_after = int(response.headers.get('retry-after', '30'))
            extra_delay = min(60, max(15, retry_after))
            logger.info(f"⏰ 遇到频率限制，等待 {extra_delay} 秒后继续...")
            try:
                time.sleep(extra_delay)
            except KeyboardInterrupt:
                logger.info("⏹️ 用户中断延迟等待")
                raise
            return None
        else:
            logger.warning(f"未知状态码 {response.status_code} for IP {ip}")
            return None
        
    except requests.exceptions.RequestException as e:
        logger.error(f"请求 {ip} 失败: {e}")
        return None
    except Exception as e:
        logger.error(f"处理 {ip} 时发生未知错误: {e}")
        return None


def write_to_csv(csv_path, ip, port, url, dns, country='', city='', province='', isp=''):
    """将数据写入CSV文件"""
    file_exists = csv_path.exists()
    
    # 简单粗暴地过滤所有非ASCII字符
    def clean_text(text):
        if isinstance(text, str):
            return ''.join(char if ord(char) < 128 else ' ' for char in text)
        return str(text)
    
    # 清理所有字段
    ip = clean_text(ip)
    port = clean_text(str(port))
    url = clean_text(url)
    dns = clean_text(dns)
    country = clean_text(country)
    city = clean_text(city)
    province = clean_text(province)
    isp = clean_text(isp)
    
    with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        
        # 如果文件不存在，写入标题行
        if not file_exists:
            writer.writerow(['ip', 'port', 'url', 'dns', 'country', 'city', 'province', 'isp'])
        
        writer.writerow([ip, port, url, dns, country, city, province, isp])


def main():
    """主函数"""
    import argparse
    
    # 命令行参数解析
    parser = argparse.ArgumentParser(description='Censys IP信息获取工具')
    parser.add_argument('--input', '-i', default='censys.txt', 
                       help='输入文件路径 (默认: censys.txt)')
    parser.add_argument('--output', '-o', default='censys.csv',
                       help='输出CSV文件路径 (默认: censys.csv)')
    parser.add_argument('--delay', '-d', type=float, default=2.0,
                       help='请求间隔时间(秒) (默认: 2.0)')
    parser.add_argument('--proxy', '-p', type=str, default=None,
                       help='代理服务器 (格式: http://ip:port 或 socks5://ip:port)')
    args = parser.parse_args()
    
    # 加载环境变量
    load_env_file()
    
    # 获取必要的配置
    cookie = os.getenv('CENSYS_COOKIE', '')
    user_agent = os.getenv('CENSYS_USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0')
    
    if not cookie:
        logger.error("请在.env文件中配置CENSYS_COOKIE")
        return
    
    # 清理cookie中的非ASCII字符，防止编码问题
    cookie = ''.join(char if ord(char) < 128 else '' for char in cookie)
    user_agent = ''.join(char if ord(char) < 128 else '' for char in user_agent)
    
    # 设置文件路径
    input_file = Path(args.input)
    output_file = Path(args.output)
    
    if not input_file.exists():
        logger.error(f"输入文件 {input_file} 不存在")
        return
    
    # 读取IP列表
    with open(input_file, 'r', encoding='utf-8') as f:
        ips = [line.strip() for line in f if line.strip()]
    
    logger.info(f"共找到 {len(ips)} 个IP地址")
    
    # 创建会话，使用Firefox浏览器特征（匹配用户的浏览器）
    session = requests.Session()
    session.headers.update({
        'User-Agent': user_agent,
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Cookie': cookie,
        'Connection': 'keep-alive',
        'Host': 'platform.censys.io',
        'Priority': 'u=4',
        'Referer': 'https://platform.censys.io/home',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'TE': 'trailers',
        # 添加Cloudflare需要的Client Hints头
        'Sec-CH-UA': '"Firefox";v="141", " Not A;Brand";v="99", "Mozilla";v="141"',
        'Sec-CH-UA-Mobile': '?0',
        'Sec-CH-UA-Platform': '"Linux"',
        'Sec-CH-UA-Arch': '"x86"',
        'Sec-CH-UA-Bitness': '"64"',
        'Sec-CH-UA-Full-Version': '"141.0"',
        'Sec-CH-UA-Platform-Version': '"6.5.0"',
        'Sec-CH-UA-Full-Version-List': '"Firefox";v="141.0", " Not A;Brand";v="99.0.0.0", "Mozilla";v="141.0"',
    })
    
    # 配置代理（如果提供了代理参数）
    if args.proxy:
        proxy_dict = {
            'http': args.proxy,
            'https': args.proxy
        }
        session.proxies.update(proxy_dict)
        logger.info(f"🌐 使用代理: {args.proxy}")
        
        # 简化的代理测试（避免暴露代理使用痕迹）
        try:
            # 只做一个简单的连接测试，不获取IP信息
            test_response = session.head('https://www.google.com', timeout=5)
            if test_response.status_code in [200, 301, 302]:
                logger.info(f"✅ 代理连接正常")
            else:
                logger.warning("⚠️ 代理测试失败，但将继续尝试")
        except Exception as e:
            logger.warning(f"⚠️ 代理连接异常: {e}，但将继续尝试")
    else:
        logger.info("🔗 使用直接连接（无代理）")
    
    # 处理每个IP
    processed_count = 0
    success_count = 0
    
    for i, ip in enumerate(ips, 1):
        logger.info(f"处理 IP {i}/{len(ips)}: {ip}")
        
        try:
            # 获取数据
            html_content = fetch_censys_data(ip, session)
            
            if html_content:
                # 提取UDPXY信息
                udpxy_info = extract_udpxy_info(html_content, ip)
                
                if udpxy_info['ports']:
                    # 为每个端口写入一行数据
                    for j, (port, url) in enumerate(zip(udpxy_info['ports'], udpxy_info['urls'])):
                        write_to_csv(output_file, ip, port, url, udpxy_info['dns'], 
                                   udpxy_info['country'], udpxy_info['city'], 
                                   udpxy_info['province'], udpxy_info['isp'])
                        logger.info(f"  发现UDPXY服务: {url} (DNS: {udpxy_info['dns']}, {udpxy_info['city']}, {udpxy_info['country']})")
                        success_count += 1
                else:
                    # 即使没有找到UDPXY服务，也记录IP和其他信息
                    write_to_csv(output_file, ip, '', '', udpxy_info['dns'],
                               udpxy_info['country'], udpxy_info['city'], 
                               udpxy_info['province'], udpxy_info['isp'])
                    logger.info(f"  未发现UDPXY服务 (DNS: {udpxy_info['dns']}, {udpxy_info['city']}, {udpxy_info['country']})")
            else:
                # 请求失败，记录IP
                write_to_csv(output_file, ip, '', '', '', '', '', '', '')
                logger.warning(f"  请求失败")
            
            processed_count += 1
            
            # 添加延迟，避免请求过于频繁
            if i < len(ips):
                logger.info(f"⏰ 等待 {args.delay} 秒后处理下一个IP...")
                try:
                    time.sleep(args.delay)
                except KeyboardInterrupt:
                    logger.info("⏹️ 用户中断程序")
                    break
                
        except Exception as e:
            logger.error(f"处理 {ip} 时出错: {e}")
            # 即使出错也记录IP
            write_to_csv(output_file, ip, '', '', '', '', '', '', '')
            continue
    
    logger.info(f"处理完成！共处理 {processed_count}/{len(ips)} 个IP，发现 {success_count} 个UDPXY服务")
    logger.info(f"结果已保存到: {output_file}")


if __name__ == "__main__":
    main()
