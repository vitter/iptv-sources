#!/usr/bin/env python3
"""
IPTV组播文件下载器

项目主页: https://github.com/vitter/iptv-sources
问题反馈: https://github.com/vitter/iptv-sources/issues
"""

import requests
import re
import os
import time
import argparse
from pathlib import Path
from urllib.parse import urljoin, urlparse

class IPTVDownloader:
    def __init__(self, base_url="https://chinaiptv.pages.dev/", proxy=None):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}
            print(f"使用代理: {proxy}")
        
        self.timeout = 15
        self.province_configs = {'Mobile': {}, 'Telecom': {}, 'Unicom': {}}
    
    def get_file_list(self):
        """获取组播文件列表"""
        try:
            print(f"正在获取文件列表: {self.base_url}")
            response = self.session.get(self.base_url, timeout=self.timeout)
            response.raise_for_status()
            
            print(f"获取到页面内容，长度: {len(response.text)} 字符")
            
            # 查找所有txt文件链接
            file_pattern = r'href="([^"]*\.txt)"'
            matches = re.findall(file_pattern, response.text)
            
            if not matches:
                print("未在页面中找到txt文件链接")
                return []
            
            # 只保留组播文件并去重
            multicast_files = []
            seen_files = set()
            
            for match in matches:
                if 'multicast' in match.lower():
                    # 去重：如果文件路径已存在就跳过
                    if match not in seen_files:
                        multicast_files.append(match)
                        seen_files.add(match)
            
            print(f"找到 {len(multicast_files)} 个组播文件（已去重）")
            return multicast_files
            
        except Exception as e:
            print(f"获取文件列表失败: {e}")
            return []
    
    def parse_filename(self, file_path):
        """从文件路径提取运营商和省份信息"""
        if '/' in file_path:
            parts = file_path.split('/')
            if len(parts) >= 3:
                province_part = parts[1].lower()
                isp_part = parts[2].lower()
                
                # 运营商映射
                isp = None
                if 'mobile' in isp_part:
                    isp = 'Mobile'
                elif 'telecom' in isp_part:
                    isp = 'Telecom'
                elif 'unicom' in isp_part:
                    isp = 'Unicom'
                
                # 省份映射
                provinces = {
                    'beijing': 'Beijing', 'shanghai': 'Shanghai', 'tianjin': 'Tianjin',
                    'chongqing': 'Chongqing', 'hebei': 'Hebei', 'shanxi': 'Shanxi',
                    'liaoning': 'Liaoning', 'jilin': 'Jilin', 'heilongjiang': 'Heilongjiang',
                    'jiangsu': 'Jiangsu', 'zhejiang': 'Zhejiang', 'anhui': 'Anhui',
                    'fujian': 'Fujian', 'jiangxi': 'Jiangxi', 'shandong': 'Shandong',
                    'henan': 'Henan', 'hubei': 'Hubei', 'hunan': 'Hunan',
                    'guangdong': 'Guangdong', 'guangxi': 'Guangxi', 'hainan': 'Hainan',
                    'sichuan': 'Sichuan', 'guizhou': 'Guizhou', 'yunnan': 'Yunnan',
                    'shaanxi': 'Shaanxi', 'gansu': 'Gansu', 'qinghai': 'Qinghai',
                    'ningxia': 'Ningxia', 'xinjiang': 'Xinjiang', 'xizang': 'Xizang',
                    'neimenggu': 'Neimenggu', 'shan3xi': 'Shaanxi'
                }
                
                province = provinces.get(province_part, province_part.capitalize())
                return isp, province
        
        return None, None
    
    def download_file(self, file_url):
        """下载文件内容"""
        try:
            full_url = urljoin(self.base_url, file_url)
            print(f"下载文件: {full_url}")
            
            response = self.session.get(full_url, timeout=self.timeout)
            response.raise_for_status()
            
            content = response.text
            print(f"  ✓ 下载成功，内容长度: {len(content)} 字符")
            return content
            
        except Exception as e:
            print(f"  ✗ 下载失败: {e}")
            return None
    
    def process_content(self, content):
        """处理文件内容，提取流媒体URL"""
        if not content:
            return []
        
        lines = content.strip().split('\n')
        processed_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检查是否包含流媒体URL
            if re.search(r'rtp://|udp://|http://.*udp/', line):
                # 转换格式: rtp://ip:port -> http://ipipip/udp/ip:port
                processed_line = re.sub(
                    r'rtp://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+)',
                    r'http://ipipip/udp/\1',
                    line
                )
                processed_line = re.sub(
                    r'udp://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+)',
                    r'http://ipipip/udp/\1',
                    processed_line
                )
                processed_lines.append(processed_line)
        
        return processed_lines
    
    def extract_first_stream_url(self, content):
        """提取第一个流媒体URL"""
        if not content:
            return None
        
        lines = content.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 查找RTP或UDP流媒体URL
            match = re.search(r'rtp://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+)', line)
            if match:
                return f"udp/{match.group(1)}"
            
            match = re.search(r'udp://([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+)', line)
            if match:
                return f"udp/{match.group(1)}"
        
        return None
    
    def save_template_file(self, isp, province, content_lines):
        """保存模板文件"""
        if not content_lines:
            return
        
        template_dir = Path(isp)
        template_dir.mkdir(exist_ok=True)
        
        template_file = template_dir / f"template_{province}.txt"
        
        try:
            with open(template_file, 'w', encoding='utf-8') as f:
                for line in content_lines:
                    f.write(line + '\n')
            
            print(f"  ✓ 保存模板文件: {template_file} ({len(content_lines)} 行)")
            
        except Exception as e:
            print(f"  ✗ 保存模板文件失败: {e}")
    
    def process_file(self, file_url):
        """处理单个文件"""
        # 从URL获取路径
        parsed_url = urlparse(file_url)
        full_path = parsed_url.path.lstrip('/')
        filename = os.path.basename(full_path)
        
        print(f"\n处理文件: {filename}")
        
        # 解析路径提取运营商和省份
        isp, province = self.parse_filename(full_path)
        
        if not isp or not province:
            print(f"  ✗ 无法识别运营商或省份")
            return
        
        print(f"  识别为: {isp}-{province}")
        
        # 下载文件内容
        content = self.download_file(file_url)
        if not content:
            return
        
        # 处理内容
        processed_lines = self.process_content(content)
        if not processed_lines:
            print(f"  ✗ 没有找到有效的流媒体内容")
            return
        
        print(f"  ✓ 处理完成，有效行数: {len(processed_lines)}")
        
        # 保存模板文件
        self.save_template_file(isp, province, processed_lines)
        
        # 提取配置URL
        stream_url = self.extract_first_stream_url(content)
        if stream_url:
            self.province_configs[isp][province] = stream_url
            print(f"  ✓ 更新配置: {isp}-{province} -> {stream_url}")
        
        # 短暂延迟
        time.sleep(0.1)
    
    def save_province_configs(self):
        """保存省份配置文件"""
        for isp in ['Mobile', 'Telecom', 'Unicom']:
            config_file = f"{isp}_province_list.txt"
            
            try:
                with open(config_file, 'w', encoding='utf-8') as f:
                    f.write("city file stream\n")
                    
                    for province, stream_url in self.province_configs[isp].items():
                        line = f"{province} {province} {stream_url}"
                        f.write(line + '\n')
                
                print(f"✓ 保存配置文件: {config_file} ({len(self.province_configs[isp])} 个省份)")
                
            except Exception as e:
                print(f"✗ 保存配置文件失败 {config_file}: {e}")
    
    def run(self):
        """主运行方法"""
        print("=== IPTV组播文件下载器 ===")
        print(f"基础URL: {self.base_url}")
        print()
        
        # 获取文件列表
        file_list = self.get_file_list()
        
        if not file_list:
            print("未找到组播文件")
            return
        
        total_files = len(file_list)
        print(f"\n=== 开始处理 {total_files} 个文件 ===")
        
        # 处理文件
        for i, file_url in enumerate(file_list, 1):
            print(f"\n--- 进度: {i}/{total_files} ---")
            self.process_file(file_url)
        
        print(f"\n=== 保存配置文件 ===")
        self.save_province_configs()
        
        # 统计信息
        total_configs = sum(len(configs) for configs in self.province_configs.values())
        print(f"\n=== 统计信息 ===")
        print(f"总处理文件数: {total_files}")
        print(f"生成配置项数: {total_configs}")
        
        for isp, configs in self.province_configs.items():
            print(f"  {isp}: {len(configs)} 个省份")

def main():
    parser = argparse.ArgumentParser(description='IPTV组播文件下载器')
    parser.add_argument('--proxy', help='代理服务器 (格式: http://host:port)')
    
    args = parser.parse_args()
    
    downloader = IPTVDownloader(proxy=args.proxy)
    downloader.run()

if __name__ == "__main__":
    main()
