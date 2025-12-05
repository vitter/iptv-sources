#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2380端口扫描工具
通过FOFA API搜索2380端口并测试连通性
"""

import os
import sys
import base64
import time
import requests
import argparse
from typing import List, Dict
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

class Port2380Scanner:
    """2380端口扫描器"""
    
    def __init__(self, region: str = None, isp: str = None, max_pages: int = 10, max_workers: int = 10, output_file: str = None):
        """
        初始化扫描器
        
        Args:
            region: 省份/地区名称（可选，不指定则搜索全国）
            isp: 运营商类型 (mobile/telecom/unicom/None)
            max_pages: 最大翻页数
            max_workers: 并发线程数
            output_file: 输出文件路径
        """
        # 加载环境变量
        load_dotenv()
        
        # 处理地区参数：支持逗号分隔的多个地区
        if region:
            # 分割地区，去除空格，首字母大写
            self.regions = [r.strip().capitalize() for r in region.split(',') if r.strip()]
        else:
            self.regions = []
        
        self.isp = isp.lower() if isp else None
        self.max_pages = max_pages
        self.max_workers = max_workers
        
        # 从环境变量读取配置
        self.fofa_user_agent = os.getenv('FOFA_USER_AGENT')
        self.fofa_api_key = os.getenv('FOFA_API_KEY', '')
        
        # 验证配置
        self._validate_config()
        
        # 输出文件
        self.output_file = Path(output_file) if output_file else Path("p2380.txt")
        # 未测试的原始结果文件
        self.raw_output_file = self.output_file.with_name(f"{self.output_file.stem}_raw{self.output_file.suffix}")
        
        print("=" * 60)
        print("🔍 2380端口扫描工具")
        print("=" * 60)
        if self.regions:
            if len(self.regions) == 1:
                print(f"地区: {self.regions[0]}")
            else:
                print(f"地区: {', '.join(self.regions)} (共{len(self.regions)}个)")
        else:
            print(f"地区: 全国")
        print(f"运营商: {self.isp if self.isp else '全部'}")
        print(f"最大翻页: {self.max_pages}")
        print(f"并发数: {self.max_workers}")
        print(f"原始结果: {self.raw_output_file}")
        print(f"测试结果: {self.output_file}")
        print("=" * 60)
    
    def _validate_config(self):
        """验证必要的配置"""
        if not self.fofa_user_agent:
            print("❌ 错误：未设置 FOFA_USER_AGENT 环境变量")
            sys.exit(1)
        
        if not self.fofa_api_key:
            print("❌ 错误：未设置 FOFA_API_KEY 环境变量")
            sys.exit(1)
        
        print("✓ 配置验证通过")
        print(f"  FOFA API Key: ✓ ({self.fofa_api_key[:10]}...)")
    
    def build_query(self) -> str:
        """
        构建FOFA搜索查询
        
        Returns:
            查询字符串
        """
        # 基础查询：fid + port + country
        base_query = f'fid="0FC01Psf64jTBZwBfHZoDg==" && port="2380" && product="OpenResty" && country="CN"'
        
        # 添加地区条件
        if self.regions:
            if len(self.regions) == 1:
                # 单地区
                base_query += f' && region="{self.regions[0]}"'
            else:
                # 多地区：使用 || 连接
                region_conditions = " || ".join([f'region="{region}"' for region in self.regions])
                base_query += f' && ( {region_conditions} )'
        
        # 根据运营商添加条件
        if self.isp == 'mobile':
            # 中国移动的ASN列表
            asn_list = [
                "9808", "56048", "24400", "56040", "56046", "24138", "56041", 
                "38019", "24444", "9394", "141425", "140895", "24547", "139080", 
                "56047", "56044", "56042", "138407", "134810", "132525", "56045", 
                "45057", "24445", "140105", "135054", "132510"
            ]
            asn_conditions = " || ".join([f'asn="{asn}"' for asn in asn_list])
            query = f'{base_query} && ({asn_conditions}) '
        
        elif self.isp == 'telecom':
            # 中国电信的ASN列表 (277个)
            # Source: https://github.com/vitter/china-mainland-asn/blob/main/asn_txt/chinanet.txt
            asn_list = [
                "4134", "4809", "4812", "23724", "4811", "58466", "38283", "58461", 
                "134774", "23650", "151397", "134773", "58563", "58542", "58540", "4816", 
                "136198", "136195", "58777", "17799", "17638", "148981", "141679", "140647", 
                "140485", "140345", "140330", "140292", "137697", "134761", "134760", "134756", 
                "133776", "133774", "132225", "131285", "63838", "63835", "58772", "58571", 
                "58543", "58541", "58539", "4835", "17897", "17633", "151823", "151058", 
                "150145", "149979", "149837", "149178", "148969", "147038", "146966", "142608", 
                "141998", "141771", "141739", "141025", "140903", "140638", "140636", "140553", 
                "140527", "140317", "139887", "139767", "139462", "138991", "138570", "138169", 
                "137699", "137695", "137694", "137693", "137692", "137689", "137266", "136200", 
                "136190", "136188", "135089", "134772", "134770", "134769", "134768", "134766", 
                "134765", "134764", "134763", "134762", "134425", "134419", "134238", "133775", 
                "132833", "132437", "131325", "59223", "58518", "58517", "4813", "23662", 
                "23611", "151185", "142404", "141006", "140486", "140484", "140329", "140320", 
                "140319", "140318", "140311", "140309", "140308", "140293", "140278", "140276", 
                "140265", "140083", "139587", "137688", "136199", "134767", "132536", "59265",
                "140863", "140862", "140861", "140860", "140859", "140858", "140857", "140856",
                "140855", "140854", "140853", "140852", "140657", "140656", "140655", "140654",
                "140653", "140652", "140651", "140650", "140649", "140648", "140538", "140537",
                "140536", "140535", "140534", "140533", "140532", "140531", "140530", "140529",
                "140528", "140522", "140521", "140520", "140519", "140518", "140517", "140516",
                "140515", "140514", "140513", "140512", "140511", "140510", "140509", "140508",
                "140497", "140496", "140495", "140494", "140493", "140492", "140491", "140490",
                "140489", "140488", "140487", "140483", "140378", "140377", "140376", "140375",
                "140374", "140373", "140372", "140371", "140370", "140369", "140368", "140367",
                "140366", "140365", "140364", "140361", "140360", "140359", "140358", "140357",
                "140356", "140355", "140354", "140353", "140352", "140351", "140350", "140349",
                "140348", "140347", "140346", "140337", "140336", "140335", "140334", "140333",
                "140332", "140331", "140328", "140316", "140315", "140314", "140313", "140312",
                "140310", "140303", "140302", "140301", "140300", "140299", "140298", "140297",
                "140296", "140295", "140294", "140291", "140290", "140261", "140260", "140259",
                "140258", "140257", "140256", "140255", "140254", "140253", "140252", "140251",
                "140250", "140249", "140248", "140247", "140246", "140245", "140238", "140056",
                "140053", "138679", "138641", "138635", "138597", "138514", "138513", "138436",
                "138409", "138387", "137402", "137401", "134775", "134488"
            ]
            asn_conditions = " || ".join([f'asn="{asn}"' for asn in asn_list])
            query = f'{base_query} && ({asn_conditions}) '
        
        elif self.isp == 'unicom':
            # 中国联通的ASN列表
            asn_list = [
                "4837", "4808", "17621", "17623", "136958", "17622", "140726", "138421", 
                "17816", "135061", "134542", "23851", "140979", "10206", "17789", "152120", 
                "140886", "140717", "140716", "140707", "139007", "137539", "136959", "134543", 
                "133119", "133118"
            ]
            asn_conditions = " || ".join([f'asn="{asn}"' for asn in asn_list])
            query = f'{base_query} && ({asn_conditions}) '
        
        else:
            # 不限制运营商
            query = f'{base_query} '
        
        return query
    
    def search_fofa_api(self) -> List[str]:
        """
        使用FOFA连续翻页API搜索IP:端口
        
        Returns:
            IP:端口列表
        """
        query = self.build_query()
        query_b64 = base64.b64encode(query.encode()).decode().replace('\n', '')
        
        print("\n" + "=" * 60)
        print("📡 从 FOFA API 检索 IP:端口 (连续翻页模式)")
        print("=" * 60)
        print(f"搜索查询: {query}")
        print(f"最大翻页数: {self.max_pages}")
        
        api_url = "https://fofa.info/api/v1/search/next"
        all_ip_ports = []
        
        try:
            # 创建session
            session = requests.Session()
            session.headers.update({
                'User-Agent': self.fofa_user_agent,
                'Accept': 'application/json'
            })
            
            # 第一次请求参数（不带next参数）
            params = {
                'key': self.fofa_api_key,
                'qbase64': query_b64,
                'fields': 'ip,port',
                'size': 200,  # 每页200条
                'full': 'false',
                'r_type': 'json'
            }
            
            print("\n🔄 发送第一次请求获取总数据量...")
            time.sleep(1)
            
            response = session.get(api_url, params=params, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            print(f"✓ 响应状态码: {response.status_code}")
            
            # 解析JSON响应
            response_json = response.json()
            
            # 检查API响应错误
            if response_json.get('error', False):
                error_msg = response_json.get('errmsg', '未知错误')
                print(f"❌ FOFA API错误: {error_msg}")
                return []
            
            # 获取结果数据
            total_size = response_json.get('size', 0)
            results = response_json.get('results', [])
            next_id = response_json.get('next', '')
            
            print(f"📊 API返回总数据量: {total_size}")
            print(f"📄 第1页结果数: {len(results)}")
            
            # 计算总页数
            page_size = 200
            total_pages = (total_size + page_size - 1) // page_size
            actual_pages = min(total_pages, self.max_pages)
            
            print(f"📚 总页数: {total_pages}, 实际获取: {actual_pages} 页")
            
            # 处理第一页数据
            page_ip_ports = self._extract_results(results)
            all_ip_ports.extend(page_ip_ports)
            print(f"✓ 第1页提取到 {len(page_ip_ports)} 个IP:端口")
            
            # 使用连续翻页接口继续获取后续页面
            current_page = 1
            while next_id and current_page < actual_pages:
                current_page += 1
                print(f"\n🔄 获取第 {current_page}/{actual_pages} 页...")
                
                # 添加next参数进行翻页
                params['next'] = next_id
                time.sleep(1)  # 避免API限流
                
                try:
                    response = session.get(api_url, params=params, timeout=30)
                    response.raise_for_status()
                    response.encoding = 'utf-8'
                    
                    response_json = response.json()
                    
                    if response_json.get('error', False):
                        print(f"⚠️  第{current_page}页获取失败，跳过")
                        break
                    
                    results = response_json.get('results', [])
                    next_id = response_json.get('next', '')  # 更新next_id用于下一页
                    
                    if not results:
                        print(f"⚠️  第{current_page}页无数据，停止翻页")
                        break
                    
                    page_ip_ports = self._extract_results(results)
                    all_ip_ports.extend(page_ip_ports)
                    print(f"✓ 第{current_page}页提取到 {len(page_ip_ports)} 个IP:端口")
                    
                    # 如果没有next_id了，说明已经到最后一页
                    if not next_id:
                        print(f"✓ 已到达最后一页")
                        break
                        
                except Exception as e:
                    print(f"⚠️  第{current_page}页请求失败: {e}")
                    break
            
            # 去重
            unique_ips = list(set(all_ip_ports))
            
            print("\n" + "=" * 60)
            print(f"📊 统计信息:")
            print(f"  - 实际获取页数: {current_page}")
            print(f"  - 总共提取: {len(all_ip_ports)} 个")
            print(f"  - 去重后: {len(unique_ips)} 个")
            print("=" * 60)
            
            return unique_ips
            
        except KeyboardInterrupt:
            print(f"\n⚠️  用户中断，已获取 {len(all_ip_ports)} 个结果")
            return list(set(all_ip_ports))
        except requests.exceptions.RequestException as e:
            print(f"❌ FOFA API请求失败: {e}")
            return []
        except Exception as e:
            print(f"❌ FOFA API搜索异常: {e}")
            return []
    
    def _extract_results(self, results: List) -> List[str]:
        """
        提取FOFA API搜索结果
        
        Args:
            results: API返回的结果列表
            
        Returns:
            IP:端口列表
        """
        ip_ports = []
        
        for result in results:
            # 连续翻页接口返回的是对象数组: {"host": "ip:port", "ip": "x.x.x.x", "port": xxxx}
            if isinstance(result, dict):
                ip = result.get('ip', '')
                port = result.get('port', '')
                if ip and port:
                    ip_ports.append(f"{ip}:{port}")
            # 传统接口返回的是数组的数组: ["ip", port]
            elif isinstance(result, list) and len(result) >= 2:
                ip = result[0]
                port = result[1]
                ip_ports.append(f"{ip}:{port}")
        
        return ip_ports
    
    def test_connectivity(self, ip_port: str) -> tuple:
        """
        测试IP:端口的连通性和OpenResty服务可用性
        
        测试策略:
        1. 快速测试根路径HTTP连接(1.2秒超时)
        2. 验证响应状态码(200表示服务正常)
        3. 检查Server响应头确认是OpenResty
        
        Args:
            ip_port: IP:端口字符串
            
        Returns:
            (IP:端口, 是否可用)
        """
        try:
            ip, port = ip_port.split(':', 1)
            test_url = f"http://{ip}:{port}/"
            
            response = requests.get(
                test_url,
                timeout=(1, 1.2),  # (连接超时, 读取超时)
                allow_redirects=False,
                headers={'User-Agent': self.fofa_user_agent}
            )
            
            # 检查状态码: 200表示正常访问
            if response.status_code == 200:
                return (ip_port, True)
            
            # 检查Server头: 确认是OpenResty服务
            # 即使非200状态,只要有OpenResty/nginx响应头也认为服务可用
            server_header = response.headers.get('Server', '').lower()
            if 'openresty' in server_header or 'nginx' in server_header:
                # 404/403等也说明服务在运行,只是路径/权限问题
                if response.status_code in [403, 404]:
                    return (ip_port, True)
            
        except requests.exceptions.Timeout:
            # 超时说明端口可能开放但服务响应慢,不认为可用
            pass
        except requests.exceptions.ConnectionError:
            # 连接错误说明端口未开放或服务未运行
            pass
        except Exception as e:
            # 其他异常
            pass
        
        return (ip_port, False)
    
    def test_all_ips(self, ip_port_list: List[str]) -> List[str]:
        """
        并发测试所有IP:端口的连通性
        
        Args:
            ip_port_list: IP:端口列表
            
        Returns:
            可用的IP:端口列表
        """
        print("\n" + "=" * 60)
        print("🔌 开始测试连通性")
        print("=" * 60)
        print(f"总数: {len(ip_port_list)} 个")
        print(f"并发数: {self.max_workers}")
        
        valid_ips = []
        completed = 0
        total = len(ip_port_list)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有测试任务
            futures = {
                executor.submit(self.test_connectivity, ip_port): ip_port 
                for ip_port in ip_port_list
            }
            
            # 处理完成的任务
            for future in as_completed(futures):
                completed += 1
                ip_port, is_valid = future.result()
                
                if is_valid:
                    valid_ips.append(ip_port)
                    print(f"✅ [{len(valid_ips)}] {ip_port} 可用")
                
                # 进度提示
                if completed % 50 == 0:
                    print(f"📊 进度: {completed}/{total}, 找到: {len(valid_ips)} 个可用IP")
        
        print("\n" + "=" * 60)
        print(f"📊 测试完成:")
        print(f"  - 总测试: {total} 个")
        print(f"  - 可用: {len(valid_ips)} 个")
        print(f"  - 成功率: {len(valid_ips)/total*100:.2f}%")
        print("=" * 60)
        
        return valid_ips
    
    def save_raw_results(self, ip_port_list: List[str]):
        """
        保存原始搜索结果到文件(未经连通性测试)
        
        Args:
            ip_port_list: IP:端口列表
        """
        if not ip_port_list:
            print("\n⚠️  没有原始IP:端口，不生成文件")
            return
        
        try:
            with open(self.raw_output_file, 'w', encoding='utf-8') as f:
                for ip_port in ip_port_list:
                    f.write(f"{ip_port}\n")
            
            print(f"\n✅ 原始结果已保存到: {self.raw_output_file}")
            print(f"   共 {len(ip_port_list)} 个IP:端口(未测试连通性)")
            
        except Exception as e:
            print(f"\n❌ 保存原始结果失败: {e}")
    
    def save_results(self, ip_port_list: List[str]):
        """
        保存测试通过的结果到文件
        
        Args:
            ip_port_list: IP:端口列表
        """
        if not ip_port_list:
            print("\n⚠️  没有可用的IP:端口，不生成文件")
            return
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                for ip_port in ip_port_list:
                    f.write(f"{ip_port}\n")
            
            print(f"\n✅ 测试结果已保存到: {self.output_file}")
            print(f"   共 {len(ip_port_list)} 个可用IP:端口(已验证连通性)")
            
        except Exception as e:
            print(f"\n❌ 保存测试结果失败: {e}")
    
    def run(self):
        """运行扫描流程"""
        start_time = time.time()
        
        # 1. 从FOFA API搜索
        ip_port_list = self.search_fofa_api()
        
        if not ip_port_list:
            print("\n❌ 未找到任何IP:端口")
            return
        
        # 2. 保存原始结果(未测试)
        self.save_raw_results(ip_port_list)
        
        # 3. 测试连通性
        valid_ips = self.test_all_ips(ip_port_list)
        
        # 4. 保存测试通过的结果
        self.save_results(valid_ips)
        
        # 4. 统计信息
        elapsed_time = time.time() - start_time
        print("\n" + "=" * 60)
        print("🎉 扫描完成")
        print("=" * 60)
        print(f"总耗时: {elapsed_time:.2f} 秒")
        print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='2380端口扫描工具 - 通过FOFA API搜索并测试连通性',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 扫描全国所有运营商的2380端口
  python port2380scan.py
  
  # 扫描全国中国移动的2380端口
  python port2380scan.py --isp mobile
  
  # 扫描广东地区所有运营商的2380端口
  python port2380scan.py --region Guangdong
  
  # 扫描多个地区（逗号分隔）
  python port2380scan.py --region "shaanxi,shanxi,Nei Mongol,Guangxi Zhuangzu,Xinjiang Uygur,Ningxia Huizu"
  
  # 扫描广东地区中国移动的2380端口
  python port2380scan.py --region Guangdong --isp mobile
  
  # 扫描多个地区的中国电信
  python port2380scan.py --region Guangdong,Jiangsu,Zhejiang --isp telecom
  
  # 扫描北京地区，最多获取5页数据，使用20个并发
  python port2380scan.py --region Beijing --max-pages 5 --max-workers 20
  
  # 指定输出文件
  python port2380scan.py --region Guangdong -o guangdong_mobile.txt
        """
    )
    
    parser.add_argument(
        '--region',
        type=str,
        default=None,
        help='省份/地区名称，支持单个或多个(逗号分隔)。如: Guangdong 或 Guangdong,Jiangsu,Hebei。不指定则搜索全国'
    )
    
    parser.add_argument(
        '--isp',
        choices=['mobile', 'telecom', 'unicom'],
        help='运营商类型 (mobile/telecom/unicom)，不指定则搜索所有运营商'
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=10,
        help='最大翻页数 (默认: 10)'
    )
    
    parser.add_argument(
        '--max-workers',
        type=int,
        default=10,
        help='并发测试线程数 (默认: 10)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出文件路径 (默认: p2380.txt)'
    )
    
    args = parser.parse_args()
    
    # 创建扫描器并运行
    scanner = Port2380Scanner(
        region=args.region,
        isp=args.isp,
        max_pages=args.max_pages,
        max_workers=args.max_workers,
        output_file=args.output
    )
    
    scanner.run()


if __name__ == "__main__":
    # 禁用SSL警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    main()
