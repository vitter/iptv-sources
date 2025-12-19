#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FOFA Socks5 代理扫描工具
通过 FOFA API 搜索 socks5 代理并可选测试连通性
"""

import os
import sys
import time
import base64
import argparse
import requests
import urllib3
from typing import List, Dict, Optional
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import socks
import socket

class FofaSocks5Scanner:
    """FOFA Socks5 代理扫描器"""
    
    def __init__(self, 
                 max_pages: int = 10, 
                 max_workers: int = 10, 
                 output_file: str = None,
                 check_url: str = None,
                 check_words: str = None):
        """
        初始化扫描器
        
        Args:
            max_pages: 最大翻页数（每页10条）
            max_workers: 并发线程数
            output_file: 输出文件路径
            check_url: 验证代理的目标URL
            check_words: 验证URL返回内容中应包含的关键词
        """
        # 加载环境变量
        load_dotenv()
        
        self.max_pages = max_pages
        self.max_workers = max_workers
        self.check_url = check_url
        self.check_words = check_words
        
        # 从环境变量读取配置
        self.fofa_user_agent = os.getenv('FOFA_USER_AGENT')
        self.fofa_api_key = os.getenv('FOFA_API_KEY', '')
        
        # 验证配置
        self._validate_config()
        
        # 输出文件
        self.output_file = Path(output_file) if output_file else Path("socks5_proxies.txt")
        # 未测试的原始结果文件
        self.raw_output_file = self.output_file.with_name(f"{self.output_file.stem}_raw{self.output_file.suffix}")
        
        print("=" * 60)
        print("🔍 FOFA Socks5 代理扫描工具")
        print("=" * 60)
        print(f"最大翻页: {self.max_pages} 页 (每页 10 条)")
        print(f"并发数: {self.max_workers}")
        if self.check_url:
            print(f"验证URL: {self.check_url}")
            if self.check_words:
                print(f"验证关键词: {self.check_words}")
        print(f"原始结果: {self.raw_output_file}")
        print(f"最终结果: {self.output_file}")
        print("=" * 60)
    
    def _validate_config(self):
        """验证必要的配置"""
        if not self.fofa_user_agent:
            raise ValueError("未找到 FOFA_USER_AGENT 环境变量，请在 .env 文件中配置")
        
        if not self.fofa_api_key:
            raise ValueError("未找到 FOFA_API_KEY 环境变量，请在 .env 文件中配置")
        
        print("✓ 配置验证通过")
        print(f"  FOFA API Key: ✓ ({self.fofa_api_key[:10]}...)")
    
    def build_query(self) -> str:
        """
        构建FOFA搜索查询
        
        Returns:
            查询字符串
        """
        # 固定的 socks5 查询语句
        query = 'protocol=="socks5" && "Version:5 Method:No Authentication(0x00)" && country="CN"'
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
        print("📡 从 FOFA API 检索 Socks5 代理 (连续翻页模式)")
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
                'size': 10,  # 每页10条
                'full': 'false',
                'r_type': 'json'
            }
            
            print("\n🔄 发送第一次请求获取总数据量...")
            time.sleep(1)
            
            response = session.get(api_url, params=params, timeout=30, verify=False)
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
            page_size = 10
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
                
                # 添加next参数进行翻页（保留原有参数）
                params['next'] = next_id
                time.sleep(1)  # 避免API限流
                
                try:
                    response = session.get(api_url, params=params, timeout=30, verify=False)
                    response.raise_for_status()
                    response.encoding = 'utf-8'
                    
                    response_json = response.json()
                    
                    if response_json.get('error', False):
                        print(f"⚠️  第{current_page}页获取失败: {response_json.get('errmsg', '未知错误')}")
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
        从 FOFA 结果中提取 IP:端口
        
        Args:
            results: FOFA API 返回的结果列表
            
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
    
    def test_socks5_proxy(self, ip_port: str) -> tuple:
        """
        测试 socks5 代理是否可用
        
        Args:
            ip_port: IP:端口字符串
            
        Returns:
            (是否可用, 响应时间/错误信息)
        """
        try:
            ip, port = ip_port.split(':')
            port = int(port)
            
            if not self.check_url:
                # 如果没有指定检查URL，只测试基本连接
                start_time = time.time()
                
                # 使用 socks 库创建连接测试
                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, ip, port)
                s.settimeout(8)  # 增加超时时间
                
                # 尝试连接到百度（HTTP）
                s.connect(("www.baidu.com", 80))
                
                # 发送简单的HTTP请求测试
                s.send(b"GET / HTTP/1.1\r\nHost: www.baidu.com\r\nConnection: close\r\n\r\n")
                
                # 接收响应，增大接收缓冲区
                data = s.recv(1024)
                s.close()
                
                elapsed = time.time() - start_time
                
                # 检查是否收到HTTP响应
                if data and (b"HTTP" in data or b"html" in data.lower()):
                    return True, f"{elapsed*1000:.0f}ms"
                else:
                    return False, "无效响应"
                    
            else:
                # 使用代理访问指定URL
                # 优先使用原生 socks 方式，更可靠
                start_time = time.time()
                
                # 解析URL
                import urllib.parse
                parsed = urllib.parse.urlparse(self.check_url)
                host = parsed.hostname
                scheme = parsed.scheme
                path = parsed.path or '/'
                
                # 根据协议选择端口
                if scheme == 'https':
                    target_port = 443
                else:
                    target_port = 80
                
                # 使用 socks 库创建连接
                s = socks.socksocket()
                s.set_proxy(socks.SOCKS5, ip, port)
                s.settimeout(8)
                
                # 连接到目标服务器
                s.connect((host, target_port))
                
                # 发送HTTP请求
                request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n"
                s.send(request.encode())
                
                # 接收响应
                response_data = b""
                try:
                    while len(response_data) < 10240:  # 最多接收10KB
                        chunk = s.recv(4096)
                        if not chunk:
                            break
                        response_data += chunk
                        # 如果已经有足够数据判断，提前退出
                        if len(response_data) > 1024:
                            break
                except socket.timeout:
                    pass  # 接收超时不是错误，可能已经收到部分数据
                
                s.close()
                elapsed = time.time() - start_time
                
                # 检查是否收到有效响应
                if not response_data:
                    return False, "未收到响应"
                
                # 解码响应（尝试多种编码）
                response_text = ""
                for encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']:
                    try:
                        response_text = response_data.decode(encoding, errors='ignore')
                        break
                    except:
                        continue
                
                # 检查HTTP状态
                if not response_text.startswith("HTTP"):
                    return False, "无效HTTP响应"
                
                # 检查关键词
                if self.check_words:
                    if self.check_words in response_text:
                        return True, f"{elapsed*1000:.0f}ms"
                    else:
                        # 提供更多调试信息
                        if "200 OK" in response_text or "200" in response_text.split('\n')[0]:
                            return False, f"HTTP 200但无关键词(收到{len(response_data)}字节)"
                        else:
                            return False, "关键词不匹配"
                else:
                    # 不检查关键词，只检查HTTP状态码
                    if "200" in response_text.split('\n')[0]:
                        return True, f"{elapsed*1000:.0f}ms"
                    else:
                        return False, "非200状态码"
                        
        except socket.timeout:
            return False, "连接超时"
        except socket.error as e:
            return False, f"Socket错误: {str(e)[:50]}"
        except Exception as e:
            error_msg = str(e)
            # 简化错误信息
            if "timed out" in error_msg.lower():
                return False, "超时"
            elif "Connection refused" in error_msg:
                return False, "连接被拒绝"
            elif "Connection reset" in error_msg:
                return False, "连接重置"
            elif "Connection closed" in error_msg:
                return False, "连接关闭"
            else:
                return False, error_msg[:80]  # 限制错误信息长度
    
    def test_all_proxies(self, ip_port_list: List[str]) -> List[str]:
        """
        并发测试所有代理
        
        Args:
            ip_port_list: IP:端口列表
            
        Returns:
            可用的IP:端口列表
        """
        if not self.check_url and not ip_port_list:
            return ip_port_list
        
        print("\n" + "=" * 60)
        print("🧪 测试代理连通性")
        print("=" * 60)
        
        working_proxies = []
        total = len(ip_port_list)
        completed = 0
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ip = {executor.submit(self.test_socks5_proxy, ip_port): ip_port 
                          for ip_port in ip_port_list}
            
            for future in as_completed(future_to_ip):
                ip_port = future_to_ip[future]
                completed += 1
                
                try:
                    is_working, info = future.result()
                    
                    if is_working:
                        working_proxies.append(ip_port)
                        print(f"[{completed}/{total}] ✓ {ip_port} - {info}")
                    else:
                        print(f"[{completed}/{total}] ✗ {ip_port} - {info}")
                        
                except Exception as e:
                    print(f"[{completed}/{total}] ✗ {ip_port} - 测试异常: {e}")
        
        print("\n" + "=" * 60)
        print(f"📊 测试完成")
        print("=" * 60)
        print(f"总数: {total}")
        print(f"可用: {len(working_proxies)} ({len(working_proxies)/total*100:.1f}%)" if total > 0 else "可用: 0")
        print(f"不可用: {total - len(working_proxies)}")
        print("=" * 60)
        
        return working_proxies
    
    def save_raw_results(self, ip_port_list: List[str]):
        """
        保存原始结果（未测试）
        
        Args:
            ip_port_list: IP:端口列表
        """
        try:
            with open(self.raw_output_file, 'w', encoding='utf-8') as f:
                for ip_port in ip_port_list:
                    f.write(f"{ip_port}\n")
            
            print(f"\n✓ 原始结果已保存到: {self.raw_output_file}")
            print(f"  总计: {len(ip_port_list)} 个代理")
            
        except Exception as e:
            print(f"\n✗ 保存原始结果失败: {e}")
    
    def save_results(self, ip_port_list: List[str]):
        """
        保存最终结果
        
        Args:
            ip_port_list: IP:端口列表
        """
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                for ip_port in ip_port_list:
                    f.write(f"{ip_port}\n")
            
            print(f"\n✓ 最终结果已保存到: {self.output_file}")
            print(f"  总计: {len(ip_port_list)} 个可用代理")
            
        except Exception as e:
            print(f"\n✗ 保存结果失败: {e}")
    
    def run(self):
        """运行扫描流程"""
        # 1. 从 FOFA 搜索
        ip_port_list = self.search_fofa_api()
        
        if not ip_port_list:
            print("\n✗ 未找到任何结果")
            return
        
        # 2. 保存原始结果
        self.save_raw_results(ip_port_list)
        
        # 3. 测试连通性（如果需要）
        if self.check_url:
            working_proxies = self.test_all_proxies(ip_port_list)
            
            if working_proxies:
                self.save_results(working_proxies)
            else:
                print("\n✗ 没有可用的代理")
        else:
            # 不测试，直接保存
            self.save_results(ip_port_list)
        
        print("\n" + "=" * 60)
        print("✅ 扫描完成")
        print("=" * 60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='FOFA Socks5 代理扫描工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基础扫描（爬取10页，不测试连通性）
  python fofa_socks5_scanner.py
  
  # 爬取20页
  python fofa_socks5_scanner.py -page 20
  
  # 验证代理能否访问百度
  python fofa_socks5_scanner.py -check "https://www.baidu.com" -checkWords "百度一下，你就知道"
  
  # 指定输出文件
  python fofa_socks5_scanner.py -o my_proxies.txt
  
  # 综合示例
  python fofa_socks5_scanner.py -page 30 -check "https://www.baidu.com" -checkWords "百度" -o baidu_proxies.txt

注意:
  - 需要在 .env 文件中配置 FOFA_USER_AGENT 和 FOFA_API_KEY
  - 如果使用 -check 参数，需要安装 PySocks: pip install PySocks
  - 默认每页爬取 10 条结果
        """
    )
    
    parser.add_argument(
        '-page',
        type=int,
        default=10,
        help='FOFA 结果爬取页数（每页 10 条，默认: 10）'
    )
    
    parser.add_argument(
        '-check',
        type=str,
        default=None,
        help='验证代理的目标URL（例如: https://www.baidu.com）'
    )
    
    parser.add_argument(
        '-checkWords',
        type=str,
        default=None,
        help='验证URL返回内容应包含的关键词（例如: 百度一下，你就知道）'
    )
    
    parser.add_argument(
        '--max-workers',
        type=int,
        default=10,
        help='并发测试线程数（默认: 10）'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='输出文件路径（默认: socks5_proxies.txt）'
    )
    
    args = parser.parse_args()
    
    # 检查依赖
    if args.check:
        try:
            import socks
        except ImportError:
            print("✗ 使用 -check 参数需要安装 PySocks 库")
            print("  请运行: pip install PySocks")
            sys.exit(1)
    
    # 创建扫描器并运行
    scanner = FofaSocks5Scanner(
        max_pages=args.page,
        max_workers=args.max_workers,
        output_file=args.output,
        check_url=args.check,
        check_words=args.checkWords
    )
    
    scanner.run()


if __name__ == "__main__":
    # 禁用SSL警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    main()
