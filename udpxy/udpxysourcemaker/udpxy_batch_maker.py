#!/usr/bin/env python3
"""
UDPXY 批量源生成器 (增强版)
支持从URL或本地文件批量导入UDPXY代理，使用ffmpeg-python进行流测试

使用方法:
    python3 udpxy_batch_maker.py --iplistfile <URL或文件路径> [选项]

选项:
    --iplistfile URL   IP列表URL或本地文件路径（默认: https://tv1288.xyz/ip.php）
    --notest           只测试 UDPXY 服务可用性，不生成源文件
    --test-count N     每个组播文件测试的地址数量（默认20）
    --timeout N        测试超时时间（默认5秒）
    --proxy URL        代理服务器地址 (格式: http://host:port)
    --force-update     强制更新组播文件，即使本地已存在
    --max-workers N    处理UDPXY服务器的最大线程数（默认3）
    --test-workers N   测试频道的最大线程数（默认5）

示例:
    python3 udpxy_batch_maker.py --iplistfile https://tv1288.xyz/ip.php
    python3 udpxy_batch_maker.py --iplistfile ip.txt --max-workers 5
    python3 udpxy_batch_maker.py --iplistfile https://tv1288.xyz/ip.php --notest
    python3 udpxy_batch_maker.py --iplistfile ip.txt --proxy http://127.0.0.1:10808

项目主页: https://github.com/vitter/iptv-sources
"""

import os
import sys
import re
import argparse
import requests
import threading
import time
import ffmpeg
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional, Tuple


