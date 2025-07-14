import argparse
import time
import datetime
import concurrent.futures
import requests
import re
import os
import threading
from queue import Queue
import csv
import asyncio
import aiohttp
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
# ===================== 通用工具 =====================
def channel_name_normalize(name):
    name = name.replace("cctv", "CCTV")
    name = name.replace("中央", "CCTV")
    name = name.replace("央视", "CCTV")
    for rep in ["高清", "超高", "HD", "标清", "频道", "-", " ", "PLUS", "＋", "(", ")"]:
        name = name.replace(rep, "" if rep not in ["PLUS", "＋"] else "+")
    name = re.sub(r"CCTV(\d+)台", r"CCTV\1", name)
    name_map = {
        "CCTV1综合": "CCTV1", "CCTV2财经": "CCTV2", "CCTV3综艺": "CCTV3", "CCTV4国际": "CCTV4",
        "CCTV4中文国际": "CCTV4", "CCTV4欧洲": "CCTV4", "CCTV5体育": "CCTV5", "CCTV6电影": "CCTV6",
        "CCTV7军事": "CCTV7", "CCTV7军农": "CCTV7", "CCTV7农业": "CCTV7", "CCTV7国防军事": "CCTV7",
        "CCTV8电视剧": "CCTV8", "CCTV9记录": "CCTV9", "CCTV9纪录": "CCTV9", "CCTV10科教": "CCTV10",
        "CCTV11戏曲": "CCTV11", "CCTV12社会与法": "CCTV12", "CCTV13新闻": "CCTV13", "CCTV新闻": "CCTV13",
        "CCTV14少儿": "CCTV14", "CCTV15音乐": "CCTV15", "CCTV16奥林匹克": "CCTV16",
        "CCTV17农业农村": "CCTV17", "CCTV17农业": "CCTV17", "CCTV5+体育赛视": "CCTV5+",
        "CCTV5+体育赛事": "CCTV5+", "CCTV5+体育": "CCTV5+"
    }
    name = name_map.get(name, name)
    return name

def channel_key(channel_name):
    match = re.search(r'\d+', channel_name)
    if match:
        return int(match.group())
    else:
        return float('inf')

def generate_ip_range_urls(base_url, ip_address, port, suffix=None):
    """生成同一C段的所有IP的URL，确保IP合法"""
    # ip_address 形如 '192.168.1.' 或 '192.168.1.1'，需取前三段
    ip_parts = ip_address.split('.')
    if len(ip_parts) < 3:
        return []
    c_prefix = '.'.join(ip_parts[:3])
    urls = []
    for i in range(1, 256):
        full_ip = f"{c_prefix}.{i}"
        url = f"{base_url}{full_ip}{port}"
        if suffix:
            url += suffix
        urls.append(url)
    return urls

def check_urls_concurrent(urls, timeout=1, max_workers=100, print_valid=True):
    """并发检测URL可用性，返回可用URL列表"""
    valid_urls = []
    def is_url_accessible(url):
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                return url
        except requests.RequestException:
            pass
        return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(is_url_accessible, url) for url in urls]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                valid_urls.append(result)
                if print_valid:
                    print(result)
    return valid_urls

# ===================== 1. jsmpeg模式 =====================
def get_channels_alltv(csv_file):
    urls = set()
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames or 'host' not in fieldnames:
            raise ValueError('CSV文件缺少host列')
        for row in reader:
            host = row['host'].strip()
            if host:
                if host.startswith('http://') or host.startswith('https://'):
                    urls.add(host)
                else:
                    urls.add(f"http://{host}")
    ip_range_urls = []
    for url in urls:
        url = url.strip()
        ip_start_index = url.find("//") + 2
        ip_end_index = url.find(":", ip_start_index)
        ip_dot_start = url.find(".") + 1
        ip_dot_second = url.find(".", ip_dot_start) + 1
        ip_dot_three = url.find(".", ip_dot_second) + 1
        base_url = url[:ip_start_index]
        ip_address = url[ip_start_index:ip_end_index]  # 修正为取 host 部分
        port = url[ip_end_index:]
        ip_range_urls.extend(generate_ip_range_urls(base_url, ip_address, port))
    valid_urls = check_urls_concurrent(set(ip_range_urls))
    channels = []
    for url in valid_urls:
        json_url = url.rstrip('/') + '/streamer/list'
        try:
            response = requests.get(json_url, timeout=1)
            json_data = response.json()
            host = url.rstrip('/')
            for item in json_data:
                name = item.get('name', '').strip()
                key = item.get('key', '').strip()
                if not name or not key:
                    continue
                channel_url = f"{host}/hls/{key}/index.m3u8"
                name = channel_name_normalize(name)
                channels.append((name, channel_url))
        except Exception:
            continue
    return channels

