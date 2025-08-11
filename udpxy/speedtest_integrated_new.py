#!/usr/bin/env python3
"""
IPTV(udpxy) IP 搜索与测速综合工具 - 新版本

使用FOFA API 或登录Cookie进行搜索，Quake360使用Token认证

功能：
1. 从 FOFA 和 Quake360 搜索 udpxy IP（FOFA支持API密钥和Cookie认证，Quake360使用Token认证）
2. 端口连通性测试
3. HTTP/M3U8 流媒体测速
4. 生成结果文件

用法：
python speedtest_integrated_new.py <省市> <运营商>
例如：python speedtest_integrated_new.py Shanghai Telecom

认证方式：
- FOFA：配置了FOFA_API_KEY时优先使用API方式，失败时回退到Cookie；未配置则使用Cookie方式
- Quake360：使用QUAKE360_TOKEN进行API认证
- FOFA 必须配置Cookie，QUAKE360必须配置Token
- 支持多线程加速搜索和测速

注意事项：
- 确保在运行前设置了必要的环境变量（见 .env.example 文件）
- 需要安装 requests 和 python-dotenv 库
"""

import argparse
import base64
import json
import math  # 新增：用于翻页计算
import os
import re
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

# 可选导入 BeautifulSoup，如果不可用则使用备用解析方法
try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    print("Warning: BeautifulSoup not available, will use regex parsing for udpxy status")


