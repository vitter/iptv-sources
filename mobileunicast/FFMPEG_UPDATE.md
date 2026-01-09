# 使用 FFmpeg 进行流媒体测速更新

## 更新说明

已将原来复杂的 HTTP 下载测速方式替换为使用 FFmpeg 进行测速，主要优点：

### 优点

1. **更像真实播放器** - FFmpeg 是专业的流媒体处理工具，服务器更难识别为爬虫
2. **统一处理** - 无需区分 M3U8、TS、直播流等不同格式，FFmpeg 统一处理
3. **自动处理重定向** - FFmpeg 内部处理 302/301 重定向
4. **更简洁** - 代码从 500+ 行简化到 100 行左右
5. **更可靠** - 避免被服务器端拒绝（之前的方式可能被认定为非正常播放器）

### 三个限制

按照要求实现了三个关键限制以保证效率：

1. **大小限制** - 最大下载 2MB 数据
2. **超时限制** - 连接/读取超时 8 秒（可配置）
3. **慢速限制** - 即使未达到大小限制，也会在超时时间后停止

## 依赖要求

### Python 依赖

代码使用 Python 标准库，无需额外的 Python 包：
- `subprocess` - 调用 ffmpeg 命令
- `tempfile` - 临时文件管理
- `time` - 时间计算
- `os` - 文件操作

### 系统依赖

**必须**安装 FFmpeg 命令行工具：

### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg
```

### CentOS/RHEL
```bash
sudo yum install epel-release
sudo yum install ffmpeg
```

### macOS
```bash
brew install ffmpeg
```

### Windows
从 [FFmpeg 官网](https://ffmpeg.org/download.html) 下载并添加到 PATH

验证安装：
```bash
ffmpeg -version
```

## 使用方法

使用方式完全不变：

```bash
# 标准模式
python unicast.py --top 20

# 使用代理
python unicast.py --top 20 --proxy http://127.0.0.1:10808

# 快速模式
python unicast.py --top 20 --fast

# 仅搜索不测速
python unicast.py --top 20 --notest
```

## 技术细节

### FFmpeg 命令参数

```bash
ffmpeg \
  -y \                                    # 覆盖输出文件
  -timeout 8000000 \                      # 网络超时 (微秒)
  -user_agent "Mozilla/5.0..." \          # 浏览器标识
  -headers "Accept: */*..." \             # HTTP 头
  -i <URL> \                              # 输入流地址
  -t 8 \                                  # 最大读取时间 (秒)
  -c copy \                               # 直接复制流，不重新编码
  -f mpegts \                             # 输出格式
  output.ts                               # 输出文件
```

### 速度计算

```python
speed_mbps = (文件大小(bytes) / 下载时间(秒)) / (1024 * 1024)
```

## 废弃的方法

以下方法已标记为废弃，但保留在代码中以兼容旧版本：

- `_create_streaming_session()` - 创建 HTTP 会话
- `_follow_redirects_manual()` - 手动处理重定向
- `_test_problematic_iptv_server()` - 特殊服务器处理
- `_browser_simulation_test()` - 浏览器模拟
- `_requests_browser_simulation()` - Requests 浏览器模拟
- `_calculate_speed_from_m3u8()` - M3U8 速度计算
- `_test_m3u8_speed()` - M3U8 测速
- `_extract_ts_urls()` - 提取 TS URL
- `_test_direct_stream_speed()` - 直播流测速

这些方法现在都直接返回默认值，不再执行实际逻辑。

## 测试建议

测试时可以观察：

1. **成功率提升** - 之前失败的源可能现在能测速成功
2. **速度更准确** - 因为模拟真实播放器，服务器不会限速
3. **更快完成** - 超时控制更精确
4. **日志更简洁** - FFmpeg 只输出错误信息

## 故障排查

### 问题：所有频道速度为 0

**原因**：FFmpeg 未安装或不在 PATH 中

**解决**：
```bash
# 检查 FFmpeg
which ffmpeg  # Linux/Mac
where ffmpeg  # Windows

# 如果没有输出，需要安装 FFmpeg
```

### 问题：部分频道失败

**原因**：可能是源本身不可用或需要认证

**解决**：这是正常现象，FFmpeg 也无法处理需要特殊认证的源

### 问题：测速很慢

**原因**：网络延迟或源服务器响应慢

**解决**：可以调整超时参数（默认 8 秒）

## 更新日期

2026年1月9日
