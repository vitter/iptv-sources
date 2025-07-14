# IPTV 频道批量探测与测速工具

这是一个功能强大的IPTV频道批量探测、测速和整理工具，支持多种IPTV服务器类型的自动化探测和频道列表生成。

## 功能特点

- **多模式支持**：支持jsmpeg-streamer、txiptv、zhgxtv三种不同的IPTV服务器类型
- **智能IP扫描**：自动扫描同一C段网络中的所有可用IP地址
- **并发测速**：使用多线程和异步技术进行高效的频道可用性检测和网速测试
- **频道标准化**：自动标准化频道名称，特别是CCTV频道的命名规范
- **多格式输出**：生成.txt和.m3u格式的播放列表文件
- **分类整理**：自动将频道分类为央视频道、卫视频道和其他频道

## 支持的IPTV服务器类型

### 1. jsmpeg-streamer 模式
- 对应FOFA搜索指纹：`fid="OBfgOOMpjONAJ/cQ1FpaDQ=="`
- 支持HLS流媒体播放
- 自动获取频道列表API

### 2. txiptv 模式
- 对应FOFA搜索指纹：`fid="7v4hVyd8x6RxODJO2Q5u5Q=="`
- 异步并发处理，支持大规模IP扫描
- JSON API接口解析

### 3. zhgxtv 模式
- 对应FOFA搜索指纹：`fid="IVS0q72nt9BgY+hjPVH+ZQ=="`
- 支持自定义接口格式
- 文本格式频道列表解析

## 安装要求

### Python版本
- Python 3.7+

### 依赖包
```bash
pip install requests aiohttp
```

## 使用方法

### 命令行参数

```bash
python all-z-j-new.py [选项]
```

#### 参数说明

- `--jsmpeg <文件路径>`：指定jsmpeg-streamer模式的CSV文件
- `--txiptv <文件路径>`：指定txiptv模式的CSV文件  
- `--zhgxtv <文件路径>`：指定zhgxtv模式的CSV文件
- `--output <前缀>`：输出文件前缀（默认：itvlist）

### 使用示例

```bash
# 单模式使用
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv

# 多模式组合使用
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv --zhgxtv zhgxtv_hosts.csv

# 自定义输出文件名
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --output my_channels
```

## CSV文件格式

### jsmpeg/zhgxtv模式
CSV文件需包含`host`列：
```csv
host
192.168.1.100:8080
10.0.0.1:9000
example.com:8080
```

### txiptv模式
CSV文件需包含`link`列：
```csv
link
http://192.168.1.100:8080/iptv/live/1000.json?key=txiptv
http://10.0.0.1:9000/iptv/live/1000.json?key=txiptv
```

## 输出文件

运行完成后会生成以下文件：

### 1. `{前缀}.txt`
标准的IPTV播放列表格式：
```
央视频道,#genre#
CCTV1,http://example.com/stream1.m3u8
CCTV2,http://example.com/stream2.m3u8

卫视频道,#genre#
湖南卫视,http://example.com/stream3.m3u8
浙江卫视,http://example.com/stream4.m3u8

其他频道,#genre#
凤凰中文,http://example.com/stream5.m3u8
```

### 2. `{前缀}.m3u`
M3U格式播放列表：
```m3u
#EXTM3U
#EXTINF:-1 group-title="央视频道",CCTV1
http://example.com/stream1.m3u8
#EXTINF:-1 group-title="央视频道",CCTV2
http://example.com/stream2.m3u8
```

### 3. `speed.txt`
详细的测速结果：
```
CCTV1,http://example.com/stream1.m3u8,2.456 MB/s
CCTV2,http://example.com/stream2.m3u8,1.234 MB/s
```

## 频道名称标准化

工具会自动标准化频道名称：

- `cctv` → `CCTV`
- `中央` → `CCTV`  
- `央视` → `CCTV`
- 移除`高清`、`HD`、`标清`等后缀
- `CCTV1综合` → `CCTV1`
- `CCTV5+体育赛事` → `CCTV5+`

## 性能特点

### 并发处理
- **jsmpeg/zhgxtv模式**：最多100个并发线程进行URL可用性检测
- **txiptv模式**：最多500个并发会话进行异步处理
- **测速阶段**：50个工作线程并发测试频道速度

### 智能限制
- 每个频道最多保留8个可用源
- 自动过滤重复频道
- 按网速排序，优先保留高速源

## 网络扫描逻辑

1. **C段扫描**：从输入IP自动推导同一C段网络（如192.168.1.1-254）
2. **端口保持**：保持原始端口号不变
3. **协议适配**：根据不同模式调用相应的API接口
4. **容错处理**：自动处理网络异常和超时情况

## 技术特性

- **异步I/O**：txiptv模式使用aiohttp实现高效异步网络请求
- **多线程**：jsmpeg/zhgxtv模式使用ThreadPoolExecutor并发处理
- **智能重试**：网络请求失败时自动跳过，不影响整体进度
- **内存优化**：流式处理大量数据，避免内存溢出

## 注意事项

1. **网络环境**：建议在网络环境良好的情况下运行
2. **防火墙**：确保目标端口未被防火墙阻止
3. **合法使用**：请确保扫描的IP地址段在合法授权范围内
4. **资源消耗**：大规模扫描会消耗较多网络带宽和CPU资源

## 故障排除

### 常见问题

1. **CSV文件格式错误**
   - 确保CSV文件包含正确的列名（host或link）
   - 检查文件编码是否为UTF-8

2. **网络连接超时**
   - 检查网络连接状态
   - 考虑增加超时时间或减少并发数

3. **无可用频道**
   - 确认输入的IP地址段确实存在IPTV服务
   - 检查端口号是否正确

## 许可证

本项目仅供学习和研究使用，请遵守相关法律法规。

## 更新日志

- 支持三种主流IPTV服务器类型
- 优化了网络扫描和测速算法
- 增强了频道名称标准化功能
- 改进了输出格式和分类逻辑