class IPTVSpeedTest:
    """IPTV 测速主类"""
    
    def __init__(self, region, isp, max_pages=10, notest=False):
        # 加载环境变量
        load_dotenv()
        
        self.region = self._format_string(region)
        self.isp = self._format_string(isp)
        self.max_pages = max_pages  # 新增：最大翻页数限制
        self.notest = notest  # 新增：是否跳过流媒体测试
        
        # 从环境变量读取配置并清理格式
        self.quake360_token = os.getenv('QUAKE360_TOKEN')
        self.fofa_user_agent = os.getenv('FOFA_USER_AGENT')
        self.fofa_api_key = os.getenv('FOFA_API_KEY', '')  # 可选的API密钥
        
        # 清理Cookie字符串 - 移除换行符、回车符和多余空格
        raw_fofa_cookie = os.getenv('FOFA_COOKIE', '')
        self.fofa_cookie = self._clean_cookie_string(raw_fofa_cookie)
        
        # Quake360 简化配置 - 只使用Token认证
        
        # 验证必要的配置
        self._validate_config()
        
        # 创建必要的目录
        self._create_directories()
        
        # 加载省份配置（仅在需要流媒体测试时加载）
        if not self.notest:
            self.city, self.stream = self._load_province_config()
        else:
            # 在notest模式下，使用region作为city，stream设为空
            self.city = self.region
            self.stream = ""
        
        # 设置输出文件路径
        self.output_dir = Path(f"sum/{self.isp}")
        self.temp_dir = Path("sum/tmp")
        self.ipfile_sum = self.output_dir / f"{self.city}_sum.ip"
        self.ipfile_uniq = self.output_dir / f"{self.city}_uniq.ip"
        self.speedtest_log = f"{self.isp}_speedtest_{self.city}.log"
        self.result_file = self.temp_dir / f"{self.isp}_result_fofa_{self.city}.txt"
    
    def _format_string(self, input_str):
        """格式化字符串：首字母大写，其他字母小写"""
        return input_str.capitalize()
    
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
        
        # Quake360配置检查 - 只需要Token
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
            print("参考.env.example文件中的格式。")
            sys.exit(1)
        
        # 显示配置状态
        print("✓ 配置验证通过")
        print("配置状态:")
        print(f"  FOFA Cookie: ✓")
        print(f"  Quake360 Token: {'✓' if self.quake360_token else '✗'}")
        
        # 检查FOFA认证方式
        if self.fofa_api_key:
            print("  → FOFA 将使用API密钥")
        else:
            print("  → FOFA 将使用Cookie认证")
            
        # Quake360使用Token认证
        print("  → Quake360 将使用 Token 认证")
    
    def _create_directories(self):
        """创建必要的目录"""
        dirs = [
            "sum/tmp",
            f"sum/{self.isp}",
            f"template/{self.isp}"
        ]
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def _load_province_config(self):
        """加载省份配置"""
        config_file = f"{self.isp}_province_list.txt"
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"错误: {config_file} 文件不存在!")
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 3 and parts[0] == self.region:
                        return parts[1], parts[2]
            
            raise ValueError(f"错误: 在 {config_file} 中未找到省份 '{self.region}' 的配置!")
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            sys.exit(1)
    
    def _create_session_with_retry(self):
        """创建带重试机制的会话"""
        session = requests.Session()
        
        # 设置重试策略
        try:
            # 新版本使用 allowed_methods
            retry_strategy = Retry(
                total=3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )
        except TypeError:
            # 旧版本使用 method_whitelist
            retry_strategy = Retry(
                total=3,
                status_forcelist=[429, 500, 502, 503, 504],
                method_whitelist=["HEAD", "GET", "OPTIONS"]
            )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 设置请求头和Cookie
        session.headers.update({
            'User-Agent': self.fofa_user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
        
        # 单独设置Cookie头，确保格式正确，处理编码问题
        if self.fofa_cookie:
            try:
                # 确保Cookie字符串是正确编码的
                if isinstance(self.fofa_cookie, bytes):
                    cookie_str = self.fofa_cookie.decode('utf-8')
                else:
                    cookie_str = str(self.fofa_cookie)
                
                # 检查Cookie中是否包含非ASCII字符，如果有则进行URL编码
                try:
                    cookie_str.encode('ascii')
                    # 如果没有异常，说明是纯ASCII，直接使用
                    session.headers['Cookie'] = cookie_str
                except UnicodeEncodeError:
                    # 包含非ASCII字符，进行URL编码处理
                    print("检测到Cookie中包含非ASCII字符，进行编码处理")
                    import urllib.parse
                    # 对Cookie值进行URL编码
                    encoded_cookie = urllib.parse.quote(cookie_str, safe='=; ')
                    session.headers['Cookie'] = encoded_cookie
                    print("Cookie编码处理完成")
                    
            except Exception as e:
                print(f"Cookie处理错误: {e}")
                print("将跳过Cookie设置，仅使用API方式")
                # 清空cookie，避免后续使用
                self.fofa_cookie = None
        
        return session
    
    def search_fofa_api(self, query):
        """使用FOFA API搜索IP - 支持翻页获取多页数据"""
        print("===============从 FOFA API 检索 IP+端口===============")
        
        # 使用base64编码查询
        query_b64 = base64.b64encode(query.encode()).decode().replace('\n', '')
        
        print(f"搜索查询: {query}")
        print(f"最大翻页数限制: {self.max_pages} 页")
        
        # 构建API请求URL
        api_url = "https://fofa.info/api/v1/search/all"
        all_ip_ports = []
        
        try:
            # 创建session
            session = requests.Session()
            session.headers.update({
                'User-Agent': self.fofa_user_agent,
                'Accept': 'application/json'
            })
            
            # 第一次请求，获取总数据量
            params = {
                'key': self.fofa_api_key,
                'qbase64': query_b64,
                'fields': 'ip,port,host',  # 指定返回字段
                'size': 10,  # 每页数量
                'page': 1,    # 页码
                'full': 'false'  # 搜索一年内数据
            }
            
            print(f"FOFA API URL: {api_url}")
            print(f"查询参数: key={self.fofa_api_key[:10]}..., size={params['size']}")
            
            print("发送第一次请求获取总数据量...")
            time.sleep(1)  # 添加延迟避免API限流
            
            response = session.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            
            # 明确设置响应编码为UTF-8
            response.encoding = 'utf-8'
            
            print(f"响应状态码: {response.status_code}")
            
            # 解析JSON响应
            response_json = response.json()
            
            # 检查API响应错误
            if response_json.get('error', False):
                error_msg = response_json.get('errmsg', '未知错误')
                print(f"FOFA API错误: {error_msg}")
                return []
            
            # 获取结果数据
            total_size = response_json.get('size', 0)
            current_page = response_json.get('page', 1)
            results = response_json.get('results', [])
            
            print(f"API返回总数据量: {total_size}")
            print(f"当前页: {current_page}, 当前页结果数: {len(results)}")
            
            # 计算总页数
            page_size = 10
            total_pages = (total_size + page_size - 1) // page_size  # 向上取整
            
            # 应用最大页数限制
            actual_pages = min(total_pages, self.max_pages)
            print(f"总页数: {total_pages}, 实际获取页数: {actual_pages}")
            
            # 处理第一页数据
            page_ip_ports = self._extract_fofa_api_results(results)
            all_ip_ports.extend(page_ip_ports)
            print(f"第1页提取到 {len(page_ip_ports)} 个IP:PORT")
            
            # 如果有多页，继续获取其他页的数据
            if actual_pages > 1:
                for page in range(2, actual_pages + 1):
                    print(f"正在获取第 {page}/{actual_pages} 页数据...")
                    
                    # 更新页码参数
                    params['page'] = page
                    
                    # 添加延迟避免API限流
                    time.sleep(1)
                    
                    try:
                        response = session.get(api_url, params=params, timeout=30)
                        response.raise_for_status()
                        
                        # 明确设置响应编码为UTF-8
                        response.encoding = 'utf-8'
                        
                        response_json = response.json()
                        
                        if response_json.get('error', False):
                            error_msg = response_json.get('errmsg', '未知错误')
                            print(f"第{page}页FOFA API错误: {error_msg}")
                            continue
                        
                        results = response_json.get('results', [])
                        page_ip_ports = self._extract_fofa_api_results(results)
                        all_ip_ports.extend(page_ip_ports)
                        print(f"第{page}页提取到 {len(page_ip_ports)} 个IP:PORT")
                        
                    except KeyboardInterrupt:
                        print(f"\n用户中断，已获取前 {page-1} 页数据")
                        break
                    except Exception as e:
                        print(f"获取第{page}页数据失败: {e}")
                        continue
            
            # 去重
            unique_ips = list(set(all_ip_ports))
            
            print(f"FOFA API总共提取到 {len(all_ip_ports)} 个IP:PORT")
            print(f"去重后共 {len(unique_ips)} 个唯一IP")
            
            if unique_ips:
                print("前10个IP:")
                for ip in unique_ips[:10]:
                    print(f"  {ip}")
                if len(unique_ips) > 10:
                    print(f"... 还有 {len(unique_ips) - 10} 个")
                return unique_ips
            else:
                print("FOFA API搜索未找到任何有效IP")
                return []
                
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_ip_ports)} 个结果")
            return list(set(all_ip_ports))  # 返回已获取的去重结果
        except requests.exceptions.RequestException as e:
            print(f"FOFA API请求失败: {e}")
            return []
        except Exception as e:
            print(f"FOFA API搜索异常: {e}")
            return []
    
    def _extract_fofa_api_results(self, results):
        """提取FOFA API搜索结果数据"""
        ip_ports = []
        
        for result in results:
            if len(result) >= 2:  # 确保有IP和端口数据
                # FOFA API返回格式通常是：[ip, port, host] 的顺序
                ip = result[0] if len(result) > 0 else None
                port = result[1] if len(result) > 1 else None
                
                # 处理IP和端口
                if ip and port:
                    # 清理IP地址（移除协议前缀）
                    ip = str(ip)
                    if ip.startswith('http://'):
                        ip = ip[7:]
                    elif ip.startswith('https://'):
                        ip = ip[8:]
                    
                    # 如果IP包含端口，提取IP部分
                    if ':' in ip:
                        ip = ip.split(':')[0]
                    
                    # 验证IP格式
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                        ip_port = f"{ip}:{port}"
                        ip_ports.append(ip_port)
        
        return ip_ports
    
    def search_fofa_cookie(self, query):
        """使用FOFA Cookie搜索IP - 支持翻页获取多页数据"""
        print("===============从 FOFA 检索 IP+端口 (使用Cookie认证)===============")
        
        query_b64 = base64.b64encode(query.encode()).decode().replace('\n', '')
        
        print(f"搜索查询: {query}")
        print(f"最大翻页数限制: {self.max_pages} 页")
        
        all_ip_ports = []
        
        try:
            session = self._create_session_with_retry()
            
            # 第一次请求，获取总数据量和页面信息
            first_url = f"https://fofa.info/result?qbase64={query_b64}&page=1&page_size=10"
            print(f"FOFA URL: {first_url}")
            
            print("发送第一次请求获取总数据量...")
            response = session.get(first_url, timeout=30)
            response.raise_for_status()
            
            # 明确设置响应编码为UTF-8
            response.encoding = 'utf-8'
            
            print(f"响应状态码: {response.status_code}")
            print(f"响应内容长度: {len(response.text)} 字符")
            
            # 检查是否被拒绝访问
            if '[-3000]' in response.text:
                print("被拒绝访问 [-3000] - 可能需要更新Cookie")
                return []
            
            # 检查是否需要登录
            if 'login' in response.url.lower() or '登录' in response.text:
                print("检测到需要登录 - 请检查Cookie是否有效")
                return []
            
            # 提取页面信息
            total_count, page_size = self._extract_fofa_page_info(response.text)
            print(f"总数据量: {total_count}")
            print(f"页面大小: {page_size}")
            
            # 计算总页数
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1  # 向上取整
            
            # 应用最大页数限制
            actual_pages = min(total_pages, self.max_pages)
            print(f"总页数: {total_pages}, 实际获取页数: {actual_pages}")
            
            # 处理第一页数据
            first_page_ips = self._extract_fofa_cookie_results(response.text)
            all_ip_ports.extend(first_page_ips)
            print(f"第1页提取到 {len(first_page_ips)} 个IP")
            
            # 如果有多页，继续获取其他页的数据
            if actual_pages > 1:
                for page in range(2, actual_pages + 1):
                    print(f"正在获取第 {page}/{actual_pages} 页数据...")
                    
                    page_url = f"https://fofa.info/result?qbase64={query_b64}&page={page}&page_size={page_size}"
                    
                    # 添加延迟避免被限流
                    time.sleep(2)
                    
                    try:
                        response = session.get(page_url, timeout=30)
                        response.raise_for_status()
                        
                        # 明确设置响应编码为UTF-8
                        response.encoding = 'utf-8'
                        
                        # 检查响应是否有效
                        if '[-3000]' in response.text:
                            print(f"第{page}页被拒绝访问 [-3000]")
                            continue
                        
                        if 'login' in response.url.lower() or '登录' in response.text:
                            print(f"第{page}页需要重新登录")
                            break
                        
                        page_ips = self._extract_fofa_cookie_results(response.text)
                        all_ip_ports.extend(page_ips)
                        print(f"第{page}页提取到 {len(page_ips)} 个IP")
                        
                    except KeyboardInterrupt:
                        print(f"\n用户中断，已获取前 {page-1} 页数据")
                        break
                    except Exception as e:
                        print(f"获取第{page}页数据失败: {e}")
                        continue
            
            # 去重结果
            unique_ips = list(set(all_ip_ports))
            
            print(f"FOFA Cookie总共提取到 {len(all_ip_ports)} 个IP:PORT")
            print(f"去重后共 {len(unique_ips)} 个唯一IP")
            
            if unique_ips:
                print("前10个IP:")
                for ip in unique_ips[:10]:
                    print(f"  {ip}")
                if len(unique_ips) > 10:
                    print(f"... 还有 {len(unique_ips) - 10} 个")
                return unique_ips
            else:
                print("FOFA搜索未找到任何IP")
                return []
                
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_ip_ports)} 个结果")
            return list(set(all_ip_ports))  # 返回已获取的去重结果
        except requests.exceptions.RequestException as e:
            print(f"FOFA请求失败: {e}")
            print(f"错误类型: {type(e).__name__}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"响应状态码: {e.response.status_code}")
                print(f"响应头: {dict(e.response.headers)}")
            return []
        except UnicodeEncodeError as e:
            print(f"FOFA搜索编码错误: {e}")
            print(f"错误发生在: 编码 '{e.object[e.start:e.end]}' 使用 '{e.encoding}' 编码")
            print("这通常是由于Cookie中包含了非ASCII字符导致的")
            print("建议检查FOFA_COOKIE环境变量中是否包含中文字符")
            return []
        except Exception as e:
            print(f"FOFA搜索异常: {e}")
            print(f"错误类型: {type(e).__name__}")
            import traceback
            print("错误堆栈:")
            traceback.print_exc()
            return []
    
    def _extract_fofa_page_info(self, content):
        """提取FOFA页面的总数量和页面大小信息"""
        total_count = 0
        page_size = 10
        
        try:
            # 方法1: 尝试从JavaScript变量中提取总数
            # 支持多种可能的变量名（bI, aC, 等混淆后的变量名）
            total_patterns = [
                r'bI\.total\s*=\s*(\d+)',     # 原始模式
                r'aC\.total\s*=\s*(\d+)',     # 新发现的模式
                r'[a-zA-Z]{1,3}\.total\s*=\s*(\d+)',  # 通用模式，匹配任意1-3个字母的变量名
            ]
            
            for pattern in total_patterns:
                total_match = re.search(pattern, content)
                if total_match:
                    total_count = int(total_match.group(1))
                    print(f"从变量提取到总数: {total_count} (模式: {pattern})")
                    break
            
            # 方法1.5: 专门处理连续赋值的情况，如 aC.size=10;aC.total=503
            if total_count == 0:
                # 查找连续赋值模式
                continuous_pattern = r'([a-zA-Z]{1,4})\.(?:size|total)\s*=\s*\d+[;\s]*\1\.(?:size|total)\s*=\s*\d+'
                continuous_match = re.search(continuous_pattern, content)
                if continuous_match:
                    var_name = continuous_match.group(1)
                    # 提取这个变量的total值
                    total_pattern = f'{var_name}\\.total\\s*=\\s*(\\d+)'
                    total_match = re.search(total_pattern, content)
                    if total_match:
                        total_count = int(total_match.group(1))
                        print(f"从连续赋值提取到总数: {total_count} (变量: {var_name})")
            
            # 方法2: 尝试从页面HTML中查找数据总数信息
            if total_count == 0:
                # 查找类似 "共xxx条数据" 的模式
                count_patterns = [
                    r'共\s*(\d+)\s*条',
                    r'total:\s*(\d+)',
                    r'count:\s*(\d+)',
                    r'results:\s*(\d+)'
                ]
                
                for pattern in count_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        total_count = int(match.group(1))
                        print(f"从页面内容提取到总数: {total_count}")
                        break
            
            # 方法3: 如果还是没找到，根据实际提取的IP数量估算
            if total_count == 0:
                # 计算页面中实际的IP数量来估算
                ip_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+\b'
                found_ips = re.findall(ip_pattern, content)
                if found_ips:
                    actual_count = len(set(found_ips))  # 去重后的数量
                    print(f"根据页面实际IP数量估算: 当前页有 {actual_count} 个IP")
                    # 如果第一页就有较多IP，可能总数更多
                    if actual_count >= 10:
                        total_count = actual_count * 3  # 保守估计
                        print(f"估算总数据量: {total_count}")
            
            # 调试：如果仍然无法提取数据，尝试查找所有可能的JavaScript变量赋值
            if total_count == 0:
                print("  [调试] 正在查找页面中的JavaScript变量...")
                # 查找所有类似 xx.total = 数字 或 xx.size = 数字 的模式
                debug_patterns = [
                    r'([a-zA-Z]{1,4})\.total\s*=\s*(\d+)',
                    r'([a-zA-Z]{1,4})\.size\s*=\s*(\d+)',
                    r'total["\']?\s*:\s*(\d+)',
                    r'size["\']?\s*:\s*(\d+)',
                ]
                
                for pattern in debug_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        for match in matches[:3]:  # 只显示前3个匹配
                            if len(match) == 2:  # 变量名和值
                                print(f"    发现变量: {match[0]}.total/size = {match[1]}")
                            else:  # 只有值
                                print(f"    发现值: {match}")
            
            # 查找页面大小的多种模式
            size_patterns = [
                r'bI\.size\s*=\s*(\d+)',      # 原始模式
                r'aC\.size\s*=\s*(\d+)',      # 新发现的模式
                r'[a-zA-Z]{1,3}\.size\s*=\s*(\d+)',   # 通用模式
            ]
            
            for pattern in size_patterns:
                size_match = re.search(pattern, content)
                if size_match:
                    extracted_page_size = int(size_match.group(1))
                    print(f"从变量提取到页面大小: {extracted_page_size} (模式: {pattern})")
                    if extracted_page_size != page_size:
                        print(f"警告: 提取的页面大小({extracted_page_size})与预期({page_size})不符")
                        if extracted_page_size > 0:
                            page_size = extracted_page_size
                    break
            
            # 如果仍未找到页面大小，尝试从总数提取中使用的同一变量名
            if page_size == 10 and total_count > 0:  # 如果总数已找到但页面大小还是默认值
                # 从前面成功的total提取中获取变量名
                for pattern in total_patterns:
                    total_match = re.search(pattern, content)
                    if total_match:
                        # 提取变量名部分
                        var_match = re.match(r'([a-zA-Z]{1,3})\.', pattern)
                        if var_match:
                            var_name = var_match.group(1)
                            size_pattern = f'{var_name}\\.size\\s*=\\s*(\\d+)'
                            size_match = re.search(size_pattern, content)
                            if size_match:
                                extracted_page_size = int(size_match.group(1))
                                print(f"从同变量提取到页面大小: {extracted_page_size} (变量: {var_name})")
                                if extracted_page_size > 0:
                                    page_size = extracted_page_size
                                break
                        break
                        
        except Exception as e:
            print(f"提取页面信息失败: {e}")
        
        return total_count, page_size
    
    def _extract_fofa_cookie_results(self, content):
        """提取FOFA Cookie搜索结果中的IP:PORT数据"""
        all_ips = []
        
        # 方法1：使用第一种方式 - 匹配行首的IP:PORT格式
        line_pattern = r'^\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)\s*$'
        lines = content.split('\n')
        method1_ips = []
        
        for line in lines:
            match = re.match(line_pattern, line)
            if match:
                method1_ips.append(match.group(1))
        
        # 方法2：使用第二种方式 - 全文匹配IP:PORT
        ip_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+\b'
        method2_ips = re.findall(ip_pattern, content)
        
        # 合并两种方法的结果
        all_ips = method1_ips + method2_ips
        
        return all_ips
    
    def search_fofa_ips(self):
        """从 FOFA 搜索 IP - 优先使用API，回退到Cookie"""
        # 根据运营商类型构建搜索查询（简化为单个查询）
        if self.isp.lower() == 'mobile':
            query = f'"udpxy" && country="CN" && region="{self.region}" && (org="{self.region} Mobile Communication Company Limited" || org="{self.region} Mobile Communications Co." || org="China Mobile Communicaitons Corporation" || org="China Mobile communications corporation" || org="China Mobile Communications Group Co., Ltd." || org="{self.region} Mobile Communications Co.,Ltd." || org="{self.region} Mobile Communications Co.,Ltd" || org="China Mobile Group {self.region} communications corporation" || org="China Mobile Group {self.region} Co.") && protocol="http"'
        elif self.isp.lower() == 'telecom':
            query = f'"udpxy" && country="CN" && region="{self.region}" && (org="Chinanet" || org="China Telecom" || org="CHINA TELECOM" || org="China Telecom Group" || org="{self.region} Telecom" || org="CHINANET {self.region} province network" || org="CHINANET {self.region} province backbone") && protocol="http"'
        elif self.isp.lower() == 'unicom':
            query = f'"udpxy" && country="CN" && region="{self.region}" && (org="CHINA UNICOM China169 Backbone" || org="China Unicom" || org="China Unicom IP network" || org="CHINA UNICOM Industrial Internet Backbone" || org="China Unicom {self.region} network" || org="China Unicom {self.region} IP network" || org="China Unicom {self.region} Province Network" || org="UNICOM {self.region} province network" || org="China Unicom IP network China169 {self.region} province") && protocol="http"'
        else:
            # 默认查询
            query = f'"udpxy" && country="CN" && region="{self.region}" && protocol="http"'
        
        print(f"使用FOFA查询")
        
        # 优先使用API方式，如果失败则回退到Cookie方式
        if self.fofa_api_key:
            print("使用API方式进行查询")
            api_results = self.search_fofa_api(query)
            if api_results:
                print(f"FOFA API找到 {len(api_results)} 个IP")
                return api_results
            else:
                print("API方式失败，尝试Cookie方式")
                cookie_results = self.search_fofa_cookie(query)
                if cookie_results:
                    print(f"FOFA Cookie找到 {len(cookie_results)} 个IP")
                    return cookie_results
        else:
            print("使用Cookie方式进行查询")
            cookie_results = self.search_fofa_cookie(query)
            if cookie_results:
                print(f"FOFA Cookie找到 {len(cookie_results)} 个IP")
                return cookie_results
        
        print("FOFA搜索未找到任何IP")
        return []
    
    def search_quake360_ips(self):
        """从 Quake360 搜索 IP - 使用Token认证"""
        print(f"===============从 Quake360 检索 IP ({self.region})=================")
        
        if not self.quake360_token:
            print("❌ 未配置QUAKE360_TOKEN，跳过Quake360搜索")
            return []
        
        print("🔑 使用 Quake360 Token 方式搜索")
        return self.search_quake360_api()
    
    def search_quake360_api(self):
        """从 Quake360 搜索 IP - API方式，支持翻页获取多页数据"""
        print("--- Quake360 API 搜索 ---")
        
        # 根据运营商类型构建搜索查询
        if self.isp.lower() == 'telecom':
            query = f'"udpxy" AND country: "China" AND province: "{self.region}" AND isp: "中国电信" AND protocol: "http"'
        elif self.isp.lower() == 'unicom':
            query = f'"udpxy" AND country: "China" AND province: "{self.region}" AND isp: "中国联通" AND protocol: "http"'
        elif self.isp.lower() == 'mobile':
            query = f'"udpxy" AND country: "China" AND province: "{self.region}" AND isp: "中国移动" AND protocol: "http"'
        else:
            # 默认查询
            query = f'"udpxy" AND country: "China" AND province: "{self.region}" AND protocol: "http"'
        
        print(f"查询参数: {query}")
        print(f"最大翻页数限制: {self.max_pages} 页")
        
        all_ip_ports = []
        
        # 第一次请求，获取总数据量
        query_data = {
            "query": query,
            "start": 0,
            "size": 10,  # 每页100条数据
            "ignore_cache": False,
            "latest": True,
            "shortcuts": "635fcb52cc57190bd8826d09"
        }
        
        headers = {
            'X-QuakeToken': self.quake360_token,
            'Content-Type': 'application/json',
            'User-Agent': self.fofa_user_agent
        }
        
        try:
            print("发送第一次请求获取总数据量...")
            # 添加延迟避免API限流
            time.sleep(2)
            
            response = requests.post(
                'https://quake.360.net/api/v3/search/quake_service',
                headers=headers,
                json=query_data,
                timeout=30
            )
            response.raise_for_status()
            
            print(f"API响应状态码: {response.status_code}")
            
            # 解析JSON响应
            response_json = response.json()
            
            # 检查API错误
            code = response_json.get('code')
            if code and str(code) not in ['0', '200', 'success']:
                error_message = response_json.get('message', '未知错误')
                print(f"Quake360 API错误: {code} - {error_message}")
                if str(code) == 'q5000':
                    print("  这是Quake360服务器内部错误，可能是临时问题，建议稍后重试")
                return []
            
            # 获取总数据量和分页信息
            meta = response_json.get('meta', {})
            pagination = meta.get('pagination', {})
            total_count = pagination.get('total', 0)
            page_size = pagination.get('page_size', 10)
            current_page = pagination.get('page_index', 1)
            
            print(f"总数据量: {total_count}")
            print(f"当前页: {current_page}, 页面大小: {page_size}")
            
            # 计算总页数
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1  # 向上取整
            
            # 应用最大页数限制
            actual_pages = min(total_pages, self.max_pages)
            print(f"总页数: {total_pages}, 实际获取页数: {actual_pages}")
            
            # 处理第一页数据
            first_page_data = response_json.get('data', [])
            page_ip_ports = self._extract_quake360_results(first_page_data)
            all_ip_ports.extend(page_ip_ports)
            print(f"第1页提取到 {len(page_ip_ports)} 个IP:PORT")
            
            # 如果有多页，继续获取其他页的数据
            if actual_pages > 1 and total_count > 0:
                for page in range(2, actual_pages + 1):
                    print(f"正在获取第 {page}/{actual_pages} 页数据...")
                    
                    # 更新分页参数
                    query_data['start'] = (page - 1) * page_size
                    
                    # 添加延迟避免API限流
                    time.sleep(2)
                    
                    try:
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
                            if str(code) == 'q5000':
                                print(f"第{page}页Quake360服务器内部错误，跳过该页")
                            else:
                                print(f"第{page}页Quake360 API错误: {code} - {error_message}")
                            continue
                        
                        page_data = response_json.get('data', [])
                        page_ip_ports = self._extract_quake360_results(page_data)
                        all_ip_ports.extend(page_ip_ports)
                        print(f"第{page}页提取到 {len(page_ip_ports)} 个IP:PORT")
                        
                    except KeyboardInterrupt:
                        print(f"\n用户中断，已获取前 {page-1} 页数据")
                        break
                    except Exception as e:
                        print(f"获取第{page}页数据失败: {e}")
                        continue
            
            # 去重结果
            unique_ips = list(set(all_ip_ports))
            
            print(f"Quake360 API总共提取到 {len(all_ip_ports)} 个IP:PORT")
            print(f"去重后共 {len(unique_ips)} 个唯一IP")
            
            if unique_ips:
                # 显示前10个IP
                print("提取到的IP地址:")
                for ip in unique_ips[:10]:
                    print(f"  {ip}")
                if len(unique_ips) > 10:
                    print(f"  ... 还有 {len(unique_ips) - 10} 个")
                
                return unique_ips
            else:
                print("Quake360 API未找到有效的IP地址")
                return []
                
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_ip_ports)} 个结果")
            return list(set(all_ip_ports))  # 返回已获取的去重结果
        except requests.exceptions.RequestException as e:
            print(f"Quake360 API请求失败: {e}")
            return []
        except Exception as e:
            print(f"Quake360 API搜索异常: {e}")
            return []
    
    def _extract_quake360_results(self, data_list):
        """提取Quake360搜索结果数据"""
        ip_ports = []
        
        for item in data_list:
            if isinstance(item, dict):
                # 提取IP地址 - 尝试多个可能的字段名
                ip = (item.get('ip') or 
                      item.get('host') or 
                      item.get('address') or
                      item.get('target') or
                      item.get('service', {}).get('ip') if isinstance(item.get('service'), dict) else None)
                
                # 提取端口 - 尝试多个可能的字段名
                port = (item.get('port') or 
                       item.get('service_port') or 
                       item.get('target_port') or
                       item.get('service', {}).get('port') if isinstance(item.get('service'), dict) else None)
                
                # 组合IP:PORT
                if ip and port:
                    # 确保IP是有效的IP地址格式（不包含域名）
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', str(ip)):
                        ip_port = f"{ip}:{port}"
                        ip_ports.append(ip_port)
        
        return ip_ports
    
        
    def test_port_connectivity(self, ip_port, timeout=2):
        """测试端口连通性"""
        try:
            ip, port = ip_port.split(':')
            port = int(port)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            return result == 0
        except Exception:
            return False
    
    def test_udpxy_service(self, ip_port, timeout=5):
        """测试是否为udpxy服务器"""
        try:
            ip, port = ip_port.split(':')
            port = int(port)
            
            # 创建socket连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            try:
                sock.connect((ip, port))
                
                # 发送HTTP GET请求
                request = f"GET / HTTP/1.1\r\nHost: {ip}:{port}\r\nConnection: close\r\nUser-Agent: udpxy-test\r\n\r\n"
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
                return is_udpxy
                
            except Exception as e:
                sock.close()
                return False
                
        except Exception as e:
            return False
    
    def get_udpxy_status(self, ip_port, timeout=5):
        """获取udpxy状态页面的详细信息（如活跃连接数）"""
        try:
            # 构建状态页面URL
            status_url = f"http://{ip_port}/status"
            
            # 创建session进行HTTP请求
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'udpxy-status-checker',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Connection': 'close'
            })
            
            response = session.get(status_url, timeout=timeout)
            response.raise_for_status()
            
            html_content = response.text
            
            # 使用BeautifulSoup解析HTML页面
            if BEAUTIFULSOUP_AVAILABLE:
                try:
                    soup = BeautifulSoup(html_content, "html.parser")
                    
                    # 查找状态表格 (cellspacing='0')
                    client_table = soup.find('table', attrs={'cellspacing': '0'})
                    
                    if client_table:
                        # 找到所有的<td>标签
                        td_tags = client_table.find_all('td')
                        
                        if len(td_tags) >= 4:
                            # 获取状态信息
                            addr = td_tags[2].text.strip() if len(td_tags) > 2 else "N/A"
                            actv = td_tags[3].text.strip() if len(td_tags) > 3 else "0"
                            
                            try:
                                actv_count = int(actv)
                            except ValueError:
                                actv_count = 0
                            
                            status_info = {
                                'address': addr,
                                'active_connections': actv_count,
                                'status_available': True
                            }
                            
                            return status_info
                    else:
                        # 没有找到标准格式的表格，尝试其他解析方式
                        return self._parse_alternative_status_format(html_content)
                        
                except Exception as e:
                    print(f"  BeautifulSoup解析状态页面失败: {e}")
                    return self._parse_status_with_regex(html_content)
            else:
                # 如果没有BeautifulSoup，使用正则表达式解析
                return self._parse_status_with_regex(html_content)
            
            # 如果所有解析方法都失败，返回默认状态
            return {
                'address': "N/A",
                'active_connections': 0,
                'status_available': False,
                'error': "所有解析方法都失败"
            }
                
        except requests.exceptions.RequestException as e:
            return {
                'address': "N/A", 
                'active_connections': 0,
                'status_available': False,
                'error': f"请求失败: {e}"
            }
        except Exception as e:
            return {
                'address': "N/A",
                'active_connections': 0, 
                'status_available': False,
                'error': f"未知错误: {e}"
            }
    
    def _parse_alternative_status_format(self, html_content):
        """解析其他格式的udpxy状态页面"""
        try:
            # 尝试查找常见的状态信息模式
            import re
            
            # 查找活跃连接数的模式
            patterns = [
                r'active[^:]*:\s*(\d+)',
                r'clients[^:]*:\s*(\d+)', 
                r'connections[^:]*:\s*(\d+)',
                r'>(\d+)</td>\s*</tr>\s*</table>',  # 表格最后一个数字
            ]
            
            actv_count = 0
            for pattern in patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    try:
                        actv_count = int(match.group(1))
                        break
                    except ValueError:
                        continue
            
            return {
                'address': "Alternative Format",
                'active_connections': actv_count,
                'status_available': True
            }
            
        except Exception as e:
            return {
                'address': "N/A",
                'active_connections': 0,
                'status_available': False,
                'error': f"备用解析失败: {e}"
            }
    
    def _parse_status_with_regex(self, html_content):
        """使用正则表达式解析状态页面（不依赖BeautifulSoup）"""
        try:
            import re
            
            # 查找表格中的数据
            td_pattern = r'<td[^>]*>(.*?)</td>'
            td_matches = re.findall(td_pattern, html_content, re.IGNORECASE | re.DOTALL)
            
            if len(td_matches) >= 4:
                addr = td_matches[2].strip() if len(td_matches) > 2 else "N/A"
                actv_text = td_matches[3].strip() if len(td_matches) > 3 else "0"
                
                # 清理HTML标签
                addr = re.sub(r'<[^>]+>', '', addr).strip()
                actv_text = re.sub(r'<[^>]+>', '', actv_text).strip()
                
                try:
                    actv_count = int(actv_text)
                except ValueError:
                    actv_count = 0
                
                return {
                    'address': addr,
                    'active_connections': actv_count,
                    'status_available': True
                }
            
            return {
                'address': "N/A",
                'active_connections': 0,
                'status_available': False,
                'error': "未找到有效的表格数据"
            }
            
        except Exception as e:
            return {
                'address': "N/A",
                'active_connections': 0,
                'status_available': False,
                'error': f"正则解析失败: {e}"
            }
    
    def filter_accessible_ips(self, ip_list):
        """过滤可访问的 IP 并验证是否为udpxy服务"""
        print(f"============IP端口检测，测试 {len(ip_list)} 个 IP==============")
        
        accessible_ips = []
        udpxy_ips = []
        
        def test_single_ip(ip_port):
            # 先测试端口连通性
            if not self.test_port_connectivity(ip_port):
                return None, False, None
            
            # 再测试是否为udpxy服务
            is_udpxy = self.test_udpxy_service(ip_port)
            
            # 如果是udpxy服务，获取状态信息
            status_info = None
            if is_udpxy:
                status_info = self.get_udpxy_status(ip_port)
            
            return ip_port, is_udpxy, status_info
        
        # 并发测试端口连通性和udpxy服务
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(test_single_ip, ip) for ip in ip_list]
            
            for future in as_completed(futures):
                result = future.result()
                if result[0]:  # 端口可达
                    accessible_ips.append(result[0])
                    print(f"端口可达: {result[0]}")
                    
                    if result[1]:  # 是udpxy服务
                        udpxy_ips.append(result[0])
                        status_info = result[2]  # 状态信息
                        
                        if status_info and status_info.get('status_available'):
                            actv = status_info.get('active_connections', 0)
                            addr = status_info.get('address', 'N/A')
                            print(f"  ✓ udpxy服务: {result[0]} (活跃连接: {actv}, 地址: {addr})")
                        else:
                            print(f"  ✓ udpxy服务: {result[0]} (状态信息不可用)")
                    else:
                        print(f"  ✗ 非udpxy服务: {result[0]}")
        
        print(f"===============检索完成，找到 {len(accessible_ips)} 个可访问 IP，{len(udpxy_ips)} 个udpxy服务===============")
        
        # 保存所有可访问的IP
        with open(self.ipfile_sum, 'w') as f:
            for ip in accessible_ips:
                f.write(f"{ip}\n")
        
        # 保存udpxy服务IP（去重）
        unique_udpxy_ips = list(set(udpxy_ips))
        with open(self.ipfile_uniq, 'w') as f:
            for ip in sorted(unique_udpxy_ips):
                f.write(f"{ip}\n")
        
        print(f"【{self.ipfile_uniq}】内 udpxy IP 共计 {len(unique_udpxy_ips)} 个")
        return unique_udpxy_ips
    
    def test_stream_speed(self, ip_port):
        """测试流媒体速度 - 直接下载流媒体数据"""
        session = None
        try:
            # 创建独立的session
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'FFmpeg/4.4.0',
                'Accept': '*/*',
                'Connection': 'keep-alive'
            })
            
            # 设置适配器
            adapter = HTTPAdapter(
                pool_connections=1,
                pool_maxsize=1,
                max_retries=0
            )
            session.mount('http://', adapter)
            
            # 构建流媒体URL
            stream_url = f"http://{ip_port}/{self.stream}"
            print(f"  测试流媒体: {stream_url}")
            
            # 直接下载流媒体数据
            start_time = time.time()
            max_download_size = 2 * 1024 * 1024  # 2MB限制
            max_download_time = 10  # 最大下载时间10秒
            downloaded_data = b''
            
            try:
                # 发起流式请求
                response = session.get(
                    stream_url,
                    timeout=(3, 5),
                    stream=True,
                    allow_redirects=True
                )
                
                if response.status_code != 200:
                    print(f"  ! {ip_port} 流媒体响应状态码: {response.status_code}")
                    return None
                
                print(f"  开始下载流媒体数据...")
                
                # 流式下载数据
                chunk_count = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_data += chunk
                        chunk_count += 1
                        
                        # 检查退出条件
                        current_time = time.time()
                        elapsed_time = current_time - start_time
                        current_size = len(downloaded_data)
                        
                        # 每接收到一定数据就显示进度
                        if chunk_count % 50 == 0:
                            current_speed = (current_size / elapsed_time) / 1024 / 1024 if elapsed_time > 0 else 0
                            print(f"    已下载: {current_size/1024:.1f}KB, 耗时: {elapsed_time:.1f}s, 当前速度: {current_speed:.2f}MB/s")
                        
                        # 超过大小限制
                        if current_size >= max_download_size:
                            print(f"    达到大小限制: {max_download_size/1024/1024}MB")
                            break
                            
                        # 超过时间限制
                        if elapsed_time > max_download_time:
                            print(f"    达到时间限制: {max_download_time}秒")
                            break
                
                end_time = time.time()
                
            except requests.exceptions.ConnectTimeout:
                print(f"  ! {ip_port} 流媒体连接超时")
                return None
            except requests.exceptions.ReadTimeout:
                print(f"  ! {ip_port} 流媒体读取超时")
                return None
            except requests.exceptions.ConnectionError as e:
                print(f"  ! {ip_port} 流媒体连接错误: {str(e)[:50]}...")
                return None
            except Exception as e:
                print(f"  ! {ip_port} 流媒体下载异常: {str(e)[:50]}...")
                return None
            
            # 计算下载统计
            total_size = len(downloaded_data)
            total_duration = end_time - start_time
            
            if total_duration <= 0:
                print(f"  ! {ip_port} 下载时间异常: {total_duration}秒")
                return None
                
            if total_size == 0:
                print(f"  ! {ip_port} 未下载到数据，可能流地址无效")
                return None
            
            # 检查是否下载量太少（可能连接有问题）
            if total_size < 1024:  # 小于1KB
                print(f"  ! {ip_port} 下载量过少: {total_size}字节，可能连接不稳定")
                return None
            
            # 计算平均速度
            speed_bytes_per_sec = total_size / total_duration
            speed_mb_per_sec = speed_bytes_per_sec / 1024 / 1024
            
            # 检查速度合理性
            if speed_mb_per_sec < 0.05:
                print(f"  ! {ip_port} 速度过慢: {speed_mb_per_sec:.3f} MB/s")
                return None
            
            if speed_mb_per_sec > 1000:
                print(f"  ! {ip_port} 速度异常: {speed_mb_per_sec:.3f} MB/s")
                return None
            
            print(f"  ✓ {ip_port} 下载完成:")
            print(f"    总大小: {total_size/1024:.1f}KB")
            print(f"    总耗时: {total_duration:.2f}秒") 
            print(f"    平均速度: {speed_mb_per_sec:.3f}MB/s")
            
            return {
                'ip': ip_port,
                'speed': speed_mb_per_sec,
                'file_size': total_size,
                'duration': total_duration,
                'url': stream_url
            }
            
        except Exception as e:
            print(f"  ! {ip_port} 测速异常: {str(e)[:100]}...")
            return None
        finally:
            # 确保session被正确关闭
            if session:
                try:
                    session.close()
                except:
                    pass
    
    def run_speed_tests(self, ip_list):
        """运行流媒体测速"""
        print("==========开始流媒体测速=================")
        
        if not ip_list:
            print("没有可测试的 IP")
            return []
        
        speed_results = []
        error_count = 0
        
        def test_single_stream(index, ip_port):
            try:
                print(f"{index + 1}/{len(ip_list)} 测试udpxy服务: {ip_port}")
                
                # 测试流媒体速度
                result = self.test_stream_speed(ip_port)
                if result:
                    speed_str = f"{result['speed']:.3f} MB/s"
                    print(f"  ✓ {ip_port} - 速度: {speed_str}")
                    
                    # 写入日志
                    with open(self.speedtest_log, 'a', encoding='utf-8') as f:
                        f.write(f"{ip_port} {speed_str} Size:{result['file_size']}\n")
                    
                    return result
                else:
                    print(f"  ✗ {ip_port} - 流媒体测速不可用!")
                    return None
            except Exception as e:
                print(f"  ✗ {ip_port} - 测试异常: {e}")
                return None
        
        # 清空之前的日志
        if os.path.exists(self.speedtest_log):
            os.remove(self.speedtest_log)
        
        # 减少并发数，增加超时控制
        with ThreadPoolExecutor(max_workers=3) as executor:
            # 提交所有任务
            future_to_ip = {
                executor.submit(test_single_stream, i, ip): ip 
                for i, ip in enumerate(ip_list)
            }
            
            # 使用更短的超时等待结果
            completed_count = 0
            for future in as_completed(future_to_ip, timeout=120):
                try:
                    result = future.result(timeout=15)
                    completed_count += 1
                    
                    if result:
                        speed_results.append(result)
                        print(f"  完成任务 {completed_count}/{len(ip_list)}: 速度 {result['speed']:.3f} MB/s")
                    else:
                        error_count += 1
                        print(f"  完成任务 {completed_count}/{len(ip_list)}: 失败")
                        
                except Exception as e:
                    error_count += 1
                    completed_count += 1
                    ip_port = future_to_ip[future]
                    print(f"  完成任务 {completed_count}/{len(ip_list)}: {ip_port} - 任务超时或异常: {e}")
                
                # 显示进度
                progress = (completed_count / len(ip_list)) * 100
                print(f"进度: {progress:.1f}% - 可用IP：{len(speed_results)} 个, 不可用IP：{error_count} 个")
        
        print(f"==========流媒体测速完成=================")
        print(f"总计: {len(speed_results)} 个可用IP, {error_count} 个失败")
        
        return speed_results
    
    def generate_results(self, speed_results):
        """生成结果文件"""
        if not speed_results:
            print("未生成测速文件")
            return
        
        # 筛选速度大于 0.1 MB/s 的结果并排序
        filtered_results = [r for r in speed_results if r['speed'] > 0.1]
        
        if not filtered_results:
            print("没有满足速度要求的 IP (>0.1 MB/s)")
            return
        
        # 按速度降序排序
        filtered_results.sort(key=lambda x: x['speed'], reverse=True)
        
        # 保存结果
        with open(self.result_file, 'w', encoding='utf-8') as f:
            for result in filtered_results:
                f.write(f"{result['speed']:.3f}  {result['ip']}\n")
        
        print(f"======本次{self.region}组播IP搜索结果=============")
        for result in filtered_results:
            print(f"{result['speed']:.3f} MB/s  {result['ip']}")
        
        # 合并模板文件
        self._merge_template_file(filtered_results)
    
    def _merge_template_file(self, results):
        """合并模板文件"""
        template_file = Path(f"template/{self.isp}/template_{self.city}.txt")
        output_file = self.output_dir / f"{self.city}.txt"
        
        if not template_file.exists():
            print(f"警告: 模板文件 {template_file} 不存在，跳过合并步骤")
            return
        
        print(f"----合并列表文件到：{output_file}---------")
        
        try:
            with open(template_file, 'r', encoding='utf-8') as tf:
                template_content = tf.read()
            
            with open(output_file, 'w', encoding='utf-8') as of:
                for result in results:
                    ip = result['ip']
                    print(f"Processing IP: {ip} (Speed: {result['speed']:.3f} MB/s)")
                    
                    # 替换模板中的占位符
                    content = template_content.replace('ipipip', ip)
                    of.write(content)
                    
        except Exception as e:
            print(f"合并模板文件失败: {e}")
    
    def _save_basic_results(self, udpxy_ips):
        """保存基本的IP检测结果（不进行流媒体测试时使用）"""
        try:
            # 确保输出目录存在
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存所有找到的udpxy IP到sum文件
            with open(self.ipfile_sum, 'w', encoding='utf-8') as f:
                for ip in udpxy_ips:
                    # 保存实际的IP:PORT格式
                    f.write(f"{ip}\n")
            print(f"保存 {len(udpxy_ips)} 个udpxy服务器到: {self.ipfile_sum}")
            
            # 也保存到uniq文件（去重文件）
            with open(self.ipfile_uniq, 'w', encoding='utf-8') as f:
                unique_ips = list(set(udpxy_ips))
                for ip in unique_ips:
                    # 保存实际的IP:PORT格式
                    f.write(f"{ip}\n")
            print(f"保存 {len(unique_ips)} 个唯一udpxy服务器到: {self.ipfile_uniq}")
            
            # 保存简单的结果报告
            report_file = self.output_dir / f"{self.city}_basic_report.txt"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(f"UDPXY服务器搜索报告\n")
                f.write(f"地区: {self.region}\n")
                f.write(f"运营商: {self.isp}\n")
                f.write(f"搜索时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"找到的udpxy服务器数量: {len(udpxy_ips)}\n")
                f.write(f"唯一服务器数量: {len(set(udpxy_ips))}\n")
                f.write(f"\n服务器列表:\n")
                for ip in udpxy_ips:
                    # 保存实际的IP:PORT格式
                    f.write(f"{ip}\n")
            print(f"保存基本报告到: {report_file}")
            
        except Exception as e:
            print(f"保存基本结果失败: {e}")
    
    def cleanup(self):
        """清理临时文件"""
        temp_files = [
            self.speedtest_log,
            "temp_video.mp4",
            "ffmpeg.log"
        ]
        
        for file_path in temp_files:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"删除临时文件: {file_path}")
    
    def run(self):
        """运行完整的测试流程"""
        try:
            print(f"开始为 {self.region} {self.isp} 搜索和测试 IP")
            if not self.notest:
                print(f"城市: {self.city}, 流地址: {self.stream}")
            else:
                print("跳过流媒体测试模式")
            
            # 1. 搜索 IP
            fofa_ips = self.search_fofa_ips()
            quake_ips = self.search_quake360_ips()
            
            # 合并并去重
            all_ips = list(set(fofa_ips + quake_ips))
            print(f"从FOFA和Quake360总共找到 {len(all_ips)} 个唯一 IP")
            
            if not all_ips:
                print("未找到任何 IP，程序退出")
                return
            
            print(f"总共将测试 {len(all_ips)} 个 IP")
            
            # 2. 过滤可访问的 IP 并验证udpxy服务
            udpxy_ips = self.filter_accessible_ips(all_ips)
            
            if not udpxy_ips:
                print("没有找到可用的udpxy服务器，程序退出")
                return
            
            if self.notest:
                # 只进行IP搜索和端口检测，不进行流媒体测试
                print(f"发现 {len(udpxy_ips)} 个可用的udpxy服务器")
                print("跳过流媒体测试和模板生成")
                
                # 保存基本结果
                self._save_basic_results(udpxy_ips)
                print("-----------------搜索完成----------------")
            else:
                # 3. 运行速度测试（只测试udpxy服务器）
                speed_results = self.run_speed_tests(udpxy_ips)
                
                # 4. 生成结果
                self.generate_results(speed_results)
                
                print("-----------------测速完成----------------")
            
        except KeyboardInterrupt:
            print("\n用户中断程序")
        except Exception as e:
            print(f"程序执行出错: {e}")
        finally:
            # 5. 清理临时文件
            self.cleanup()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='IPTV IP 搜索与测速综合工具 - 新版本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python speedtest_integrated_new.py Shanghai Telecom
  python speedtest_integrated_new.py Beijing Unicom
  python speedtest_integrated_new.py Guangzhou Mobile
  python speedtest_integrated_new.py Shanghai Telecom --max-pages 5
  python speedtest_integrated_new.py Beijing Mobile --notest

