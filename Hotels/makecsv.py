#!/usr/bin/env python3
"""
IPTV 源数据获取与合并工具

功能：
1. 从 FOFA 和 Quake360 搜索指定类型的IPTV服务
2. 合并现有CSV文件数据
3. 按照指定规则进行去重（host排重，同一个C段IP不同端口去重）
4. 更新CSV文件

用法：
单模式：python makecsv.py --jsmpeg jsmpeg_hosts.csv
多模式：python makecsv.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv --zhgxtv zhgxtv_hosts.csv

搜索规则：
--jsmpeg: 搜索 title="jsmpeg-streamer" && country="CN"
--txiptv: 搜索 body="/iptv/live/zh_cn.js" && country="CN"  
--zhgxtv: 搜索 body="ZHGXTV" && country="CN"

环境变量配置：
FOFA_COOKIE - FOFA网站登录Cookie
FOFA_USER_AGENT - 浏览器User-Agent
FOFA_API_KEY - FOFA API密钥（可选）
QUAKE360_TOKEN - Quake360 API Token
"""

import argparse
import base64
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

# 尝试导入第三方库，如果失败则提示安装
try:
    import requests
except ImportError:
    print("错误: 缺少 requests 库，请安装: pip install requests")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("警告: 缺少 python-dotenv 库，将尝试从系统环境变量读取配置")
    print("建议安装: pip install python-dotenv")
    def load_dotenv():
        pass


