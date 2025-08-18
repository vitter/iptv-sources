#!/usr/bin/env python3
"""
IPTV(udpxy) IP 搜索与测速综合工具 - 新版本

使用FOFA API 或登录Cookie进行搜索，Quake360使用Token认证，ZoomEye使用API Key或Cookie认证，Hunter使用API Key认证

功能：
1. 从 FOFA、Quake360、ZoomEye 和 Hunter 搜索 udpxy IP
   - FOFA支持API密钥和Cookie认证
   - Quake360使用Token认证（可选）
   - ZoomEye使用API Key或Cookie认证（可选）
   - Hunter使用API Key认证（可选）
2. 端口连通性测试
3. HTTP/M3U8 流媒体测速
4. 生成结果文件

项目主页: https://github.com/vitter/iptv-sources
问题反馈: https://github.com/vitter/iptv-sources/issues

用法：
python speedtest_integrated_new.py <省市> <运营商>
例如：python speedtest_integrated_new.py Shanghai Telecom

认证方式：
- FOFA：配置了FOFA_API_KEY时优先使用API方式，失败时回退到Cookie；未配置则使用Cookie方式
- Quake360：使用QUAKE360_TOKEN进行API认证（可选）
- ZoomEye：配置了ZOOMEYE_API_KEY时优先使用API方式；配置ZOOMEYE_COOKIE时必须同时配置cube-authorization（可选）
- Hunter：使用HUNTER_API_KEY进行API认证（可选）
- FOFA 必须配置Cookie，其他三个引擎可选配置（未配置时跳过对应搜索引擎）
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
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta  # Hunter API时间范围
from pathlib import Path
import traceback

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

# Hunter搜索引擎省份拼音到汉字映射
PROVINCE_PINYIN_TO_CHINESE = {
    'beijing': '北京',
    'tianjin': '天津', 
    'hebei': '河北',
    'shanxi': '山西',
    'neimenggu': '内蒙古',
    'liaoning': '辽宁',
    'jilin': '吉林',
    'heilongjiang': '黑龙江',
    'shanghai': '上海',
    'jiangsu': '江苏',
    'zhejiang': '浙江',
    'anhui': '安徽',
    'fujian': '福建',
    'jiangxi': '江西',
    'shandong': '山东',
    'henan': '河南',
    'hubei': '湖北',
    'hunan': '湖南',
    'guangdong': '广东',
    'guangxi': '广西',
    'hainan': '海南',
    'chongqing': '重庆',
    'sichuan': '四川',
    'guizhou': '贵州',
    'yunnan': '云南',
    'xizang': '西藏',
    'shaanxi': '陕西',
    'gansu': '甘肃',
    'qinghai': '青海',
    'ningxia': '宁夏',
    'xinjiang': '新疆',
    'hongkong': '香港',
    'macao': '澳门',
    'taiwan': '台湾'
}


class IPTVSpeedTest:
    """IPTV 测速主类"""
    
    def __init__(self, region, isp, max_pages=10, notest=False, fast=False):
        # 加载环境变量
        load_dotenv()
        
        self.region = self._format_string(region)
        self.isp = self._format_string(isp)
        self.max_pages = max_pages  # 新增：最大翻页数限制
        self.notest = notest  # 新增：是否跳过流媒体测试
        self.fast = fast  # 新增：快速模式，只进行第一阶段测试
        
        # 从环境变量读取配置并清理格式
        self.quake360_token = os.getenv('QUAKE360_TOKEN')
        self.fofa_user_agent = os.getenv('FOFA_USER_AGENT')
        self.fofa_api_key = os.getenv('FOFA_API_KEY', '')  # 可选的API密钥
        self.zoomeye_api_key = os.getenv('ZOOMEYE_API_KEY', '')  # ZoomEye API密钥
        self.zoomeye_cookie = os.getenv('ZOOMEYE_COOKIE', '')  # ZoomEye Cookie
        self.cube_authorization = os.getenv('cube-authorization', '')  # ZoomEye cube-authorization
        self.hunter_api_key = os.getenv('HUNTER_API_KEY', '')  # Hunter API密钥
        
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
            # 初始化默认配置信息，用于后续可能的配置切换
            self.current_isp = self.isp
            self.current_region = self.region
        else:
            # 在notest模式下，使用region作为city，stream设为空
            self.city = self.region
            self.stream = ""
            self.current_isp = self.isp
            self.current_region = self.region
        
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
        
        # FOFA配置检查 - 必需的配置
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
        print(f"  ZoomEye API Key: {'✓' if self.zoomeye_api_key else '✗'}")
        print(f"  ZoomEye Cookie: {'✓' if self.zoomeye_cookie else '✗'}")
        print(f"  ZoomEye cube-authorization: {'✓' if self.cube_authorization else '✗'}")
        print(f"  Hunter API Key: {'✓' if self.hunter_api_key else '✗'}")
        
        # 检查FOFA认证方式
        if self.fofa_api_key:
            print("  → FOFA 将使用API密钥")
        else:
            print("  → FOFA 将使用Cookie认证")
            
        # Quake360使用Token认证（可选）
        if self.quake360_token:
            print("  → Quake360 将使用 Token 认证")
        else:
            print("  → Quake360 未配置，将跳过Quake360搜索")
        
        # ZoomEye认证方式（可选，优先使用API Key）
        if self.zoomeye_api_key and self.zoomeye_cookie and self.cube_authorization:
            print("  → ZoomEye 将使用 API Key 认证（优先）")
        elif self.zoomeye_api_key:
            print("  → ZoomEye 将使用 API Key 认证")
        elif self.zoomeye_cookie and self.cube_authorization:
            print("  → ZoomEye 将使用 Cookie 认证")
        elif self.zoomeye_cookie and not self.cube_authorization:
            print("  → ZoomEye Cookie配置不完整（缺少cube-authorization），将跳过ZoomEye搜索")
        else:
            print("  → ZoomEye 未配置，将跳过ZoomEye搜索")
        
        # Hunter使用API Key认证（可选）
        if self.hunter_api_key:
            print("  → Hunter 将使用 API Key 认证")
        else:
            print("  → Hunter 未配置，将跳过Hunter搜索")
    
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
    
    def _load_all_province_configs(self):
        """加载所有运营商的所有省份配置"""
        all_configs = []
        isps = ['Telecom', 'Unicom', 'Mobile']
        
        for isp in isps:
            config_file = f"{isp}_province_list.txt"
            if not os.path.exists(config_file):
                print(f"警告: 配置文件 {config_file} 不存在，跳过")
                continue
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        parts = line.strip().split()
                        if len(parts) >= 3 and parts[0] != 'city':  # 跳过标题行
                            config = {
                                'isp': isp,
                                'region': parts[0],
                                'city': parts[1],
                                'stream': parts[2],
                                'config_file': config_file,
                                'line_num': line_num
                            }
                            all_configs.append(config)
            except Exception as e:
                print(f"读取配置文件 {config_file} 失败: {e}")
                continue
        
        print(f"加载了 {len(all_configs)} 个配置项（来自 {len(isps)} 个运营商）")
        return all_configs
    
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
            #query = f'"udpxy" && country="CN" && region="{self.region}" && org*="*obile*" && protocol="http"'
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
            "size": 10,  # 每页10条数据
            "ignore_cache": False,
            "latest": True,
            "shortcuts": ["635fcb52cc57190bd8826d09"]
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
    
    def search_zoomeye_ips(self):
        """从 ZoomEye 搜索 IP - 支持API Key和Cookie认证"""
        print(f"===============从 ZoomEye 检索 IP ({self.region})=================")
        
        # 优先级：如果都配置了，优先使用API方式
        if self.zoomeye_api_key and self.zoomeye_cookie and self.cube_authorization:
            print("🔑 配置了API Key和Cookie，优先使用API Key方式搜索")
            return self.search_zoomeye_api()
        elif self.zoomeye_api_key:
            print("🔑 使用 ZoomEye API Key 方式搜索")
            return self.search_zoomeye_api()
        elif self.zoomeye_cookie and self.cube_authorization:
            print("🍪 使用 ZoomEye Cookie 方式搜索")
            return self.search_zoomeye_cookie()
        elif self.zoomeye_cookie and not self.cube_authorization:
            print("❌ 配置了ZOOMEYE_COOKIE但缺少cube-authorization，跳过ZoomEye搜索")
            return []
        else:
            print("❌ 未配置ZOOMEYE_API_KEY或(ZOOMEYE_COOKIE + cube-authorization)，跳过ZoomEye搜索")
            return []
    
    def search_zoomeye_api(self):
        """从 ZoomEye 搜索 IP - API方式，支持翻页获取多页数据"""
        print("--- ZoomEye API 搜索 ---")
        
        # 根据运营商类型构建搜索查询
        if self.isp.lower() == 'telecom':
            query = f'app="udpxy" && country="CN" && isp="China Telecom" && subdivisions="{self.region}"'
        elif self.isp.lower() == 'unicom':
            query = f'app="udpxy" && country="CN" && isp="China Unicom" && subdivisions="{self.region}"'
        elif self.isp.lower() == 'mobile':
            query = f'app="udpxy" && country="CN" && isp="China Mobile" && subdivisions="{self.region}"'
        else:
            # 默认查询
            query = f'app="udpxy" && country="CN" && subdivisions="{self.region}"'
        
        print(f"查询参数: {query}")
        print(f"最大翻页数限制: {self.max_pages} 页")
        
        # 将查询转换为base64编码
        query_b64 = base64.b64encode(query.encode()).decode().replace('\n', '')
        
        all_ip_ports = []
        
        # 构建请求头
        headers = {
            'API-KEY': self.zoomeye_api_key,
            'Content-Type': 'application/json',
            'User-Agent': self.fofa_user_agent
        }
        
        try:
            print("发送第一次请求获取总数据量...")
            # 添加延迟避免API限流
            time.sleep(2)
            
            # 第一次请求，获取总数据量
            request_data = {
                "qbase64": query_b64,
                "page": 1,
                "pagesize": 10,  # 每页10条数据
                "sub_type": "v4",  # IPv4数据
                "fields": "ip,port,domain,update_time"  # 指定返回字段
            }
            
            response = requests.post(
                'https://api.zoomeye.org/v2/search',
                headers=headers,
                json=request_data,
                timeout=30
            )
            response.raise_for_status()
            
            print(f"API响应状态码: {response.status_code}")
            
            # 解析JSON响应
            response_json = response.json()
            
            # 检查API错误
            code = response_json.get('code')
            if code and str(code) != '60000':  # ZoomEye成功响应码是60000
                error_message = response_json.get('message', '未知错误')
                print(f"ZoomEye API错误: {code} - {error_message}")
                return []
            
            # 获取总数据量
            total_count = response_json.get('total', 0)
            query_info = response_json.get('query', '')
            
            print(f"总数据量: {total_count}")
            print(f"查询语句: {query_info}")
            
            # 计算总页数
            page_size = 10  # ZoomEye每页固定10条
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1  # 向上取整
            
            # 应用最大页数限制
            actual_pages = min(total_pages, self.max_pages)
            print(f"总页数: {total_pages}, 实际获取页数: {actual_pages}")
            
            # 处理第一页数据
            first_page_data = response_json.get('data', [])
            page_ip_ports = self._extract_zoomeye_results(first_page_data)
            all_ip_ports.extend(page_ip_ports)
            print(f"第1页提取到 {len(page_ip_ports)} 个IP:PORT")
            
            # 如果有多页，继续获取其他页的数据
            if actual_pages > 1 and total_count > 0:
                for page in range(2, actual_pages + 1):
                    print(f"正在获取第 {page}/{actual_pages} 页数据...")
                    
                    # 更新页码参数
                    request_data['page'] = page
                    
                    # 添加延迟避免API限流
                    time.sleep(2)
                    
                    try:
                        response = requests.post(
                            'https://api.zoomeye.org/v2/search',
                            headers=headers,
                            json=request_data,
                            timeout=30
                        )
                        response.raise_for_status()
                        
                        response_json = response.json()
                        
                        # 检查错误
                        code = response_json.get('code')
                        if code and str(code) != '60000':
                            error_message = response_json.get('message', '未知错误')
                            print(f"第{page}页ZoomEye API错误: {code} - {error_message}")
                            continue
                        
                        page_data = response_json.get('data', [])
                        page_ip_ports = self._extract_zoomeye_results(page_data)
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
            
            print(f"ZoomEye API总共提取到 {len(all_ip_ports)} 个IP:PORT")
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
                print("ZoomEye API未找到有效的IP地址")
                return []
                
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_ip_ports)} 个结果")
            return list(set(all_ip_ports))  # 返回已获取的去重结果
        except requests.exceptions.RequestException as e:
            print(f"ZoomEye API请求失败: {e}")
            return []
        except Exception as e:
            print(f"ZoomEye API搜索异常: {e}")
            return []
    
    def _extract_zoomeye_results(self, data_list):
        """提取ZoomEye搜索结果数据"""
        ip_ports = []
        
        for item in data_list:
            if isinstance(item, dict):
                # 提取IP地址
                ip = item.get('ip')
                # 提取端口
                port = item.get('port')
                
                # 组合IP:PORT
                if ip and port:
                    # 确保IP是有效的IP地址格式
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', str(ip)):
                        ip_port = f"{ip}:{port}"
                        ip_ports.append(ip_port)
        
        return ip_ports
    
    def search_zoomeye_cookie(self):
        """从 ZoomEye 搜索 IP - Cookie方式，支持翻页获取多页数据"""
        print("--- ZoomEye Cookie 搜索 ---")
        
        # 根据运营商类型构建搜索查询
        if self.isp.lower() == 'telecom':
            query = f'app="udpxy" && country="CN" && isp="China Telecom" && subdivisions="{self.region}"'
        elif self.isp.lower() == 'unicom':
            query = f'app="udpxy" && country="CN" && isp="China Unicom" && subdivisions="{self.region}"'
        elif self.isp.lower() == 'mobile':
            query = f'app="udpxy" && country="CN" && isp="China Mobile" && subdivisions="{self.region}"'
        else:
            # 默认查询
            query = f'app="udpxy" && country="CN" && subdivisions="{self.region}"'
        
        print(f"查询参数: {query}")
        print(f"最大翻页数限制: {self.max_pages} 页")
        
        # 将查询转换为base64编码
        query_b64 = base64.b64encode(query.encode()).decode().replace('\n', '')
        
        all_ip_ports = []
        
        # 构建请求头
        headers = {
            'Cookie': self.zoomeye_cookie,
            'Content-Type': 'application/json',
            'User-Agent': self.fofa_user_agent,
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.zoomeye.org/searchResult'
        }
        
        # 如果配置了cube-authorization，添加到请求头
        if self.cube_authorization:
            headers['cube-authorization'] = self.cube_authorization
        
        try:
            print("发送第一次请求获取总数据量...")
            # 添加延迟避免频率限制
            time.sleep(2)
            
            # 第一次请求，获取总数据量（对查询参数进行URL编码）
            query_encoded = urllib.parse.quote(query_b64, safe='')
            search_total_url = f"https://www.zoomeye.org/api/search_total?q={query_encoded}&t=v4%2Bv6%2Bweb"
            
            response = requests.get(
                search_total_url,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            print(f"API响应状态码: {response.status_code}")
            
            # 解析JSON响应
            response_json = response.json()
            
            # 获取总数据量
            total_count = response_json.get('total', 0)
            
            print(f"总数据量: {total_count}")
            
            # 计算总页数 (默认每页10条，最大50条)
            page_size = min(10, 50)  # 使用最大每页数量以减少请求次数
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1  # 向上取整
            
            # 应用最大页数限制
            actual_pages = min(total_pages, self.max_pages)
            print(f"总页数: {total_pages}, 实际获取页数: {actual_pages}, 每页数量: {page_size}")
            
            # 获取搜索数据
            for page in range(1, actual_pages + 1):
                print(f"正在获取第 {page}/{actual_pages} 页数据...")
                
                # 构建搜索请求URL（对查询参数进行URL编码）
                search_url = f"https://www.zoomeye.org/api/search?q={query_encoded}&page={page}&pageSize={page_size}&t=v4%2Bv6%2Bweb"
                
                # 添加延迟避免频率限制
                if page > 1:
                    time.sleep(2)
                
                try:
                    response = requests.get(
                        search_url,
                        headers=headers,
                        timeout=30
                    )
                    response.raise_for_status()
                    
                    response_json = response.json()
                    
                    # 提取搜索结果
                    matches = response_json.get('matches', [])
                    page_ip_ports = self._extract_zoomeye_cookie_results(matches)
                    all_ip_ports.extend(page_ip_ports)
                    print(f"第{page}页提取到 {len(page_ip_ports)} 个IP:PORT")
                    
                    # 如果当前页没有数据，说明已经到了最后一页
                    if not matches:
                        print("当前页无数据，停止翻页")
                        break
                        
                except KeyboardInterrupt:
                    print(f"\n用户中断，已获取前 {page-1} 页数据")
                    break
                except Exception as e:
                    print(f"获取第{page}页数据失败: {e}")
                    continue
            
            # 去重结果
            unique_ips = list(set(all_ip_ports))
            
            print(f"ZoomEye Cookie总共提取到 {len(all_ip_ports)} 个IP:PORT")
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
                print("ZoomEye Cookie未找到有效的IP地址")
                return []
                
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_ip_ports)} 个结果")
            return list(set(all_ip_ports))  # 返回已获取的去重结果
        except requests.exceptions.RequestException as e:
            print(f"ZoomEye Cookie请求失败: {e}")
            return []
        except Exception as e:
            print(f"ZoomEye Cookie搜索异常: {e}")
            return []
    
    def _extract_zoomeye_cookie_results(self, matches_list):
        """提取ZoomEye Cookie搜索结果数据"""
        ip_ports = []
        
        for item in matches_list:
            if isinstance(item, dict):
                # 提取IP地址
                ip = item.get('ip')
                
                # 从portinfo中提取端口
                portinfo = item.get('portinfo', {})
                port = portinfo.get('port') if portinfo else None
                
                # 组合IP:PORT
                if ip and port:
                    # 确保IP是有效的IP地址格式
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', str(ip)):
                        ip_port = f"{ip}:{port}"
                        ip_ports.append(ip_port)
        
        return ip_ports
    
    def search_hunter_ips(self):
        """从 Hunter 搜索 IP - 使用API Key认证"""
        print(f"===============从 Hunter 检索 IP ({self.region})=================")
        
        if not self.hunter_api_key:
            print("❌ 未配置HUNTER_API_KEY，跳过Hunter搜索")
            return []
        
        print("🔑 使用 Hunter API Key 方式搜索")
        return self.search_hunter_api()
    
    def search_hunter_api(self):
        """从 Hunter 搜索 IP - API方式，支持翻页获取多页数据"""
        print("--- Hunter API 搜索 ---")
        
        # 获取省份中文名
        province_chinese = PROVINCE_PINYIN_TO_CHINESE.get(self.region.lower())
        if not province_chinese:
            print(f"警告: 未找到省份 '{self.region}' 的中文映射，使用原始名称")
            province_chinese = self.region
        
        # 根据运营商类型构建搜索查询
        if self.isp.lower() == 'telecom':
            isp_chinese = '电信'
        elif self.isp.lower() == 'unicom':
            isp_chinese = '联通'
        elif self.isp.lower() == 'mobile':
            isp_chinese = '移动'
        else:
            print(f"警告: 未知运营商类型 '{self.isp}'，使用默认查询")
            isp_chinese = ''
        
        # 构建Hunter查询语句
        if isp_chinese:
            query = f'protocol.banner="Server: udpxy"&&app="Linux"&&protocol=="http"&&ip.country="CN"&&ip.isp="{isp_chinese}"&&ip.province="{province_chinese}"'
        else:
            query = f'protocol.banner="Server: udpxy"&&app="Linux"&&protocol=="http"&&ip.country="CN"&&ip.province="{province_chinese}"'
        
        print(f"查询参数: {query}")
        print(f"省份: {self.region} -> {province_chinese}")
        print(f"运营商: {self.isp} -> {isp_chinese}")
        print(f"最大翻页数限制: {self.max_pages} 页")
        
        # 将查询转换为base64url编码
        query_b64 = base64.urlsafe_b64encode(query.encode('utf-8')).decode('utf-8')
        
        # 计算时间范围（最近30天以内避免扣除积分）
        end_time = datetime.now().strftime('%Y-%m-%d')
        start_time = (datetime.now() - timedelta(days=29)).strftime('%Y-%m-%d')
        
        all_ip_ports = []
        
        try:
            print("发送第一次请求获取总数据量...")
            # 添加延迟避免API限流
            time.sleep(2)
            
            # 第一次请求，获取总数据量
            params = {
                'api-key': self.hunter_api_key,
                'search': query_b64,
                'page': 1,
                'page_size': 10,  # 每页10条数据
                'is_web': 1,      # 1代表"web资产"
                'port_filter': 'false',
                'start_time': start_time,
                'end_time': end_time
            }
            
            response = requests.get(
                'https://hunter.qianxin.com/openApi/search',
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            print(f"API响应状态码: {response.status_code}")
            
            # 解析JSON响应
            response_json = response.json()
            
            # 检查API错误
            code = response_json.get('code')
            if code != 200:
                error_message = response_json.get('message', '未知错误')
                print(f"Hunter API错误: {code} - {error_message}")
                return []
            
            # 获取总数据量
            data = response_json.get('data', {})
            total_count = data.get('total', 0)
            consume_quota = data.get('consume_quota', '')
            rest_quota = data.get('rest_quota', '')
            
            print(f"总数据量: {total_count}")
            print(f"积分消耗: {consume_quota}")
            print(f"剩余积分: {rest_quota}")
            
            # 计算总页数
            page_size = 10  # Hunter每页固定10条
            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1  # 向上取整
            
            # 应用最大页数限制
            actual_pages = min(total_pages, self.max_pages)
            print(f"总页数: {total_pages}, 实际获取页数: {actual_pages}")
            
            # 处理第一页数据
            first_page_data = data.get('arr', [])
            page_ip_ports = self._extract_hunter_results(first_page_data)
            all_ip_ports.extend(page_ip_ports)
            print(f"第1页提取到 {len(page_ip_ports)} 个IP:PORT")
            
            # 如果有多页，继续获取其他页的数据
            if actual_pages > 1 and total_count > 0:
                for page in range(2, actual_pages + 1):
                    print(f"正在获取第 {page}/{actual_pages} 页数据...")
                    
                    # 更新页码参数
                    params['page'] = page
                    
                    # 添加延迟避免API限流
                    time.sleep(2)
                    
                    try:
                        response = requests.get(
                            'https://hunter.qianxin.com/openApi/search',
                            params=params,
                            timeout=30
                        )
                        response.raise_for_status()
                        
                        response_json = response.json()
                        
                        # 检查错误
                        code = response_json.get('code')
                        if code != 200:
                            error_message = response_json.get('message', '未知错误')
                            print(f"第{page}页Hunter API错误: {code} - {error_message}")
                            continue
                        
                        page_data = response_json.get('data', {}).get('arr', [])
                        page_ip_ports = self._extract_hunter_results(page_data)
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
            
            print(f"Hunter API总共提取到 {len(all_ip_ports)} 个IP:PORT")
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
                print("Hunter API未找到有效的IP地址")
                return []
                
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_ip_ports)} 个结果")
            return list(set(all_ip_ports))  # 返回已获取的去重结果
        except requests.exceptions.RequestException as e:
            print(f"Hunter API请求失败: {e}")
            return []
        except Exception as e:
            print(f"Hunter API搜索异常: {e}")
            return []
    
    def _extract_hunter_results(self, data_list):
        """提取Hunter搜索结果数据"""
        ip_ports = []
        
        for item in data_list:
            if isinstance(item, dict):
                # 提取IP地址
                ip = item.get('ip')
                # 提取端口
                port = item.get('port')
                
                # 组合IP:PORT
                if ip and port:
                    # 确保IP是有效的IP地址格式
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
    
    def test_stream_speed(self, ip_port, custom_config=None):
        """测试流媒体速度 - 直接下载流媒体数据
        
        Args:
            ip_port: IP:PORT格式的地址
            custom_config: 自定义配置字典，包含 {'stream': 'udp/xxx:xxx', 'isp': 'xxx', 'region': 'xxx', 'city': 'xxx'}
        """
        session = None
        try:
            # 使用自定义配置或默认配置
            if custom_config:
                stream_path = custom_config['stream']
                test_info = f"{custom_config['isp']}-{custom_config['region']}"
            else:
                stream_path = self.stream
                test_info = f"{self.current_isp}-{self.current_region}"
            
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
            stream_url = f"http://{ip_port}/{stream_path}"
            print(f"  测试流媒体: {stream_url} ({test_info})")
            
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
                    print(f"  ! {ip_port} 流媒体响应状态码: {response.status_code} ({test_info})")
                    return None
                
                print(f"  开始下载流媒体数据... ({test_info})")
                
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
            
            print(f"  ✓ {ip_port} 下载完成: ({test_info})")
            print(f"    总大小: {total_size/1024:.1f}KB")
            print(f"    总耗时: {total_duration:.2f}秒") 
            print(f"    平均速度: {speed_mb_per_sec:.3f}MB/s")
            
            result = {
                'ip': ip_port,
                'speed': speed_mb_per_sec,
                'file_size': total_size,
                'duration': total_duration,
                'url': stream_url
            }
            
            # 如果使用了自定义配置，将配置信息也加入结果
            if custom_config:
                result['config'] = custom_config
                print(f"    使用配置: {custom_config['isp']}-{custom_config['region']}-{custom_config['city']}")
            
            return result
            
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
    
    def test_stream_with_fallback_configs(self, ip_port):
        """使用回退配置测试流媒体速度
        
        首先使用默认配置测试，如果失败则尝试所有可能的配置
        """
        print(f"开始测试 {ip_port} 的流媒体连接...")
        
        # 1. 首先使用默认配置
        print(f"1. 尝试默认配置: {self.current_isp}-{self.current_region}")
        result = self.test_stream_speed(ip_port)
        if result:
            print(f"✓ 默认配置测试成功")
            return result
        
        print(f"✗ 默认配置测试失败，开始尝试其他配置...")
        
        # 2. 加载所有配置并逐一尝试
        all_configs = self._load_all_province_configs()
        
        # 过滤掉已经尝试过的默认配置
        remaining_configs = [
            config for config in all_configs 
            if not (config['isp'].lower() == self.current_isp.lower() and 
                   config['region'].lower() == self.current_region.lower())
        ]
        
        print(f"将尝试 {len(remaining_configs)} 个其他配置...")
        
        # 3. 逐一尝试其他配置
        for i, config in enumerate(remaining_configs, 2):
            print(f"{i}. 尝试配置: {config['isp']}-{config['region']}-{config['city']}")
            
            # 使用自定义配置测试
            result = self.test_stream_speed(ip_port, config)
            if result:
                print(f"✓ 找到匹配的配置: {config['isp']}-{config['region']}-{config['city']}")
                print(f"   流地址: {config['stream']}")
                return result
            
            # 限制尝试次数，避免过度测试
            if i > 96:  # 最多尝试96个配置
                print(f"已尝试 {i-1} 个配置，停止继续尝试")
                break
        
        print(f"✗ 所有配置都测试失败，该IP可能不支持流媒体服务")
        return None

    def test_with_other_configs(self, ip_port):
        """对单个IP测试除默认配置外的其他所有配置"""
        # 加载所有配置并排除默认配置
        all_configs = self._load_all_province_configs()
        
        remaining_configs = [
            config for config in all_configs 
            if not (config['isp'].lower() == self.current_isp.lower() and 
                   config['region'].lower() == self.current_region.lower())
        ]
        
        print(f"    尝试 {len(remaining_configs)} 个其他配置...")
        
        # 逐一尝试其他配置
        for i, config in enumerate(remaining_configs, 1):
            if i % 10 == 0:  # 每10个配置显示一次进度
                print(f"    已尝试 {i}/{len(remaining_configs)} 个配置...")
            
            try:
                result = self.test_stream_speed(ip_port, config)
                if result:
                    print(f"    ✓ 找到匹配配置: {config['isp']}-{config['region']}-{config['city']}")
                    return result
            except Exception as e:
                # 单个配置测试失败不影响其他配置
                if i % 20 == 0:  # 每20个配置显示一次错误统计
                    print(f"    第{i}个配置测试异常: {str(e)[:50]}...")
                continue
            
            # 限制尝试次数，避免过度测试
            if i >= 96:  # 减少到最多96个配置，提高效率
                print(f"    已尝试 {i} 个配置，停止继续尝试")
                break
        
        print(f"    ✗ 尝试了 {min(i, len(remaining_configs))} 个配置都失败")
        return None

    def run_speed_tests(self, ip_list):
        """运行流媒体测速 - 优化版两阶段测试"""
        mode_text = "（快速模式）" if self.fast else "（两阶段优化版）"
        print(f"==========开始流媒体测速{mode_text}=================")
        
        if self.fast:
            print("🚀 快速模式启用：仅进行第一阶段默认配置测试")
        
        if not ip_list:
            print("没有可测试的 IP")
            return []
        
        # 清空之前的日志
        if os.path.exists(self.speedtest_log):
            os.remove(self.speedtest_log)
        
        # 初始化结果文件，清空之前的内容
        self._initialize_result_files()
        
        speed_results = []
        
        # ==================== 第一阶段：批量测试默认配置 ====================
        print(f"第一阶段：使用默认配置 {self.current_isp}-{self.current_region} 测试 {len(ip_list)} 个IP")
        print("提高并发数，快速筛选出可用的IP...")
        
        failed_ips = []
        completed_count = 0
        
        def test_default_config(ip_port):
            try:
                result = self.test_stream_speed(ip_port)
                return ip_port, result, None
            except Exception as e:
                return ip_port, None, str(e)
        
        # 第一阶段使用更高并发
        with ThreadPoolExecutor(max_workers=8) as executor:
            future_to_ip = {
                executor.submit(test_default_config, ip): ip 
                for ip in ip_list
            }
            
            try:
                for future in as_completed(future_to_ip, timeout=180):
                    completed_count += 1
                    try:
                        ip_port, result, error = future.result(timeout=10)
                        
                        if result:
                            speed_str = f"{result['speed']:.3f} MB/s"
                            print(f"  ✓ [{completed_count}/{len(ip_list)}] {ip_port} - 默认配置成功: {speed_str}")
                            
                            # 写入日志
                            with open(self.speedtest_log, 'a', encoding='utf-8') as f:
                                f.write(f"{ip_port} {speed_str} Size:{result['file_size']} [默认配置]\n")
                            
                            # 实时写入到结果文件和生成播放列表
                            self._append_result_immediately(result)
                            
                            speed_results.append(result)
                        else:
                            failed_ips.append(ip_port)
                            print(f"  ✗ [{completed_count}/{len(ip_list)}] {ip_port} - 默认配置失败")
                            
                    except TimeoutError:
                        ip_port = future_to_ip[future]
                        failed_ips.append(ip_port)
                        print(f"  ✗ [{completed_count}/{len(ip_list)}] {ip_port} - 默认配置超时")
                        future.cancel()
                    except Exception as e:
                        ip_port = future_to_ip[future]
                        failed_ips.append(ip_port)
                        print(f"  ✗ [{completed_count}/{len(ip_list)}] {ip_port} - 默认配置异常: {e}")
                    
                    # 显示阶段进度
                    progress = (completed_count / len(ip_list)) * 100
                    print(f"  第一阶段进度: {progress:.1f}% - 成功: {len(speed_results)} 个, 待重试: {len(failed_ips)} 个")
            
            except TimeoutError:
                print(f"第一阶段整体超时，处理未完成的任务...")
                # 处理未完成的任务
                for future in future_to_ip:
                    if not future.done():
                        ip_port = future_to_ip[future]
                        failed_ips.append(ip_port)
                        print(f"  ✗ 超时取消: {ip_port}")
                        future.cancel()
        
        print(f"第一阶段完成：成功 {len(speed_results)} 个，失败 {len(failed_ips)} 个")
        
        # ==================== 第二阶段：失败IP尝试其他配置 ====================
        if failed_ips and not self.fast:
            print(f"\n第二阶段：对 {len(failed_ips)} 个失败IP尝试其他配置...")
            print("降低并发数，避免过载，逐一尝试所有可能配置...")
            
            def test_other_configs(index, ip_port):
                try:
                    print(f"  第二阶段 [{index + 1}/{len(failed_ips)}] 测试 {ip_port}")
                    result = self.test_with_other_configs(ip_port)
                    if result:
                        config_info = ""
                        if 'config' in result:
                            config_info = f" [{result['config']['isp']}-{result['config']['region']}]"
                        return result, config_info
                    return None, ""
                except Exception as e:
                    print(f"    ✗ {ip_port} - 其他配置测试异常: {e}")
                    return None, ""
            
            # 第二阶段使用较低并发，避免过载
            completed_second = 0
            with ThreadPoolExecutor(max_workers=3) as executor:
                future_to_data = {
                    executor.submit(test_other_configs, i, ip): (i, ip) 
                    for i, ip in enumerate(failed_ips)
                }
                
                try:
                    # 使用更灵活的超时处理
                    for future in as_completed(future_to_data, timeout=600):  # 增加总超时到10分钟
                        completed_second += 1
                        try:
                            result, config_info = future.result(timeout=120)  # 每个任务最多2分钟
                            index, ip_port = future_to_data[future]
                            
                            if result:
                                speed_str = f"{result['speed']:.3f} MB/s"
                                print(f"  ✓ [{completed_second}/{len(failed_ips)}] {ip_port} - 找到匹配配置: {speed_str}{config_info}")
                                
                                # 写入日志
                                with open(self.speedtest_log, 'a', encoding='utf-8') as f:
                                    f.write(f"{ip_port} {speed_str} Size:{result['file_size']}{config_info}\n")
                                
                                # 实时写入到结果文件和生成播放列表
                                self._append_result_immediately(result)
                                
                                speed_results.append(result)
                            else:
                                print(f"  ✗ [{completed_second}/{len(failed_ips)}] {ip_port} - 所有配置都失败")
                                
                        except TimeoutError:
                            index, ip_port = future_to_data[future]
                            print(f"  ✗ [{completed_second}/{len(failed_ips)}] {ip_port} - 第二阶段任务超时(2分钟)")
                            # 取消超时的任务
                            future.cancel()
                        except Exception as e:
                            index, ip_port = future_to_data[future]
                            print(f"  ✗ [{completed_second}/{len(failed_ips)}] {ip_port} - 第二阶段任务异常: {e}")
                        
                        # 显示第二阶段进度
                        progress = (completed_second / len(failed_ips)) * 100
                        new_success = len(speed_results) - (len(ip_list) - len(failed_ips))
                        print(f"  第二阶段进度: {progress:.1f}% - 本阶段新增成功: {new_success} 个")
                
                except TimeoutError:
                    print(f"第二阶段整体超时，处理未完成的任务...")
                    # 处理未完成的任务
                    unfinished_count = 0
                    for future in future_to_data:
                        if not future.done():
                            unfinished_count += 1
                            index, ip_port = future_to_data[future]
                            print(f"  取消未完成任务: {ip_port}")
                            future.cancel()
                    
                    if unfinished_count > 0:
                        print(f"  共取消 {unfinished_count} 个未完成的任务")
                
                finally:
                    # 最终清理：确保所有未完成的任务都被取消
                    remaining_tasks = 0
                    for future in future_to_data:
                        if not future.done():
                            remaining_tasks += 1
                            future.cancel()
                    
                    if remaining_tasks > 0:
                        print(f"  最终清理：取消 {remaining_tasks} 个剩余任务")
        
        elif failed_ips and self.fast:
            print(f"\n🚀 快速模式启用：跳过第二阶段测试")
            print(f"   失败的 {len(failed_ips)} 个IP将不进行其他配置测试")
            print(f"   如需完整测试，请移除 --fast 参数")
        
        else:
            print("✓ 所有IP都通过默认配置测试成功，无需第二阶段！")
        
        # ==================== 测速总结 ====================
        total_success = len(speed_results)
        total_failed = len(ip_list) - total_success
        success_rate = (total_success / len(ip_list)) * 100 if ip_list else 0
        
        print(f"\n==========流媒体测速完成=================")
        print(f"总计: {total_success} 个可用IP, {total_failed} 个失败")
        print(f"成功率: {success_rate:.1f}%")
        print(f"其中默认配置成功: {len(ip_list) - len(failed_ips)} 个")
        print(f"其他配置成功: {total_success - (len(ip_list) - len(failed_ips))} 个")
        
        return speed_results
    
    def _append_result_immediately(self, result):
        """实时追加单个测试结果到结果文件和播放列表"""
        try:
            # 只处理速度大于 0.1 MB/s 的结果
            if result['speed'] <= 0.1:
                return
            
            # 确定配置信息
            if 'config' in result:
                config = result['config']
                isp = config['isp']
                city = config['city']
                config_info = f" [{config['isp']}-{config['region']}]"
            else:
                isp = self.isp
                city = self.city
                config_info = ""
            
            # 1. 追加到原始结果文件
            result_file = self.temp_dir / f"{isp}_result_fofa_{city}.txt"
            with open(result_file, 'a', encoding='utf-8') as f:
                f.write(f"{result['speed']:.3f}  {result['ip']}{config_info}\n")
            
            # 2. 实时生成/更新播放列表文件
            template_file = Path(f"template/{isp}/template_{city}.txt")
            output_dir = Path(f"sum/{isp}")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{city}.txt"
            
            if template_file.exists():
                # 读取模板内容
                with open(template_file, 'r', encoding='utf-8') as tf:
                    template_content = tf.read()
                
                # 替换模板中的占位符并追加到播放列表
                content = template_content.replace('ipipip', result['ip'])
                with open(output_file, 'a', encoding='utf-8') as of:
                    of.write(content)
                
                print(f"    ✓ 实时更新播放列表: {output_file}")
            else:
                print(f"    ⚠ 模板文件不存在: {template_file}")
                
        except Exception as e:
            print(f"    ✗ 实时写入结果失败: {e}")
    
    def _initialize_result_files(self):
        """初始化结果文件 - 清空之前的内容"""
        try:
            # 确保目录存在
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            
            # 清空原始结果文件
            result_file = self.temp_dir / f"{self.isp}_result_fofa_{self.city}.txt"
            with open(result_file, 'w', encoding='utf-8') as f:
                pass  # 创建空文件
            
            # 清空播放列表文件
            output_file = self.output_dir / f"{self.city}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                pass  # 创建空文件
                
            print(f"✓ 初始化结果文件: {result_file}")
            print(f"✓ 初始化播放列表: {output_file}")
            
        except Exception as e:
            print(f"✗ 初始化结果文件失败: {e}")
    
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
        
        # 保存结果到原始格式文件
        with open(self.result_file, 'w', encoding='utf-8') as f:
            for result in filtered_results:
                config_info = ""
                if 'config' in result:
                    config_info = f" [{result['config']['isp']}-{result['config']['region']}]"
                f.write(f"{result['speed']:.3f}  {result['ip']}{config_info}\n")
        
        # 统计配置分布
        config_stats = {}
        for result in filtered_results:
            if 'config' in result:
                config = result['config']
                key = f"{config['isp']}-{config['region']}"
            else:
                key = f"{self.current_isp}-{self.current_region}"
            
            config_stats[key] = config_stats.get(key, 0) + 1
        
        print(f"======本次{self.region}组播IP搜索结果=============")
        print(f"共找到 {len(filtered_results)} 个可用IP，配置分布：")
        for config, count in config_stats.items():
            print(f"  {config}: {count} 个IP")
        print("详细结果：")
        for result in filtered_results:
            config_info = ""
            if 'config' in result:
                config_info = f" [{result['config']['isp']}-{result['config']['region']}]"
            print(f"{result['speed']:.3f} MB/s  {result['ip']}{config_info}")
        
        # 合并模板文件
        self._merge_template_file(filtered_results)
    
    def _merge_template_file(self, results):
        """合并模板文件 - 支持多配置结果"""
        if not results:
            print("没有结果需要合并模板")
            return
            
        # 按配置分组结果
        config_groups = {}
        for result in results:
            if 'config' in result:
                # 使用测试出的正确配置
                config = result['config']
                isp = config['isp']
                city = config['city']
            else:
                # 使用默认配置
                isp = self.isp
                city = self.city
                
            key = f"{isp}_{city}"
            if key not in config_groups:
                config_groups[key] = {
                    'isp': isp,
                    'city': city,
                    'results': []
                }
            config_groups[key]['results'].append(result)
        
        print(f"发现 {len(config_groups)} 种配置的结果，将分别生成文件：")
        
        # 为每种配置生成对应的文件
        for key, group in config_groups.items():
            isp = group['isp']
            city = group['city']
            group_results = group['results']
            
            print(f"  {isp}-{city}: {len(group_results)} 个IP")
            
            # 构建模板文件路径
            template_file = Path(f"template/{isp}/template_{city}.txt")
            
            # 构建输出文件路径，确保目录存在
            output_dir = Path(f"sum/{isp}")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{city}.txt"
            
            if not template_file.exists():
                print(f"    警告: 模板文件 {template_file} 不存在，跳过该组")
                continue
            
            print(f"    合并列表文件到：{output_file}")
            
            try:
                with open(template_file, 'r', encoding='utf-8') as tf:
                    template_content = tf.read()
                
                with open(output_file, 'w', encoding='utf-8') as of:
                    for result in group_results:
                        ip = result['ip']
                        config_info = ""
                        if 'config' in result:
                            config_info = f" ({result['config']['isp']}-{result['config']['region']})"
                        print(f"    Processing IP: {ip} (Speed: {result['speed']:.3f} MB/s){config_info}")
                        
                        # 替换模板中的占位符
                        content = template_content.replace('ipipip', ip)
                        of.write(content)
                        
                print(f"    ✓ 成功生成 {output_file}")
                        
            except Exception as e:
                print(f"    ✗ 合并模板文件失败: {e}")
    
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
    
    def cleanup(self, keep_logs=False):
        """清理临时文件
        
        Args:
            keep_logs: 是否保留日志文件（用于调试异常情况）
        """
        temp_files = [
            "temp_video.mp4",
            "ffmpeg.log"
        ]
        
        # 只有在明确要求清理或正常完成时才删除日志文件
        if not keep_logs:
            temp_files.append(self.speedtest_log)
        
        for file_path in temp_files:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"删除临时文件: {file_path}")
        
        if keep_logs and os.path.exists(self.speedtest_log):
            print(f"保留日志文件用于调试: {self.speedtest_log}")
    
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
            zoomeye_ips = self.search_zoomeye_ips()
            hunter_ips = self.search_hunter_ips()
            
            # 合并并去重
            all_ips = list(set(fofa_ips + quake_ips + zoomeye_ips + hunter_ips))
            print(f"从FOFA、Quake360、ZoomEye和Hunter总共找到 {len(all_ips)} 个唯一 IP")
            print(f"  FOFA: {len(fofa_ips)} 个")
            print(f"  Quake360: {len(quake_ips)} 个") 
            print(f"  ZoomEye: {len(zoomeye_ips)} 个")
            print(f"  Hunter: {len(hunter_ips)} 个")
            
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
            # 用户中断时保留日志文件用于调试
            self.cleanup(keep_logs=True)
        except Exception as e:
            print(f"程序执行出错: {e}")
            # 异常时保留日志文件用于调试
            self.cleanup(keep_logs=True)
        else:
            # 正常完成时清理所有临时文件
            self.cleanup(keep_logs=False)


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
  python speedtest_integrated_new.py Hebei Telecom --fast

运营商可选: Telecom, Unicom, Mobile

参数说明:
  --max-pages: 限制搜索的最大页数
  --notest: 跳过流媒体测试，仅进行IP搜索和端口检测
  --fast: 快速模式，只进行第一阶段默认配置测试，跳过第二阶段其他配置测试
        """
    )
    
    parser.add_argument('region', help='省市名称 (如: Shanghai, Beijing)')
    parser.add_argument('isp', help='运营商 (Telecom/Unicom/Mobile)')
    parser.add_argument('--max-pages', type=int, default=10, 
                       help='最大翻页数限制 (默认: 10页)')
    parser.add_argument('--notest', action='store_true',
                       help='跳过流媒体测试和模板生成，仅进行IP搜索和端口检测')
    parser.add_argument('--fast', action='store_true',
                       help='快速模式：只进行第一阶段默认配置测试，跳过第二阶段其他配置测试')
    
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
    elif args.fast:
        print(f"  模式: 快速测试模式（仅第一阶段默认配置测试）")
    else:
        print(f"  模式: 完整测试模式")
    
    # 创建测试实例并运行
    speedtest = IPTVSpeedTest(args.region, args.isp, args.max_pages, args.notest, args.fast)
    speedtest.run()


if __name__ == "__main__":
    main()