运营商可选: Telecom, Unicom, Mobile

参数说明:
  --max-pages: 限制搜索的最大页数
  --notest: 跳过流媒体测试，仅进行IP搜索和端口检测
        """
    )
    
    parser.add_argument('region', help='省市名称 (如: Shanghai, Beijing)')
    parser.add_argument('isp', help='运营商 (Telecom/Unicom/Mobile)')
    parser.add_argument('--max-pages', type=int, default=10, 
                       help='最大翻页数限制 (默认: 10页)')
    parser.add_argument('--notest', action='store_true',
                       help='跳过流媒体测试和模板生成，仅进行IP搜索和端口检测')
    
    args = parser.parse_args()
    
    # 验证运营商参数
    valid_isps = ['telecom', 'unicom', 'mobile']
    if args.isp.lower() not in valid_isps:
        print(f"错误: 不支持的运营商 '{args.isp}'")
        print(f"支持的运营商: {', '.join(valid_isps)}")
        sys.exit(1)
    
    # 验证最大页数参数
    if args.max_pages < 1:
        print(f"错误: 最大页数必须大于0，当前值: {args.max_pages}")
        sys.exit(1)
    
    if args.max_pages > 50:
        print(f"警告: 最大页数过大({args.max_pages})，建议不超过50页")
        response = input("是否继续? (y/N): ")
        if response.lower() != 'y':
            print("用户取消操作")
            sys.exit(0)
    
    print(f"配置信息:")
    print(f"  地区: {args.region}")
    print(f"  运营商: {args.isp}")
    print(f"  最大翻页数: {args.max_pages}")
    if args.notest:
        print(f"  模式: 仅搜索模式（跳过流媒体测试）")
    else:
        print(f"  模式: 完整测试模式")
    
    # 创建测试实例并运行
    speedtest = IPTVSpeedTest(args.region, args.isp, args.max_pages, args.notest)
    speedtest.run()


if __name__ == "__main__":
    main()
