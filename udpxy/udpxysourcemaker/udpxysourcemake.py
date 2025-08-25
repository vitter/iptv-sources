#!/usr/bin/env python3
"""
UDPXY 源生成器
根据 UDPXY 服务自动生成可播放的 IPTV 源文件

使用方法:
    python3 udpxysourcemake.py IP:PORT [选项]

选项:
    --notest         只测试 UDPXY 服务可用性，不生成源文件
    --test-count N   每个组播文件测试的地址数量（默认20）
    --timeout N      测试超时时间（默认5秒）
    --proxy URL      代理服务器地址 (格式: http://host:port)
    --force-update   强制更新组播文件，即使本地已存在

示例:
    python3 udpxysourcemake.py 192.168.1.100:8098
    python3 udpxysourcemake.py 192.168.1.100:8098 --notest
    python3 udpxysourcemake.py 192.168.1.100:8098 --test-count 10
    python3 udpxysourcemake.py 192.168.1.100:8098 --proxy http://127.0.0.1:10808

项目主页: https://github.com/vitter/iptv-sources
问题反馈: https://github.com/vitter/iptv-sources/issues
"""

import argparse
import os
import re
import requests
import socket
import sys
import time
import json
from pathlib import Path
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class UDPXYSourceMaker:
    def __init__(self, udpxy_server, test_count=20, timeout=5, notest=False, proxy=None, force_update=False, max_workers=5):
        self.udpxy_server = udpxy_server
        self.test_count = test_count
        self.timeout = timeout
        self.notest = notest
        self.proxy = proxy
        self.force_update = force_update
        self.max_workers = max_workers  # 最大线程数
        
        # 线程锁，用于同步输出
        self.print_lock = threading.Lock()
        
        # 解析 UDPXY 服务器地址
        if ':' not in udpxy_server:
            raise ValueError("UDPXY 服务器地址格式错误，应为 IP:PORT")
        
        self.udpxy_ip, self.udpxy_port = udpxy_server.split(':', 1)
        try:
            self.udpxy_port = int(self.udpxy_port)
        except ValueError:
            raise ValueError("端口号必须是数字")
        
        # 设置基础目录
        self.base_dir = Path("multicast_sources")
        self.output_dir = Path("generated_sources")
        
        # 创建目录
        self.base_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
        # 组播源基础URL
        self.base_url = "https://chinaiptv.pages.dev/"
        
        # 省份和运营商映射
        self.provinces = [
            "anhui", "beijing", "chongqing", "fujian", "gansu", "guangdong", 
            "guangxi", "guizhou", "hainan", "hebei", "heilongjiang", "henan", 
            "hubei", "hunan", "jiangsu", "jiangxi", "jilin", "liaoning", 
            "neimenggu", "ningxia", "qinghai", "shan3xi", "shandong", "shanghai", 
            "shanxi", "sichuan", "tianjin", "xinjiang", "xizang", "yunnan", "zhejiang"
        ]
        
        self.isps = ["telecom", "unicom", "mobile"]
        
        # IP归属地查询API
        self.ip_api_url = "http://ip-api.com/json/"
        
        # 配置代理
        self.session = requests.Session()
        if self.proxy:
            self.session.proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
            print(f"使用代理: {self.proxy}")
        
        print(f"初始化 UDPXY 源生成器")
        print(f"UDPXY 服务器: {self.udpxy_server}")
        print(f"测试地址数量: {self.test_count}")
        print(f"超时时间: {self.timeout}秒")
        print(f"最大线程数: {self.max_workers}")
        print(f"仅测试模式: {'是' if self.notest else '否'}")
        print(f"强制更新: {'是' if self.force_update else '否'}")
    
    def test_udpxy_service(self):
        """测试 UDPXY 服务是否可用"""
        print(f"\n==== 测试 UDPXY 服务 {self.udpxy_server} ====")
        
        try:
            # 1. 测试端口连通性
            print(f"1. 测试端口连通性...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((self.udpxy_ip, self.udpxy_port))
            sock.close()
            
            if result != 0:
                print(f"✗ 端口连接失败: {self.udpxy_ip}:{self.udpxy_port}")
                return False
            
            print(f"✓ 端口连接成功")
            
            # 2. 测试 UDPXY 服务
            print(f"2. 测试 UDPXY 服务...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            try:
                sock.connect((self.udpxy_ip, self.udpxy_port))
                
                # 发送HTTP GET请求
                request = f"GET / HTTP/1.1\r\nHost: {self.udpxy_ip}:{self.udpxy_port}\r\nConnection: close\r\nUser-Agent: udpxy-test\r\n\r\n"
                sock.send(request.encode())
                
                # 接收响应
                response = b""
                start_time = time.time()
                
                while True:
                    try:
                        sock.settimeout(2)
                        chunk = sock.recv(1024)
                        if not chunk:
                            break
                        response += chunk
                        
                        if len(response) > 512 or (time.time() - start_time) > 3:
                            break
                            
                    except socket.timeout:
                        break
                
                sock.close()
                
                # 解码响应并检查是否包含udpxy标识
                text = response.decode(errors="ignore")
                text_lower = text.lower()
                
                # udpxy判断标准
                udpxy_indicators = [
                    'server:' in text_lower and 'udpxy' in text_lower,
                    'udpxy' in text_lower and 'unrecognized request' in text_lower,
                    'udpxy' in text_lower and any(version in text_lower for version in ['1.0-', '0.', 'prod', 'standard']),
                    '400' in text_lower and 'unrecognized request' in text_lower and 'server:' in text_lower,
                    'server: udpxy' in text_lower,
                    'udpxy' in text_lower,
                ]
                
                is_udpxy = any(udpxy_indicators)
                
                if is_udpxy:
                    print(f"✓ 确认为 UDPXY 服务")
                    
                    # 3. 获取状态信息
                    print(f"3. 获取 UDPXY 状态...")
                    status_info = self.get_udpxy_status()
                    if status_info.get('status_available'):
                        print(f"✓ UDPXY 状态: 活跃连接 {status_info.get('active_connections', 0)} 个")
                    else:
                        print(f"! UDPXY 状态页面无法访问，但服务可用")
                    
                    return True
                else:
                    print(f"✗ 不是 UDPXY 服务，响应内容: {text[:100]}...")
                    return False
                    
            except Exception as e:
                sock.close()
                print(f"✗ UDPXY 服务测试失败: {e}")
                return False
                
        except Exception as e:
            print(f"✗ UDPXY 服务测试异常: {e}")
            return False
    
    def get_udpxy_status(self):
        """获取 UDPXY 状态信息"""
        try:
            status_url = f"http://{self.udpxy_server}/status"
            response = requests.get(status_url, timeout=self.timeout)
            response.raise_for_status()
            
            html_content = response.text
            
            # 解析HTML页面
            try:
                soup = BeautifulSoup(html_content, "html.parser")
                
                # 查找状态表格
                client_table = soup.find('table', attrs={'cellspacing': '0'})
                
                if client_table:
                    td_tags = client_table.find_all('td')
                    
                    if len(td_tags) >= 4:
                        addr = td_tags[2].text.strip() if len(td_tags) > 2 else "N/A"
                        actv = td_tags[3].text.strip() if len(td_tags) > 3 else "0"
                        
                        try:
                            actv_count = int(actv)
                        except ValueError:
                            actv_count = 0
                        
                        return {
                            'address': addr,
                            'active_connections': actv_count,
                            'status_available': True
                        }
                        
            except Exception as e:
                print(f"状态页面解析失败: {e}")
            
            return {
                'address': "N/A",
                'active_connections': 0,
                'status_available': False
            }
                
        except Exception as e:
            return {
                'address': "N/A", 
                'active_connections': 0,
                'status_available': False,
                'error': f"请求失败: {e}"
            }
    
    def get_ip_location(self):
        """获取IP地址归属地"""
        print(f"\n==== 查询IP归属地 ====")
        try:
            response = self.session.get(f"{self.ip_api_url}{self.udpxy_ip}", timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') == 'success':
                country = data.get('country', '')
                region = data.get('regionName', '')
                city = data.get('city', '')
                isp = data.get('isp', '')
                
                print(f"IP地址: {self.udpxy_ip}")
                print(f"国家: {country}")
                print(f"省份/地区: {region}")
                print(f"城市: {city}")
                print(f"ISP: {isp}")
                
                # 尝试匹配省份
                region_lower = region.lower()
                matched_province = None
                
                # 省份名称映射
                province_mapping = {
                    'anhui': ['anhui', '安徽'],
                    'beijing': ['beijing', '北京'],
                    'chongqing': ['chongqing', '重庆'],
                    'fujian': ['fujian', '福建'],
                    'gansu': ['gansu', '甘肃'],
                    'guangdong': ['guangdong', '广东'],
                    'guangxi': ['guangxi', '广西'],
                    'guizhou': ['guizhou', '贵州'],
                    'hainan': ['hainan', '海南'],
                    'hebei': ['hebei', '河北'],
                    'heilongjiang': ['heilongjiang', '黑龙江'],
                    'henan': ['henan', '河南'],
                    'hubei': ['hubei', '湖北'],
                    'hunan': ['hunan', '湖南'],
                    'jiangsu': ['jiangsu', '江苏'],
                    'jiangxi': ['jiangxi', '江西'],
                    'jilin': ['jilin', '吉林'],
                    'liaoning': ['liaoning', '辽宁'],
                    'neimenggu': ['inner mongolia', 'neimenggu', '内蒙古'],
                    'ningxia': ['ningxia', '宁夏'],
                    'qinghai': ['qinghai', '青海'],
                    'shan3xi': ['shan3xi', 'shaanxi', '陕西'],
                    'shandong': ['shandong', '山东'],
                    'shanghai': ['shanghai', '上海'],
                    'shanxi': ['shanxi', '山西'],
                    'sichuan': ['sichuan', '四川'],
                    'tianjin': ['tianjin', '天津'],
                    'xinjiang': ['xinjiang', '新疆'],
                    'xizang': ['tibet', 'xizang', '西藏'],
                    'yunnan': ['yunnan', '云南'],
                    'zhejiang': ['zhejiang', '浙江']
                }
                
                for province, aliases in province_mapping.items():
                    for alias in aliases:
                        if alias in region_lower:
                            matched_province = province
                            break
                    if matched_province:
                        break
                
                if matched_province:
                    print(f"匹配省份: {matched_province}")
                    return matched_province
                else:
                    print(f"未能匹配到已知省份，将测试所有省份")
                    return None
                    
            else:
                print(f"IP归属地查询失败: {data.get('message', '未知错误')}")
                return None
                
        except Exception as e:
            print(f"IP归属地查询异常: {e}")
            return None
    
    def fetch_multicast_index(self):
        """获取组播源网站的省份和运营商列表"""
        print(f"\n==== 获取组播源列表 ====")
        try:
            response = self.session.get(self.base_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 查找表格中的链接
            links = soup.find_all('a', href=True)
            multicast_links = []
            seen_combinations = set()  # 用于去重
            
            for link in links:
                href = link.get('href', '')
                if 'Multicast/' in href and href.endswith('.txt'):
                    # 解析省份和运营商
                    # 例如: Multicast/anhui/telecom.txt
                    parts = href.split('/')
                    if len(parts) >= 3:
                        province = parts[-2].lower()
                        isp_file = parts[-1].lower()
                        isp = isp_file.replace('.txt', '')
                        
                        # 创建唯一标识符进行去重
                        combination_key = f"{province}_{isp}"
                        
                        if province in self.provinces and isp in self.isps and combination_key not in seen_combinations:
                            seen_combinations.add(combination_key)
                            full_url = urljoin(self.base_url, href)
                            multicast_links.append({
                                'province': province,
                                'isp': isp,
                                'url': full_url,
                                'filename': f"{province}_{isp}.txt"
                            })
            
            print(f"发现 {len(multicast_links)} 个组播源文件")
            return multicast_links
            
        except Exception as e:
            print(f"获取组播源列表失败: {e}")
            return []
    
    def download_multicast_file(self, multicast_info):
        """下载单个组播文件"""
        try:
            province = multicast_info['province']
            isp = multicast_info['isp']
            url = multicast_info['url']
            filename = multicast_info['filename']
            
            # 创建目录
            target_dir = self.base_dir / province
            target_dir.mkdir(exist_ok=True)
            
            target_file = target_dir / f"{isp}.txt"
            
            # 检查是否需要下载
            should_download = self.force_update or not target_file.exists() or target_file.stat().st_size == 0
            
            if not should_download:
                # 检查文件是否需要更新（比较远程文件大小或最后修改时间）
                try:
                    # 发送HEAD请求获取远程文件信息
                    head_response = self.session.head(url, timeout=10)
                    if head_response.status_code == 200:
                        remote_size = head_response.headers.get('content-length')
                        if remote_size:
                            remote_size = int(remote_size)
                            local_size = target_file.stat().st_size
                            if remote_size != local_size:
                                print(f"  检测到文件大小变化，需要更新: {province}/{isp}.txt")
                                should_download = True
                except Exception as e:
                    print(f"  无法检查远程文件信息，使用本地文件: {province}/{isp}.txt")
            
            if not should_download:
                print(f"  跳过已存在的文件: {province}/{isp}.txt")
                return str(target_file)
            
            print(f"  下载: {province}/{isp}.txt")
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # 保存文件
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            return str(target_file)
            
        except Exception as e:
            print(f"  下载失败 {multicast_info['filename']}: {e}")
            return None
    
    def download_all_multicast_files(self):
        """下载所有组播文件"""
        print(f"\n==== 下载组播源文件 ====")
        
        multicast_links = self.fetch_multicast_index()
        if not multicast_links:
            print("未找到组播源文件")
            # 如果无法获取在线列表，尝试使用本地已有的文件
            return self.get_local_multicast_files()
        
        downloaded_files = []
        
        for i, multicast_info in enumerate(multicast_links, 1):
            print(f"[{i}/{len(multicast_links)}] ", end="")
            file_path = self.download_multicast_file(multicast_info)
            if file_path:
                downloaded_files.append({
                    'path': file_path,
                    'province': multicast_info['province'],
                    'isp': multicast_info['isp']
                })
        
        print(f"成功下载 {len(downloaded_files)} 个组播文件")
        return downloaded_files
    
    def get_local_multicast_files(self):
        """获取本地已有的组播文件"""
        print("尝试使用本地已有的组播文件...")
        local_files = []
        
        if not self.base_dir.exists():
            return local_files
        
        for province_dir in self.base_dir.iterdir():
            if province_dir.is_dir() and province_dir.name in self.provinces:
                for isp_file in province_dir.glob("*.txt"):
                    isp_name = isp_file.stem
                    if isp_name in self.isps:
                        local_files.append({
                            'path': str(isp_file),
                            'province': province_dir.name,
                            'isp': isp_name
                        })
        
        print(f"找到 {len(local_files)} 个本地组播文件")
        return local_files
    
    def parse_multicast_file(self, file_path):
        """解析组播文件，提取频道信息"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            channels = []
            current_group = ""
            
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                # 检查是否是分组标识
                if line.endswith(',#genre#'):
                    current_group = line.replace(',#genre#', '')
                    continue
                
                # 检查是否是频道信息
                if ',' in line and ('rtp://' in line or 'udp://' in line):
                    parts = line.split(',', 1)
                    if len(parts) == 2:
                        channel_name = parts[0].strip()
                        channel_url = parts[1].strip()
                        
                        # 提取组播地址
                        if channel_url.startswith('rtp://') or channel_url.startswith('udp://'):
                            # 移除协议前缀
                            multicast_addr = channel_url.replace('rtp://', '').replace('udp://', '')
                            
                            channels.append({
                                'name': channel_name,
                                'group': current_group,
                                'multicast': multicast_addr,
                                'original_url': channel_url
                            })
            
            return channels
            
        except Exception as e:
            print(f"解析组播文件失败 {file_path}: {e}")
            return []
    
    def safe_print(self, message):
        """线程安全的打印函数"""
        with self.print_lock:
            print(message)
    
    def test_multicast_stream_with_result(self, channel, channel_index, total_channels):
        """测试单个组播流并返回详细结果（多线程版本）"""
        try:
            # 构建 UDPXY URL
            udpxy_url = f"http://{self.udpxy_server}/udp/{channel['multicast']}"
            
            # 创建请求会话
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'IPTV-Test/1.0',
                'Accept': '*/*',
                'Connection': 'keep-alive'
            })
            
            # 尝试下载流数据
            start_time = time.time()
            max_download_size = 100 * 1024  # 100KB
            max_download_time = 3  # 3秒
            downloaded_data = b''
            
            try:
                response = session.get(
                    udpxy_url,
                    timeout=(3, 5),
                    stream=True,
                    allow_redirects=True
                )
                
                if response.status_code != 200:
                    return {
                        'channel': channel,
                        'index': channel_index,
                        'success': False,
                        'error': f"HTTP {response.status_code}",
                        'duration': time.time() - start_time
                    }
                
                # 流式下载数据
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_data += chunk
                        
                        current_size = len(downloaded_data)
                        elapsed_time = time.time() - start_time
                        
                        # 超过大小限制
                        if current_size >= max_download_size:
                            break
                            
                        # 超过时间限制
                        if elapsed_time > max_download_time:
                            break
                
                # 检查下载结果
                total_size = len(downloaded_data)
                total_duration = time.time() - start_time
                
                if total_size > 1024 and total_duration > 0:  # 至少下载1KB
                    speed = (total_size / total_duration) / 1024  # KB/s
                    if speed > 10:  # 速度至少10KB/s
                        return {
                            'channel': channel,
                            'index': channel_index,
                            'success': True,
                            'size': total_size,
                            'speed': speed,
                            'duration': total_duration
                        }
                
                return {
                    'channel': channel,
                    'index': channel_index,
                    'success': False,
                    'error': f"数据不足 ({total_size}B) 或速度过慢",
                    'duration': total_duration
                }
                
            except Exception as e:
                return {
                    'channel': channel,
                    'index': channel_index,
                    'success': False,
                    'error': str(e),
                    'duration': time.time() - start_time
                }
                
        except Exception as e:
            return {
                'channel': channel,
                'index': channel_index,
                'success': False,
                'error': str(e),
                'duration': 0
            }
    
    def test_multicast_stream(self, multicast_addr):
        """测试单个组播流（兼容性方法）"""
        dummy_channel = {'multicast': multicast_addr, 'name': 'test'}
        result = self.test_multicast_stream_with_result(dummy_channel, 0, 1)
        return result['success']

    def test_multicast_file(self, file_info):
        """测试单个组播文件（多线程版本）"""
        self.safe_print(f"\n测试 {file_info['province']}/{file_info['isp']}.txt")
        
        channels = self.parse_multicast_file(file_info['path'])
        if not channels:
            self.safe_print(f"  解析失败或无有效频道")
            return False
        
        self.safe_print(f"  解析到 {len(channels)} 个频道")
        
        # 取前N个频道进行测试
        test_channels = channels[:self.test_count]
        self.safe_print(f"  使用 {self.max_workers} 个线程并行测试前 {len(test_channels)} 个频道...")
        
        success_count = 0
        first_success = None
        
        # 使用线程池并行测试
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_channel = {
                executor.submit(self.test_multicast_stream_with_result, channel, i, len(test_channels)): channel
                for i, channel in enumerate(test_channels, 1)
            }
            
            # 处理完成的任务
            completed_tasks = 0
            for future in as_completed(future_to_channel):
                completed_tasks += 1
                try:
                    result = future.result()
                    
                    if result['success']:
                        success_count += 1
                        if first_success is None:
                            first_success = result
                        
                        self.safe_print(
                            f"    [{result['index']}/{len(test_channels)}] ✓ {result['channel']['name']} "
                            f"({result['channel']['multicast']}) - "
                            f"{result['size']/1024:.1f}KB, {result['speed']:.1f}KB/s"
                        )
                        
                        # 找到一个可用的就可以认为文件可用，但继续完成其他正在进行的测试
                        if first_success and completed_tasks >= min(3, len(test_channels)):
                            # 取消剩余任务
                            for f in future_to_channel:
                                if not f.done():
                                    f.cancel()
                            break
                    else:
                        self.safe_print(
                            f"    [{result['index']}/{len(test_channels)}] ✗ {result['channel']['name']} "
                            f"({result['channel']['multicast']}) - {result['error']}"
                        )
                        
                except Exception as e:
                    self.safe_print(f"    测试异常: {e}")
        
        if success_count > 0:
            self.safe_print(f"  ✓ 文件可用 (成功 {success_count}/{len(test_channels)})")
            return True
        else:
            self.safe_print(f"  ✗ 文件不可用 (成功 0/{len(test_channels)})")
            return False
    
    def find_working_multicast_file(self, downloaded_files, preferred_province=None):
        """查找可用的组播文件"""
        print(f"\n==== 测试组播文件 ====")
        
        if not downloaded_files:
            print("没有组播文件可测试")
            return None
        
        # 根据省份优先级排序
        if preferred_province:
            print(f"优先测试 {preferred_province} 省份的文件")
            # 将首选省份的文件排在前面
            preferred_files = [f for f in downloaded_files if f['province'] == preferred_province]
            other_files = [f for f in downloaded_files if f['province'] != preferred_province]
            test_order = preferred_files + other_files
        else:
            test_order = downloaded_files
        
        print(f"总共需要测试 {len(test_order)} 个文件")
        
        for i, file_info in enumerate(test_order, 1):
            print(f"\n[{i}/{len(test_order)}] ", end="")
            
            if self.test_multicast_file(file_info):
                print(f"\n找到可用的组播文件: {file_info['province']}/{file_info['isp']}.txt")
                return file_info
        
        print(f"\n未找到任何可用的组播文件")
        return None
    
    def generate_txt_source(self, working_file, output_path):
        """生成 TXT 格式的 IPTV 源文件"""
        try:
            channels = self.parse_multicast_file(working_file['path'])
            if not channels:
                return False
            
            with open(output_path, 'w', encoding='utf-8') as f:
                current_group = ""
                
                for channel in channels:
                    # 写入分组
                    if channel['group'] != current_group:
                        current_group = channel['group']
                        f.write(f"{current_group},#genre#\n")
                    
                    # 写入频道
                    udpxy_url = f"http://{self.udpxy_server}/udp/{channel['multicast']}"
                    f.write(f"{channel['name']},{udpxy_url}\n")
            
            print(f"生成 TXT 源文件: {output_path}")
            return True
            
        except Exception as e:
            print(f"生成 TXT 源文件失败: {e}")
            return False
    
    def generate_m3u_source(self, working_file, output_path):
        """生成 M3U 格式的 IPTV 源文件"""
        try:
            channels = self.parse_multicast_file(working_file['path'])
            if not channels:
                return False
            
            with open(output_path, 'w', encoding='utf-8') as f:
                # 写入M3U头
                f.write('#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"\n')
                
                for channel in channels:
                    # 生成logo URL
                    logo_url = f"https://live.fanmingming.com/tv/{channel['name']}.png"
                    
                    # 写入频道信息
                    f.write(f'#EXTINF:-1 tvg-name="{channel["name"]}" tvg-logo="{logo_url}" group-title="{channel["group"]}",{channel["name"]}\n')
                    
                    # 写入播放地址
                    udpxy_url = f"http://{self.udpxy_server}/udp/{channel['multicast']}"
                    f.write(f"{udpxy_url}\n")
            
            print(f"生成 M3U 源文件: {output_path}")
            return True
            
        except Exception as e:
            print(f"生成 M3U 源文件失败: {e}")
            return False
    
    def generate_sources(self, working_file):
        """生成 IPTV 源文件"""
        print(f"\n==== 生成 IPTV 源文件 ====")
        
        # 生成文件名
        base_name = f"{working_file['province']}_{working_file['isp']}_{self.udpxy_ip}_{self.udpxy_port}"
        txt_file = self.output_dir / f"{base_name}.txt"
        m3u_file = self.output_dir / f"{base_name}.m3u"
        
        success_count = 0
        
        # 生成 TXT 格式
        if self.generate_txt_source(working_file, txt_file):
            success_count += 1
        
        # 生成 M3U 格式
        if self.generate_m3u_source(working_file, m3u_file):
            success_count += 1
        
        if success_count > 0:
            print(f"\n✓ 成功生成 {success_count} 个源文件")
            print(f"基于模板: {working_file['province']}/{working_file['isp']}.txt")
            
            # 显示文件信息
            if txt_file.exists():
                print(f"TXT 文件: {txt_file} ({txt_file.stat().st_size} 字节)")
            if m3u_file.exists():
                print(f"M3U 文件: {m3u_file} ({m3u_file.stat().st_size} 字节)")
        else:
            print(f"✗ 生成源文件失败")
    
    def run(self):
        """主运行函数"""
        print(f"开始处理 UDPXY 服务器: {self.udpxy_server}")
        
        # 1. 测试 UDPXY 服务
        if not self.test_udpxy_service():
            print(f"\n✗ UDPXY 服务不可用，程序退出")
            return False
        
        print(f"\n✓ UDPXY 服务可用")
        
        # 如果只是测试模式，到此结束
        if self.notest:
            print(f"\n仅测试模式完成")
            return True
        
        # 2. 查询IP归属地
        preferred_province = self.get_ip_location()
        
        # 3. 下载组播文件
        downloaded_files = self.download_all_multicast_files()
        if not downloaded_files:
            print(f"\n✗ 没有可用的组播文件")
            return False
        
        # 4. 测试组播文件
        working_file = self.find_working_multicast_file(downloaded_files, preferred_province)
        if not working_file:
            print(f"\n✗ 没有找到可用的组播文件")
            return False
        
        # 5. 生成源文件
        self.generate_sources(working_file)
        
        print(f"\n🎉 处理完成！")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="UDPXY 源生成器 - 根据 UDPXY 服务自动生成可播放的 IPTV 源文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 udpxysourcemake.py 192.168.1.100:8098
  python3 udpxysourcemake.py 192.168.1.100:8098 --notest
  python3 udpxysourcemake.py 192.168.1.100:8098 --test-count 10 --timeout 3
  python3 udpxysourcemake.py 192.168.1.100:8098 --proxy http://127.0.0.1:10808
  python3 udpxysourcemake.py 192.168.1.100:8098 --max-workers 10
        """
    )
    
    parser.add_argument('udpxy_server', help='UDPXY 服务器地址 (格式: IP:PORT)')
    parser.add_argument('--notest', action='store_true', help='只测试 UDPXY 服务可用性，不生成源文件')
    parser.add_argument('--test-count', type=int, default=20, help='每个组播文件测试的地址数量 (默认: 20)')
    parser.add_argument('--timeout', type=int, default=5, help='测试超时时间，秒 (默认: 5)')
    parser.add_argument('--proxy', help='代理服务器地址 (格式: http://host:port)')
    parser.add_argument('--force-update', action='store_true', help='强制更新组播文件，即使本地已存在')
    parser.add_argument('--max-workers', type=int, default=5, help='最大并发线程数 (默认: 5)')
    
    args = parser.parse_args()
    
    try:
        maker = UDPXYSourceMaker(
            udpxy_server=args.udpxy_server,
            test_count=args.test_count,
            timeout=args.timeout,
            notest=args.notest,
            proxy=args.proxy,
            force_update=args.force_update,
            max_workers=args.max_workers
        )
        
        success = maker.run()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print(f"\n用户中断程序")
        sys.exit(1)
    except Exception as e:
        print(f"\n程序运行异常: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
