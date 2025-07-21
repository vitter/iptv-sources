#!/usr/bin/env python3
"""
IPTV 源数据获取与合并工具

功能：
1. 从 FOFA 和 Quake360 搜索指定类型的IPTV服务
2. 合并现有CSV文件数据
3. 按照指定规则进行去重（host排重，同一个C段IP不同端口去重）
4. 更新CSV文件
5. 支持按省份和运营商过滤搜索结果

用法：
单模式：python makecsv.py --jsmpeg jsmpeg_hosts.csv
多模式：python makecsv.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv --zhgxtv zhgxtv_hosts.csv
指定天数：python makecsv.py --jsmpeg jsmpeg_hosts.csv --days 7
指定省份：python makecsv.py --jsmpeg jsmpeg_hosts.csv --region beijing
指定运营商：python makecsv.py --jsmpeg jsmpeg_hosts.csv --isp telecom
综合使用：python makecsv.py --jsmpeg jsmpeg_hosts.csv --days 7 --region guangdong --isp mobile

参数说明：
--days: 日期过滤天数，搜索最近N天的数据，默认为30天
--region: 指定省份，不区分大小写，格式化为首字母大写其他小写
--isp: 指定运营商 (Telecom/Unicom/Mobile)，不区分大小写，格式化为首字母大写其他小写

搜索规则（自动添加指定天数的日期限制，以及省份和运营商限制）：
--jsmpeg: 搜索 title="jsmpeg-streamer" && country="CN" && after="YYYY-MM-DD"
--txiptv: 搜索 body="/iptv/live/zh_cn.js" && country="CN" && after="YYYY-MM-DD"
--zhgxtv: 搜索 body="ZHGXTV" && country="CN" && after="YYYY-MM-DD"

省份和运营商过滤规则：
1. 只指定region：FOFA增加 && region="{region}"，Quake360增加 AND province:"{region}"
2. 只指定isp：FOFA增加运营商org过滤条件，Quake360增加 AND isp:"中国XXX"
3. 同时指定region和isp：同时应用上述两种过滤规则

环境变量配置：
FOFA_COOKIE - FOFA网站登录Cookie
FOFA_USER_AGENT - 浏览器User-Agent
FOFA_API_KEY - FOFA API密钥（可选）
QUAKE360_TOKEN - Quake360 API Token
"""
#三个csv对应fofa上的搜索指纹分别是：
#jsmpeg-streamer fid="OBfgOOMpjONAJ/cQ1FpaDQ=="
#txiptv fid="7v4hVyd8x6RxODJO2Q5u5Q=="
#zhgxtv fid="IVS0q72nt9BgY+hjPVH+ZQ=="
#
#智慧光迅平台(广东公司) body="ZHGXTV"
#/ZHGXTV/Public/json/live_interface.txt
#http://ip:port/hls/1/index.m3u8
#智慧桌面 智能KUTV(陕西公司) body="/iptv/live/zh_cn.js"
#http://ip:port/tsfile/live/0001_1.m3u8
#华视美达 华视私云(浙江公司) body="华视美达"
#http://ip:port/newlive/live/hls/1/live.m3u8
#