class UDPXYBatchMaker:
    """UDPXY批量源生成器"""
    
    def __init__(self, 
                 test_count=20, 
                 timeout=5, 
                 notest=False, 
                 proxy=None, 
                 force_update=False,
                 max_workers=3,
                 test_workers=5):
        self.test_count = test_count
        self.timeout = timeout
        self.notest = notest
        self.proxy = proxy
        self.force_update = force_update
        self.max_workers = max_workers  # 处理UDPXY服务器的线程数
        self.test_workers = test_workers  # 测试频道的线程数
        
        # 线程锁
        self.print_lock = threading.Lock()
        self.stats_lock = threading.Lock()
        
        # 统计信息
        self.total_servers = 0
        self.success_servers = 0
        self.failed_servers = 0
        
        # 设置基础目录
        self.base_dir = Path("multicast_sources")
        self.output_dir = Path("generated_sources_batch")
        
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
        
        # 配置代理
        # session_proxy: 用于外网访问（下载IP列表、组播文件等）
        self.session_proxy = requests.Session()
        if self.proxy:
            self.session_proxy.proxies = {
                'http': self.proxy,
                'https': self.proxy
            }
            self.safe_print(f"使用代理（仅外网访问）: {self.proxy}")
        
        # session_local: 用于本地UDPXY访问（不使用代理）
        self.session_local = requests.Session()
    
    def safe_print(self, message):
        """线程安全的打印"""
        with self.print_lock:
            print(message)
            sys.stdout.flush()
    
    def update_stats(self, success=True):
        """更新统计信息"""
        with self.stats_lock:
            if success:
                self.success_servers += 1
            else:
                self.failed_servers += 1
    
    def download_ip_list(self, source: str) -> List[str]:
        """
        从URL或本地文件获取IP列表
        
        Args:
            source: URL地址或本地文件路径
        
        Returns:
            IP:端口格式的列表
        """
        self.safe_print(f"\n==== 获取IP列表 ====")
        self.safe_print(f"来源: {source}")
        
        ip_list = []
        
        # 判断是URL还是本地文件
        if source.startswith('http://') or source.startswith('https://'):
            # 从URL下载（使用代理）
            self.safe_print("正在从URL下载...")
            try:
                response = self.session_proxy.get(source, timeout=30)
                response.raise_for_status()
                content = response.text
                self.safe_print("✓ 下载成功")
            except Exception as e:
                self.safe_print(f"✗ 下载失败: {e}")
                return []
        else:
            # 从本地文件读取
            self.safe_print("正在从本地文件读取...")
            try:
                with open(source, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.safe_print("✓ 读取成功")
            except Exception as e:
                self.safe_print(f"✗ 读取失败: {e}")
                return []
        
        # 提取IP:端口格式
        self.safe_print("正在提取IP地址...")
        pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)'
        matches = re.findall(pattern, content)
        
        # 去重并排序
        ip_list = sorted(set(matches))
        
        self.safe_print(f"✓ 成功提取 {len(ip_list)} 个代理地址")
        
        return ip_list
    
    def test_udpxy_service(self, udpxy_server: str) -> bool:
        """
        测试UDPXY服务是否可用（不使用代理）
        
        Args:
            udpxy_server: UDPXY服务器地址 (格式: IP:PORT)
        
        Returns:
            服务是否可用
        """
        try:
            # 测试状态页面（不使用代理）
            status_url = f"http://{udpxy_server}/status"
            response = self.session_local.get(status_url, timeout=self.timeout)
            
            if response.status_code == 200:
                # 进一步检查是否包含UDPXY特征
                if 'udpxy' in response.text.lower() or 'status' in response.text.lower():
                    return True
            
            return False
            
        except Exception:
            return False
    
    def get_ip_location(self, ip: str) -> Optional[Dict]:
        """
        获取IP地理位置信息（使用代理，返回英文字段）
        Args:
            ip: IP地址
        Returns:
            位置信息字典或None
        """
        try:
            api_url = f"http://ip-api.com/json/{ip}"
            response = self.session_proxy.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country', 'Unknown'),
                        'region': data.get('regionName', 'Unknown'),
                        'city': data.get('city', 'Unknown'),
                        'isp': data.get('isp', 'Unknown')
                    }
        except Exception:
            pass
        return None
    
    def fetch_multicast_index(self) -> List[Dict]:
        """获取组播源索引（使用代理）"""
        try:
            response = self.session_proxy.get(self.base_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            multicast_files = []
            
            for link in soup.find_all('a'):
                href = link.get('href')
                if href and href.endswith('.txt'):
                    file_info = {
                        'name': href,
                        'url': self.base_url + href,
                        'province': None,
                        'isp': None
                    }
                    
                    # 解析文件名获取省份和运营商
                    for province in self.provinces:
                        if province in href.lower():
                            file_info['province'] = province
                            break
                    
                    for isp in self.isps:
                        if isp in href.lower():
                            file_info['isp'] = isp
                            break
                    
                    multicast_files.append(file_info)
            
            return multicast_files
            
        except Exception as e:
            self.safe_print(f"获取组播源索引失败: {e}")
            return []
    
    def download_multicast_file(self, multicast_info: Dict) -> Optional[Path]:
        """下载组播文件（使用代理）"""
        try:
            file_path = self.base_dir / multicast_info['name']
            
            # 如果文件已存在且不强制更新，则跳过
            if file_path.exists() and not self.force_update:
                return file_path
            
            response = self.session_proxy.get(multicast_info['url'], timeout=10)
            response.raise_for_status()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            return file_path
            
        except Exception:
            return None
    
    def get_local_multicast_files(self) -> List[Dict]:
        """递归获取本地所有组播txt文件（支持多级目录）"""
        multicast_files = []
        if not self.base_dir.exists():
            return multicast_files
        # 递归查找所有txt文件
        for file_path in self.base_dir.rglob('*.txt'):
            file_info = {
                'name': file_path.name,
                'path': file_path,
                'province': None,
                'isp': None
            }
            # 解析文件路径
            filename = file_path.name.lower()
            for province in self.provinces:
                if province in str(file_path).lower():
                    file_info['province'] = province
                    break
            for isp in self.isps:
                if isp in filename:
                    file_info['isp'] = isp
                    break
            multicast_files.append(file_info)
        return multicast_files
    
    def parse_multicast_file(self, file_path: Path) -> List[Dict]:
        """解析组播文件"""
        channels = []
        current_group = "未分类"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    # 解析分组标记
                    if line.endswith(',#genre#'):
                        current_group = line.replace(',#genre#', '').strip()
                        continue
                    
                    # 解析频道
                    if ',' in line:
                        parts = line.split(',', 1)
                        if len(parts) == 2:
                            name = parts[0].strip()
                            url = parts[1].strip()
                            
                            channels.append({
                                'name': name,
                                'url': url,
                                'group': current_group
                            })
        except Exception:
            pass
        
        return channels
    
    def test_stream_with_ffmpeg(self, stream_url: str) -> bool:
        """
        使用ffmpeg-python测试流媒体URL（不使用代理）
        
        Args:
            stream_url: 流媒体URL
        
        Returns:
            流是否可播放
        """
        try:
            # 使用ffmpeg probe测试流（不使用代理，因为UDPXY是本地访问）
            probe = ffmpeg.probe(
                stream_url,
                timeout=self.timeout,
                loglevel='quiet'
            )
            
            # 检查是否有视频流
            if 'streams' in probe and len(probe['streams']) > 0:
                for stream in probe['streams']:
                    if stream.get('codec_type') == 'video':
                        return True
            
            return False
            
        except ffmpeg.Error:
            return False
        except Exception:
            return False
    
    def convert_to_udpxy_url(self, udpxy_server: str, multicast_url: str) -> str:
        """
        将组播地址转换为UDPXY代理URL
        
        Args:
            udpxy_server: UDPXY服务器地址
            multicast_url: 组播地址
        
        Returns:
            UDPXY代理URL
        """
        # 提取组播地址
        if multicast_url.startswith('rtp://'):
            multicast_addr = multicast_url.replace('rtp://', '')
        else:
            multicast_addr = multicast_url
        
        # 构建UDPXY URL
        return f"http://{udpxy_server}/rtp/{multicast_addr}"
    
    def test_multicast_stream(self, udpxy_server: str, channel: Dict, 
                             channel_index: int, total_channels: int) -> Tuple[Dict, bool]:
        """
        测试单个组播流
        
        Args:
            udpxy_server: UDPXY服务器地址
            channel: 频道信息
            channel_index: 频道索引
            total_channels: 总频道数
        
        Returns:
            (频道信息, 是否可播放)
        """
        udpxy_url = self.convert_to_udpxy_url(udpxy_server, channel['url'])
        
        self.safe_print(
            f"  [{channel_index}/{total_channels}] 测试: {channel['name']} - {channel['url']}"
        )
        
        is_working = self.test_stream_with_ffmpeg(udpxy_url)
        
        if is_working:
            self.safe_print(f"    ✓ 可播放")
            channel['udpxy_url'] = udpxy_url
            return channel, True
        else:
            self.safe_print(f"    ✗ 不可播放")
            return channel, False
    
    def test_multicast_file(self, udpxy_server: str, file_info: Dict) -> Tuple[Dict, List[Dict]]:
        """
        测试组播文件中的频道
        
        Args:
            udpxy_server: UDPXY服务器地址
            file_info: 文件信息
        
        Returns:
            (文件信息, 可播放频道列表)
        """
        file_path = file_info.get('path')
        if not file_path:
            return file_info, []
        
        self.safe_print(f"\n测试文件: {file_info['name']}")
        
        # 解析频道
        channels = self.parse_multicast_file(file_path)
        if not channels:
            self.safe_print("  ✗ 未找到有效频道")
            return file_info, []
        
        # 限制测试数量
        test_channels = channels[:self.test_count]
        self.safe_print(f"  找到 {len(channels)} 个频道，测试前 {len(test_channels)} 个")
        
        # 多线程测试频道
        working_channels = []
        with ThreadPoolExecutor(max_workers=self.test_workers) as executor:
            futures = []
            for idx, channel in enumerate(test_channels, 1):
                future = executor.submit(
                    self.test_multicast_stream,
                    udpxy_server,
                    channel,
                    idx,
                    len(test_channels)
                )
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    channel, is_working = future.result()
                    if is_working:
                        working_channels.append(channel)
                except Exception:
                    pass
        
        self.safe_print(
            f"  测试完成: {len(working_channels)}/{len(test_channels)} 个频道可播放"
        )
        
        return file_info, working_channels
    
    def find_working_multicast_file(self, udpxy_server: str, 
                                   multicast_files: List[Dict],
                                   preferred_province: Optional[str] = None) -> Optional[Tuple[Dict, List[Dict]]]:
        """
        查找可用的组播文件
        优先本省，省内按电信→联通→移动顺序，失败后全局遍历所有省份（每省电信→联通→移动）
        Args:
            udpxy_server: UDPXY服务器地址
            multicast_files: 组播文件列表
            preferred_province: 优先省份
        Returns:
            (文件信息, 可播放频道列表) 或 None
        """
        isp_priority = {'telecom': 3, 'unicom': 2, 'mobile': 1}
        # 先分组
        province_files = {}
        for f in multicast_files:
            prov = f.get('province') or 'unknown'
            province_files.setdefault(prov, []).append(f)
        # 运营商顺序
        def sort_isp(files):
            return sorted(files, key=lambda x: isp_priority.get(x.get('isp', ''), 0), reverse=True)
        # 1. 优先本省
        if preferred_province and preferred_province in province_files:
            self.safe_print(f"  测试顺序: 优先 {preferred_province} 地区，按电信→联通→移动顺序")
            for file_info in sort_isp(province_files[preferred_province]):
                file_info, working_channels = self.test_multicast_file(udpxy_server, file_info)
                if working_channels:
                    return file_info, working_channels
            self.safe_print(f"  本省全部失败，开始全局遍历所有地区")
        else:
            self.safe_print(f"  测试顺序: 按地区顺序测试所有地区，每个地区的所有运营按电信→联通→移动顺序，直到成功为止")
        # 2. 全局遍历所有省份（本省已测过则跳过）
        for prov in sorted(province_files.keys()):
            if preferred_province and prov == preferred_province:
                continue
            for file_info in sort_isp(province_files[prov]):
                file_info, working_channels = self.test_multicast_file(udpxy_server, file_info)
                if working_channels:
                    return file_info, working_channels
        return None
    
    def generate_txt_source(self, udpxy_server: str, template_channels: List[Dict], output_path: Path):
        """生成TXT格式源文件（全量模板替换IP）"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                current_group = None
                for channel in template_channels:
                    # 写入分组标记
                    if channel['group'] != current_group:
                        current_group = channel['group']
                        f.write(f"{current_group},#genre#\n")
                    # 替换为当前UDPXY
                    udpxy_url = self.convert_to_udpxy_url(udpxy_server, channel['url'])
                    f.write(f"{channel['name']},{udpxy_url}\n")
            return True
        except Exception:
            return False
    
    def generate_m3u_source(self, udpxy_server: str, template_channels: List[Dict], output_path: Path):
        """生成M3U格式源文件（全量模板替换IP）"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                for channel in template_channels:
                    udpxy_url = self.convert_to_udpxy_url(udpxy_server, channel['url'])
                    f.write(
                        f'#EXTINF:-1 tvg-name="{channel["name"]}" '
                        f'group-title="{channel["group"]}",{channel["name"]}\n'
                    )
                    f.write(f"{udpxy_url}\n")
            return True
        except Exception:
            return False
    
    def generate_sources(self, udpxy_server: str, working_file: Dict, working_channels: List[Dict]) -> bool:
        """
        生成源文件（全量模板替换IP，命名为地区_运营商_UDPXYIP前缀）
        Args:
            udpxy_server: UDPXY服务器地址
            working_file: 可用的组播文件信息
            working_channels: 可播放频道列表（实际只用于确定模板文件）
        Returns:
            是否成功
        """
        if not working_file or not working_file.get('path'):
            return False
        # 解析命名
        province = working_file.get('province', 'unknown')
        isp = working_file.get('isp', 'unknown')
        ip_prefix = udpxy_server.replace(':', '_').replace('.', '_')
        base_name = f"{province}_{isp}_{ip_prefix}"
        # 解析模板文件所有频道
        template_channels = self.parse_multicast_file(working_file['path'])
        if not template_channels:
            return False
        # 生成TXT文件
        txt_path = self.output_dir / f"{base_name}.txt"
        txt_success = self.generate_txt_source(udpxy_server, template_channels, txt_path)
        # 生成M3U文件
        m3u_path = self.output_dir / f"{base_name}.m3u"
        m3u_success = self.generate_m3u_source(udpxy_server, template_channels, m3u_path)
        if txt_success and m3u_success:
            self.safe_print(f"\n✓ 源文件生成成功:")
            self.safe_print(f"  TXT: {txt_path}")
            self.safe_print(f"  M3U: {m3u_path}")
            return True
        else:
            self.safe_print(f"\n✗ 源文件生成失败")
            return False
    
    def process_single_udpxy(self, udpxy_server: str, server_index: int) -> bool:
        """
        处理单个UDPXY服务器
        
        Args:
            udpxy_server: UDPXY服务器地址
            server_index: 服务器索引
        
        Returns:
            是否成功
        """
        self.safe_print(f"\n{'='*60}")
        self.safe_print(f"[{server_index}/{self.total_servers}] 处理 UDPXY 服务器: {udpxy_server}")
        self.safe_print(f"{'='*60}")
        
        # 验证格式
        if ':' not in udpxy_server:
            self.safe_print(f"✗ 格式错误: 需要 IP:PORT 格式")
            self.update_stats(success=False)
            return False
        
        try:
            ip, port = udpxy_server.split(':', 1)
            port = int(port)
        except ValueError:
            self.safe_print(f"✗ 格式错误: 端口必须是数字")
            self.update_stats(success=False)
            return False
        
        # 测试服务可用性
        self.safe_print(f"\n步骤 1: 测试 UDPXY 服务...")
        if not self.test_udpxy_service(udpxy_server):
            self.safe_print(f"✗ UDPXY 服务不可用")
            self.update_stats(success=False)
            return False
        
        self.safe_print(f"✓ UDPXY 服务可用")
        
        # 如果只测试，则返回
        if self.notest:
            self.safe_print(f"✓ 仅测试模式，跳过源生成")
            self.update_stats(success=True)
            return True
        
        # 获取IP位置信息
        self.safe_print(f"\n步骤 2: 获取IP地理位置...")
        location = self.get_ip_location(ip)
        preferred_province = None
        
        if location:
            self.safe_print(f"✓ IP位置: {location['country']} - {location['region']} - {location['city']}")
            
            # 尝试匹配省份
            region_lower = location['region'].lower()
            for province in self.provinces:
                if province in region_lower or region_lower in province:
                    preferred_province = province
                    self.safe_print(f"  匹配省份: {preferred_province}")
                    break
            
            if not preferred_province:
                self.safe_print(f"  未匹配到对应省份，将测试所有地区")
        else:
            self.safe_print(f"✗ 无法获取IP位置信息，将测试所有地区")
        
        # 获取组播文件
        self.safe_print(f"\n步骤 3: 准备组播文件...")
        
        # 优先使用本地文件
        multicast_files = self.get_local_multicast_files()
        
        if not multicast_files:
            self.safe_print("本地无组播文件，尝试下载...")
            
            # 获取索引
            index_files = self.fetch_multicast_index()
            if not index_files:
                self.safe_print("✗ 无法获取组播源索引")
                self.update_stats(success=False)
                return False
            
            # 下载文件
            self.safe_print(f"找到 {len(index_files)} 个组播文件")
            multicast_files = []
            
            for file_info in index_files:
                file_path = self.download_multicast_file(file_info)
                if file_path:
                    file_info['path'] = file_path
                    multicast_files.append(file_info)
        
        if not multicast_files:
            self.safe_print("✗ 无可用的组播文件")
            self.update_stats(success=False)
            return False
        
        self.safe_print(f"✓ 找到 {len(multicast_files)} 个组播文件")
        
        # 查找可用的组播文件
        self.safe_print(f"\n步骤 4: 测试组播频道...")
        result = self.find_working_multicast_file(
            udpxy_server,
            multicast_files,
            preferred_province
        )
        
        if not result:
            self.safe_print("✗ 未找到可播放的频道")
            self.update_stats(success=False)
            return False
        
        working_file, working_channels = result
        
        # 生成源文件
        self.safe_print(f"\n步骤 5: 生成源文件...")
        success = self.generate_sources(udpxy_server, working_file, working_channels)
        
        self.update_stats(success=success)
        return success
    
    def run(self, ip_list_source: str):
        """
        运行批量处理
        
        Args:
            ip_list_source: IP列表来源（URL或本地文件）
        """
        # 获取IP列表
        ip_list = self.download_ip_list(ip_list_source)
        
        if not ip_list:
            self.safe_print("\n✗ 未找到有效的IP地址")
            return
        
        self.total_servers = len(ip_list)
        
        self.safe_print(f"\n{'='*60}")
        self.safe_print(f"开始批量处理 {self.total_servers} 个 UDPXY 服务器")
        self.safe_print(f"最大并发数: {self.max_workers}")
        self.safe_print(f"测试并发数: {self.test_workers}")
        self.safe_print(f"{'='*60}\n")
        
        start_time = time.time()
        
        # 多线程处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for idx, udpxy_server in enumerate(ip_list, 1):
                future = executor.submit(
                    self.process_single_udpxy,
                    udpxy_server,
                    idx
                )
                futures.append(future)
            
            # 等待所有任务完成
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.safe_print(f"\n✗ 处理出错: {e}")
        
        # 输出统计信息
        elapsed_time = time.time() - start_time
        
        self.safe_print(f"\n{'='*60}")
        self.safe_print("批量处理完成！")
        self.safe_print(f"{'='*60}")
        self.safe_print(f"总服务器数: {self.total_servers}")
        self.safe_print(f"成功处理: {self.success_servers}")
        self.safe_print(f"失败处理: {self.failed_servers}")
        
        if self.total_servers > 0:
            success_rate = (self.success_servers / self.total_servers) * 100
            self.safe_print(f"成功率: {success_rate:.2f}%")
        
        self.safe_print(f"耗时: {elapsed_time:.2f} 秒")
        self.safe_print(f"{'='*60}")
        
        if self.success_servers > 0:
            self.safe_print(f"\n✓ 源文件已保存到: {self.output_dir.absolute()}")


def main():
    parser = argparse.ArgumentParser(
        description="UDPXY 批量源生成器 (增强版) - 支持从URL或本地文件批量导入UDPXY代理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从URL批量处理（默认）
  python3 udpxy_batch_maker.py --iplistfile https://tv1288.xyz/ip.php
  
  # 从本地文件批量处理
  python3 udpxy_batch_maker.py --iplistfile ip.txt
  
  # 仅测试服务可用性
  python3 udpxy_batch_maker.py --iplistfile ip.txt --notest
  
  # 自定义并发数
  python3 udpxy_batch_maker.py --iplistfile ip.txt --max-workers 5 --test-workers 10
  
  # 使用代理
  python3 udpxy_batch_maker.py --iplistfile ip.txt --proxy http://127.0.0.1:10808
        """
    )
    
    parser.add_argument(
        '--iplistfile',
        default='https://tv1288.xyz/ip.php',
        help='IP列表URL或本地文件路径（默认: https://tv1288.xyz/ip.php）'
    )
    parser.add_argument(
        '--notest',
        action='store_true',
        help='只测试 UDPXY 服务可用性，不生成源文件'
    )
    parser.add_argument(
        '--test-count',
        type=int,
        default=20,
        help='每个组播文件测试的地址数量 (默认: 20)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=5,
        help='测试超时时间，秒 (默认: 5)'
    )
    parser.add_argument(
        '--proxy',
        help='代理服务器地址 (格式: http://host:port)'
    )
    parser.add_argument(
        '--force-update',
        action='store_true',
        help='强制更新组播文件，即使本地已存在'
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=3,
        help='处理UDPXY服务器的最大线程数 (默认: 3)'
    )
    parser.add_argument(
        '--test-workers',
        type=int,
        default=5,
        help='测试频道的最大线程数 (默认: 5)'
    )
    
    args = parser.parse_args()
    
    try:
        print("="*60)
        print("UDPXY 批量源生成器 (增强版)")
        print("="*60)
        
        maker = UDPXYBatchMaker(
            test_count=args.test_count,
            timeout=args.timeout,
            notest=args.notest,
            proxy=args.proxy,
            force_update=args.force_update,
            max_workers=args.max_workers,
            test_workers=args.test_workers
        )
        
        maker.run(args.iplistfile)
        
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
