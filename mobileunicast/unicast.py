#!/usr/bin/env python3
"""
IPTV直播源下载、合并、测速与分组工具

功能：
1. 从指定URL列表下载直播源txt文件
2. 合并所有频道（忽略原分组）
3. 对流媒体地址进行测速
4. 按速度排序并保留前N个
5. 重新分组并生成结果文件

用法：
python unicast.py --top 20
python unicast.py --top 20 --proxy http://127.0.0.1:10808

项目主页: https://github.com/vitter/iptv-sources
问题反馈: https://github.com/vitter/iptv-sources/issues
"""

import os
import re
import sys
import time
import socket
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ChannelInfo:
    """频道信息"""
    name: str
    url: str
    speed: float = 0.0


class ChannelGroup:
    """频道分组枚举类"""
    CCTV = "央视频道"
    WEI_SHI = "卫视频道"
    LOCAL = "省级频道"
    HKMOTW = "港澳台频道"
    CITY = "市级频道"
    OTHER = "其它频道"


class UnicastProcessor:
    """IPTV直播源处理器"""
    
    # URL列表
    URLS = [
        "https://live.zbds.org/tv/yd.txt",
        "https://chinaiptv.pages.dev/Unicast/anhui/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/fujian/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/guangxi/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/hebei/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/heilongjiang/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/henan/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/hubei/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/jiangxi/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/jiangsu/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/shan3xi/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/shandong/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/zhejiang/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/shanghai/mobile.txt",
        "https://chinaiptv.pages.dev/Unicast/liaoning/mobile.txt",
        "https://mycode.zhoujie218.top/me/jsyd.txt",
        "https://raw.githubusercontent.com/q1017673817/iptv_zubo/refs/heads/main/hnyd.txt",
        "https://raw.githubusercontent.com/suxuang/myIPTV/refs/heads/main/%E7%A7%BB%E5%8A%A8%E4%B8%93%E4%BA%AB.txt",
        "https://live.zbds.org/tv/iptv6.txt",
        "https://live.zbds.org/tv/zjyd.txt",
        "https://live.zbds.org/tv/zjyd1.txt",
        "https://live.zbds.org/tv/jxyd.txt",
        "https://live.zbds.org/tv/sxyd.txt",
        "https://vdyun.com/hbm3u.txt",
        "https://vdyun.com/hbcm.txt",
        "https://vdyun.com/hbcm1.txt",
        "https://vdyun.com/hbcm2.txt",
        "https://vdyun.com/yd.txt",
        "https://vdyun.com/yd1.txt",
        "https://vdyun.com/yd2.txt",
        "https://vdyun.com/yd3.txt",
        "https://vdyun.com/ipv6.txt",
        "https://vdyun.com/sjzcm1.txt",
        "https://vdyun.com/sjzcm2.txt",
        "https://vdyun.com/hljcm.txt",
        "https://vdyun.com/shxcm.txt",
        "https://vdyun.com/shxcm1.txt"
    ]
    
    # 分组关键字
    locals = ("北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林", "黑龙江", 
              "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南", 
              "广东", "海南", "四川", "贵州", "云南", "陕西", "甘肃", "青海", "内蒙", 
              "广西", "西藏", "宁夏", "新疆", "东南", "东方")
    
    hkmotw = ("凤凰", "香港", "TVB", "tvb", "RTHK", "港台", "明珠", "翡翠", "面包", "人间", "唯心", "星空", "无线", "有线", "无线电视", "无线新闻", "无线娱乐", "大爱", "番薯", "亚洲", "华视", "中天", "中视", "民视", "东森", "三立", "台视", "公视", "台湾","澳门", "澳视", "澳亚", "澳广")
    
    wei_shi = ("卫视",)
    
    citys = ("石家庄", "唐山", "秦皇岛", "邯郸", "邢台", "保定", "张家口", "承德", "沧州", "廊坊", "衡水",
"太原", "大同", "阳泉", "长治", "晋城", "朔州", "晋中", "运城", "忻州", "临汾", "吕梁",
"呼和浩特", "包头", "乌海", "赤峰", "通辽", "鄂尔多斯", "呼伦贝尔", "巴彦淖尔", "乌兰察布",
"沈阳", "大连", "鞍山", "抚顺", "本溪", "丹东", "锦州", "营口", "阜新", "辽阳", "盘锦", "铁岭", "朝阳", "葫芦岛",
"长春", "吉林", "四平", "辽源", "通化", "白山", "松原", "白城", "延边朝鲜族自治州",
"哈尔滨", "齐齐哈尔", "鸡西", "鹤岗", "双鸭山", "大庆", "伊春", "佳木斯", "七台河", "牡丹江", "黑河", "绥化", "大兴安岭地区",
"南京", "无锡", "徐州", "常州", "苏州", "南通", "连云港", "淮安", "盐城", "扬州", "镇江", "泰州", "宿迁",
"杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "衢州", "舟山", "台州", "丽水",
"合肥", "芜湖", "蚌埠", "淮南", "马鞍山", "淮北", "铜陵", "安庆", "黄山", "滁州", "阜阳", "宿州", "六安", "亳州", "池州", "宣城",
"福州", "厦门", "莆田", "三明", "泉州", "漳州", "南平", "龙岩", "宁德",
"南昌", "景德镇", "萍乡", "九江", "新余", "鹰潭", "赣州", "吉安", "宜春", "抚州", "上饶",
"济南", "青岛", "淄博", "枣庄", "东营", "烟台", "潍坊", "济宁", "泰安", "威海", "日照", "临沂", "德州", "聊城", "滨州", "菏泽",
"郑州", "开封", "洛阳", "平顶山", "安阳", "鹤壁", "新乡", "焦作", "濮阳", "许昌", "漯河", "三门峡", "南阳", "商丘", "信阳", "周口", "驻马店",
"武汉", "黄石", "十堰", "宜昌", "襄阳", "鄂州", "荆门", "孝感", "荆州", "黄冈", "咸宁", "随州", "恩施土家族苗族自治州",
"长沙", "株洲", "湘潭", "衡阳", "邵阳", "岳阳", "常德", "张家界", "益阳", "郴州", "永州", "怀化", "娄底", "湘西土家族苗族自治州",
"广州", "韶关", "深圳", "珠海", "汕头", "佛山", "江门", "湛江", "茂名", "肇庆", "惠州", "梅州", "汕尾", "河源", "阳江", "清远", "东莞", "中山", "潮州", "揭阳", "云浮",
"南宁", "柳州", "桂林", "梧州", "北海", "防城港", "钦州", "贵港", "玉林", "百色", "贺州", "河池", "来宾", "崇左",
"海口", "三亚", "三沙", "儋州",
"重庆",
"成都", "自贡", "攀枝花", "泸州", "德阳", "绵阳", "广元", "遂宁", "内江", "乐山", "南充", "眉山", "宜宾", "广安", "达州", "雅安", "巴中", "资阳", "阿坝藏族羌族自治州", "甘孜藏族自治州", "凉山彝族自治州",
"贵阳", "六盘水", "遵义", "安顺", "毕节", "铜仁", "黔东南苗族侗族自治州", "黔南布依族苗族自治州", "黔西南布依族苗族自治州",
"昆明", "曲靖", "玉溪", "保山", "昭通", "丽江", "普洱", "临沧", "楚雄彝族自治州", "红河哈尼族彝族自治州", "文山壮族苗族自治州", "西双版纳傣族自治州", "大理白族自治州", "德宏傣族景颇族自治州", "怒江傈僳族自治州", "迪庆藏族自治州",
"拉萨", "日喀则", "昌都", "林芝", "山南", "那曲", "阿里地区",
"西安", "铜川", "宝鸡", "咸阳", "渭南", "延安", "汉中", "榆林", "安康", "商洛",
"兰州", "嘉峪关", "金昌", "白银", "天水", "武威", "张掖", "平凉", "酒泉", "庆阳", "定西", "陇南", "临夏回族自治州", "甘南藏族自治州",
"西宁", "海东", "海北藏族自治州", "黄南藏族自治州", "海南藏族自治州", "果洛藏族自治州", "玉树藏族自治州", "海西蒙古族藏族自治州",
"银川", "石嘴山", "吴忠", "固原", "中卫",
"乌鲁木齐", "克拉玛依", "吐鲁番", "哈密", "昌吉回族自治州", "博尔塔拉蒙古自治州", "巴音郭楞蒙古自治州", "阿克苏地区", "克孜勒苏柯尔克孜自治州", "喀什地区", "和田地区", "伊犁哈萨克自治州", "塔城地区", "阿勒泰地区")
    
    def __init__(self, top_count=20, proxy=None):
        self.top_count = top_count
        self.proxy = proxy
        self.download_dir = Path("downloads")
        self.output_dir = Path("output")
        self.temp_file = Path("txt.tmp")  # 汇总临时文件
        self.speed_log = Path("speed.log")  # 测速日志文件
        self._create_directories()
        
    def _create_directories(self):
        """创建必要的目录"""
        self.download_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
    def download_files(self):
        """下载所有txt文件"""
        print("开始下载直播源文件...")
        if self.proxy:
            print(f"使用代理: {self.proxy}")
        
        def download_single_file(url):
            try:
                # 解析URL生成唯一文件名
                filename = self._generate_unique_filename(url)
                filepath = self.download_dir / filename
                
                # 设置代理
                proxies = {}
                if self.proxy:
                    proxies = {
                        'http': self.proxy,
                        'https': self.proxy
                    }
                
                response = requests.get(url, timeout=30, proxies=proxies, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                response.raise_for_status()
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                    
                print(f"✓ 下载成功: {filename}")
                return filepath
                
            except Exception as e:
                print(f"✗ 下载失败 {url}: {e}")
                return None
        
        # 并发下载
        downloaded_files = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(download_single_file, url) for url in self.URLS]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    downloaded_files.append(result)
        
        print(f"下载完成，共获得 {len(downloaded_files)} 个文件")
        return downloaded_files
    
    def _generate_unique_filename(self, url):
        """根据URL生成唯一的文件名"""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        path_parts = [part for part in parsed.path.split('/') if part]
        
        # 获取原始文件名
        original_filename = path_parts[-1] if path_parts else "unknown.txt"
        
        # 如果没有.txt扩展名，添加它
        if not original_filename.endswith('.txt'):
            original_filename = f"{original_filename}.txt"
        
        # 生成前缀：使用域名和路径
        domain = parsed.netloc.replace('.', '_')
        
        # 如果路径有多个部分，使用倒数第二个作为前缀
        if len(path_parts) > 1:
            prefix = path_parts[-2]  # 使用目录名作为前缀
        else:
            prefix = domain.split('_')[0]  # 使用域名第一部分
        
        # 组合生成唯一文件名
        name_without_ext = original_filename.rsplit('.', 1)[0]
        unique_filename = f"{prefix}_{name_without_ext}.txt"
        
        return unique_filename
    
    def parse_txt_files(self, filepaths):
        """解析txt文件并提取频道信息"""
        print("解析直播源文件...")
        all_channels = []
        all_content = []  # 收集所有文件内容用于合并
        
        for filepath in filepaths:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                all_content.append(f"# 来源文件: {filepath.name}\n{content}\n")
                
                channels = self._parse_content(content)
                all_channels.extend(channels)
                print(f"✓ 解析 {filepath.name}: 获得 {len(channels)} 个频道")
                
            except Exception as e:
                print(f"✗ 解析失败 {filepath}: {e}")
        
        # 生成汇总临时文件
        self._create_merged_temp_file(all_content)
        
        print(f"总共解析出 {len(all_channels)} 个频道")
        return all_channels
    
    def _create_merged_temp_file(self, all_content):
        """创建合并的临时文件"""
        try:
            with open(self.temp_file, 'w', encoding='utf-8') as f:
                f.write("# IPTV直播源汇总临时文件\n")
                f.write(f"# 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.writelines(all_content)
            
            print(f"✓ 汇总临时文件已生成: {self.temp_file}")
            
        except Exception as e:
            print(f"✗ 生成汇总临时文件失败: {e}")
    
    def _parse_content(self, content):
        """解析txt内容提取频道信息"""
        channels = []
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        for line in lines:
            # 跳过分组行
            if line.endswith('#genre#'):
                continue
                
            # 解析频道行：频道名,url或url1#url2#url3
            if ',' in line:
                parts = line.split(',', 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    url_part = parts[1].strip()
                    
                    # 统一频道名称格式：将CCTV-1统一为CCTV1
                    name = self._normalize_channel_name(name)
                    
                    # 处理多个URL用#分隔的情况
                    urls = [url.strip() for url in url_part.split('#') if url.strip()]
                    
                    # 为每个URL创建频道条目
                    for url in urls:
                        if url and url.startswith('http'):
                            channels.append(ChannelInfo(name, url))
        
        return channels
    
    def _normalize_channel_name(self, name):
        """统一频道名称格式"""
        # 将CCTV-1统一为CCTV1，CGTN-英语统一为CGTN英语等
        name = re.sub(r'CCTV-(\d+)', r'CCTV\1', name, flags=re.IGNORECASE)
        name = re.sub(r'CGTN-(\w+)', r'CGTN\1', name, flags=re.IGNORECASE)
        
        # CCTV频道特殊处理：除了CCTV5+，其他CCTV频道去除+、-、空格、*符号
        if re.match(r'CCTV', name, re.IGNORECASE):
            # 保护CCTV5+不被修改
            if not re.match(r'CCTV5\+', name, re.IGNORECASE):
                # 去除+、-、空格、*符号
                name = re.sub(r'[+\-\s*]', '', name)
        
        return name
    
    def test_stream_speed(self, channel: ChannelInfo, timeout=8):
        """测试单个流媒体速度"""
        try:
            # 创建会话，设置更短的超时
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            # 如果是M3U8流，先获取M3U8文件内容
            if channel.url.endswith('.m3u8'):
                return self._test_m3u8_speed(session, channel, timeout)
            else:
                return self._test_direct_stream_speed(session, channel, timeout)
            
        except Exception as e:
            # 可以记录具体错误信息用于调试
            pass
        
        channel.speed = 0.0
        return channel
    
    def _test_m3u8_speed(self, session, channel: ChannelInfo, timeout=8):
        """测试M3U8流媒体速度"""
        try:
            # 1. 获取M3U8文件 - 缩短超时时间
            m3u8_response = session.get(channel.url, timeout=5)
            m3u8_response.raise_for_status()
            m3u8_content = m3u8_response.text
            
            # 2. 解析M3U8文件，提取TS分片URL
            ts_urls = self._extract_ts_urls(m3u8_content, channel.url)
            
            if not ts_urls:
                channel.speed = 0.0
                return channel
            
            # 3. 只测试第一个TS分片的速度，减少测试时间
            ts_url = ts_urls[0]
            start_time = time.time()
            
            try:
                response = session.get(ts_url, stream=True, timeout=5)
                response.raise_for_status()
                
                downloaded_size = 0
                target_size = 2 * 1024 * 1024  # 降低到2MB
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        downloaded_size += len(chunk)
                        
                    # 如果测试时间超过5秒就停止
                    current_time = time.time()
                    if (current_time - start_time) > 5:
                        break
                        
                    # 达到目标大小就停止
                    if downloaded_size >= target_size:
                        break
                
                elapsed_time = time.time() - start_time
                min_size = 256 * 1024  # 最少256KB才计算速度
                
                if elapsed_time > 0 and downloaded_size >= min_size:
                    speed = downloaded_size / elapsed_time / 1024 / 1024  # MB/s
                    channel.speed = round(speed, 2)
                else:
                    channel.speed = 0.0
                    
            except Exception:
                channel.speed = 0.0
                
            return channel
            
        except Exception:
            channel.speed = 0.0
            return channel
    
    def _extract_ts_urls(self, m3u8_content, base_url):
        """从M3U8内容中提取TS文件URL"""
        ts_urls = []
        lines = m3u8_content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # 如果是相对路径，拼接完整URL
                if not line.startswith('http'):
                    from urllib.parse import urljoin
                    ts_url = urljoin(base_url, line)
                else:
                    ts_url = line
                ts_urls.append(ts_url)
        
        return ts_urls
    
    def _test_direct_stream_speed(self, session, channel: ChannelInfo, timeout=8):
        """测试直接流媒体速度"""
        try:
            # 下载前2MB数据计算速度，缩短测试时间
            response = session.get(channel.url, stream=True, timeout=timeout)
            response.raise_for_status()
            
            downloaded_size = 0
            target_size = 2 * 1024 * 1024  # 2MB
            min_size = 256 * 1024  # 最少下载256KB才计算速度
            
            # 记录开始下载数据的时间
            data_start_time = time.time()
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded_size += len(chunk)
                    current_time = time.time()
                    
                    # 如果下载时间超过5秒就停止
                    if (current_time - data_start_time) > 5:
                        break
                        
                    # 达到目标大小就停止
                    if downloaded_size >= target_size:
                        break
            
            # 计算速度
            elapsed_time = time.time() - data_start_time
            if elapsed_time > 0 and downloaded_size >= min_size:
                speed = downloaded_size / elapsed_time / 1024 / 1024  # MB/s
                channel.speed = round(speed, 2)
            else:
                channel.speed = 0.0
                
            return channel
            
        except Exception:
            channel.speed = 0.0
            return channel
    
    def speed_test_channels(self, channels):
        """并发测速所有频道"""
        print(f"开始测速 {len(channels)} 个频道...")
        
        # 初始化测速日志文件
        self._init_speed_log()
        
        def test_single_channel(index, channel):
            import signal
            import threading
            
            result_container = [None]
            exception_container = [None]
            
            def timeout_handler():
                # 超时处理函数
                exception_container[0] = "timeout"
            
            def test_worker():
                try:
                    result_container[0] = self.test_stream_speed(channel, timeout=8)
                except Exception as e:
                    exception_container[0] = str(e)
            
            # 创建测试线程
            test_thread = threading.Thread(target=test_worker)
            test_thread.daemon = True
            test_thread.start()
            
            # 等待最多12秒
            test_thread.join(timeout=12)
            
            if test_thread.is_alive():
                # 线程还在运行，说明超时了
                channel.speed = 0.0
                result = channel
                print(f"[{index+1}/{len(channels)}] {channel.name}: 超时")
            elif exception_container[0]:
                # 发生异常
                channel.speed = 0.0
                result = channel
                print(f"[{index+1}/{len(channels)}] {channel.name}: 测试失败")
            elif result_container[0]:
                # 测试成功
                result = result_container[0]
                if result.speed > 0:
                    print(f"[{index+1}/{len(channels)}] {channel.name}: {result.speed:.2f} MB/s")
                else:
                    print(f"[{index+1}/{len(channels)}] {channel.name}: 测试失败")
            else:
                # 未知情况
                channel.speed = 0.0
                result = channel
                print(f"[{index+1}/{len(channels)}] {channel.name}: 未知错误")
            
            # 写入测速日志
            self._write_speed_log(channel.name, channel.url, result.speed)
            
            return result
        
        tested_channels = []
        
        # 进一步减少并发数，避免网络拥堵和系统资源耗尽
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(test_single_channel, i, channel) 
                      for i, channel in enumerate(channels)]
            
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=15)  # 给future本身也加个超时
                    if result.speed > 0:
                        tested_channels.append(result)
                except Exception as e:
                    print(f"获取测试结果时出错: {e}")
                    continue
        
        print(f"测速完成，有效频道: {len(tested_channels)}")
        print(f"测速日志已保存到: {self.speed_log}")
        return tested_channels
    
    def _init_speed_log(self):
        """初始化测速日志文件"""
        try:
            with open(self.speed_log, 'w', encoding='utf-8') as f:
                f.write("# IPTV频道测速日志\n")
                f.write(f"# 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("# 格式: 频道名称 | 下载速度(MB/s) | 流媒体地址\n\n")
        except Exception as e:
            print(f"✗ 初始化测速日志失败: {e}")
    
    def _write_speed_log(self, channel_name, url, speed):
        """写入测速日志"""
        try:
            with open(self.speed_log, 'a', encoding='utf-8') as f:
                if speed > 0:
                    f.write(f"{channel_name} | {speed:.2f} MB/s | {url}\n")
                else:
                    f.write(f"{channel_name} | 测试失败 | {url}\n")
        except Exception as e:
            print(f"✗ 写入测速日志失败: {e}")
    
    def _select_top_urls_per_channel(self, tested_channels):
        """为每个频道选择速度最快的前N个URL"""
        print(f"为每个频道选择速度最快的前 {self.top_count} 个URL源...")
        
        # 按频道名分组
        channel_groups = {}
        for channel in tested_channels:
            if channel.speed > 0:  # 只考虑测速成功的频道
                if channel.name not in channel_groups:
                    channel_groups[channel.name] = []
                channel_groups[channel.name].append(channel)
        
        # 为每个频道选择前N个最快的URL
        selected_channels = []
        for channel_name, channels in channel_groups.items():
            # 按速度降序排序
            channels.sort(key=lambda x: x.speed, reverse=True)
            
            # 取前N个
            top_channels_for_this_name = channels[:self.top_count]
            selected_channels.extend(top_channels_for_this_name)
            
            # 打印每个频道的保留情况
            if len(channels) > self.top_count:
                print(f"  {channel_name}: 从 {len(channels)} 个源中保留前 {len(top_channels_for_this_name)} 个")
            else:
                print(f"  {channel_name}: 保留全部 {len(top_channels_for_this_name)} 个源")
        
        return selected_channels
    
    def group_channel(self, channel_name):
        """对频道进行分组"""
        name = channel_name.lower()
        
        if "cctv" in name or "cgtn" in name:
            return ChannelGroup.CCTV
        
        if any(key in channel_name for key in self.hkmotw):
            return ChannelGroup.HKMOTW
        
        if any(key in channel_name for key in self.wei_shi):
            return ChannelGroup.WEI_SHI
            
        if any(key in channel_name for key in self.locals):
            return ChannelGroup.LOCAL
            
        if any(key in channel_name for key in self.citys):
            return ChannelGroup.CITY
            
        return ChannelGroup.OTHER
    
    def group_channels(self, channels):
        """将频道按组分类"""
        grouped = {
            ChannelGroup.CCTV: [],
            ChannelGroup.WEI_SHI: [],
            ChannelGroup.LOCAL: [],
            ChannelGroup.HKMOTW: [],
            ChannelGroup.CITY: [],
            ChannelGroup.OTHER: []
        }
        
        for channel in channels:
            group = self.group_channel(channel.name)
            grouped[group].append(channel)
        
        # 在每个分组内，按频道名称和速度排序
        for group_name in grouped:
            # 先按频道名称分组，再在每个频道内按速度排序
            channel_dict = {}
            for channel in grouped[group_name]:
                if channel.name not in channel_dict:
                    channel_dict[channel.name] = []
                channel_dict[channel.name].append(channel)
            
            # 对每个频道内的URL按速度排序（快到慢）
            sorted_channels = []
            
            # CCTV频道特殊排序：按数字大小排序
            if group_name == ChannelGroup.CCTV:
                def cctv_sort_key(channel_name):
                    # 提取CCTV后面的数字
                    match = re.search(r'CCTV(\d+)', channel_name, re.IGNORECASE)
                    if match:
                        return int(match.group(1))
                    # 非数字CCTV频道（如CGTN）排在最后
                    return 999
                
                # 按CCTV数字大小排序
                sorted_channel_names = sorted(channel_dict.keys(), key=cctv_sort_key)
            else:
                # 其他分组按频道名称字母排序
                sorted_channel_names = sorted(channel_dict.keys())
            
            for channel_name in sorted_channel_names:
                channel_urls = channel_dict[channel_name]
                channel_urls.sort(key=lambda x: x.speed, reverse=True)
                sorted_channels.extend(channel_urls)
            
            grouped[group_name] = sorted_channels
        
        return grouped
    
    def generate_m3u_file(self, grouped_channels, output_path):
        """生成M3U格式的播放列表文件"""
        print(f"生成M3U文件: {output_path}")
        
        # 按组的优先级排序
        group_order = [
            ChannelGroup.CCTV,
            ChannelGroup.WEI_SHI, 
            ChannelGroup.HKMOTW,
            ChannelGroup.LOCAL,
            ChannelGroup.CITY,
            ChannelGroup.OTHER
        ]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            
            for group_name in group_order:
                channels = grouped_channels.get(group_name, [])
                if not channels:
                    continue
                
                # 按频道名称合并，显示速度信息
                channel_dict = {}
                for channel in channels:
                    if channel.name not in channel_dict:
                        channel_dict[channel.name] = []
                    channel_dict[channel.name].append(channel)
                
                # CCTV频道特殊排序逻辑
                if group_name == ChannelGroup.CCTV:
                    def cctv_sort_key(channel_name):
                        # 提取CCTV后面的数字
                        match = re.search(r'CCTV(\d+)', channel_name, re.IGNORECASE)
                        if match:
                            return int(match.group(1))
                        # 非数字CCTV频道（如CGTN）排在最后
                        return 999
                    sorted_channel_names = sorted(channel_dict.keys(), key=cctv_sort_key)
                else:
                    sorted_channel_names = sorted(channel_dict.keys())
                
                # 写入每个频道的每个URL（在M3U中分别列出）
                for channel_name in sorted_channel_names:
                    channel_urls = channel_dict[channel_name]
                    # 确保按速度排序（快到慢）
                    channel_urls.sort(key=lambda x: x.speed, reverse=True)
                    
                    for channel in channel_urls:
                        # 统一使用频道名，不添加序号和速度信息
                        f.write(f'#EXTINF:-1 group-title="{group_name}",{channel.name}\n')
                        f.write(f'{channel.url}\n')
        
        print(f"M3U文件已生成，包含以下分组:")
        for group_name in group_order:
            count = len(grouped_channels.get(group_name, []))
            if count > 0:
                print(f"  {group_name}: {count} 个频道源")
    
    def generate_txt_file(self, grouped_channels, output_path):
        """生成TXT格式的播放列表文件"""
        print(f"生成TXT文件: {output_path}")
        
        # 按组的优先级排序
        group_order = [
            ChannelGroup.CCTV,
            ChannelGroup.WEI_SHI,
            ChannelGroup.HKMOTW,
            ChannelGroup.LOCAL, 
            ChannelGroup.CITY,
            ChannelGroup.OTHER
        ]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for group_name in group_order:
                channels = grouped_channels.get(group_name, [])
                if not channels:
                    continue
                    
                f.write(f"{group_name},#genre#\n")
                
                # 按频道名称合并多个URL
                channel_dict = {}
                for channel in channels:
                    if channel.name not in channel_dict:
                        channel_dict[channel.name] = []
                    channel_dict[channel.name].append(channel)
                
                # CCTV频道特殊排序逻辑
                if group_name == ChannelGroup.CCTV:
                    def cctv_sort_key(channel_name):
                        # 提取CCTV后面的数字
                        match = re.search(r'CCTV(\d+)', channel_name, re.IGNORECASE)
                        if match:
                            return int(match.group(1))
                        # 非数字CCTV频道（如CGTN）排在最后
                        return 999
                    sorted_channel_names = sorted(channel_dict.keys(), key=cctv_sort_key)
                else:
                    sorted_channel_names = sorted(channel_dict.keys())
                
                # 写入每个频道（每个URL单独一行）
                for channel_name in sorted_channel_names:
                    channel_urls = channel_dict[channel_name]
                    # 确保按速度排序（快到慢）
                    channel_urls.sort(key=lambda x: x.speed, reverse=True)
                    
                    for channel in channel_urls:
                        f.write(f"{channel.name},{channel.url}\n")
                
                f.write("\n")
    
    def run(self):
        """运行主流程"""
        print("=== IPTV直播源处理工具 ===")
        
        # 1. 下载文件
        downloaded_files = self.download_files()
        if not downloaded_files:
            print("没有成功下载任何文件，程序退出")
            return
            
        # 2. 解析频道
        all_channels = self.parse_txt_files(downloaded_files)
        if not all_channels:
            print("没有解析到任何频道，程序退出")
            return
        
        # 3. 去重（基于频道名和URL）
        unique_channels = []
        seen = set()
        for channel in all_channels:
            key = f"{channel.name}_{channel.url}"
            if key not in seen:
                seen.add(key)
                unique_channels.append(channel)
        
        print(f"去重后剩余 {len(unique_channels)} 个频道")
        
        # 4. 测速
        tested_channels = self.speed_test_channels(unique_channels)
        
        # 5. 按频道名分组，每个频道保留速度最快的前N个URL
        top_channels = self._select_top_urls_per_channel(tested_channels)
        
        print(f"处理后总共保留 {len(top_channels)} 个频道源")
        
        # 6. 重新分组
        grouped_channels = self.group_channels(top_channels)
        
        # 7. 生成输出文件
        m3u_output = self.output_dir / "unicast_result.m3u"
        txt_output = self.output_dir / "unicast_result.txt"
        
        self.generate_m3u_file(grouped_channels, m3u_output)
        self.generate_txt_file(grouped_channels, txt_output)
        
        print("\n=== 处理完成 ===")
        print(f"输出文件:")
        print(f"  M3U格式: {m3u_output}")
        print(f"  TXT格式: {txt_output}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='IPTV直播源下载、合并、测速与分组工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--top', type=int, default=20,
                       help='每个频道最多保留速度最快的前N个URL源 (默认: 20)')
    
    parser.add_argument('--proxy', type=str, default=None,
                       help='代理服务器地址，格式：http://127.0.0.1:10808 (仅用于下载URL列表)')
    
    args = parser.parse_args()
    
    if args.top < 1:
        print("错误: --top 参数必须大于0")
        sys.exit(1)
    
    processor = UnicastProcessor(top_count=args.top, proxy=args.proxy)
    processor.run()


if __name__ == "__main__":
    main()







