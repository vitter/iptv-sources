#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面测试 socks5 代理功能
"""

import sys
import time
import socket
import socks

def test_website(s, host, port, path="/"):
    """通过代理测试访问网站"""
    try:
        s.connect((host, port))
        request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        s.send(request.encode())
        
        # 接收响应
        data = b""
        try:
            while len(data) < 2048:
                chunk = s.recv(1024)
                if not chunk:
                    break
                data += chunk
                if len(data) > 512:  # 收到足够数据即可
                    break
        except socket.timeout:
            pass
        
        if data:
            response = data.decode('utf-8', errors='ignore')
            status_line = response.split('\r\n')[0]
            return True, status_line, len(data)
        return False, "未收到响应", 0
    except Exception as e:
        return False, str(e)[:50], 0

def test_comprehensive(ip, port):
    """全面测试代理"""
    print(f"🔍 全面测试代理: {ip}:{port}")
    print("=" * 70)
    
    results = []
    
    # 测试1: 百度
    print("\n📌 测试1: 访问百度 (http://www.baidu.com)")
    try:
        start = time.time()
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, ip, int(port))
        s.settimeout(8)
        
        success, info, size = test_website(s, "www.baidu.com", 80)
        elapsed = (time.time() - start) * 1000
        s.close()
        
        if success:
            print(f"  ✅ 成功 - {info} ({size}字节, {elapsed:.0f}ms)")
            results.append(True)
        else:
            print(f"  ❌ 失败 - {info}")
            results.append(False)
    except Exception as e:
        print(f"  ❌ 异常 - {e}")
        results.append(False)
    
    # 测试2: httpbin.org (国外网站)
    print("\n📌 测试2: 访问国外测试站 (http://httpbin.org/ip)")
    try:
        start = time.time()
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, ip, int(port))
        s.settimeout(10)
        
        success, info, size = test_website(s, "httpbin.org", 80, "/ip")
        elapsed = (time.time() - start) * 1000
        s.close()
        
        if success:
            print(f"  ✅ 成功 - {info} ({size}字节, {elapsed:.0f}ms)")
            results.append(True)
        else:
            print(f"  ❌ 失败 - {info}")
            results.append(False)
    except Exception as e:
        print(f"  ❌ 异常 - {e}")
        results.append(False)
    
    # 测试3: 新浪
    print("\n📌 测试3: 访问新浪 (http://www.sina.com.cn)")
    try:
        start = time.time()
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, ip, int(port))
        s.settimeout(8)
        
        success, info, size = test_website(s, "www.sina.com.cn", 80)
        elapsed = (time.time() - start) * 1000
        s.close()
        
        if success:
            print(f"  ✅ 成功 - {info} ({size}字节, {elapsed:.0f}ms)")
            results.append(True)
        else:
            print(f"  ❌ 失败 - {info}")
            results.append(False)
    except Exception as e:
        print(f"  ❌ 异常 - {e}")
        results.append(False)
    
    # 测试4: GitHub
    print("\n📌 测试4: 访问 GitHub (http://github.com)")
    try:
        start = time.time()
        s = socks.socksocket()
        s.set_proxy(socks.SOCKS5, ip, int(port))
        s.settimeout(10)
        
        success, info, size = test_website(s, "github.com", 80)
        elapsed = (time.time() - start) * 1000
        s.close()
        
        if success:
            print(f"  ✅ 成功 - {info} ({size}字节, {elapsed:.0f}ms)")
            results.append(True)
        else:
            print(f"  ❌ 失败 - {info}")
            results.append(False)
    except Exception as e:
        print(f"  ❌ 异常 - {e}")
        results.append(False)
    
    # 结果统计
    print("\n" + "=" * 70)
    success_count = sum(results)
    total_count = len(results)
    print(f"📊 测试结果: {success_count}/{total_count} 成功")
    
    if success_count == total_count:
        print("🎉 代理完全可用，所有测试通过！")
    elif success_count > 0:
        print(f"⚠️  代理部分可用，{success_count}个测试通过")
    else:
        print("❌ 代理不可用，所有测试失败")
    
    print("=" * 70)
    
    return success_count, total_count

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python test_proxy_comprehensive.py <IP> <端口>")
        print("示例: python test_proxy_comprehensive.py 222.138.59.70 5555")
        sys.exit(1)
    
    ip = sys.argv[1]
    port = sys.argv[2]
    
    test_comprehensive(ip, port)
