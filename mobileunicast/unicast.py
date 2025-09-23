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


def load_env_file(env_path=".env"):
    """加载环境变量文件，支持多行值"""
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用正则表达式解析环境变量，支持多行值
        pattern = r'^([A-Z_][A-Z0-9_]*)=(.*)$'
        lines = content.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line and not line.startswith('#') and '=' in line:
                match = re.match(pattern, line)
                if match:
                    key = match.group(1)
                    value = match.group(2)
                    
                    # 处理引号包围的多行值
                    if value.startswith('"') and not value.endswith('"'):
                        # 多行值，继续读取直到找到结束引号
                        i += 1
                        while i < len(lines):
                            next_line = lines[i]
                            value += '\n' + next_line
                            if next_line.rstrip().endswith('"'):
                                break
                            i += 1
                    
                    # 移除首尾引号
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value
            i += 1


def load_urls_from_env():
    """从环境变量加载URL列表防止有人拿走代码不注明出处不感谢就直接使用"""
    urls_env = os.getenv('IPTV_URLS', '')
    if urls_env:
        # 支持多种分隔符：换行符、逗号、分号
        urls = []
        for url in re.split(r'[,;\n]+', urls_env):
            url = url.strip()
            if url:
                urls.append(url)
        return urls
    return None


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
    
    # 默认URL列表（作为备用）
    DEFAULT_URLS = [
        "https://live.zbds.org/tv/yd.txt",
        "https://chinaiptv.pages.dev/Unicast/anhui/mobile.txt"
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
        
        # 加载环境变量文件
        load_env_file()
        
        # 从环境变量或使用默认URL列表
        env_urls = load_urls_from_env()
        if env_urls:
            self.URLS = env_urls
            print(f"✓ 从环境变量加载了 {len(env_urls)} 个URL")
        else:
            self.URLS = self.DEFAULT_URLS
            print(f"! 未找到环境变量IPTV_URLS，使用默认的 {len(self.DEFAULT_URLS)} 个URL")
            
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
                
                print(f"⏳ 正在下载: {url}")
                response = requests.get(url, timeout=15, proxies=proxies, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                response.raise_for_status()
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                    
                print(f"✓ 下载成功: {filename}")
                return filepath
                
            except requests.exceptions.Timeout:
                print(f"✗ 下载超时: {url}")
                return None
            except requests.exceptions.ConnectionError:
                print(f"✗ 连接失败: {url}")
                return None
            except requests.exceptions.HTTPError as e:
                print(f"✗ HTTP错误 {e.response.status_code}: {url}")
                return None
            except Exception as e:
                print(f"✗ 下载失败 {url}: {e}")
                return None
        
        # 减少并发数量，避免网络拥堵
        downloaded_files = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(download_single_file, url) for url in self.URLS]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    downloaded_files.append(result)
        
        print(f"下载完成，共获得 {len(downloaded_files)} 个文件，失败 {len(self.URLS) - len(downloaded_files)} 个")
        return downloaded_files
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
        # 1. 先转换为大写
        name = name.upper()
        
        # 2. 按顺序删除指定字符和内容
        remove_patterns = [
            r'\s+',  # 空格
            r'-',    # 连字符
            r'\*',   # 星号
            r'频道',
            r'高清测试',
            r'超高清',
            r'高清',
            r'标清',
            r'UD',
            r'超清',
            r'\(试用\)',
            r'\(测试\)',
            r'\(试看\)',
            r'\(576P\)',
            r'\(720P\)',
            r'\(1080P\)',
            r'『',
            r'』',
            r'｜',
            r'\(',
            r'\)',
            r'10M',
            r'12M',
            r'17M',
            r'22M',
            r'1M',
            r'2M',
            r'3M',
            r'7\.5M',
            r'3\.5M',
            r'4M',
            r'5M',
            r'6M',
            r'7M',
            r'8M',
            r'9M',
            r'576',
            r'720',
            r'1920X1080',
            r'1080',
            r'2160',
            r'50P',
            r'HEVC',
            r'HDR',
            r'CHD',
            r'HD',
            r'NEWTV',
            r'SITV',
            r'IHOT',
            r'HOT',
            r'UTV',
            r'NNM',
            r'IPTV',
            r'IPV6'
        ]
        
        for pattern in remove_patterns:
            name = re.sub(pattern, '', name)
        
        # 3. 现有的CCTV和CGTN规则
        # 将CCTV-1统一为CCTV1，CGTN-英语统一为CGTN英语等
        name = re.sub(r'CCTV-?(\d+)', r'CCTV\1', name)
        name = re.sub(r'CGTN-?(\w+)', r'CGTN\1', name)
        
        # CCTV频道特殊处理：除了CCTV5+，其他CCTV频道去除+、-、空格、*符号
        if re.match(r'CCTV', name):
            # 保护CCTV5+不被修改
            if not re.match(r'CCTV5\+', name):
                # 去除+、-、空格、*符号
                name = re.sub(r'[+\-\s*]', '', name)
        
        # 4. 处理CCTV数字后的文字说明
        cctv_replacements = {
            r'CCTV1综合': 'CCTV1',
            r'CCTV2财经': 'CCTV2',
            r'CCTV3综艺': 'CCTV3',
            r'CCTV4中文国际': 'CCTV4',
            r'CCTV5体育': 'CCTV5',
            r'CCTV5\+体育赛事': 'CCTV5+',  # 特殊保留5+
            r'CCTV6电影': 'CCTV6',
            r'CCTV7国防军事': 'CCTV7',
            r'CCTV8电视剧': 'CCTV8',
            r'CCTV9纪录': 'CCTV9',
            r'CCTV9中文': 'CCTV9',
            r'CCTV10科教': 'CCTV10',
            r'CCTV11戏曲': 'CCTV11',
            r'CCTV12社会与法': 'CCTV12',
            r'CCTV13新闻': 'CCTV13',
            r'CCTV14少儿': 'CCTV14',
            r'CCTV少儿': 'CCTV14',
            r'CCTV15音乐': 'CCTV15',
            r'CCTV16奥林匹克': 'CCTV16',
            r'CCTV164K': 'CCTV16',
            r'CCTV4K测试': 'CCTV4K',
            r'CCTV17农业农村': 'CCTV17',
            r'CGTN1': 'CGTN',
            r'CGTN2': 'CGTN纪录',
            r'CGTN记录': 'CGTN纪录',
            r'CGTN西班牙语': 'CGTN西语',
            r'CGTN纪录片': 'CGTN纪录',
            r'CGTN阿拉伯语': 'CGTN阿语',
            r'CGTN俄罗斯语': 'CGTN俄语',
            r'CGTN新闻': 'CGTN',
            r'CGTN英语记录': 'CGTN纪录',
            r'CGTN英语': 'CGTN',
            r'CGTN英文记录': 'CGTN纪录'
        }
        
        for pattern, replacement in cctv_replacements.items():
            name = re.sub(pattern, replacement, name)
        
        return name
    
    def _create_streaming_session(self):
        """创建针对流媒体优化的会话"""
        session = requests.Session()
        
        # 使用VLC播放器的User-Agent，但保持简单的headers
        session.headers.update({
            'User-Agent': 'VLC/3.0.16 LibVLC/3.0.16'
        })
        
        return session

    def test_stream_speed(self, channel: ChannelInfo, timeout=8):
        """测试单个流媒体速度 - 使用VLC User-Agent"""
        # 增加重试机制，某些IPTV源可能需要多次尝试
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                # 创建流媒体优化的会话
                session = self._create_streaming_session()
                
                # 处理带查询参数的URL，如 .m3u8?xxx
                # 修复: 原来使用 endswith('.m3u8') 无法正确识别带查询参数的M3U8 URL
                url_path = channel.url.split('?')[0]  # 去掉查询参数部分
                if url_path.endswith('.m3u8'):
                    result = self._test_m3u8_speed(session, channel, timeout)
                else:
                    result = self._test_direct_stream_speed(session, channel, timeout)
                
                # 如果测试成功（速度 > 0），直接返回结果
                if result.speed > 0:
                    return result
                    
                # 如果是最后一次尝试，返回失败结果
                if attempt == max_retries - 1:
                    return result
                    
            except Exception as e:
                # 记录错误但继续尝试
                if attempt == max_retries - 1:
                    # 最后一次尝试也失败了
                    pass
        
        channel.speed = 0.0
        return channel
    
    def _test_problematic_iptv_server(self, session, channel: ChannelInfo):
        """专门处理有问题的IPTV服务器，使用完整浏览器模拟"""
        
        # 识别ZTE OTT服务器（路径包含030000001000且URL以m3u8?结尾的典型特征）
        is_zte_ott = ('000000' in channel.url and channel.url.endswith('m3u8?'))
        
        if is_zte_ott:
            print(f"  检测到ZTE OTT服务器，尝试特殊处理: {channel.name}")
            
            # 方法1: 完整浏览器模拟
            browser_result = self._browser_simulation_test(channel)
            if browser_result:
                return browser_result
            
            # 方法2: 尝试不同的User-Agent（回退方案）
            user_agents = [
                'VLC/3.0.16 LibVLC/3.0.16',
                'ffmpeg/4.4.0', 
                'curl/8.5.0',
                'Mozilla/5.0 (compatible; IPTV-Player)',
            ]
            
            for ua in user_agents:
                try:
                    test_session = requests.Session()
                    test_session.headers.update({'User-Agent': ua})
                    
                    # 尝试访问
                    response = test_session.get(channel.url, timeout=8, allow_redirects=True)
                    
                    if response.status_code == 200 and response.text.strip().startswith('#EXTM3U'):
                        print(f"  ✓ 使用 {ua} 成功")
                        return self._calculate_speed_from_m3u8(test_session, channel, response.text)
                    
                    # 如果是302重定向，手动处理
                    if response.history:
                        print(f"  发现重定向历史: {[r.url for r in response.history]}")
                        if response.text.strip().startswith('#EXTM3U'):
                            return self._calculate_speed_from_m3u8(test_session, channel, response.text)
                    
                except Exception as e:
                    continue
            
            # 如果所有方法都失败，标记为问题源
            print(f"  ✗ 所有方法都失败，可能是服务器临时不可用")
            
        return None

    def _browser_simulation_test(self, channel: ChannelInfo):
        """完整的浏览器模拟测试，专门处理ZTE OTT服务器"""
        try:
            # 方法1: 使用urllib（ZTE OTT服务器拒绝requests但接受urllib）
            import urllib.request
            import urllib.error
            
            print(f"    🌐 使用urllib模拟浏览器访问...")
            
            # 创建请求
            req = urllib.request.Request(channel.url)
            req.add_header('User-Agent', 'curl/8.5.0')
            req.add_header('Accept', '*/*')
            
            try:
                # 发送请求
                response = urllib.request.urlopen(req, timeout=10)
                
                if response.status == 200:
                    print(f"    ✅ urllib访问成功，状态码: {response.status}")
                    
                    # 读取M3U8内容进行验证
                    content = response.read(500).decode('utf-8', errors='ignore')
                    
                    if '#EXTM3U' in content:
                        print(f"    🎯 确认M3U8格式，开始速度测试...")
                        
                        # 重新打开连接进行速度测试
                        req2 = urllib.request.Request(channel.url)
                        req2.add_header('User-Agent', 'curl/8.5.0')
                        req2.add_header('Accept', '*/*')
                        
                        response2 = urllib.request.urlopen(req2, timeout=10)
                        
                        # 速度测试
                        start_time = time.time()
                        total_size = 0
                        chunk_count = 0
                        
                        while chunk_count < 50:  # 读取更多数据以获得准确速度
                            chunk = response2.read(8192)
                            if not chunk:
                                break
                            total_size += len(chunk)
                            chunk_count += 1
                            
                            # 避免测试时间过长
                            if time.time() - start_time > 8:
                                break
                        
                        end_time = time.time()
                        duration = end_time - start_time
                        response2.close()
                        
                        if total_size > 0 and duration > 0:
                            speed_mbps = (total_size / duration) / (1024 * 1024)
                            channel.speed = round(max(speed_mbps, 0.1), 2)
                            print(f"    🚀 urllib成功，速度: {channel.speed} MB/s")
                            return channel
                    else:
                        print(f"    ❌ 不是有效的M3U8内容")
                        
                response.close()
                        
            except urllib.error.HTTPError as e:
                if e.code == 302:
                    # 处理重定向
                    redirect_url = e.headers.get('Location')
                    if redirect_url:
                        print(f"    📡 检测到302重定向，尝试访问: {redirect_url[:60]}...")
                        
                        req_redirect = urllib.request.Request(redirect_url)
                        req_redirect.add_header('User-Agent', 'curl/8.5.0')
                        req_redirect.add_header('Accept', '*/*')
                        
                        response_redirect = urllib.request.urlopen(req_redirect, timeout=10)
                        
                        if response_redirect.status == 200:
                            content = response_redirect.read(300).decode('utf-8', errors='ignore')
                            if '#EXTM3U' in content:
                                print(f"    ✅ 重定向后成功获取M3U8")
                                # 简化的速度测试
                                channel.speed = 1.0  # 给一个合理的默认速度
                                response_redirect.close()
                                return channel
                        response_redirect.close()
                else:
                    print(f"    ❌ urllib HTTP错误: {e.code}")
            
            # 方法2: 回退到requests的浏览器模拟（用于其他类型服务器）
            print(f"    🔄 urllib失败，尝试requests浏览器模拟...")
            return self._requests_browser_simulation(channel)
            
        except Exception as e:
            print(f"    ❌ 浏览器模拟失败: {str(e)[:50]}")
            
        return None

    def _requests_browser_simulation(self, channel: ChannelInfo):
        """使用requests的浏览器模拟（回退方案）"""
        try:
            browser_session = requests.Session()
            
            browser_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            browser_session.headers.update(browser_headers)
            
            response = browser_session.get(channel.url, timeout=10, allow_redirects=False)
            
            if response.status_code == 302:
                redirect_url = response.headers.get('Location')
                if redirect_url and 'IASHttpSessionId' in redirect_url:
                    final_response = browser_session.get(redirect_url, timeout=10, stream=True)
                    
                    if final_response.status_code == 200:
                        content_sample = ''
                        total_size = 0
                        start_time = time.time()
                        
                        for chunk in final_response.iter_content(chunk_size=8192):
                            if chunk:
                                total_size += len(chunk)
                                if not content_sample:
                                    content_sample = chunk.decode('utf-8', errors='ignore')[:300]
                                    if '#EXTM3U' not in content_sample:
                                        browser_session.close()
                                        return None
                                
                                if total_size >= 100*1024:  # 100KB
                                    break
                        
                        end_time = time.time()
                        duration = end_time - start_time
                        
                        if total_size > 0 and duration > 0:
                            speed_mbps = (total_size / duration) / (1024 * 1024)
                            channel.speed = round(max(speed_mbps, 0.1), 2)
                            browser_session.close()
                            return channel
                            
            elif response.status_code == 200:
                content = response.text[:300]
                if '#EXTM3U' in content:
                    channel.speed = 1.0  # 默认速度
                    browser_session.close()
                    return channel
            
            browser_session.close()
            
        except Exception:
            pass
            
        return None
    
    def _calculate_speed_from_m3u8(self, session, channel: ChannelInfo, m3u8_content):
        """从M3U8内容计算速度"""
        try:
            # 解析M3U8文件，提取TS分片URL
            ts_urls = self._extract_ts_urls(m3u8_content, channel.url)
            
            if not ts_urls:
                channel.speed = 0.0
                return channel
            
            # 测试第一个TS分片的速度
            ts_url = ts_urls[0]
            start_time = time.time()
            
            response = session.get(ts_url, stream=True, timeout=5)
            response.raise_for_status()
            
            downloaded_size = 0
            target_size = 1 * 1024 * 1024  # 1MB
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded_size += len(chunk)
                    
                current_time = time.time()
                if (current_time - start_time) > 4:
                    break
                    
                if downloaded_size >= target_size:
                    break
            
            elapsed_time = time.time() - start_time
            min_size = 128 * 1024  # 最少128KB才计算速度
            
            if elapsed_time > 0 and downloaded_size >= min_size:
                speed = downloaded_size / elapsed_time / 1024 / 1024  # MB/s
                channel.speed = round(speed, 2)
            else:
                channel.speed = 0.0
                
            return channel
            
        except Exception:
            channel.speed = 0.0
            return channel

    def _test_m3u8_speed(self, session, channel: ChannelInfo, timeout=8):
        """测试M3U8流媒体速度 - 支持问题服务器特殊处理"""
        try:
            # 首先检查是否是已知的问题服务器
            special_result = self._test_problematic_iptv_server(session, channel)
            if special_result is not None:
                return special_result
            
            # 标准的M3U8测试流程
            m3u8_response = session.get(channel.url, timeout=5)
            m3u8_response.raise_for_status()
            m3u8_content = m3u8_response.text
            
            # 检查是否是有效的M3U8内容
            if not m3u8_content.strip().startswith('#EXTM3U'):
                channel.speed = 0.0
                return channel
            
            return self._calculate_speed_from_m3u8(session, channel, m3u8_content)
            
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







