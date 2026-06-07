import requests
from concurrent.futures import ThreadPoolExecutor
import time
import json
import subprocess
import os
import re
import argparse
from urllib.parse import quote

# 频道识别模块（YOLO + OCR 混合识别）
try:
    from channel_recognizer import recognize_channel
    HAS_CHANNEL_RECOGNIZER = True
except ImportError:
    HAS_CHANNEL_RECOGNIZER = False
    print("警告: channel_recognizer 模块未找到，将跳过频道识别")

ICON_PREFIX = "https://gcore.jsdelivr.net/gh/taksssss/tv/icon/"

# 超时时间配置（秒）
REQUEST_TIMEOUT = 5      # HTTP 请求超时
PROBE_TIMEOUT = 10       # ffprobe 探测超时
CAPTURE_TIMEOUT = 15     # ffmpeg 截图超时

PLAYLIST_CONTENT_TYPES = {
    "application/vnd.apple.mpegurl",
    "application/x-mpegurl",
    "application/mpegurl",
    "audio/x-mpegurl",
}

try:
    import ffmpeg  # ffmpeg-python
except ImportError:
    ffmpeg = None


def _format_fps(rate_str):
    if not rate_str or rate_str == "0/0":
        return "未知FPS"

    try:
        num, den = rate_str.split("/")
        num = float(num)
        den = float(den)
        if den == 0:
            return "未知FPS"
        fps = num / den
        if abs(fps - round(fps)) < 0.01:
            return f"{int(round(fps))}FPS"
        return f"{fps:.2f}FPS"
    except (ValueError, ZeroDivisionError):
        return "未知FPS"


def _extract_video_meta(probe_data):
    streams = probe_data.get("streams", [])
    for stream in streams:
        if stream.get("codec_type") == "video":
            width = stream.get("width")
            height = stream.get("height")
            fps = _format_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
            if width and height:
                return f"{width}x{height}", fps
            return "未知分辨率", fps
    return "未知分辨率", "未知FPS"


def _safe_filename(text):
    if not text:
        return "screenshot"
    text = text.strip().replace('"', "").replace("'", "")
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", text)
    return text[:120] or "screenshot"


def _normalize_content_type(content_type):
    return (content_type or "").split(";", 1)[0].strip().lower()


def _looks_like_playlist(payload, content_type):
    normalized_type = _normalize_content_type(content_type)
    if normalized_type in PLAYLIST_CONTENT_TYPES or "mpegurl" in normalized_type:
        return True

    if not payload:
        return False

    head = payload.lstrip()
    if not head:
        return False

    if head.startswith(b"#EXTM3U") or b"#EXT-X-" in head[:4096]:
        return True

    try:
        text = head[:4096].decode("utf-8-sig", errors="ignore").lstrip()
    except Exception:
        return False

    return text.startswith("#EXTM3U") or "#EXT-X-" in text


def _looks_like_stream_media(content_type):
    normalized_type = _normalize_content_type(content_type)
    if not normalized_type:
        return False

    return (
        normalized_type.startswith("video/")
        or normalized_type.startswith("audio/")
        or normalized_type in {"application/octet-stream", "application/vnd.apple.mpegurl"}
        or "mpegts" in normalized_type
        or "mp2t" in normalized_type
        or "stream" in normalized_type
    )


def capture_frame(url, image_path):
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            url,
            "-frames:v",
            "1",
            "-vf",
            "scale=960:-1",
            image_path,
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=CAPTURE_TIMEOUT, check=True)
        return True
    except (subprocess.SubprocessError, OSError):
        return False


def probe_stream_info(url):
    # 优先使用 ffmpeg-python 的 probe 接口
    if ffmpeg is not None:
        try:
            probe_data = ffmpeg.probe(url)
            return _extract_video_meta(probe_data)
        except Exception:
            pass

    # 回退到 ffprobe 命令行
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate,r_frame_rate",
            "-of",
            "json",
            url,
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT, check=True)
        probe_data = json.loads(completed.stdout)
        return _extract_video_meta(probe_data)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return "未知分辨率", "未知FPS"


def build_urls(url_pattern, step):
    if step <= 0:
        raise ValueError("步长必须大于0")

    match = re.search(r"\((\d+)-(\d+)\)", url_pattern)
    if not match:
        return [url_pattern]

    start = int(match.group(1))
    end = int(match.group(2))

    real_step = step if start <= end else -step
    stop = end + (1 if real_step > 0 else -1)

    urls = []
    for number in range(start, stop, real_step):
        url = f"{url_pattern[:match.start()]}{number}{url_pattern[match.end():]}"
        urls.append(url)
    return urls


