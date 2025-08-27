#!/usr/bin/env python3
"""
中国移动 UDPXY 服务搜索工具
支持 FOFA、Quake360、ZoomEye、Hunter 四个API，自动分页，参数统一。
只输出 ip:port，每行一个，结果去重，写入 txt 文件。
支持 --region、--max-pages、--all-pages、--output 参数。
FOFA 全国需穷举省份，其他引擎直接用“移动”相关字段。
每页统一 10 条数据，API只取 ip 和 port 字段。
"""


import argparse
import base64
import os
import sys
import time
from datetime import datetime, timedelta

# 自动加载.env文件
try:
	from dotenv import load_dotenv
	load_dotenv()
except ImportError:
	print("如需自动加载.env文件，请先安装python-dotenv：pip install python-dotenv")

try:
	import requests
except ImportError:
	print("缺少requests库，请先pip install requests")
	sys.exit(1)

CHINA_PROVINCES = [
	'Beijing', 'Tianjin', 'Hebei', 'Shanxi', 'Neimenggu', 'Liaoning', 'Jilin', 'Heilongjiang',
	'Shanghai', 'Jiangsu', 'Zhejiang', 'Anhui', 'Fujian', 'Jiangxi', 'Shandong', 'Henan',
	'Hubei', 'Hunan', 'Guangdong', 'Guangxi', 'Hainan', 'Chongqing', 'Sichuan', 'Guizhou',
	'Yunnan', 'Xizang', 'Shaanxi', 'Gansu', 'Qinghai', 'Ningxia', 'Xinjiang'
]

