# UDPXY 源生成器

根据 UDPXY 服务自动生成可播放的 IPTV 源文件

## 功能特点

- 🚀 **多线程并发测试** - 支持多线程并行测试组播流，大幅提升测试速度
- 🔍 **智能服务检测** - 自动测试 UDPXY 服务可用性和状态信息
- 📡 **组播源管理** - 从组播源网站下载最新的组播地址列表
- 🌐 **代理网络支持** - 支持HTTP/SOCKS5代理访问网络资源
- 🔄 **智能文件更新** - 检测远程文件变化，仅下载有更新的文件
- ⚡ **高效流测试** - 自动测试组播地址可用性，支持并发测试
- 📋 **多格式输出** - 生成 TXT 和 M3U 格式的 IPTV 源文件
- 🗺️ **地理位置优化** - 根据 IP 归属地优先测试对应省份的组播源
- 🔒 **线程安全输出** - 多线程环境下的安全日志输出
- ⏱️ **超时控制** - 可配置的连接和测试超时时间

## 安装依赖

```bash
# 安装必要的 Python 库
sudo apt install python3-bs4 python3-requests -y

# 或者使用 pip 安装
pip3 install requests beautifulsoup4
```

## 使用方法

### 基本用法

```bash
# 测试 UDPXY 服务并生成 IPTV 源文件
python3 udpxysourcemake.py 10.0.0.1:8098

# 仅测试 UDPXY 服务可用性
python3 udpxysourcemake.py 10.0.0.1:8098 --notest

# 使用代理访问组播源网站
python3 udpxysourcemake.py 10.0.0.1:8098 --proxy http://127.0.0.1:10808

# 强制更新组播文件
python3 udpxysourcemake.py 10.0.0.1:8098 --force-update

# 自定义测试参数和多线程
python3 udpxysourcemake.py 10.0.0.1:8098 --test-count 10 --timeout 3 --max-workers 8

# 快速测试模式（少量测试，多线程）
python3 udpxysourcemake.py 10.0.0.1:8098 --test-count 5 --max-workers 10
```

### 参数说明

- `udpxy_server`: UDPXY 服务器地址，格式为 IP:PORT
- `--notest`: 仅测试 UDPXY 服务可用性，不生成源文件
- `--test-count N`: 每个组播文件测试的地址数量（默认20）
- `--timeout N`: 测试超时时间，秒（默认5）
- `--proxy URL`: 代理服务器地址，格式为 http://host:port
- `--force-update`: 强制更新组播文件，即使本地已存在
- `--max-workers N`: 最大并发线程数（默认5，建议范围3-10）

### 性能优化建议

- **快速测试**：使用 `--test-count 5 --max-workers 8` 进行快速测试
- **全面测试**：使用 `--test-count 20 --max-workers 5` 进行全面测试
- **网络较慢**：使用 `--timeout 10 --max-workers 3` 适应慢速网络
- **资源受限**：使用 `--max-workers 2` 减少资源占用

## 工作流程

1. **测试 UDPXY 服务**
   - 检查端口连通性
   - 验证服务类型
   - 获取服务状态

2. **查询 IP 归属地**（可选）
   - 通过 IP-API 查询 UDPXY 服务器的地理位置
   - 用于优先测试对应省份的组播源

3. **下载组播文件**
   - 从 https://chinaiptv.pages.dev/ 获取组播源列表
   - 智能更新：检测远程文件变化，仅下载有更新的文件
   - 支持代理访问
   - 如果网络不可用，使用本地已有文件

4. **测试组播文件**（多线程并发）
   - 解析组播文件，提取频道信息
   - 优先测试归属地对应的省份文件
   - 使用多线程并发测试每个文件的前 N 个频道
   - 线程安全的输出和状态管理
   - 智能早停机制：找到可用频道后快速结束测试

5. **生成 IPTV 源文件**
   - 基于可用的组播文件生成源文件
   - 生成 TXT 和 M3U 两种格式
   - 文件名包含省份、运营商和 UDPXY 服务器信息

## 输出文件

生成的文件保存在 `generated_sources/` 目录下：

- `{省份}_{运营商}_{IP}_{端口}.txt`: TXT 格式源文件
- `{省份}_{运营商}_{IP}_{端口}.m3u`: M3U 格式源文件

### TXT 格式示例

```
央视,#genre#
CCTV1,http://10.0.0.1:8098/udp/238.1.78.166:7200
CCTV2,http://10.0.0.1:8098/udp/238.1.78.235:7752
...
```

### M3U 格式示例

```
#EXTM3U x-tvg-url="https://live.fanmingming.com/e.xml"
#EXTINF:-1 tvg-name="CCTV1" tvg-logo="https://live.fanmingming.com/tv/CCTV1.png" group-title="央视",CCTV1
http://10.0.0.1:8098/udp/238.1.78.166:7200
#EXTINF:-1 tvg-name="CCTV2" tvg-logo="https://live.fanmingming.com/tv/CCTV2.png" group-title="央视",CCTV2
http://10.0.0.1:8098/udp/238.1.78.235:7752
...
```

## 代理配置

如果需要通过代理访问组播源网站，可以使用 `--proxy` 参数：

```bash
# HTTP 代理
python3 udpxysourcemake.py 10.0.0.1:8098 --proxy http://127.0.0.1:10808

# SOCKS5 代理（需要安装 PySocks）
python3 udpxysourcemake.py 10.0.0.1:8098 --proxy socks5://127.0.0.1:1080
```

## 故障排除

### 1. 网络连接问题

如果遇到网络连接问题：
- 尝试使用代理：`--proxy http://your-proxy:port`
- 使用本地已有的组播文件（程序会自动回退）

### 2. UDPXY 服务测试失败

确保：
- UDPXY 服务正在运行
- 网络连接正常
- 端口没有被防火墙阻止

### 3. 组播测试失败

这是正常现象，因为：
- 组播地址可能仅在特定网络环境下可用
- 需要与对应运营商网络连接
- 程序会尝试多个组播文件直到找到可用的

### 4. 性能问题

如果测试速度慢：
- 增加线程数：`--max-workers 8`
- 减少测试数量：`--test-count 5`
- 减少超时时间：`--timeout 3`

如果资源占用高：
- 减少线程数：`--max-workers 3`
- 增加超时时间：`--timeout 10`

## 技术说明

- 基于 requests 库进行 HTTP 请求
- 使用 BeautifulSoup 解析 HTML 页面
- 支持流式下载测试组播流
- 智能文件更新机制
- 多省份、多运营商组播源支持
- **ThreadPoolExecutor** 实现多线程并发测试
- **threading.Lock** 确保线程安全的日志输出
- **concurrent.futures** 管理异步任务执行
- **智能任务取消** 机制避免不必要的资源消耗

## 更新日志

### v2.0.0 (最新版本)
- ✨ 新增多线程并发测试功能
- ✨ 新增 `--max-workers` 参数控制线程数
- 🔧 优化测试性能，支持并行流测试
- 🔒 实现线程安全的日志输出
- ⚡ 智能早停机制，找到可用流后快速结束
- 📊 详细的测试进度和性能统计

### v1.0.0
- 🎯 基础 UDPXY 服务测试
- 📡 组播源下载和管理
- 🌐 代理支持
- 📋 TXT/M3U 格式输出

## 许可证

本项目基于 MIT 许可证开源。