class IPTVSourceCollector:
    """IPTV 源数据收集器"""
    
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        # 从环境变量读取配置
        self.quake360_token = os.getenv('QUAKE360_TOKEN')
        self.fofa_user_agent = os.getenv('FOFA_USER_AGENT')
        self.fofa_api_key = os.getenv('FOFA_API_KEY', '')
        
        # 清理Cookie字符串
        raw_fofa_cookie = os.getenv('FOFA_COOKIE', '')
        self.fofa_cookie = self._clean_cookie_string(raw_fofa_cookie)
        
        # 验证必要配置
        self._validate_config()
    
    def _clean_cookie_string(self, cookie_str):
        """清理Cookie字符串，移除换行符、回车符和多余空格"""
        if not cookie_str:
            return ''
        
        # 移除换行符、回车符、制表符
        cleaned = cookie_str.replace('\n', '').replace('\r', '').replace('\t', '')
        
        # 移除多余的空格但保留cookie之间的单个空格
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def _validate_config(self):
        """验证必要的配置是否已设置"""
        missing_configs = []
        
        if not self.quake360_token:
            missing_configs.append('QUAKE360_TOKEN')
        
        if not self.fofa_user_agent:
            missing_configs.append('FOFA_USER_AGENT')
        
        if not self.fofa_cookie:
            missing_configs.append('FOFA_COOKIE')
        
        if missing_configs:
            print("错误: 缺少必要的环境变量配置:")
            for config in missing_configs:
                print(f"  - {config}")
            print("\n请在.env文件中设置这些配置项，或者创建.env文件。")
            sys.exit(1)
        
        print("✓ 配置验证通过")
    
    def _create_session_with_retry(self):
        """创建带重试机制的会话"""
        session = requests.Session()
        
        # 设置重试策略（简化版本，避免依赖问题）
        try:
            from urllib3.util.retry import Retry
            from requests.adapters import HTTPAdapter
            
            # 设置重试策略
            try:
                retry_strategy = Retry(
                    total=3,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "OPTIONS"]
                )
            except TypeError:
                retry_strategy = Retry(
                    total=3,
                    status_forcelist=[429, 500, 502, 503, 504],
                    method_whitelist=["HEAD", "GET", "OPTIONS"]
                )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
        except ImportError:
            # 如果没有urllib3，就使用基本的session
            pass
        
        # 设置请求头和Cookie
        session.headers.update({
            'User-Agent': self.fofa_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        if self.fofa_cookie:
            session.headers['Cookie'] = self.fofa_cookie
        
        return session
    
    def search_fofa_api(self, query):
        """使用FOFA API搜索"""
        print(f"===============从 FOFA API 搜索===============")
        print(f"搜索查询: {query}")
        
        # 使用base64编码查询
        query_b64 = base64.b64encode(query.encode()).decode().replace('\n', '')
        
        api_url = "https://fofa.info/api/v1/search/all"
        params = {
            'key': self.fofa_api_key,
            'qbase64': query_b64,
            'fields': 'ip,host,port,link',
            'size': 10,  # 增加返回数量
            'page': 1,
            'full': 'false'
        }
        
        try:
            # 添加延迟避免API限流
            time.sleep(1)
            
            session = requests.Session()
            session.headers.update({
                'User-Agent': self.fofa_user_agent,
                'Accept': 'application/json'
            })
            
            response = session.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            
            response_json = response.json()
            
            if response_json.get('error', False):
                error_msg = response_json.get('errmsg', '未知错误')
                print(f"FOFA API错误: {error_msg}")
                return []
            
            results = response_json.get('results', [])
            print(f"API返回结果数: {len(results)}")
            
            # 显示前几个结果的结构用于调试
            if results:
                print("前3个结果示例:")
                for i, result in enumerate(results[:3]):
                    print(f"  结果 {i+1}: {result} (长度: {len(result)})")
            
            # 提取数据
            extracted_data = []
            for result in results:
                if len(result) >= 4:  # 确保有4个字段：ip, host, port, link
                    ip = str(result[0]).strip() if result[0] else ''
                    host = str(result[1]).strip() if result[1] else ''
                    port = str(result[2]).strip() if result[2] else ''
                    link = str(result[3]).strip() if result[3] else ''
                    
                    # 如果host为空，尝试从ip和port组合
                    if not host and ip and port:
                        host = f"{ip}:{port}"
                    
                    # 如果link为空，尝试从host构建
                    if not link and host:
                        if host.startswith(('http://', 'https://')):
                            link = host
                        else:
                            link = f"http://{host}"
                    
                    # 如果ip为空，尝试从host提取
                    if not ip and host:
                        if '://' in host:
                            host_part = host.split('://', 1)[1]
                        else:
                            host_part = host
                        
                        if ':' in host_part:
                            ip = host_part.split(':')[0]
                        else:
                            ip = host_part
                    
                    # 验证必要字段
                    if ip and port and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                        # 确保host格式为ip:port
                        if not host or ':' not in host:
                            host = f"{ip}:{port}"
                        
                        # 确保link格式正确
                        if not link or not link.startswith(('http://', 'https://')):
                            link = f"http://{ip}:{port}"
                        
                        extracted_data.append({
                            'host': host,
                            'ip': ip,
                            'port': port,
                            'link': link,
                            'protocol': 'http',
                            'title': '',
                            'domain': '',
                            'country': 'CN',
                            'city': '',
                            'org': '',
                            '_source': 'fofa_api'
                        })
            
            print(f"FOFA API提取到 {len(extracted_data)} 个有效结果")
            return extracted_data
            
        except Exception as e:
            print(f"FOFA API搜索失败: {e}")
            return []
    
    def search_fofa_cookie(self, query):
        """使用FOFA Cookie搜索"""
        print(f"===============从 FOFA Cookie 搜索===============")
        print(f"搜索查询: {query}")
        
        # 使用base64编码查询
        query_b64 = base64.b64encode(query.encode()).decode()
        
        # 构建URL
        search_url = f"https://fofa.info/result?qbase64={query_b64}&page=1&page_size=10"
        
        try:
            session = self._create_session_with_retry()
            
            print("发送请求到FOFA...")
            response = session.get(search_url, timeout=30)
            response.raise_for_status()
            
            # 从HTML页面提取数据
            content = response.text
            
            # 使用正则表达式提取IP:PORT
            ip_port_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)'
            matches = re.findall(ip_port_pattern, content)
            
            extracted_data = []
            for ip, port in matches:
                host = f"{ip}:{port}"
                link = f"http://{host}"
                extracted_data.append({
                    'host': host,
                    'ip': ip,
                    'port': port,
                    'link': link,
                    'protocol': 'http',
                    'title': '',
                    'domain': '',
                    'country': 'CN',
                    'city': '',
                    'org': '',
                    '_source': 'fofa_cookie'
                })
            
            # 去重
            unique_data = []
            seen_hosts = set()
            for item in extracted_data:
                if item['host'] not in seen_hosts:
                    unique_data.append(item)
                    seen_hosts.add(item['host'])
            
            print(f"FOFA Cookie提取到 {len(unique_data)} 个有效结果")
            return unique_data
            
        except Exception as e:
            print(f"FOFA Cookie搜索失败: {e}")
            return []
    
    def search_quake360_api(self, query):
        """使用Quake360 API搜索"""
        print(f"===============从 Quake360 API 搜索===============")
        print(f"搜索查询: {query}")
        
        if not self.quake360_token:
            print("未配置QUAKE360_TOKEN，跳过Quake360搜索")
            return []
        
        query_data = {
            "query": query,
            "start": 0,
            "size": 10,
            "ignore_cache": False,
            "latest": True,
            "shortcuts": "635fcb52cc57190bd8826d09"  # 排除蜜罐系统结果
        }
        
        headers = {
            'X-QuakeToken': self.quake360_token,
            'Content-Type': 'application/json',
            'User-Agent': self.fofa_user_agent
        }
        
        try:
            # 添加延迟避免API限流
            time.sleep(2)
            
            response = requests.post(
                'https://quake.360.net/api/v3/search/quake_service',
                headers=headers,
                json=query_data,
                timeout=30
            )
            response.raise_for_status()
            
            response_json = response.json()
            
            # 检查错误
            code = response_json.get('code')
            if code and str(code) not in ['0', '200', 'success']:
                error_message = response_json.get('message', '未知错误')
                print(f"Quake360 API错误: {code} - {error_message}")
                return []
            
            # 提取数据
            extracted_data = []
            if 'data' in response_json and isinstance(response_json['data'], list):
                data_count = len(response_json['data'])
                print(f"找到 {data_count} 个数据项")
                
                # 显示前几个结果的结构用于调试
                if response_json['data']:
                    print("前3个结果示例:")
                    for i, item in enumerate(response_json['data'][:3]):
                        print(f"  结果 {i+1}: {item}")
                
                for item in response_json['data']:
                    if isinstance(item, dict):
                        # 直接提取IP和端口
                        ip = item.get('ip', '')
                        port = item.get('port', '')
                        
                        # 确保ip和port都存在且有效
                        if ip and port and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', str(ip)):
                            ip = str(ip).strip()
                            port = str(port).strip()
                            
                            # 组合host和link
                            host = f"{ip}:{port}"
                            link = f"http://{host}"
                            
                            extracted_data.append({
                                'host': host,
                                'ip': ip,
                                'port': port,
                                'link': link,
                                'protocol': 'http',
                                'title': '',
                                'domain': '',
                                'country': 'CN',
                                'city': '',
                                'org': '',
                                '_source': 'quake360'
                            })
            
            print(f"Quake360 API提取到 {len(extracted_data)} 个有效结果")
            return extracted_data
            
        except Exception as e:
            print(f"Quake360 API搜索失败: {e}")
            return []
    
    def search_both_engines(self, query_fofa, query_quake360):
        """从两个搜索引擎获取数据"""
        all_data = []
        
        # 1. FOFA搜索
        if self.fofa_api_key:
            print("使用FOFA API搜索")
            fofa_data = self.search_fofa_api(query_fofa)
        else:
            print("使用FOFA Cookie搜索")
            fofa_data = self.search_fofa_cookie(query_fofa)
        
        all_data.extend(fofa_data)
        
        # 2. Quake360搜索
        quake_data = self.search_quake360_api(query_quake360)
        all_data.extend(quake_data)
        
        print(f"总共从两个引擎获取到 {len(all_data)} 个结果")
        return all_data
    
    def read_existing_csv(self, csv_file):
        """读取现有CSV文件"""
        if not os.path.exists(csv_file):
            print(f"CSV文件 {csv_file} 不存在，将创建新文件")
            return []
        
        existing_data = []
        try:
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 确保所有必要字段存在
                    host = row.get('host', '').strip() if row.get('host') else ''
                    ip = row.get('ip', '').strip() if row.get('ip') else ''
                    port = row.get('port', '').strip() if row.get('port') else ''
                    link = row.get('link', '').strip() if row.get('link') else ''
                    
                    if host and ip and port and link:
                        # 保留所有字段，包括其他可能存在的字段
                        item_data = {
                            'host': host,
                            'ip': ip, 
                            'port': port,
                            'link': link,
                            'protocol': row.get('protocol', '').strip(),
                            'title': row.get('title', '').strip(),
                            'domain': row.get('domain', '').strip(),
                            'country': row.get('country', '').strip(),
                            'city': row.get('city', '').strip(),
                            'org': row.get('org', '').strip(),
                            # 标记这是来自现有数据
                            '_source': 'existing'
                        }
                        existing_data.append(item_data)
            
            print(f"从 {csv_file} 读取到 {len(existing_data)} 条现有数据")
            return existing_data
            
        except Exception as e:
            print(f"读取CSV文件失败: {e}")
            print(f"错误：无法读取现有CSV文件 {csv_file}，为了避免数据丢失，程序退出")
            print("请检查文件格式是否正确，或者删除损坏的文件后重新运行")
            sys.exit(1)
    
    def deduplicate_data(self, all_data):
        """数据去重：先按host去重，再按同一C段IP+端口去重"""
        print("开始数据去重...")
        
        # 1. 按host去重，优先保留现有数据（有更多字段内容）
        host_seen = set()
        host_unique_data = []
        
        # 先处理现有数据，再处理新搜索的数据
        existing_data = [item for item in all_data if item.get('_source') == 'existing']
        new_data = [item for item in all_data if item.get('_source') != 'existing']
        
        # 首先添加现有数据
        for item in existing_data:
            host = item['host']
            if host not in host_seen:
                host_unique_data.append(item)
                host_seen.add(host)
        
        # 然后添加新数据（如果host不重复）
        for item in new_data:
            host = item['host']
            if host not in host_seen:
                host_unique_data.append(item)
                host_seen.add(host)
        
        print(f"按host去重后剩余 {len(host_unique_data)} 条数据")
        
        # 2. 按同一C段IP+端口去重，同样优先保留现有数据
        # 同一个C段的同一端口只保留一个IP
        c_segment_port_map = defaultdict(list)
        
        for item in host_unique_data:
            try:
                ip = item['ip']
                port = item['port']
                
                # 提取C段（前三段IP）
                ip_parts = ip.split('.')
                if len(ip_parts) >= 3:
                    c_segment = '.'.join(ip_parts[:3])
                    key = f"{c_segment}.x:{port}"
                    c_segment_port_map[key].append(item)
            except Exception:
                # 如果IP格式有问题，直接保留
                continue
        
        # 每个C段+端口组合优先保留现有数据，如果没有现有数据则保留第一个新数据
        final_data = []
        for key, items in c_segment_port_map.items():
            if items:
                # 优先选择现有数据
                existing_items = [item for item in items if item.get('_source') == 'existing']
                if existing_items:
                    final_data.append(existing_items[0])  # 保留第一个现有数据
                    if len(items) > 1:
                        print(f"C段去重: {key} 有 {len(items)} 个IP，保留现有数据 {existing_items[0]['host']}")
                else:
                    final_data.append(items[0])  # 没有现有数据时保留第一个新数据
                    if len(items) > 1:
                        print(f"C段去重: {key} 有 {len(items)} 个IP，保留新数据 {items[0]['host']}")
        
        # 移除内部使用的_source标记
        for item in final_data:
            if '_source' in item:
                del item['_source']
        
        print(f"按C段+端口去重后剩余 {len(final_data)} 条数据")
        return final_data
    
    def write_csv(self, data, csv_file):
        """写入CSV文件"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(csv_file) if os.path.dirname(csv_file) else '.', exist_ok=True)
            
            with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                fieldnames = ['host', 'ip', 'port', 'protocol', 'title', 'domain', 'country', 'city', 'link', 'org']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                writer.writeheader()
                for item in data:
                    # 使用现有值或默认值
                    row = {
                        'host': item.get('host', ''),
                        'ip': item.get('ip', ''),
                        'port': item.get('port', ''),
                        'protocol': item.get('protocol', 'http'),
                        'title': item.get('title', ''),
                        'domain': item.get('domain', ''),
                        'country': item.get('country', 'CN'),
                        'city': item.get('city', ''),
                        'link': item.get('link', ''),
                        'org': item.get('org', '')
                    }
                    writer.writerow(row)
            
            print(f"已写入 {len(data)} 条数据到 {csv_file}")
            
        except Exception as e:
            print(f"写入CSV文件失败: {e}")
    
    def process_jsmpeg(self, csv_file):
        """处理jsmpeg模式"""
        print("\n=== 处理 jsmpeg 模式 ===")
        
        # 搜索查询
        fofa_query = 'title="jsmpeg-streamer" && country="CN"'
        quake360_query = 'title:"jsmpeg-streamer" AND country:"China"'
        
        # 从搜索引擎获取新数据
        new_data = self.search_both_engines(fofa_query, quake360_query)
        
        # 读取现有数据
        existing_data = self.read_existing_csv(csv_file)
        
        # 合并数据
        all_data = existing_data + new_data
        
        # 去重
        final_data = self.deduplicate_data(all_data)
        
        # 写入文件
        self.write_csv(final_data, csv_file)
    
    def process_txiptv(self, csv_file):
        """处理txiptv模式"""
        print("\n=== 处理 txiptv 模式 ===")
        
        # 搜索查询
        fofa_query = 'body="/iptv/live/zh_cn.js" && country="CN"'
        quake360_query = 'body:"/iptv/live/zh_cn.js" AND country:"China"'
        
        # 从搜索引擎获取新数据
        new_data = self.search_both_engines(fofa_query, quake360_query)
        
        # 读取现有数据
        existing_data = self.read_existing_csv(csv_file)
        
        # 合并数据
        all_data = existing_data + new_data
        
        # 去重
        final_data = self.deduplicate_data(all_data)
        
        # 写入文件
        self.write_csv(final_data, csv_file)
    
    def process_zhgxtv(self, csv_file):
        """处理zhgxtv模式"""
        print("\n=== 处理 zhgxtv 模式 ===")
        
        # 搜索查询
        fofa_query = 'body="ZHGXTV" && country="CN"'
        quake360_query = 'body:"ZHGXTV" AND country:"China"'
        
        # 从搜索引擎获取新数据
        new_data = self.search_both_engines(fofa_query, quake360_query)
        
        # 读取现有数据
        existing_data = self.read_existing_csv(csv_file)
        
        # 合并数据
        all_data = existing_data + new_data
        
        # 去重
        final_data = self.deduplicate_data(all_data)
        
        # 写入文件
        self.write_csv(final_data, csv_file)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='IPTV源数据获取与合并工具')
    parser.add_argument('--jsmpeg', help='jsmpeg模式CSV文件路径')
    parser.add_argument('--txiptv', help='txiptv模式CSV文件路径')
    parser.add_argument('--zhgxtv', help='zhgxtv模式CSV文件路径')
    
    args = parser.parse_args()
    
    # 检查至少指定了一个模式
    if not any([args.jsmpeg, args.txiptv, args.zhgxtv]):
        print("错误: 请至少指定一个模式参数")
        print("用法示例:")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv --zhgxtv zhgxtv_hosts.csv")
        sys.exit(1)
    
    # 创建收集器实例
    collector = IPTVSourceCollector()
    
    # 处理各种模式
    if args.jsmpeg:
        collector.process_jsmpeg(args.jsmpeg)
    
    if args.txiptv:
        collector.process_txiptv(args.txiptv)
    
    if args.zhgxtv:
        collector.process_zhgxtv(args.zhgxtv)
    
    print("\n=== 处理完成 ===")


if __name__ == "__main__":
    main()