class UDPXYMobileCollector:
	def __init__(self, region=None, max_pages=10, output_file="mobile_udpxy.txt", all_pages=False):
		self.region = region
		self.max_pages = max_pages
		self.output_file = output_file
		self.all_pages = all_pages
		self.fofa_api_key = os.getenv('FOFA_API_KEY', '')
		self.quake360_token = os.getenv('QUAKE360_TOKEN', '')
		self.zoomeye_api_key = os.getenv('ZOOMEYE_API_KEY', '')
		self.hunter_api_key = os.getenv('HUNTER_API_KEY', '')
		self.fofa_user_agent = os.getenv('FOFA_USER_AGENT', 'Mozilla/5.0')

	def collect_all(self):
		all_results = set()
		print("\n=============== FOFA ===============")
		all_results.update(self.search_fofa())
		print("\n=============== Quake360 ===============")
		all_results.update(self.search_quake360())
		print("\n=============== ZoomEye ===============")
		all_results.update(self.search_zoomeye())
		print("\n=============== Hunter ===============")
		all_results.update(self.search_hunter())
		self.save_results(sorted(all_results))

	def save_results(self, results):
		try:
			with open(self.output_file, 'w', encoding='utf-8') as f:
				for ip_port in results:
					f.write(f"{ip_port}\n")
			print(f"\n✓ 结果已保存到: {self.output_file}，共 {len(results)} 个IP:PORT")
			for i, ip_port in enumerate(results[:10], 1):
				print(f"  {i:2d}. {ip_port}")
			if len(results) > 10:
				print(f"  ... 还有 {len(results) - 10} 个")
		except Exception as e:
			print(f"保存文件失败: {e}")

	def search_fofa(self):
		if not self.fofa_api_key:
			print("未配置FOFA_API_KEY，跳过FOFA")
			return []
		# 移动ASN列表
		mobile_asns = [
			"9808", "56048", "24400", "56040", "56046", "24138", "56041", "38019", "24444", "9394",
			"141425", "140895", "24547", "139080", "56047", "56044", "56042", "138407", "134810", "132525",
			"56045", "45057", "24445", "140105", "135054", "132510"
		]
		asn_query = " || ".join([f'asn="{asn}"' for asn in mobile_asns])
		query = f'"udpxy" && country="CN" && protocol="http" && ({asn_query})'
		if self.region:
			query += f' && region="{self.region}"'
		print(f"FOFA查询语句: {query}")
		query_b64 = base64.b64encode(query.encode()).decode()
		api_url = "https://fofa.info/api/v1/search/all"
		page = 1
		total = 0
		total_pages = 0
		results = set()
		while True:
			params = {
				'key': self.fofa_api_key,
				'qbase64': query_b64,
				'page': page,
				'size': 10,
				'fields': 'ip,port',
				'r_type': 'json'
			}
			headers = {'User-Agent': self.fofa_user_agent}
			try:
				resp = requests.get(api_url, params=params, headers=headers, timeout=30)
				data = resp.json()
				if data.get('error'):
					print(f"FOFA API错误: {data.get('errmsg', '未知错误')}")
					break
				# 兼容FOFA返回格式，可能是[[ip, port], ...] 或 [{'ip':..., 'port':...}, ...]
				page_results = []
				for item in data.get('results', []):
					if isinstance(item, (list, tuple)) and len(item) >= 2:
						ip, port = item[0], item[1]
					elif isinstance(item, dict):
						ip, port = item.get('ip'), item.get('port')
					else:
						continue
					if ip and port:
						page_results.append(f"{ip}:{port}")
				results.update(page_results)
				print(f"FOFA第{page}页: {len(page_results)} 条")
				total = data.get('size', 0)
				total_pages = (total + 9) // 10
				if self.all_pages and page < total_pages:
					page += 1
					time.sleep(1)
				else:
					break
			except Exception as e:
				print(f"FOFA API请求失败: {e}")
				break
		print(f"FOFA总数: {total}，总页数: {total_pages}，实际获取: {len(results)} 条")
		print("FOFA头三条:")
		for i, ip_port in enumerate(list(results)[:3], 1):
			print(f"  {i}. {ip_port}")
		return results

	def search_quake360(self):
		if not self.quake360_token:
			print("未配置QUAKE360_TOKEN，跳过Quake360")
			return []
		query = f'"udpxy" AND country: "China" AND isp: "中国移动" AND protocol: "http"'
		if self.region:
			query = f'"udpxy" AND country: "China" AND province: "{self.region}" AND isp: "中国移动" AND protocol: "http"'
		print(f"Quake360查询语句: {query}")
		api_url = 'https://quake.360.net/api/v3/search/quake_service'
		headers = {
			'X-QuakeToken': self.quake360_token,
			'Content-Type': 'application/json',
			'User-Agent': self.fofa_user_agent
		}
		results = set()
		page = 1
		total = 0
		total_pages = 0
		while True:
			data = {
				"query": query,
				"start": (page - 1) * 10,
				"size": 10,
				"ignore_cache": False,
				"latest": True,
				"include": ["ip", "port"],
				"shortcuts": ["635fcb52cc57190bd8826d09"]
			}
			try:
				resp = requests.post(api_url, headers=headers, json=data, timeout=30)
				resp_json = resp.json()
				page_results = [f"{item.get('ip', item.get('service', {}).get('ip', ''))}:{item.get('port', item.get('service', {}).get('port', ''))}" for item in resp_json.get('data', []) if item.get('ip', item.get('service', {}).get('ip', '')) and item.get('port', item.get('service', {}).get('port', ''))]
				results.update(page_results)
				print(f"Quake360第{page}页: {len(page_results)} 条")
				total = resp_json.get('meta', {}).get('pagination', {}).get('total', 0)
				total_pages = (total + 9) // 10
				if self.all_pages and page < total_pages:
					page += 1
					time.sleep(1)
				else:
					break
			except Exception as e:
				print(f"Quake360 API请求失败: {e}")
				break
			if not self.all_pages:
				break
		print(f"Quake360总数: {total}，总页数: {total_pages}，实际获取: {len(results)} 条")
		print("Quake360头三条:")
		for i, ip_port in enumerate(list(results)[:3], 1):
			print(f"  {i}. {ip_port}")
		return results

	def search_zoomeye(self):
		if not self.zoomeye_api_key:
			print("未配置ZOOMEYE_API_KEY，跳过ZoomEye")
			return []
		query = f'app="udpxy" && country="CN" && isp="China Mobile"'
		if self.region:
			query = f'app="udpxy" && country="CN" && isp="China Mobile" && subdivisions="{self.region}"'
		print(f"ZoomEye查询语句: {query}")
		api_url = 'https://api.zoomeye.org/v2/search'
		headers = {
			'API-KEY': self.zoomeye_api_key,
			'Content-Type': 'application/json',
			'User-Agent': self.fofa_user_agent
		}
		results = set()
		page = 1
		total = 0
		total_pages = 0
		while True:
			data = {
				'qbase64': base64.b64encode(query.encode()).decode(),
				'page': page,
				'pagesize': 10,
				'fields': 'ip,port'
			}
			try:
				resp = requests.post(api_url, headers=headers, json=data, timeout=30)
				resp_json = resp.json()
				page_results = [f"{item.get('ip', '')}:{item.get('port', '')}" for item in resp_json.get('data', []) if item.get('ip', '') and item.get('port', '')]
				results.update(page_results)
				print(f"ZoomEye第{page}页: {len(page_results)} 条")
				total = resp_json.get('total', 0)
				total_pages = (total + 9) // 10
				if self.all_pages and page < total_pages:
					page += 1
					time.sleep(1)
				else:
					break
			except Exception as e:
				print(f"ZoomEye API请求失败: {e}")
				break
			if not self.all_pages:
				break
		print(f"ZoomEye总数: {total}，总页数: {total_pages}，实际获取: {len(results)} 条")
		print("ZoomEye头三条:")
		for i, ip_port in enumerate(list(results)[:3], 1):
			print(f"  {i}. {ip_port}")
		return results

	def search_hunter(self):
		if not self.hunter_api_key:
			print("未配置HUNTER_API_KEY，跳过Hunter")
			return []
		# 省份中文映射
		province_map = {
			'Beijing': '北京', 'Tianjin': '天津', 'Hebei': '河北', 'Shanxi': '山西', 'Neimenggu': '内蒙古',
			'Liaoning': '辽宁', 'Jilin': '吉林', 'Heilongjiang': '黑龙江', 'Shanghai': '上海', 'Jiangsu': '江苏',
			'Zhejiang': '浙江', 'Anhui': '安徽', 'Fujian': '福建', 'Jiangxi': '江西', 'Shandong': '山东',
			'Henan': '河南', 'Hubei': '湖北', 'Hunan': '湖南', 'Guangdong': '广东', 'Guangxi': '广西',
			'Hainan': '海南', 'Chongqing': '重庆', 'Sichuan': '四川', 'Guizhou': '贵州', 'Yunnan': '云南',
			'Xizang': '西藏', 'Shaanxi': '陕西', 'Gansu': '甘肃', 'Qinghai': '青海', 'Ningxia': '宁夏', 'Xinjiang': '新疆'
		}
		if self.region:
			province = province_map.get(self.region, self.region)
		else:
			province = ''
		query = f'protocol.banner="Server: udpxy"&&app="Linux"&&protocol=="http"&&ip.country="CN"&&ip.isp="移动"'
		if province:
			query += f'&&ip.province="{province}"'
		print(f"Hunter查询语句: {query}")
		query_b64 = base64.urlsafe_b64encode(query.encode('utf-8')).decode('utf-8')
		api_url = 'https://hunter.qianxin.com/openApi/search'
		results = set()
		page = 1
		total = 0
		total_pages = 0
		end_time = datetime.now().strftime('%Y-%m-%d')
		start_time = (datetime.now() - timedelta(days=179)).strftime('%Y-%m-%d')
		while True:
			params = {
				'api-key': self.hunter_api_key,
				'search': query_b64,
				'page': page,
				'page_size': 10,
				'is_web': 1,
				'port_filter': 'false',
				'start_time': start_time,
				'end_time': end_time
			}
			try:
				resp = requests.get(api_url, params=params, timeout=30)
				resp_json = resp.json()
				arr = resp_json.get('data', {}).get('arr', [])
				page_results = [f"{item.get('ip', '')}:{item.get('port', '')}" for item in arr if item.get('ip', '') and item.get('port', '')]
				results.update(page_results)
				print(f"Hunter第{page}页: {len(page_results)} 条")
				total = resp_json.get('data', {}).get('total', 0)
				total_pages = (total + 9) // 10
				if self.all_pages and page < total_pages:
					page += 1
					time.sleep(1)
				else:
					break
			except Exception as e:
				print(f"Hunter API请求失败: {e}")
				break
			if not self.all_pages:
				break
		print(f"Hunter总数: {total}，总页数: {total_pages}，实际获取: {len(results)} 条")
		print("Hunter头三条:")
		for i, ip_port in enumerate(list(results)[:3], 1):
			print(f"  {i}. {ip_port}")
		return results

def main():
	parser = argparse.ArgumentParser(description='中国移动UDPXY服务搜索工具')
	parser.add_argument('--region', help='指定省份，如: guangdong, beijing')
	parser.add_argument('--max-pages', type=int, default=10, help='最大搜索页数，默认10页')
	parser.add_argument('--all-pages', action='store_true', help='自动获取所有页')
	parser.add_argument('--output', default='mobile_udpxy.txt', help='输出文件名')
	args = parser.parse_args()

	print("=" * 60)
	print("           中国移动UDPXY服务搜索工具")
	print("=" * 60)

	region_fmt = args.region.capitalize() if args.region else None
	collector = UDPXYMobileCollector(
		region=region_fmt,
		max_pages=args.max_pages,
		output_file=args.output,
		all_pages=args.all_pages
	)
	collector.collect_all()

	print("\n" + "=" * 60)
	print("搜索完成！")
	print("=" * 60)

if __name__ == "__main__":
	main()