# ===================== 2. txiptv模式（异步） =====================
async def get_channels_newnew(csv_file):
    urls = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        url_set = set()
        for row in reader:
            link = row.get('link', '').strip()
            if link:
                url_set.add(link)
        urls = list(url_set)
    async def modify_urls(url):
        modified_urls = []
        ip_start_index = url.find("//") + 2
        ip_end_index = url.find(":", ip_start_index)
        base_url = url[:ip_start_index]
        ip_address = url[ip_start_index:ip_end_index]
        ip_parts = ip_address.split('.')
        if len(ip_parts) < 3:
            return []
        c_prefix = '.'.join(ip_parts[:3])
        port = url[ip_end_index:]
        ip_end = "/iptv/live/1000.json?key=txiptv"
        for i in range(1, 256):
            full_ip = f"{c_prefix}.{i}"
            modified_url = f"{base_url}{full_ip}{port}{ip_end}"
            modified_urls.append(modified_url)
        return modified_urls
    async def is_url_accessible(session, url, semaphore):
        async with semaphore:
            try:
                async with session.get(url, timeout=1) as response:
                    if response.status == 200:
                        return url
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass
        return None
    async def check_urls(session, urls, semaphore):
        tasks = []
        for url in urls:
            url = url.strip()
            modified_urls = await modify_urls(url)
            for modified_url in modified_urls:
                task = asyncio.create_task(is_url_accessible(session, modified_url, semaphore))
                tasks.append(task)
        results = await asyncio.gather(*tasks)
        valid_urls = [result for result in results if result]
        for url in valid_urls:
            print(url)  # 新增：打印可访问的url
        return valid_urls
    async def fetch_json(session, url, semaphore):
        async with semaphore:
            try:
                ip_start_index = url.find("//") + 2
                ip_dot_start = url.find(".") + 1
                ip_index_second = url.find("/", ip_dot_start)
                base_url = url[:ip_start_index]
                ip_address = url[ip_start_index:ip_index_second]
                url_x = f"{base_url}{ip_address}"
                json_url = f"{url}"
                async with session.get(json_url, timeout=1) as response:
                    json_data = await response.json()
                    channels = []
                    try:
                        for item in json_data['data']:
                            if isinstance(item, dict):
                                name = item.get('name')
                                urlx = item.get('url')
                                if ',' in urlx:
                                    urlx = "aaaaaaaa"
                                if 'http' in urlx:
                                    urld = f"{urlx}"
                                else:
                                    urld = f"{url_x}{urlx}"
                                if name and urlx:
                                    name = channel_name_normalize(name)
                                    channels.append((name, urld))
                    except Exception:
                        pass
                    return channels
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                return []
    x_urls = []
    for url in urls:
        url = url.strip()
        ip_start_index = url.find("//") + 2
        ip_end_index = url.find(":", ip_start_index)
        ip_dot_start = url.find(".") + 1
        ip_dot_second = url.find(".", ip_dot_start) + 1
        ip_dot_three = url.find(".", ip_dot_second) + 1
        base_url = url[:ip_start_index]
        ip_address = url[ip_start_index:ip_dot_three]
        port = url[ip_end_index:]
        ip_end = "1"
        modified_ip = f"{ip_address}{ip_end}"
        x_url = f"{base_url}{modified_ip}{port}"
        x_urls.append(x_url)
    unique_urls = set(x_urls)
    semaphore = asyncio.Semaphore(500)
    async with aiohttp.ClientSession() as session:
        valid_urls = await check_urls(session, unique_urls, semaphore)
        all_channels = []
        tasks = []
        for url in valid_urls:
            task = asyncio.create_task(fetch_json(session, url, semaphore))
            tasks.append(task)
        results = await asyncio.gather(*tasks)
        for sublist in results:
            all_channels.extend(sublist)
    return all_channels