def check_url(url, no_probe=False):
    try:
        with requests.get(url, timeout=REQUEST_TIMEOUT, stream=True) as response:
            if response.status_code != 200:
                print(f"[失败] {url} - 状态码: {response.status_code}")
                return None

            content_type = response.headers.get("Content-Type", "")
            initial_payload = b""
            if not _looks_like_playlist(initial_payload, content_type) and not _looks_like_stream_media(content_type):
                try:
                    initial_payload = next(response.iter_content(chunk_size=4096), b"")
                except requests.RequestException as e:
                    print(f"[错误] {url} - {str(e)}")
                    return None

            is_playlist = _looks_like_playlist(initial_payload, content_type)
            is_stream_media = _looks_like_stream_media(content_type)

            if not is_playlist and not is_stream_media:
                print(f"[失败] {url} - 内容不像 m3u8 或流媒体, Content-Type: {content_type or '未知'}")
                return None

            if no_probe:
                resolution, fps = "未探测", "未探测"
            else:
                resolution, fps = probe_stream_info(url)

            print(f"[成功] {url} - {resolution}_{fps}")
            return {"url": url, "resolution": resolution, "fps": fps}
    except requests.RequestException as e:
        print(f"[错误] {url} - {str(e)}")
        return None


def write_txt(valid_urls, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        for index, item in enumerate(valid_urls, 1):
            display_name = item.get("channel_name", f"频道{index}")
            channel_title = f"{display_name}[{item['resolution']}_{item['fps']}]"
            f.write(f"{channel_title},{item['url']}\n")


def write_m3u(valid_urls, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for index, item in enumerate(valid_urls, 1):
            display_name = item.get("channel_name", f"频道{index}")
            channel_title = f"{display_name}[{item['resolution']}_{item['fps']}]"
            icon_url = f"{ICON_PREFIX}{quote(display_name)}.png"
            f.write(f'#EXTINF:-1 tvg-name="{display_name}" tvg-logo="{icon_url}",{channel_title}\n')
            f.write(f"{item['url']}\n")


def parse_args():
    parser = argparse.ArgumentParser(description="通用m3u8地址扫描工具")
    parser.add_argument(
        "url_pattern",
        nargs="?",
        default="http://example.com/hls/(1-100)/index.m3u8",
        help="URL模板，支持区间格式：(1-100),默认 http://example.com/hls/(1-100)/index.m3u8",
    )
    parser.add_argument("--step", type=int, default=1, help="区间步长，默认1")
    parser.add_argument("--threads", type=int, default=20, help="最大线程数，默认20")
    parser.add_argument("--output", default="playlist.txt", help="输出文件名，可支持.m3u/.m3u8格式，根据扩展名决定输出格式，默认playlist.txt （txt格式）")
    parser.add_argument("--no-probe", action="store_true", help="仅检测URL可访问，跳过分辨率/帧率探测、截图、频道识别，默认False")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.threads <= 0:
        raise ValueError("最大线程数必须大于0")

    target_urls = build_urls(args.url_pattern, args.step)
    start_time = time.time()
    valid_urls = []
    output_base = os.path.splitext(os.path.basename(args.output))[0]
    screenshot_dir = f"{output_base}_screenshots"

    print(f"待扫描地址数量: {len(target_urls)}")
    print(f"线程数: {args.threads}")
    print(f"探测模式: {'仅连通性' if args.no_probe else '完整探测'}")
    print(f"截图目录: {screenshot_dir}")

    # 使用线程池加速请求
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = [executor.submit(check_url, url, args.no_probe) for url in target_urls]
        for future in futures:
            result = future.result()
            if result:
                valid_urls.append(result)

    # 保存截图，文件名使用频道名（仅在完整探测模式下）
    if valid_urls and not args.no_probe:
        os.makedirs(screenshot_dir, exist_ok=True)
        for index, item in enumerate(valid_urls, 1):
            channel_name = f"频道{index}"
            item["channel_name"] = channel_name
            filename = f"{_safe_filename(channel_name)}.jpg"
            image_path = os.path.join(screenshot_dir, filename)
            if capture_frame(item["url"], image_path):
                print(f"[截图] {item['url']} -> {image_path}")
                item["screenshot"] = image_path
                # 频道识别：用 YOLO + OCR 识别台标
                if HAS_CHANNEL_RECOGNIZER:
                    try:
                        channel = recognize_channel(image_path)
                        if channel:
                            item["channel_name"] = channel
                            print(f"  频道识别: {channel}")
                        else:
                            print(f"  频道识别: 未识别出频道")
                    except Exception as e:
                        print(f"  频道识别失败: {e}")
            else:
                print(f"[截图失败] {item['url']}")
                item["screenshot"] = None
    elif valid_urls:
        # 仅连通性模式下设置默认频道名
        for index, item in enumerate(valid_urls, 1):
            item["channel_name"] = f"频道{index}"
            item["screenshot"] = None

    # 打印统计信息
    print("\n检查完成!")
    print(f"总用时: {time.time() - start_time:.2f} 秒")
    print(f"有效地址数量: {len(valid_urls)}")

    # 根据输出文件扩展名决定格式：.m3u/.m3u8 输出m3u，其余输出txt
    if valid_urls:
        output_ext = os.path.splitext(args.output)[1].lower()
        if output_ext in {".m3u", ".m3u8"}:
            write_m3u(valid_urls, args.output)
            print(f"播放列表已保存到 {args.output} (m3u格式)")
        else:
            write_txt(valid_urls, args.output)
            print(f"播放列表已保存到 {args.output} (txt格式)")

if __name__ == "__main__":
    main()