import argparse
import base64
import csv
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta

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
    
    def __init__(self, days=30, region=None, isp=None):
        # 保存日期过滤参数
        self.days = days
        
        # 格式化region和isp参数
        self.region = self._format_region(region) if region else None
        self.isp = self._format_isp(isp) if isp else None
        
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
    
    def _format_region(self, region):
        """格式化省份参数，首字母大写其他小写"""
        if not region:
            return None
        return region.strip().capitalize()
    
    def _format_isp(self, isp):
        """格式化运营商参数，首字母大写其他小写"""
        if not isp:
            return None
        formatted = isp.strip().capitalize()
        # 验证运营商参数是否有效
        valid_isps = ['Telecom', 'Unicom', 'Mobile']
        if formatted not in valid_isps:
            print(f"警告: 无效的运营商参数 '{isp}', 有效值为: {', '.join(valid_isps)}")
            return None
        return formatted
    
    def _get_date_filter(self, days=30):
        """获取日期过滤器，返回当前日期减去指定天数的日期字符串"""
        # 计算指定天数前的日期
        target_date = datetime.now() - timedelta(days=days)
        # 格式化为 YYYY-MM-DD 格式
        date_str = target_date.strftime("%Y-%m-%d")
        return f'after="{date_str}"'
    
    def _get_region_filter_fofa(self):
        """获取FOFA的省份过滤器"""
        if not self.region:
            return ""
        return f' && region="{self.region}"'
    
    def _get_region_filter_quake360(self):
        """获取Quake360的省份过滤器"""
        if not self.region:
            return ""
        return f' AND province:"{self.region}"'
    
    def _get_isp_filter_fofa(self):
        """获取FOFA的运营商过滤器"""
        if not self.isp:
            return ""
        
        if self.isp == 'Telecom':
            if self.region:
                return f' && (org="Chinanet" || org="China Telecom" || org="CHINA TELECOM" || org="China Telecom Group" || org="{self.region} Telecom" || org="CHINANET {self.region} province network" || org="CHINANET {self.region} province backbone")'
            else:
                return f' && (org="Chinanet" || org="China Telecom" || org="CHINA TELECOM" || org="China Telecom Group")'
        elif self.isp == 'Mobile':
            if self.region:
                return f' && (org="{self.region} Mobile Communication Company Limited" || org="{self.region} Mobile Communications Co." || org="China Mobile Communicaitons Corporation" || org="China Mobile Group {self.region} communications corporation" || org="China Mobile Group {self.region} Co.")'
            else:
                return f' && (org="China Mobile Communicaitons Corporation")'
        elif self.isp == 'Unicom':
            if self.region:
                return f' && (org="CHINA UNICOM China169 Backbone" || org="China Unicom" || org="China Unicom IP network" || org="CHINA UNICOM Industrial Internet Backbone" || org="China Unicom {self.region} network" || org="China Unicom {self.region} IP network" || org="China Unicom {self.region} Province Network" || org="UNICOM {self.region} province network" || org="China Unicom IP network China169 {self.region} province")'
            else:
                return f' && (org="CHINA UNICOM China169 Backbone" || org="China Unicom" || org="China Unicom IP network" || org="CHINA UNICOM Industrial Internet Backbone")'
        
        return ""
    
    def _get_isp_filter_quake360(self):
        """获取Quake360的运营商过滤器"""
        if not self.isp:
            return ""
        
        isp_mapping = {
            'Telecom': ' AND isp:"中国电信"',
            'Unicom': ' AND isp:"中国联通"',
            'Mobile': ' AND isp:"中国移动"'
        }
        
        return isp_mapping.get(self.isp, "")
    
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
        """使用FOFA API搜索，支持翻页获取全部数据"""
        print(f"===============从 FOFA API 搜索===============")
        print(f"搜索查询: {query}")
        
        # 使用base64编码查询
        query_b64 = base64.b64encode(query.encode()).decode().replace('\n', '')
        
        api_url = "https://fofa.info/api/v1/search/all"
        all_extracted_data = []
        
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': self.fofa_user_agent,
                'Accept': 'application/json'
            })
            
            # 第一次请求，获取总数据量
            params = {
                'key': self.fofa_api_key,
                'qbase64': query_b64,
                'fields': 'ip,host,port,link,org',
                'size': 100,  # 默认每页100条
                'page': 1,
                'full': 'false'
            }
            
            print("发送第一次请求获取总数据量...")
            time.sleep(1)  # 添加延迟避免API限流
            
            response = session.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            
            response_json = response.json()
            
            if response_json.get('error', False):
                error_msg = response_json.get('errmsg', '未知错误')
                print(f"FOFA API错误: {error_msg}")
                return []
            
            # 获取总数据量和当前页数据
            total_size = response_json.get('size', 0)
            current_page = response_json.get('page', 1)
            results = response_json.get('results', [])
            
            print(f"总数据量: {total_size}")
            print(f"当前页: {current_page}, 当前页结果数: {len(results)}")
            
            # 计算总页数
            page_size = 100
            total_pages = math.ceil(total_size / page_size)
            
            print(f"将获取 {total_pages} 页数据")
            
            # 处理第一页数据
            extracted_data = self._extract_fofa_results(results)
            all_extracted_data.extend(extracted_data)
            print(f"第1页提取到 {len(extracted_data)} 个有效结果")
            
            # 如果有多页，继续获取其他页的数据
            if total_pages > 1:
                for page in range(2, total_pages + 1):
                    print(f"正在获取第 {page}/{total_pages} 页数据...")
                    
                    # 更新页码参数
                    params['page'] = page
                    
                    # 添加延迟避免API限流
                    time.sleep(1)
                    
                    try:
                        response = session.get(api_url, params=params, timeout=30)
                        response.raise_for_status()
                        
                        response_json = response.json()
                        
                        if response_json.get('error', False):
                            error_msg = response_json.get('errmsg', '未知错误')
                            print(f"第{page}页FOFA API错误: {error_msg}")
                            continue
                        
                        results = response_json.get('results', [])
                        extracted_data = self._extract_fofa_results(results)
                        all_extracted_data.extend(extracted_data)
                        print(f"第{page}页提取到 {len(extracted_data)} 个有效结果")
                        
                    except KeyboardInterrupt:
                        print(f"\n用户中断，已获取前 {page-1} 页数据")
                        break
                    except Exception as e:
                        print(f"获取第{page}页数据失败: {e}")
                        continue
            
            print(f"FOFA API总共提取到 {len(all_extracted_data)} 个有效结果")
            return all_extracted_data
            
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_extracted_data)} 个结果")
            return all_extracted_data
        except Exception as e:
            print(f"FOFA API搜索失败: {e}")
            return []
    
    def _extract_fofa_results(self, results):
        """提取FOFA搜索结果数据"""
        extracted_data = []
        
        # 添加调试信息
        if results:
            print(f"FOFA API返回结果示例:")
            for i, result in enumerate(results[:3]):  # 只显示前3个
                print(f"  结果 {i+1}: {result} (长度: {len(result) if result else 0})")
        
        for result in results:
            if len(result) >= 3:  # 至少需要3个字段
                # FOFA API fields='ip,host,port,link,org' 返回格式为 [ip, host, port, link, org]
                ip = str(result[0]).strip() if result[0] else ''
                host = str(result[1]).strip() if result[1] else ''
                port = str(result[2]).strip() if result[2] else ''
                link = str(result[3]).strip() if len(result) > 3 and result[3] else ''
                org = str(result[4]).strip() if len(result) > 4 and result[4] else ''
                
                # 处理host字段
                if not host and ip and port:
                    # host为空，使用ip:port
                    host = f"{ip}:{port}"
                elif host and ':' not in host and ip and port:
                    # host只是域名，补充为ip:port格式
                    host = f"{ip}:{port}"
                elif host and ':' in host and not ip:
                    # host是ip:port格式，需要分离
                    parts = host.split(':')
                    if len(parts) == 2:
                        ip = parts[0]
                        port = parts[1]
                
                # 构建link（如果API没有返回）
                if not link and ip and port:
                    link = f"http://{ip}:{port}"
                
                # 验证IP格式和端口
                if (ip and port and 
                    re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip) and
                    port.isdigit() and 1 <= int(port) <= 65535):
                    
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
                        'org': org,
                        '_source': 'fofa_api'
                    })
        
        return extracted_data
    
    def _extract_fofa_page_info(self, content):
        """从FOFA页面内容中提取总数据量信息"""
        total_count = 0
        page_size = 50
        
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
            
            # 方法2: 提取 "共 x 条" 格式作为验证
            total_pattern = r'共\s*(\d+)\s*条'
            total_match = re.search(total_pattern, content)
            if total_match:
                verification_count = int(total_match.group(1))
                print(f"从 '共 X 条' 验证总数: {verification_count}")
                
                # 如果两种方法得到的数字不一致，使用较大的那个
                if total_count == 0:
                    total_count = verification_count
                elif verification_count != total_count:
                    print(f"警告: 两种方法提取的总数不一致，使用较大值")
                    total_count = max(total_count, verification_count)
            
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
            if page_size == 50 and total_count > 0:  # 如果总数已找到但页面大小还是默认值
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
    
    def _extract_fofa_page_data(self, content):
        """从FOFA页面内容中提取IP端口数据"""
        # 使用更精确的正则表达式提取IP:PORT，避免匹配到CSS、JS等内容
        # 匹配类似 href="http://1.2.3.4:80" 或者 >1.2.3.4:80< 的格式
        ip_port_patterns = [
            # 匹配 href 链接中的IP:PORT
            r'href=["\']https?://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)',
            # 匹配表格或列表中的IP:PORT（前后有标签包围）
            r'>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)<',
            # 匹配直接的IP:PORT格式（但要求前后有空白字符或特定字符）
            r'[\s>](\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)[\s<]',
            # 匹配数据属性中的IP:PORT
            r'data-[^=]*=["\']([^"\']*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)[^"\']*?)["\']'
        ]
        
        extracted_data = []
        seen_hosts = set()  # 在提取阶段就进行去重
        
        for pattern in ip_port_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) >= 2:
                    # 根据不同的模式提取IP和端口
                    if len(match) == 2:
                        ip, port = match[0], match[1]
                    else:  # len(match) > 2，比如data属性模式
                        ip, port = match[-2], match[-1]
                    
                    # 验证IP格式和端口范围
                    if (re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip) and
                        port.isdigit() and 1 <= int(port) <= 65535):
                        
                        # 验证IP地址的每个段都在0-255范围内
                        ip_parts = ip.split('.')
                        if all(0 <= int(part) <= 255 for part in ip_parts):
                            host = f"{ip}:{port}"
                            
                            # 在提取阶段就避免重复
                            if host not in seen_hosts:
                                seen_hosts.add(host)
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
        
        return extracted_data

    def search_fofa_cookie(self, query):
        """使用FOFA Cookie搜索，支持翻页获取全部数据"""
        print(f"===============从 FOFA Cookie 搜索===============")
        print(f"搜索查询: {query}")
        
        # 使用base64编码查询
        query_b64 = base64.b64encode(query.encode()).decode()
        
        all_extracted_data = []
        
        try:
            session = self._create_session_with_retry()
            
            # 第一次请求，获取总数据量
            search_url = f"https://fofa.info/result?qbase64={query_b64}&page=1&page_size=50"
            
            print("发送第一次请求获取总数据量...")
            time.sleep(1)  # 添加延迟避免限流
            
            response = session.get(search_url, timeout=30)
            response.raise_for_status()
            
            # 从HTML页面提取总数据量和当前页数据
            content = response.text
            total_count, page_size = self._extract_fofa_page_info(content)
            
            print(f"总数据量: {total_count}")
            print(f"页面大小: {page_size}")
            
            # 计算总页数
            total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
            
            print(f"将获取 {total_pages} 页数据")
            
            # 处理第一页数据
            extracted_data = self._extract_fofa_page_data(content)
            all_extracted_data.extend(extracted_data)
            print(f"第1页提取到 {len(extracted_data)} 个结果")
            
            # 如果有多页，继续获取其他页的数据
            if total_pages > 1 and total_count > 0:
                for page in range(2, total_pages + 1):
                    print(f"正在获取第 {page}/{total_pages} 页数据...")
                    
                    # 构建新的URL
                    page_url = f"https://fofa.info/result?qbase64={query_b64}&page={page}&page_size={page_size}"
                    
                    # 添加延迟避免限流
                    time.sleep(1)
                    
                    try:
                        response = session.get(page_url, timeout=30)
                        response.raise_for_status()
                        
                        # 提取当前页数据
                        page_content = response.text
                        page_data = self._extract_fofa_page_data(page_content)
                        all_extracted_data.extend(page_data)
                        print(f"第{page}页提取到 {len(page_data)} 个结果")
                        
                    except KeyboardInterrupt:
                        print(f"\n用户中断，已获取前 {page-1} 页数据")
                        break
                    except Exception as e:
                        print(f"获取第{page}页数据失败: {e}")
                        continue
            
            # 去重处理
            unique_data = []
            seen_hosts = set()
            for item in all_extracted_data:
                if item['host'] not in seen_hosts:
                    unique_data.append(item)
                    seen_hosts.add(item['host'])
            
            print(f"FOFA Cookie总共提取到 {len(all_extracted_data)} 个结果，去重后 {len(unique_data)} 个有效结果")
            return unique_data
            
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_extracted_data)} 个结果")
            # 仍然需要去重处理
            unique_data = []
            seen_hosts = set()
            for item in all_extracted_data:
                if item['host'] not in seen_hosts:
                    unique_data.append(item)
                    seen_hosts.add(item['host'])
            return unique_data
        except Exception as e:
            print(f"FOFA Cookie搜索失败: {e}")
            return []
    
    def search_quake360_api(self, query):
        """使用Quake360 API搜索，支持翻页获取全部数据"""
        print(f"===============从 Quake360 API 搜索===============")
        print(f"搜索查询: {query}")
        
        if not self.quake360_token:
            print("未配置QUAKE360_TOKEN，跳过Quake360搜索")
            return []
        
        all_extracted_data = []
        
        # 第一次请求，获取总数据量
        query_data = {
            "query": query,
            "start": 0,
            "size": 100,  # 每页100条数据
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
            
            response_json = response.json()
            
            # 检查错误
            code = response_json.get('code')
            if code and str(code) not in ['0', '200', 'success']:
                error_message = response_json.get('message', '未知错误')
                print(f"Quake360 API错误: {code} - {error_message}")
                return []
            
            # 获取总数据量和分页信息
            meta = response_json.get('meta', {})
            pagination = meta.get('pagination', {})
            total_count = pagination.get('total', 0)
            page_size = pagination.get('page_size', 100)
            current_page = pagination.get('page_index', 1)
            
            print(f"总数据量: {total_count}")
            print(f"当前页: {current_page}, 页面大小: {page_size}")
            
            # 计算总页数
            total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
            print(f"将获取 {total_pages} 页数据")
            
            # 处理第一页数据
            first_page_data = response_json.get('data', [])
            extracted_data = self._extract_quake360_results(first_page_data)
            all_extracted_data.extend(extracted_data)
            print(f"第1页提取到 {len(extracted_data)} 个有效结果")
            
            # 如果有多页，继续获取其他页的数据
            if total_pages > 1 and total_count > 0:
                for page in range(2, total_pages + 1):
                    print(f"正在获取第 {page}/{total_pages} 页数据...")
                    
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
                            print(f"第{page}页Quake360 API错误: {code} - {error_message}")
                            continue
                        
                        page_data = response_json.get('data', [])
                        extracted_data = self._extract_quake360_results(page_data)
                        all_extracted_data.extend(extracted_data)
                        print(f"第{page}页提取到 {len(extracted_data)} 个有效结果")
                        
                    except KeyboardInterrupt:
                        print(f"\n用户中断，已获取前 {page-1} 页数据")
                        break
                    except Exception as e:
                        print(f"获取第{page}页数据失败: {e}")
                        continue
            
            print(f"Quake360 API总共提取到 {len(all_extracted_data)} 个有效结果")
            return all_extracted_data
            
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_extracted_data)} 个结果")
            return all_extracted_data
        except Exception as e:
            print(f"Quake360 API搜索失败: {e}")
            return []
    
    def _extract_quake360_results(self, data_list):
        """提取Quake360搜索结果数据"""
        extracted_data = []
        
        # 添加调试信息
        if data_list:
            print(f"Quake360 API返回结果示例:")
            for i, item in enumerate(data_list[:3]):  # 只显示前3个
                print(f"  结果 {i+1}: {item}")
        
        for item in data_list:
            if isinstance(item, dict):
                # 直接提取IP和端口
                ip = item.get('ip', '')
                port = item.get('port', '')
                
                # 确保ip和port都存在且有效
                if ip and port and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', str(ip)):
                    ip = str(ip).strip()
                    port = str(port).strip()
                    
                    # 验证端口范围
                    if port.isdigit() and 1 <= int(port) <= 65535:
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
        
        return extracted_data
    
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
        
        # 获取日期过滤器
        date_filter = self._get_date_filter(self.days)
        
        # 获取省份和运营商过滤器
        region_filter_fofa = self._get_region_filter_fofa()
        isp_filter_fofa = self._get_isp_filter_fofa()
        region_filter_quake360 = self._get_region_filter_quake360()
        isp_filter_quake360 = self._get_isp_filter_quake360()
        
        # 搜索查询（添加日期限制和省份运营商限制）
        fofa_query = f'title="jsmpeg-streamer" && country="CN" && {date_filter}{region_filter_fofa}{isp_filter_fofa}'
        quake360_query = f'title:"jsmpeg-streamer" AND country:"China"{region_filter_quake360}{isp_filter_quake360}'
        
        print(f"FOFA查询: {fofa_query}")
        print(f"Quake360查询: {quake360_query}")
        
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
        
        # 获取日期过滤器
        date_filter = self._get_date_filter(self.days)
        
        # 获取省份和运营商过滤器
        region_filter_fofa = self._get_region_filter_fofa()
        isp_filter_fofa = self._get_isp_filter_fofa()
        region_filter_quake360 = self._get_region_filter_quake360()
        isp_filter_quake360 = self._get_isp_filter_quake360()
        
        # 搜索查询（添加日期限制和省份运营商限制）
        fofa_query = f'body="/iptv/live/zh_cn.js" && country="CN" && {date_filter}{region_filter_fofa}{isp_filter_fofa}'
        quake360_query = f'body:"/iptv/live/zh_cn.js" AND country:"China"{region_filter_quake360}{isp_filter_quake360}'
        
        print(f"FOFA查询: {fofa_query}")
        print(f"Quake360查询: {quake360_query}")
        
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
        
        # 获取日期过滤器
        date_filter = self._get_date_filter(self.days)
        
        # 获取省份和运营商过滤器
        region_filter_fofa = self._get_region_filter_fofa()
        isp_filter_fofa = self._get_isp_filter_fofa()
        region_filter_quake360 = self._get_region_filter_quake360()
        isp_filter_quake360 = self._get_isp_filter_quake360()
        
        # 搜索查询（添加日期限制和省份运营商限制）
        fofa_query = f'body="ZHGXTV" && country="CN" && {date_filter}{region_filter_fofa}{isp_filter_fofa}'
        quake360_query = f'body:"ZHGXTV" AND country:"China"{region_filter_quake360}{isp_filter_quake360}'
        
        print(f"FOFA查询: {fofa_query}")
        print(f"Quake360查询: {quake360_query}")
        
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
    parser.add_argument('--days', type=int, default=30, help='日期过滤天数，默认30天')
    parser.add_argument('--region', help='指定省份，不区分大小写，格式化为首字母大写其他小写')
    parser.add_argument('--isp', help='指定运营商 (Telecom/Unicom/Mobile)，不区分大小写，格式化为首字母大写其他小写')
    
    args = parser.parse_args()
    
    # 检查至少指定了一个模式
    if not any([args.jsmpeg, args.txiptv, args.zhgxtv]):
        print("错误: 请至少指定一个模式参数")
        print("用法示例:")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv --days 7")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv --region beijing --isp telecom")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv --zhgxtv zhgxtv_hosts.csv --days 15 --region guangdong --isp mobile")
        sys.exit(1)
    
    # 创建收集器实例
    collector = IPTVSourceCollector(days=args.days, region=args.region, isp=args.isp)
    
    # 处理各种模式
    if args.jsmpeg:
        collector.process_jsmpeg(args.jsmpeg)
    
    if args.txiptv:
        collector.process_txiptv(args.txiptv)
    
    if args.zhgxtv:
        collector.process_zhgxtv(args.zhgxtv)
    
    print("\n=== 处理完成 ===")
    
    # 显示使用的参数
    if collector.region or collector.isp:
        print(f"使用的参数:")
        if collector.region:
            print(f"  省份: {collector.region}")
        if collector.isp:
            print(f"  运营商: {collector.isp}")


if __name__ == "__main__":
    main()