# ===================== 3. zhgxtv模式 =====================
def get_channels_hgxtv(csv_file):
    urls = set()
    with open(csv_file, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            host = row['host'].strip()
            if host:
                if host.startswith('http://') or host.startswith('https://'):
                    url = host
                else:
                    url = f"http://{host}" if ':' in host else f"http://{host}:80"
                urls.add(url)
    ip_range_urls = []
    for url in urls:
        url = url.strip()
        ip_start_index = url.find("//") + 2
        ip_end_index = url.find(":", ip_start_index)
        ip_dot_start = url.find(".") + 1
        ip_dot_second = url.find(".", ip_dot_start) + 1
        ip_dot_three = url.find(".", ip_dot_second) + 1
        base_url = url[:ip_start_index]
        ip_address = url[ip_start_index:ip_end_index]  # 修正为取 host 部分
        port = url[ip_end_index:]
        ip_range_urls.extend(generate_ip_range_urls(base_url, ip_address, port, "/ZHGXTV/Public/json/live_interface.txt"))
    valid_urls = check_urls_concurrent(set(ip_range_urls))
    channels = []
    for url in valid_urls:
        try:
            json_url = f"{url}"
            response = requests.get(json_url, timeout=1)
            json_data = response.content.decode('utf-8')
            try:
                lines = json_data.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        name, channel_url = line.split(',')
                        urls = channel_url.split('/', 3)
                        url_data = json_url.split('/', 3)
                        if len(urls) >= 4:
                            urld = (f"{urls[0]}//{url_data[2]}/{urls[3]}")
                        else:
                            urld = (f"{urls[0]}//{url_data[2]}")
                        name = channel_name_normalize(name)
                        channels.append((name, urld))
            except:
                continue
        except:
            continue
    return channels

# ===================== 通用测速与输出 =====================
def test_speed_and_output(channels, output_prefix="itvlist"):
    task_queue = Queue()
    speed_results = []
    error_channels = []
    def worker():
        while True:
            channel_name, channel_url = task_queue.get()
            try:
                channel_url_t = channel_url.rstrip(channel_url.split('/')[-1])
                lines = requests.get(channel_url, timeout=1).text.strip().split('\n')
                ts_lists = [line.split('/')[-1] for line in lines if not line.startswith('#')]
                ts_lists_0 = ts_lists[0].rstrip(ts_lists[0].split('.ts')[-1])
                ts_url = channel_url_t + ts_lists[0]
                start_time = time.time()
                content = requests.get(ts_url, timeout=5).content
                end_time = time.time()
                response_time = (end_time - start_time) * 1
                if content:
                    with open(ts_lists_0, 'ab') as f:
                        f.write(content)
                    file_size = len(content)
                    download_speed = file_size / response_time / 1024
                    normalized_speed = min(max(download_speed / 1024, 0.001), 100)
                    os.remove(ts_lists_0)
                    result = channel_name, channel_url, f"{normalized_speed:.3f} MB/s"
                    speed_results.append(result)
                    numberx = (len(speed_results) + len(error_channels)) / len(channels) * 100
                    print(f"可用频道：{len(speed_results)} 个 , 不可用频道：{len(error_channels)} 个 , 总频道：{len(channels)} 个 ,总进度：{numberx:.2f} %。")
            except:
                error_channel = channel_name, channel_url
                error_channels.append(error_channel)
                numberx = (len(speed_results) + len(error_channels)) / len(channels) * 100
                print(f"可用频道：{len(speed_results)} 个 , 不可用频道：{len(error_channels)} 个 , 总频道：{len(channels)} 个 ,总进度：{numberx:.2f} %。")
            task_queue.task_done()
    num_threads = 50
    for _ in range(num_threads):
        t = threading.Thread(target=worker, daemon=True)
        t.start()
    for channel in channels:
        task_queue.put(channel)
    task_queue.join()
    # 排序
    speed_results.sort(key=lambda x: (x[0], -float(x[2].split()[0])))
    speed_results.sort(key=lambda x: channel_key(x[0]))
    result_counter = 8
    with open(f"{output_prefix}.txt", 'w', encoding='utf-8') as file:
        channel_counters = {}
        file.write('央视频道,#genre#\n')
        for result in speed_results:
            channel_name, channel_url, speed = result
            if 'CCTV' in channel_name:
                if channel_name in channel_counters:
                    if channel_counters[channel_name] >= result_counter:
                        continue
                    else:
                        file.write(f"{channel_name},{channel_url}\n")
                        channel_counters[channel_name] += 1
                else:
                    file.write(f"{channel_name},{channel_url}\n")
                    channel_counters[channel_name] = 1
        channel_counters = {}
        file.write('卫视频道,#genre#\n')
        for result in speed_results:
            channel_name, channel_url, speed = result
            if '卫视' in channel_name:
                if channel_name in channel_counters:
                    if channel_counters[channel_name] >= result_counter:
                        continue
                    else:
                        file.write(f"{channel_name},{channel_url}\n")
                        channel_counters[channel_name] += 1
                else:
                    file.write(f"{channel_name},{channel_url}\n")
                    channel_counters[channel_name] = 1
        channel_counters = {}
        file.write('其他频道,#genre#\n')
        for result in speed_results:
            channel_name, channel_url, speed = result
            if 'CCTV' not in channel_name and '卫视' not in channel_name and '测试' not in channel_name:
                if channel_name in channel_counters:
                    if channel_counters[channel_name] >= result_counter:
                        continue
                    else:
                        file.write(f"{channel_name},{channel_url}\n")
                        channel_counters[channel_name] += 1
                else:
                    file.write(f"{channel_name},{channel_url}\n")
                    channel_counters[channel_name] = 1
    with open(f"{output_prefix}.m3u", 'w', encoding='utf-8') as file:
        channel_counters = {}
        file.write('#EXTM3U\n')
        for result in speed_results:
            channel_name, channel_url, speed = result
            if 'CCTV' in channel_name:
                if channel_name in channel_counters:
                    if channel_counters[channel_name] >= result_counter:
                        continue
                    else:
                        file.write(f"#EXTINF:-1 group-title=\"央视频道\",{channel_name}\n")
                        file.write(f"{channel_url}\n")
                        channel_counters[channel_name] += 1
                else:
                    file.write(f"#EXTINF:-1 group-title=\"央视频道\",{channel_name}\n")
                    file.write(f"{channel_url}\n")
                    channel_counters[channel_name] = 1
        channel_counters = {}
        for result in speed_results:
            channel_name, channel_url, speed = result
            if '卫视' in channel_name:
                if channel_name in channel_counters:
                    if channel_counters[channel_name] >= result_counter:
                        continue
                    else:
                        file.write(f"#EXTINF:-1 group-title=\"卫视频道\",{channel_name}\n")
                        file.write(f"{channel_url}\n")
                        channel_counters[channel_name] += 1
                else:
                    file.write(f"#EXTINF:-1 group-title=\"卫视频道\",{channel_name}\n")
                    file.write(f"{channel_url}\n")
                    channel_counters[channel_name] = 1
        channel_counters = {}
        for result in speed_results:
            channel_name, channel_url, speed = result
            if 'CCTV' not in channel_name and '卫视' not in channel_name and '测试' not in channel_name:
                if channel_name in channel_counters:
                    if channel_counters[channel_name] >= result_counter:
                        continue
                    else:
                        file.write(f"#EXTINF:-1 group-title=\"其他频道\",{channel_name}\n")
                        file.write(f"{channel_url}\n")
                        channel_counters[channel_name] += 1
                else:
                    file.write(f"#EXTINF:-1 group-title=\"其他频道\",{channel_name}\n")
                    file.write(f"{channel_url}\n")
                    channel_counters[channel_name] = 1
    with open(f"speed.txt", 'w', encoding='utf-8') as speed_file:
        for result in speed_results:
            channel_name, channel_url, speed = result
            speed_file.write(f"{channel_name},{channel_url},{speed}\n")

# ===================== 主入口 =====================
def main():
    parser = argparse.ArgumentParser(description='多模式IPTV频道批量探测与测速')
    parser.add_argument('--jsmpeg', help='jsmpeg-streamer模式csv文件')
    parser.add_argument('--txiptv', help='txiptv模式csv文件')
    parser.add_argument('--zhgxtv', help='zhgxtv模式csv文件')
    parser.add_argument('--output', default='itvlist', help='输出文件前缀')
    args = parser.parse_args()
    channels = []
    if args.jsmpeg:
        channels.extend(get_channels_alltv(args.jsmpeg))
    if args.zhgxtv:
        channels.extend(get_channels_hgxtv(args.zhgxtv))
    if args.txiptv:
        channels.extend(asyncio.run(get_channels_newnew(args.txiptv)))
    if not channels:
        print('请至少指定一个csv文件')
        return
    test_speed_and_output(channels, args.output)

if __name__ == "__main__":
    main()
