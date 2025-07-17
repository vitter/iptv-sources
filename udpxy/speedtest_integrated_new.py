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


class IPTVSpeedTest:
    """IPTV 测速主类"""
    
    def __init__(self, region, isp):
        # 加载环境变量
        load_dotenv()
        
        self.region = self._format_string(region)
        self.isp = self._format_string(isp)
        
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
        
        # 加载省份配置
        self.city, self.stream = self._load_province_config()
        
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
        
        # 单独设置Cookie头，确保格式正确
        if self.fofa_cookie:
            session.headers['Cookie'] = self.fofa_cookie
        
        return session
    
    def search_fofa_api(self, query):
        """使用FOFA API搜索IP"""
        print("===============从 FOFA API 检索 IP+端口===============")
        
        # 使用base64编码查询
        query_b64 = base64.b64encode(query.encode()).decode().replace('\n', '')
        
        print(f"搜索查询: {query}")
        
        # 构建API请求URL
        api_url = "https://fofa.info/api/v1/search/all"
        params = {
            'key': self.fofa_api_key,
            'qbase64': query_b64,
            'fields': 'ip,port,host',  # 指定返回字段
            'size': 10,  # 每页数量
            'page': 1,    # 页码
            'full': 'false'  # 搜索一年内数据
        }
        
        print(f"FOFA API URL: {api_url}")
        print(f"查询参数: key={self.fofa_api_key[:10]}..., size={params['size']}, page={params['page']}")
        
        try:
            # 创建session
            session = requests.Session()
            session.headers.update({
                'User-Agent': self.fofa_user_agent,
                'Accept': 'application/json'
            })
            
            print("发送FOFA API请求...")
            response = session.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            
            print(f"响应状态码: {response.status_code}")
            
            # 解析JSON响应
            try:
                response_json = response.json()
                
                # 检查API响应错误
                if response_json.get('error', False):
                    error_msg = response_json.get('errmsg', '未知错误')
                    print(f"FOFA API错误: {error_msg}")
                    return []
                
                # 获取结果数据
                results = response_json.get('results', [])
                size = response_json.get('size', 0)
                
                print(f"API返回总数据量: {size}")
                print(f"当前页结果数: {len(results)}")
                
                # 提取IP:PORT组合
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
                                
                print(f"调试信息: 处理了 {len(results)} 个原始结果")
                if results:
                    print("前3个原始结果:")
                    for i, result in enumerate(results[:3]):
                        print(f"  结果 {i+1}: {result} (长度: {len(result)})")
                print(f"成功提取 {len(ip_ports)} 个IP:PORT")
                
                # 去重
                unique_ips = list(set(ip_ports))
                
                if unique_ips:
                    print(f"FOFA API搜索成功，总共找到 {len(unique_ips)} 个唯一 IP")
                    print("前10个IP:")
                    for ip in unique_ips[:10]:
                        print(f"  {ip}")
                    if len(unique_ips) > 10:
                        print(f"... 还有 {len(unique_ips) - 10} 个")
                    return unique_ips
                else:
                    print("FOFA API搜索未找到任何有效IP")
                    # 输出原始数据结构用于调试
                    if results:
                        print("原始数据结构示例:")
                        for i, result in enumerate(results[:3]):
                            print(f"  结果 {i+1}: {result}")
                    return []
                    
            except json.JSONDecodeError as e:
                print(f"JSON解析失败: {e}")
                print("响应内容片段 (前500字符):")
                print(response.text[:500])
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"FOFA API请求失败: {e}")
            return []
        except Exception as e:
            print(f"FOFA API搜索异常: {e}")
            return []
    
    def search_fofa_cookie(self, query):
        """使用FOFA Cookie搜索IP"""
        print("===============从 FOFA 检索 IP+端口 (使用Cookie认证)===============")
        
        query_b64 = base64.b64encode(query.encode()).decode().replace('\n', '')
        fofa_url = f"https://fofa.info/result?qbase64={query_b64}&page=1&page_size=10"
        
        print(f"搜索查询: {query}")
        print(f"FOFA URL: {fofa_url}")
        
        try:
            session = self._create_session_with_retry()
            print("发送FOFA请求...")
            response = session.get(fofa_url, timeout=30)
            response.raise_for_status()
            
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
            
            # 方法1：使用第一种方式 - 匹配行首的IP:PORT格式
            line_pattern = r'^\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+)\s*$'
            lines = response.text.split('\n')
            method1_ips = []
            
            for line in lines:
                match = re.match(line_pattern, line)
                if match:
                    method1_ips.append(match.group(1))
            
            print(f"方法1 (行首匹配): 找到 {len(method1_ips)} 个IP")
            
            # 方法2：使用第二种方式 - 全文匹配IP:PORT
            ip_pattern = r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+\b'
            method2_ips = re.findall(ip_pattern, response.text)
            
            print(f"方法2 (全文匹配): 找到 {len(method2_ips)} 个IP")
            
            # 合并两种方法的结果
            all_ips = method1_ips + method2_ips
            unique_ips = list(set(all_ips))
            
            if unique_ips:
                print(f"FOFA搜索成功，总共找到 {len(unique_ips)} 个唯一 IP")
                print("前10个IP:")
                for ip in unique_ips[:10]:
                    print(f"  {ip}")
                if len(unique_ips) > 10:
                    print(f"... 还有 {len(unique_ips) - 10} 个")
                return unique_ips
            else:
                print("FOFA搜索未找到任何IP")
                # 输出部分响应内容用于调试
                print("响应内容片段 (前500字符):")
                print(response.text[:500])
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"FOFA请求失败: {e}")
            return []
        except Exception as e:
            print(f"FOFA搜索异常: {e}")
            return []
    
    def search_fofa_ips(self):
        """从 FOFA 搜索 IP - 优先使用API，回退到Cookie"""
        # 根据运营商类型构建搜索查询（简化为单个查询）
        if self.isp.lower() == 'mobile':
            query = f'"udpxy" && country="CN" && region="{self.region}" && (org="{self.region} Mobile Communication Company Limited" || org="{self.region} Mobile Communications Co." || org="China Mobile Communicaitons Corporation" || org="China Mobile Group {self.region} communications corporation" || org="China Mobile Group {self.region} Co.") && protocol="http"'
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
        """从 Quake360 搜索 IP - API方式"""
        print("--- Quake360 API 搜索 ---")
        
        # 根据运营商类型构建搜索查询
        if self.isp.lower() == 'telecom':
            query = f'"udpxy" AND country: "CN" AND province: "{self.region}" AND isp: "中国电信" AND protocol: "http"'
        elif self.isp.lower() == 'unicom':
            query = f'"udpxy" AND country: "CN" AND province: "{self.region}" AND isp: "中国联通" AND protocol: "http"'
        elif self.isp.lower() == 'mobile':
            query = f'"udpxy" AND country: "CN" AND province: "{self.region}" AND isp: "中国移动" AND protocol: "http"'
        else:
            # 默认查询
            query = f'"udpxy" AND country: "CN" AND province: "{self.region}" AND protocol: "http"'
        
        print(f"查询参数: {query}")
        
        query_data = {
            "query": query,
            "start": 0,
            "size": 10,  
            "ignore_cache": False,
            "latest": True
        }
        
        headers = {
            'X-QuakeToken': self.quake360_token,
            'Content-Type': 'application/json',
            'User-Agent': self.fofa_user_agent
        }
        
        try:
            response = requests.post(
                'https://quake.360.net/api/v3/search/quake_service',
                headers=headers,
                json=query_data,
                timeout=30
            )
            response.raise_for_status()
            
            print(f"API响应状态码: {response.status_code}")
            
            # 解析JSON响应
            try:
                response_json = response.json()
                
                # 检查API错误
                code = response_json.get('code')
                if code and str(code) not in ['0', '200', 'success']:
                    error_message = response_json.get('message', '未知错误')
                    print(f"Quake360 API错误: {code} - {error_message}")
                    return []
                
                # 从JSON结构中提取IP和端口
                all_ips = []
                if 'data' in response_json and isinstance(response_json['data'], list):
                    data_count = len(response_json['data'])
                    print(f"找到 {data_count} 个数据项")
                    
                    for item in response_json['data']:
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
                                    all_ips.append(ip_port)
                else:
                    print("API响应中未找到有效数据结构")
                    print(f"响应结构: {list(response_json.keys()) if isinstance(response_json, dict) else 'non-dict'}")
                    return []
                
                # 去重结果
                unique_ips = list(set(all_ips))
                
                if unique_ips:
                    print(f"Quake360 API搜索成功: 总共找到 {len(unique_ips)} 个唯一IP")
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
                    
            except json.JSONDecodeError as e:
                print(f"JSON解析失败: {e}")
                print("响应内容片段:")
                print(response.text[:500])
                return []
            
        except requests.exceptions.RequestException as e:
            print(f"Quake360 API请求失败: {e}")
            return []
        except Exception as e:
            print(f"Quake360 API搜索异常: {e}")
            return []
    
        
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
    
    def filter_accessible_ips(self, ip_list):
        """过滤可访问的 IP 并验证是否为udpxy服务"""
        print(f"============IP端口检测，测试 {len(ip_list)} 个 IP==============")
        
        accessible_ips = []
        udpxy_ips = []
        
        def test_single_ip(ip_port):
            # 先测试端口连通性
            if not self.test_port_connectivity(ip_port):
                return None, False
            
            # 再测试是否为udpxy服务
            is_udpxy = self.test_udpxy_service(ip_port)
            return ip_port, is_udpxy
        
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
                        print(f"  ✓ udpxy服务: {result[0]}")
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
            
            if total_duration <= 0 or total_size == 0:
                print(f"  ! {ip_port} 无效的下载统计: size={total_size}, duration={total_duration}")
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
            print(f"城市: {self.city}, 流地址: {self.stream}")
            
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

运营商可选: Telecom, Unicom, Mobile
        """
    )
    
    parser.add_argument('region', help='省市名称 (如: Shanghai, Beijing)')
    parser.add_argument('isp', help='运营商 (Telecom/Unicom/Mobile)')
    
    args = parser.parse_args()
    
    # 验证运营商参数
    valid_isps = ['telecom', 'unicom', 'mobile']
    if args.isp.lower() not in valid_isps:
        print(f"错误: 不支持的运营商 '{args.isp}'")
        print(f"支持的运营商: {', '.join(valid_isps)}")
        sys.exit(1)
    
    # 创建测试实例并运行
    speedtest = IPTVSpeedTest(args.region, args.isp)
    speedtest.run()


if __name__ == "__main__":
    main()
