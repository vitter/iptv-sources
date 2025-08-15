#!/usr/bin/env python3
"""
IPTV 源数据获取与合并工具

功能：
1. 从 FOFA、Quake360、ZoomEye 和 Hunter 搜索指定类型的IPTV服务
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
限制翻页：python makecsv.py --jsmpeg jsmpeg_hosts.csv --max-pages 5
综合使用：python makecsv.py --jsmpeg jsmpeg_hosts.csv --days 7 --region guangdong --isp mobile --max-pages 10

参数说明：
--days: 日期过滤天数，搜索最近N天的数据，默认为29天
--region: 指定省份，不区分大小写，格式化为首字母大写其他小写
--isp: 指定运营商 (Telecom/Unicom/Mobile)，不区分大小写，格式化为首字母大写其他小写
--max-pages: 限制最大翻页数，不指定则无限制

搜索规则（自动添加指定天数的日期限制，以及省份和运营商限制）：
--jsmpeg: 搜索 title="jsmpeg-streamer" && country="CN" && after="YYYY-MM-DD"
--txiptv: 搜索 body="/iptv/live/zh_cn.js" && country="CN" && after="YYYY-MM-DD"
--zhgxtv: 搜索 body="ZHGXTV" && country="CN" && after="YYYY-MM-DD"

省份和运营商过滤规则：
1. 只指定region：FOFA增加 && region="{region}"，Quake360增加 AND province:"{region}"，ZoomEye增加 && subdivisions="{region}"，Hunter增加 && ip.province="{region_chinese}"
2. 只指定isp：FOFA增加运营商org过滤条件，Quake360增加 AND isp:"中国XXX"，ZoomEye增加 && isp="China XXX"，Hunter增加 && ip.isp="{isp_chinese}"
3. 同时指定region和isp：同时应用上述两种过滤规则

环境变量配置：
FOFA_COOKIE - FOFA网站登录Cookie
FOFA_USER_AGENT - 浏览器User-Agent
FOFA_API_KEY - FOFA API密钥（可选）
QUAKE360_TOKEN - Quake360 API Token（可选）
ZOOMEYE_API_KEY - ZoomEye API密钥（可选）
HUNTER_API_KEY - Hunter API密钥（可选）
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

# Hunter搜索引擎省份拼音到中文的映射字典
PROVINCE_PINYIN_TO_CHINESE = {
    'beijing': '北京', 'tianjin': '天津', 'hebei': '河北', 'shanxi': '山西', 'neimenggu': '内蒙古',
    'liaoning': '辽宁', 'jilin': '吉林', 'heilongjiang': '黑龙江', 'shanghai': '上海', 
    'jiangsu': '江苏', 'zhejiang': '浙江', 'anhui': '安徽', 'fujian': '福建', 'jiangxi': '江西',
    'shandong': '山东', 'henan': '河南', 'hubei': '湖北', 'hunan': '湖南', 'guangdong': '广东',
    'guangxi': '广西', 'hainan': '海南', 'chongqing': '重庆', 'sichuan': '四川', 'guizhou': '贵州',
    'yunnan': '云南', 'xizang': '西藏', 'shaanxi': '陕西', 'gansu': '甘肃', 'qinghai': '青海',
    'ningxia': '宁夏', 'xinjiang': '新疆', 'taiwan': '台湾', 'xianggang': '香港', 'aomen': '澳门'
}


class IPTVSourceCollector:
    """IPTV 源数据收集器"""
    
    def __init__(self, days=29, region=None, isp=None, max_pages=None):
        # 保存日期过滤参数
        self.days = days
        
        # 保存最大翻页数参数
        self.max_pages = max_pages
        
        # 格式化region和isp参数
        self.region = self._format_region(region) if region else None
        self.isp = self._format_isp(isp) if isp else None
        
        # 加载环境变量
        load_dotenv()
        
        # 从环境变量读取配置
        self.quake360_token = os.getenv('QUAKE360_TOKEN')
        self.fofa_user_agent = os.getenv('FOFA_USER_AGENT')
        self.fofa_api_key = os.getenv('FOFA_API_KEY', '')
        self.zoomeye_api_key = os.getenv('ZOOMEYE_API_KEY', '')  # ZoomEye API密钥
        self.hunter_api_key = os.getenv('HUNTER_API_KEY', '')  # Hunter API密钥
        
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
    
    def _get_date_filter(self, days=29):
        """获取日期过滤器，返回当前日期减去指定天数的日期字符串（仅用于FOFA）"""
        # 计算指定天数前的日期
        target_date = datetime.now() - timedelta(days=days)
        # 格式化为 YYYY-MM-DD 格式
        date_str = target_date.strftime("%Y-%m-%d")
        return f'after="{date_str}"'
    
    def _get_zoomeye_date_filter(self, days=29):
        """获取ZoomEye的时间过滤器"""
        # ZoomEye支持 after="2020-01-01" 格式
        target_date = datetime.now() - timedelta(days=days)
        date_str = target_date.strftime("%Y-%m-%d")
        return f' && after="{date_str}"'
    
    def _get_hunter_time_range(self, days=29):
        """获取Hunter的时间范围参数"""
        # Hunter使用 start_time 和 end_time 参数
        end_time = datetime.now().strftime('%Y-%m-%d')
        start_time = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        return start_time, end_time
    
    def _get_quake360_time_range(self, days=29):
        """获取360 Quake的时间范围参数"""
        # 360 Quake使用 start_time 和 end_time 参数，格式为 YYYY-MM-DD HH:MM:SS (UTC)
        end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        start_time = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        return start_time, end_time
    
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
    
    def _get_region_filter_zoomeye(self):
        """获取ZoomEye的地区过滤器"""
        if not self.region:
            return ""
        return f' && subdivisions="{self.region}"'
    
    def _get_isp_filter_zoomeye(self):
        """获取ZoomEye的运营商过滤器"""
        if not self.isp:
            return ""
        
        isp_mapping = {
            'Telecom': ' && isp="China Telecom"',
            'Unicom': ' && isp="China Unicom"',
            'Mobile': ' && isp="China Mobile"'
        }
        
        return isp_mapping.get(self.isp, "")
    
    def _get_region_filter_hunter(self):
        """获取Hunter的地区过滤器"""
        if not self.region:
            return ""
        
        # 获取省份中文名
        province_chinese = PROVINCE_PINYIN_TO_CHINESE.get(self.region.lower())
        if not province_chinese:
            province_chinese = self.region
        
        return f'&&ip.province="{province_chinese}"'
    
    def _get_isp_filter_hunter(self):
        """获取Hunter的运营商过滤器"""
        if not self.isp:
            return ""
        
        isp_mapping = {
            'Telecom': '&&ip.isp="电信"',
            'Unicom': '&&ip.isp="联通"',
            'Mobile': '&&ip.isp="移动"'
        }
        
        return isp_mapping.get(self.isp, "")
    
    def _validate_config(self):
        """验证必要的配置是否已设置"""
        # 检查可用的搜索引擎
        available_engines = []
        missing_configs = []
        
        # 检查FOFA配置（需要User-Agent和Cookie）
        if self.fofa_user_agent and self.fofa_cookie:
            available_engines.append('FOFA')
        else:
            if not self.fofa_user_agent:
                missing_configs.append('FOFA_USER_AGENT')
            if not self.fofa_cookie:
                missing_configs.append('FOFA_COOKIE')
        
        # 检查FOFA API配置
        if self.fofa_api_key:
            available_engines.append('FOFA API')
        
        # 检查Quake360配置
        if self.quake360_token:
            available_engines.append('Quake360')
        
        # 检查ZoomEye配置
        if self.zoomeye_api_key:
            available_engines.append('ZoomEye')
        
        # 检查Hunter配置
        if self.hunter_api_key:
            available_engines.append('Hunter')
        
        # 至少需要一个搜索引擎可用
        if not available_engines:
            print("错误: 没有可用的搜索引擎配置!")
            print("缺少的必要配置:")
            for config in missing_configs:
                print(f"  - {config}")
            print("\n请至少配置以下其中一组:")
            print("  1. FOFA: FOFA_USER_AGENT + FOFA_COOKIE")
            print("  2. FOFA API: FOFA_API_KEY")
            print("  3. Quake360: QUAKE360_TOKEN")
            print("  4. ZoomEye: ZOOMEYE_API_KEY")
            print("  5. Hunter: HUNTER_API_KEY")
            print("\n请在.env文件中设置这些配置项。")
            sys.exit(1)
        
        print("✓ 配置验证通过")
        print(f"可用搜索引擎: {', '.join(available_engines)}")
    
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
            
            # 应用最大页数限制
            if self.max_pages is not None:
                actual_pages = min(total_pages, self.max_pages)
                print(f"总页数: {total_pages}, 限制最大页数: {self.max_pages}, 实际获取: {actual_pages} 页数据")
            else:
                actual_pages = total_pages
                print(f"将获取 {total_pages} 页数据")
            
            # 处理第一页数据
            extracted_data = self._extract_fofa_results(results)
            all_extracted_data.extend(extracted_data)
            print(f"第1页提取到 {len(extracted_data)} 个有效结果")
            
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
            
            # 应用最大页数限制
            if self.max_pages is not None:
                actual_pages = min(total_pages, self.max_pages)
                print(f"总页数: {total_pages}, 限制最大页数: {self.max_pages}, 实际获取: {actual_pages} 页数据")
            else:
                actual_pages = total_pages
                print(f"将获取 {total_pages} 页数据")
            
            # 处理第一页数据
            extracted_data = self._extract_fofa_page_data(content)
            all_extracted_data.extend(extracted_data)
            print(f"第1页提取到 {len(extracted_data)} 个结果")
            
            # 如果有多页，继续获取其他页的数据
            if actual_pages > 1 and total_count > 0:
                for page in range(2, actual_pages + 1):
                    print(f"正在获取第 {page}/{actual_pages} 页数据...")
                    
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
        
        if not self.quake360_token:
            print("未配置QUAKE360_TOKEN，跳过Quake360搜索")
            return []
        
        # 获取时间范围参数
        start_time, end_time = self._get_quake360_time_range(self.days)
        print(f"360 Quake时间范围: {start_time} 到 {end_time} ({self.days}天)")
        print(f"搜索查询: {query}")
        
        all_extracted_data = []
        
        # 第一次请求，获取总数据量
        query_data = {
            "query": query,  # 基础查询语句
            "start": 0,
            "size": 20,  # 每页20条数据
            "ignore_cache": False,
            "latest": True,
            "shortcuts": ["635fcb52cc57190bd8826d09"],  # 排除蜜罐系统结果
            "start_time": start_time,  # 查询起始时间，格式：2020-10-14 00:00:00，UTC时区
            "end_time": end_time       # 查询截止时间，格式：2020-10-14 00:00:00，UTC时区
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
            page_size = pagination.get('page_size', 20)
            current_page = pagination.get('page_index', 1)
            
            print(f"总数据量: {total_count}")
            print(f"当前页: {current_page}, 页面大小: {page_size}")
            
            # 计算总页数
            total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
            
            # 应用最大页数限制
            if self.max_pages is not None:
                actual_pages = min(total_pages, self.max_pages)
                print(f"总页数: {total_pages}, 限制最大页数: {self.max_pages}, 实际获取: {actual_pages} 页数据")
            else:
                actual_pages = total_pages
                print(f"将获取 {total_pages} 页数据")
            
            # 处理第一页数据
            first_page_data = response_json.get('data', [])
            extracted_data = self._extract_quake360_results(first_page_data)
            all_extracted_data.extend(extracted_data)
            print(f"第1页提取到 {len(extracted_data)} 个有效结果")
            
            # 如果有多页，继续获取其他页的数据
            if actual_pages > 1 and total_count > 0:
                for page in range(2, actual_pages + 1):
                    print(f"正在获取第 {page}/{actual_pages} 页数据...")
                    
                    # 更新分页参数
                    query_data['start'] = (page - 1) * page_size
                    
                    # 添加延迟避免API限流 - 增加到5秒避免q3005错误
                    time.sleep(5)
                    
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
        
        # 添加调试信息 - 只显示关键字段
        if data_list:
            print(f"Quake360 API返回结果示例:")
            for i, item in enumerate(data_list[:3]):  # 只显示前3个
                ip = item.get('ip', 'N/A')
                port = item.get('port', 'N/A')
                org = item.get('org', 'N/A')
                print(f"  结果 {i+1}: IP={ip}, Port={port}, Org={org}")
        
        for item in data_list:
            if isinstance(item, dict):
                # 提取关键字段
                ip = item.get('ip', '')
                port = item.get('port', '')
                org = item.get('org', '')
                
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
                            'org': org,
                            '_source': 'quake360'
                        })
        
        return extracted_data
    
    def search_zoomeye_api(self, query):
        """从 ZoomEye 搜索数据 - API方式，支持翻页获取全部数据"""
        if not self.zoomeye_api_key:
            print("❌ 未配置ZOOMEYE_API_KEY，跳过ZoomEye搜索")
            return []
        
        print("使用ZoomEye API搜索")
        
        # 为ZoomEye查询添加时间过滤器
        zoomeye_date_filter = self._get_zoomeye_date_filter(self.days)
        full_query = query + zoomeye_date_filter
        
        print(f"ZoomEye完整查询: {full_query}")
        
        # 将查询转换为base64编码
        query_b64 = base64.b64encode(full_query.encode()).decode().replace('\n', '')
        
        all_data = []
        
        # 构建请求头
        headers = {
            'API-KEY': self.zoomeye_api_key,
            'Content-Type': 'application/json',
            'User-Agent': self.fofa_user_agent
        }
        
        try:
            # 第一次请求，获取总数据量
            print("发送第一次请求获取总数据量...")
            time.sleep(2)
            
            # 构建请求数据
            request_data = {
                "qbase64": query_b64,
                "page": 1,
                "pagesize": 20,  # 每页20条数据
                "sub_type": "v4",  # IPv4数据
                "fields": "ip,port,domain,url,title,service,country.name,city.name,isp.name,organization.name,update_time"  # 与CSV字段对应的必要信息
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
            page_size = 20
            print(f"ZoomEye总数据量: {total_count}")
            print(f"页面大小: {page_size}")
            
            # 计算总页数
            total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
            
            # 应用最大页数限制
            if self.max_pages is not None:
                actual_pages = min(total_pages, self.max_pages)
                print(f"总页数: {total_pages}, 限制最大页数: {self.max_pages}, 实际获取: {actual_pages} 页数据")
            else:
                actual_pages = total_pages
                print(f"将获取 {total_pages} 页数据")
            
            # 处理第一页数据
            data_list = response_json.get('data', [])
            
            # 显示前3个原始结果示例
            if data_list:
                print(f"ZoomEye API返回结果示例:")
                for i, result in enumerate(data_list[:3]):
                    # 提取关键字段显示，与FOFA格式保持一致
                    ip = result.get('ip', '')
                    port = result.get('port', '')
                    host = f"{ip}:{port}" if ip and port else ''
                    
                    # 优先使用url字段
                    link = result.get('url', '')
                    if not link and host:
                        link = f"http://{host}"
                    
                    domain = result.get('domain', '')
                    title = result.get('title', '')
                    
                    # 地理位置信息
                    country = result.get('country.name', '')
                    city = result.get('city.name', '')
                    
                    # ISP和组织信息
                    isp = result.get('isp.name', '')
                    organization = result.get('organization.name', '')
                    
                    # 服务信息
                    service = result.get('service', '')
                    update_time = result.get('update_time', '')
                    
                    # 构建额外信息字符串（简化版本）
                    extra_info_parts = []
                    
                    # 标题和域名
                    if title:
                        title_str = ' '.join(title) if isinstance(title, list) else str(title)
                        extra_info_parts.append(f"Title: {title_str[:30]}")
                    if domain:
                        extra_info_parts.append(f"Domain: {domain}")
                    
                    # 地理位置
                    if country or city:
                        location = f"{country}/{city}".strip('/')
                        if location:
                            extra_info_parts.append(f"Location: {location}")
                    
                    # 组织信息
                    if organization:
                        extra_info_parts.append(f"Org: {organization}")
                    elif isp:
                        extra_info_parts.append(f"ISP: {isp}")
                    
                    # 服务类型
                    if service:
                        extra_info_parts.append(f"Service: {service}")
                    
                    # 更新时间
                    if update_time:
                        extra_info_parts.append(f"Updated: {update_time}")
                    
                    extra_info = ", ".join(extra_info_parts)
                    
                    # 模拟FOFA的5字段格式：[ip, host, port, link, extra_info]
                    formatted_result = [ip, host, str(port), link, extra_info]
                    print(f"  结果 {i+1}: {formatted_result} (长度: {len(formatted_result)})")
                    if i >= 2:  # 只显示前3个
                        break
            
            extracted_data = self._extract_zoomeye_results(data_list)
            all_data.extend(extracted_data)
            print(f"第1页提取到 {len(extracted_data)} 个有效结果")
            
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
                        extracted_data = self._extract_zoomeye_results(page_data)
                        all_data.extend(extracted_data)
                        print(f"第{page}页提取到 {len(extracted_data)} 个有效结果")
                        
                    except KeyboardInterrupt:
                        print(f"\n用户中断，已获取前 {page-1} 页数据")
                        break
                    except Exception as e:
                        print(f"获取第{page}页数据失败: {e}")
                        continue
            
            print(f"ZoomEye总共提取到 {len(all_data)} 个结果")
            return all_data
            
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_data)} 个结果")
            return all_data
        except requests.exceptions.RequestException as e:
            print(f"ZoomEye搜索请求失败: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"ZoomEye响应JSON解析错误: {e}")
            return []
        except Exception as e:
            print(f"ZoomEye搜索过程中发生未知错误: {e}")
            return []
    
    def _extract_zoomeye_results(self, data_list):
        """从ZoomEye API响应中提取结果"""
        extracted_data = []
        
        for item in data_list:
            try:
                # ZoomEye API字段映射（简化版本，只取CSV需要的字段）
                ip = item.get('ip', '').strip()
                port = str(item.get('port', '')).strip()
                domain = item.get('domain', '').strip()
                url = item.get('url', '').strip()
                
                # 获取标题信息
                title = item.get('title', [])
                if isinstance(title, list) and title:
                    title_str = ' '.join(title)
                else:
                    title_str = str(title) if title else ''
                
                # 地理位置信息
                country = item.get('country.name', 'CN')
                city = item.get('city.name', '')
                
                # ISP和组织信息
                isp = item.get('isp.name', '')
                organization = item.get('organization.name', '')
                
                # 服务信息
                service = item.get('service', 'http')
                update_time = item.get('update_time', '')
                
                if ip and port:
                    # 确保IP是有效的IP地址格式
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', str(ip)):
                        host = f"{ip}:{port}"
                        
                        # 优先使用url字段，否则构造链接
                        if url:
                            link = url
                        else:
                            # 根据service确定协议
                            protocol_prefix = 'https' if service in ['https', 'ssl'] else 'http'
                            link = f"{protocol_prefix}://{host}"
                        
                        # 构建组织信息，优先使用organization，其次是isp
                        org_info = organization if organization else isp
                        
                        extracted_data.append({
                            'host': host,
                            'ip': ip,
                            'port': port,
                            'link': link,
                            'protocol': service if service in ['http', 'https'] else 'http',
                            'title': title_str[:100],  # 限制标题长度
                            'domain': domain,
                            'country': country,
                            'city': city,
                            'org': org_info,
                            '_source': 'zoomeye'
                        })
            except Exception as e:
                print(f"处理ZoomEye结果项时出错: {e}")
                continue
        
        return extracted_data
    
    def search_hunter_api(self, query):
        """从 Hunter 搜索数据 - API方式，支持翻页获取全部数据"""
        if not self.hunter_api_key:
            print("❌ 未配置HUNTER_API_KEY，跳过Hunter搜索")
            return []
        
        print("使用Hunter API搜索")
        print(f"查询参数: {query}")
        
        # 将查询转换为base64url编码
        query_b64 = base64.urlsafe_b64encode(query.encode('utf-8')).decode('utf-8')
        
        # 获取时间范围（使用用户指定的天数）
        start_time, end_time = self._get_hunter_time_range(self.days)
        print(f"Hunter时间范围: {start_time} 到 {end_time} ({self.days}天)")
        
        all_data = []
        
        try:
            # 第一次请求，获取总数据量
            print("发送第一次请求获取总数据量...")
            time.sleep(2)
            
            # 构建请求参数
            params = {
                'api-key': self.hunter_api_key,
                'search': query_b64,
                'page': 1,
                'page_size': 20,  # 每页20条数据
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
            
            # 添加调试信息
            print(f"Hunter API响应结构: {list(response_json.keys())}")
            
            # 检查API错误
            code = response_json.get('code')
            if code != 200:
                error_message = response_json.get('message', '未知错误')
                print(f"Hunter API错误: {code} - {error_message}")
                return []
            
            # 获取总数据量
            data = response_json.get('data', {})
            if not data:
                print("Hunter API返回的data字段为空")
                return []
                
            print(f"Hunter data字段结构: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            
            total_count = data.get('total', 0)
            consume_quota = data.get('consume_quota', '')
            rest_quota = data.get('rest_quota', '')
            
            print(f"Hunter总数据量: {total_count}")
            print(f"积分消耗: {consume_quota}")
            print(f"剩余积分: {rest_quota}")
            
            # 计算总页数
            page_size = 20
            total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1
            
            # 应用最大页数限制
            if self.max_pages is not None:
                actual_pages = min(total_pages, self.max_pages)
                print(f"总页数: {total_pages}, 限制最大页数: {self.max_pages}, 实际获取: {actual_pages} 页数据")
            else:
                actual_pages = total_pages
                print(f"将获取 {total_pages} 页数据")
            
            # 处理第一页数据
            data_list = data.get('arr', [])
            if data_list is None:
                data_list = []
                print("Hunter API返回的数据列表为空")
            
            print(f"Hunter数据列表类型: {type(data_list)}, 长度: {len(data_list) if data_list else 0}")
            
            # 显示前3个原始结果示例
            if data_list:
                print(f"Hunter API返回结果示例:")
                for i, result in enumerate(data_list[:3]):
                    # 提取关键字段显示，与FOFA格式保持一致
                    ip = result.get('ip', '')
                    port = result.get('port', '')
                    host = f"{ip}:{port}" if ip and port else ''
                    link = result.get('url', f"http://{host}" if host else '')
                    web_title = result.get('web_title', '')
                    city = result.get('city', '')
                    isp = result.get('isp', '')
                    # 模拟FOFA的5字段格式：[ip, host, port, link, extra_info]
                    formatted_result = [ip, host, str(port), link, f"{web_title} - {city} {isp}".strip(" -")]
                    print(f"  结果 {i+1}: {formatted_result} (长度: {len(formatted_result)})")
                    if i >= 2:  # 只显示前3个
                        break
            
            extracted_data = self._extract_hunter_results(data_list)
            all_data.extend(extracted_data)
            print(f"第1页提取到 {len(extracted_data)} 个有效结果")
            
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
                        
                        page_data_wrapper = response_json.get('data', {})
                        page_data = page_data_wrapper.get('arr', []) if page_data_wrapper else []
                        extracted_data = self._extract_hunter_results(page_data)
                        all_data.extend(extracted_data)
                        print(f"第{page}页提取到 {len(extracted_data)} 个有效结果")
                        
                    except KeyboardInterrupt:
                        print(f"\n用户中断，已获取前 {page-1} 页数据")
                        break
                    except Exception as e:
                        print(f"获取第{page}页数据失败: {e}")
                        continue
            
            print(f"Hunter总共提取到 {len(all_data)} 个结果")
            return all_data
            
        except KeyboardInterrupt:
            print(f"\n用户中断，已获取 {len(all_data)} 个结果")
            return all_data
        except requests.exceptions.RequestException as e:
            print(f"Hunter搜索请求失败: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"Hunter响应JSON解析错误: {e}")
            return []
        except Exception as e:
            print(f"Hunter搜索过程中发生未知错误: {e}")
            return []
            

    
    def _extract_hunter_results(self, data_list):
        """从Hunter API响应中提取结果"""
        extracted_data = []
        
        # 检查数据列表是否有效
        if not data_list or not isinstance(data_list, list):
            print("Hunter数据列表为空或格式不正确")
            return extracted_data
        
        for item in data_list:
            try:
                # Hunter API字段映射
                ip = item.get('ip', '').strip()
                port = str(item.get('port', '')).strip()
                domain = item.get('domain', '').strip()
                
                # 获取更多字段信息
                web_title = item.get('web_title', '')
                country = item.get('country', 'CN')
                province = item.get('province', '')
                city = item.get('city', '')
                isp = item.get('isp', '')
                protocol = item.get('protocol', 'http')
                
                # 处理组件信息
                components = item.get('component', [])
                component_info = ''
                if isinstance(components, list) and components:
                    component_names = [comp.get('name', '') for comp in components if comp.get('name')]
                    component_info = ', '.join(component_names)
                
                if ip and port:
                    # 确保IP是有效的IP地址格式
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', str(ip)):
                        host = f"{ip}:{port}"
                        
                        # 使用协议信息构建链接
                        protocol_scheme = 'https' if protocol.lower() == 'https' else 'http'
                        link = f"{protocol_scheme}://{host}"
                        
                        extracted_data.append({
                            'host': host,
                            'ip': ip,
                            'port': port,
                            'link': link,
                            'protocol': protocol_scheme,
                            'title': web_title[:100] if web_title else '',  # 限制标题长度
                            'domain': domain,
                            'country': country,
                            'city': f"{province} {city}".strip(),
                            'org': isp,
                            'component': component_info,
                            '_source': 'hunter'
                        })
            except Exception as e:
                print(f"处理Hunter结果项时出错: {e}")
                continue
        
        return extracted_data
    
    def search_all_engines(self, query_fofa, query_quake360, query_zoomeye, query_hunter):
        """从四个搜索引擎获取数据"""
        all_data = []
        
        # 1. FOFA搜索
        if self.fofa_api_key:
            print("使用FOFA API搜索")
            fofa_data = self.search_fofa_api(query_fofa)
        else:
            print("使用FOFA Cookie搜索")
            fofa_data = self.search_fofa_cookie(query_fofa)
        
        all_data.extend(fofa_data)
        
        # 2. Quake360搜索（可选）
        if self.quake360_token:
            quake_data = self.search_quake360_api(query_quake360)
            all_data.extend(quake_data)
        else:
            print("❌ 未配置QUAKE360_TOKEN，跳过Quake360搜索")
        
        # 3. ZoomEye搜索（可选）
        if self.zoomeye_api_key:
            zoomeye_data = self.search_zoomeye_api(query_zoomeye)
            all_data.extend(zoomeye_data)
        else:
            print("❌ 未配置ZOOMEYE_API_KEY，跳过ZoomEye搜索")
        
        # 4. Hunter搜索（可选）
        if self.hunter_api_key:
            hunter_data = self.search_hunter_api(query_hunter)
            all_data.extend(hunter_data)
        else:
            print("❌ 未配置HUNTER_API_KEY，跳过Hunter搜索")
        
        print(f"总共从四个引擎获取到 {len(all_data)} 个结果")
        return all_data
    
    def search_both_engines(self, query_fofa, query_quake360):
        """从两个搜索引擎获取数据（保持向后兼容）"""
        # 为了保持向后兼容，将ZoomEye和Hunter查询设为空
        return self.search_all_engines(query_fofa, query_quake360, "", "")
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
        
        # 获取日期过滤器（仅用于FOFA）
        date_filter = self._get_date_filter(self.days)
        
        # 获取省份和运营商过滤器
        region_filter_fofa = self._get_region_filter_fofa()
        isp_filter_fofa = self._get_isp_filter_fofa()
        region_filter_quake360 = self._get_region_filter_quake360()
        isp_filter_quake360 = self._get_isp_filter_quake360()
        region_filter_zoomeye = self._get_region_filter_zoomeye()
        isp_filter_zoomeye = self._get_isp_filter_zoomeye()
        region_filter_hunter = self._get_region_filter_hunter()
        isp_filter_hunter = self._get_isp_filter_hunter()
        
        # 搜索查询（注意：ZoomEye、Hunter、360 Quake的时间过滤在各自API方法中处理）
        fofa_query = f'title="jsmpeg-streamer" && country="CN" && {date_filter}{region_filter_fofa}{isp_filter_fofa}'
        quake360_query = f'title:"jsmpeg-streamer" AND country:"China"{region_filter_quake360}{isp_filter_quake360}'
        zoomeye_query = f'title="jsmpeg-streamer" && country="CN"{region_filter_zoomeye}{isp_filter_zoomeye}'
        hunter_query = f'web.title="jsmpeg-streamer"&&ip.country="CN"{region_filter_hunter}{isp_filter_hunter}'
        
        print(f"FOFA查询: {fofa_query}")
        print(f"Quake360查询: {quake360_query}")
        print(f"ZoomEye查询: {zoomeye_query}")
        print(f"Hunter查询: {hunter_query}")
        
        # 从四个搜索引擎获取新数据
        new_data = self.search_all_engines(fofa_query, quake360_query, zoomeye_query, hunter_query)
        
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
        
        # 获取日期过滤器（仅用于FOFA）
        date_filter = self._get_date_filter(self.days)
        
        # 获取省份和运营商过滤器
        region_filter_fofa = self._get_region_filter_fofa()
        isp_filter_fofa = self._get_isp_filter_fofa()
        region_filter_quake360 = self._get_region_filter_quake360()
        isp_filter_quake360 = self._get_isp_filter_quake360()
        region_filter_zoomeye = self._get_region_filter_zoomeye()
        isp_filter_zoomeye = self._get_isp_filter_zoomeye()
        region_filter_hunter = self._get_region_filter_hunter()
        isp_filter_hunter = self._get_isp_filter_hunter()
        
        # 搜索查询（注意：ZoomEye、Hunter、360 Quake的时间过滤在各自API方法中处理）
        fofa_query = f'body="/iptv/live/zh_cn.js" && country="CN" && {date_filter}{region_filter_fofa}{isp_filter_fofa}'
        quake360_query = f'body:"/iptv/live/zh_cn.js" AND country:"China"{region_filter_quake360}{isp_filter_quake360}'
        zoomeye_query = f'http.body="/iptv/live/zh_cn.js" && country="CN"{region_filter_zoomeye}{isp_filter_zoomeye}'
        hunter_query = f'web.body="/iptv/live/zh_cn.js"&&ip.country="CN"{region_filter_hunter}{isp_filter_hunter}'
        
        print(f"FOFA查询: {fofa_query}")
        print(f"Quake360查询: {quake360_query}")
        print(f"ZoomEye查询: {zoomeye_query}")
        print(f"Hunter查询: {hunter_query}")
        
        # 从四个搜索引擎获取新数据
        new_data = self.search_all_engines(fofa_query, quake360_query, zoomeye_query, hunter_query)
        
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
        
        # 获取日期过滤器（仅用于FOFA）
        date_filter = self._get_date_filter(self.days)
        
        # 获取省份和运营商过滤器
        region_filter_fofa = self._get_region_filter_fofa()
        isp_filter_fofa = self._get_isp_filter_fofa()
        region_filter_quake360 = self._get_region_filter_quake360()
        isp_filter_quake360 = self._get_isp_filter_quake360()
        region_filter_zoomeye = self._get_region_filter_zoomeye()
        isp_filter_zoomeye = self._get_isp_filter_zoomeye()
        region_filter_hunter = self._get_region_filter_hunter()
        isp_filter_hunter = self._get_isp_filter_hunter()
        
        # 搜索查询（注意：ZoomEye、Hunter、360 Quake的时间过滤在各自API方法中处理）
        fofa_query = f'body="ZHGXTV" && country="CN" && {date_filter}{region_filter_fofa}{isp_filter_fofa}'
        quake360_query = f'body:"ZHGXTV" AND country:"China"{region_filter_quake360}{isp_filter_quake360}'
        zoomeye_query = f'http.body="ZHGXTV" && country="CN"{region_filter_zoomeye}{isp_filter_zoomeye}'
        hunter_query = f'web.body="ZHGXTV"&&ip.country="CN"{region_filter_hunter}{isp_filter_hunter}'
        
        print(f"FOFA查询: {fofa_query}")
        print(f"Quake360查询: {quake360_query}")
        print(f"ZoomEye查询: {zoomeye_query}")
        print(f"Hunter查询: {hunter_query}")
        
        # 从四个搜索引擎获取新数据
        new_data = self.search_all_engines(fofa_query, quake360_query, zoomeye_query, hunter_query)
        
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
    parser.add_argument('--days', type=int, default=29, help='日期过滤天数，默认29天')
    parser.add_argument('--region', help='指定省份，不区分大小写，格式化为首字母大写其他小写')
    parser.add_argument('--isp', help='指定运营商 (Telecom/Unicom/Mobile)，不区分大小写，格式化为首字母大写其他小写')
    parser.add_argument('--max-pages', type=int, help='限制最大翻页数，不指定则无限制')
    
    args = parser.parse_args()
    
    # 检查至少指定了一个模式
    if not any([args.jsmpeg, args.txiptv, args.zhgxtv]):
        print("错误: 请至少指定一个模式参数")
        print("用法示例:")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv --days 7")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv --region beijing --isp telecom")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv --zhgxtv zhgxtv_hosts.csv --days 15 --region guangdong --isp mobile")
        print("  python makecsv.py --jsmpeg jsmpeg_hosts.csv --max-pages 5")
        sys.exit(1)
    
    # 创建收集器实例
    collector = IPTVSourceCollector(days=args.days, region=args.region, isp=args.isp, max_pages=args.max_pages)
    
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
