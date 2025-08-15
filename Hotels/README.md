# IPTV 源数据获取与合并工具

这是一个功能强大的IPTV源数据获取与合并工具，支持从多个网络空间搜索引擎中自动收集IPTV服务器信息，并提供全面的数据处理和优化功能。

## 🚀 功能特点

- **四引擎搜索**：集成FOFA、360 Quake、ZoomEye、Hunter四大搜索引擎
- **多模式支持**：支持jsmpeg-streamer、txiptv、zhgxtv三种不同的IPTV服务器类型
- **智能翻页**：自动翻页获取全部搜索结果，支持自定义最大翻页数限制
- **时间过滤**：支持按时间范围搜索最新的IPTV源
- **地理位置过滤**：支持按省份和运营商精确筛选搜索结果
- **智能去重**：自动去除重复的IP地址和同一C段不同端口的重复数据
- **灵活配置**：支持灵活的环境变量配置，至少配置一个搜索引擎即可使用
- **高效率**：支持API并发请求和批量数据处理

## 🔍 搜索引擎支持

### 支持的搜索引擎

| 搜索引擎 | 每页数据量 | 配置方式 | 费用 | 特色功能 |
|---------|-----------|---------|------|--------|
| **FOFA API** | 100条 | API密钥 | 💰 付费 | 高效率，支持时间过滤 |
| **FOFA Web** | 50条 | Cookie | 🆓 免费 | 推荐方式，稳定可靠 |
| **Quake360** | 20条 | API Token | 💰 付费 | 时间过滤需付费账户 |
| **ZoomEye** | 20条 | API密钥 | 💰 付费 | 专业网络空间搜索 |
| **Hunter** | 20条 | API密钥 | 💰 付费 | 鹰图平台搜索引擎 |

### 🔧 环境变量配置

创建 `.env` 文件并配置以下变量（**至少需要配置其中一组**）：

```bash
# ===== FOFA配置 =====
# 选项1: FOFA Cookie方式（推荐，免费）
FOFA_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
FOFA_COOKIE=你的FOFA_Cookie

# 选项2: FOFA API方式（付费）
FOFA_API_KEY=你的FOFA_API密钥

# ===== 其他搜索引擎配置（可选） =====
# Quake360 API（付费）
QUAKE360_TOKEN=你的Quake360_Token

# ZoomEye API（付费）
ZOOMEYE_API_KEY=你的ZoomEye_API密钥

# Hunter API（付费）
HUNTER_API_KEY=你的Hunter_API密钥
```

#### 配置获取方法

1. **FOFA Cookie获取**：
   - 登录 [FOFA网站](https://fofa.info)
   - 按F12打开开发者工具 → Network标签
   - 刷新页面，找到请求头中的Cookie值

2. **API密钥申请**：
   - **FOFA API**: [FOFA API文档](https://fofa.info/api)
   - **Quake360**: [360 Quake平台](https://quake.360.net)
   - **ZoomEye**: [ZoomEye平台](https://www.zoomeye.org)
   - **Hunter**: [鹰图平台](https://hunter.qianxin.com)

## 📋 支持的IPTV服务器类型

### 1. jsmpeg-streamer 模式
- **搜索指纹**: `title="jsmpeg-streamer" && country="CN"`
- **特点**: HLS流媒体播放，实时视频流
- **输出文件**: `jsmpeg_hosts.csv`

### 2. txiptv 模式  
- **搜索指纹**: `body="/iptv/live/zh_cn.js" && country="CN"`
- **特点**: JSON API接口，频道列表丰富
- **输出文件**: `txiptv_hosts.csv`

### 3. zhgxtv 模式
- **搜索指纹**: `body="ZHGXTV" && country="CN"`
- **特点**: 智慧光迅平台，自定义接口格式  
- **输出文件**: `zhgxtv_hosts.csv`

## 🛠 安装依赖

```bash
pip install -r requirements.txt
```

主要依赖包：
- `requests` - HTTP请求库
- `python-dotenv` - 环境变量管理
- `asyncio` - 异步编程支持

## 🚀 使用方法

### makecsv.py - IPTV源数据收集工具

#### 基本用法

```bash
# 收集jsmpeg类型的IPTV源
python makecsv.py --jsmpeg jsmpeg_hosts.csv

# 收集txiptv类型的IPTV源  
python makecsv.py --txiptv txiptv_hosts.csv

# 收集zhgxtv类型的IPTV源
python makecsv.py --zhgxtv zhgxtv_hosts.csv
```

#### 高级用法

```bash
# 使用地区和运营商过滤
python makecsv.py --jsmpeg jsmpeg_hosts.csv --region Hebei --isp Telecom

# 指定时间范围（最近7天）
python makecsv.py --txiptv txiptv_hosts.csv --days 7

# 限制最大翻页数
python makecsv.py --zhgxtv zhgxtv_hosts.csv --max-pages 10

# 组合使用多个筛选条件
python makecsv.py --jsmpeg jsmpeg_hosts.csv --region Beijing --isp Unicom --days 3 --max-pages 5
```

#### 📝 makecsv.py 命令行参数

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--jsmpeg` | string | ❌ | - | jsmpeg模式CSV文件路径 |
| `--txiptv` | string | ❌ | - | txiptv模式CSV文件路径 |
| `--zhgxtv` | string | ❌ | - | zhgxtv模式CSV文件路径 |
| `--region` | string | ❌ | - | 指定省份（如：Hebei, Beijing, Shanghai等） |
| `--isp` | string | ❌ | - | 指定运营商（Telecom/Unicom/Mobile） |
| `--days` | integer | ❌ | 29 | 日期过滤天数 |
| `--max-pages` | integer | ❌ | 无限制 | 限制最大翻页数 |

**注意**：必须指定至少一个模式参数（--jsmpeg、--txiptv、--zhgxtv）

### all-z-j-new.py - IPTV频道探测与测速工具

基于makecsv.py收集的源进行频道探测和测速的工具。

#### 基本用法

```bash
# 单模式探测
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv

# 多模式组合探测
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv --zhgxtv zhgxtv_hosts.csv

# 自定义输出文件前缀
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --output my_channels
```

#### 📝 all-z-j-new.py 命令行参数

| 参数 | 类型 | 必选 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--jsmpeg` | string | ❌ | - | jsmpeg-streamer模式csv文件 |
| `--txiptv` | string | ❌ | - | txiptv模式csv文件 |
| `--zhgxtv` | string | ❌ | - | zhgxtv模式csv文件 |
| `--output` | string | ❌ | itvlist | 输出文件前缀 |

**注意**：必须指定至少一个模式文件（--jsmpeg、--txiptv、--zhgxtv）

### 🔍 地区和运营商支持

#### 支持的地区（英文格式）
Beijing, Tianjin, Hebei, Shanxi, Neimenggu, Liaoning, Jilin, Heilongjiang, Shanghai, Jiangsu, Zhejiang, Anhui, Fujian, Jiangxi, Shandong, Henan, Hubei, Hunan, Guangdong, Guangxi, Hainan, Chongqing, Sichuan, Guizhou, Yunnan, Xizang, Shaanxi, Gansu, Qinghai, Ningxia, Xinjiang

#### 支持的运营商
- **Telecom** - 中国电信
- **Unicom** - 中国联通  
- **Mobile** - 中国移动

## 📋 完整工作流程

### 第一步：配置环境变量
在`.env`文件中配置至少一个搜索引擎的API密钥（推荐FOFA Cookie方式）

### 第二步：收集IPTV源
使用`makecsv.py`从四大搜索引擎收集IPTV服务器信息：

```bash
# 收集河北电信的jsmpeg类型源，最近7天数据，最多10页
python makecsv.py --jsmpeg jsmpeg_hosts.csv --region Hebei --isp Telecom --days 7 --max-pages 10

# 收集北京联通的txiptv类型源
python makecsv.py --txiptv txiptv_hosts.csv --region Beijing --isp Unicom

# 收集上海移动的zhgxtv类型源
python makecsv.py --zhgxtv zhgxtv_hosts.csv --region Shanghai --isp Mobile
```

### 第三步：探测频道并生成播放列表
使用`all-z-j-new.py`基于收集的CSV文件进行频道探测：

```bash
# 基于单个文件进行频道探测
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --output hebei_telecom

# 同时使用多个源文件进行综合探测
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv --zhgxtv zhgxtv_hosts.csv --output multi_source
```

## 📊 CSV文件格式说明

### makecsv.py 输出格式
程序会自动生成包含以下字段的CSV文件：

```csv
host,ip,port,protocol,title,domain,country,city,link,org
192.168.1.100:9003,192.168.1.100,9003,http,,,CN,,http://192.168.1.100:9003,China Telecom
10.0.0.1:9000,10.0.0.1,9000,http,,,CN,,http://10.0.0.1:9000,China Unicom
```

**字段说明**：
- `host`: 主机地址（IP:端口格式）
- `ip`: IP地址
- `port`: 端口号
- `protocol`: 协议（通常为http）
- `title`: 页面标题
- `domain`: 域名
- `country`: 国家代码
- `city`: 城市
- `link`: 完整URL链接
- `org`: 组织/运营商信息

### all-z-j-new.py 输入格式要求

#### jsmpeg/zhgxtv模式
CSV文件需包含`host`列，makecsv.py的输出格式直接兼容：
```csv
host,ip,port,protocol,title,domain,country,city,link,org
192.168.1.100:8080,192.168.1.100,8080,http,,,CN,,http://192.168.1.100:8080,China Telecom
10.0.0.1:9000,10.0.0.1,9000,http,,,CN,,http://10.0.0.1:9000,China Unicom
```

#### txiptv模式
CSV文件需包含`link`列，makecsv.py的输出格式也直接兼容：
```csv
host,ip,port,protocol,title,domain,country,city,link,org
192.168.1.100:8080,192.168.1.100,8080,http,,,CN,,http://192.168.1.100:8080/iptv/live/1000.json?key=txiptv,China Telecom
10.0.0.1:9000,10.0.0.1,9000,http,,,CN,,http://10.0.0.1:9000/iptv/live/1000.json?key=txiptv,China Unicom
```

**注意**：makecsv.py生成的CSV文件可以直接用于all-z-j-new.py，无需格式转换。

## 📄 输出文件说明

### makecsv.py 输出文件
- `jsmpeg_hosts.csv` - jsmpeg服务器列表
- `txiptv_hosts.csv` - txiptv服务器列表
- `zhgxtv_hosts.csv` - zhgxtv服务器列表

### all-z-j-new.py 输出文件
运行完成后会生成以下文件：

#### 1. `{前缀}.txt`
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

#### 2. `{前缀}.m3u`
M3U格式播放列表：
```m3u
#EXTM3U
#EXTINF:-1 group-title="央视频道",CCTV1
http://example.com/stream1.m3u8
#EXTINF:-1 group-title="央视频道",CCTV2
http://example.com/stream2.m3u8
```

#### 3. `speed.txt`
详细的测速结果：
```
CCTV1,http://example.com/stream1.m3u8,2.456 MB/s
CCTV2,http://example.com/stream2.m3u8,1.234 MB/s
```

## ⚙️ 配置说明

### 灵活配置系统

程序采用灵活的配置系统，**不再要求配置所有搜索引擎**：

- ✅ **至少配置一个搜索引擎**即可正常使用
- ✅ 推荐使用FOFA Cookie方式（免费且稳定）
- ✅ 可以根据需要选择配置付费API
- ✅ 程序会自动跳过未配置的搜索引擎

### 时间过滤说明

- **免费用户**：部分搜索引擎的时间过滤功能受限
- **付费用户**：可完整使用所有时间过滤功能
- **Quake360**：时间过滤需要付费账户支持

### 翻页控制功能

使用 `--max-pages` 参数可以：
- 🚀 **提高效率**：限制搜索深度，快速获取热门结果
- 💰 **节省配额**：避免消耗过多API调用次数
- ⏱️ **节省时间**：在大量结果时快速完成搜索

## 🎯 使用示例

### makecsv.py 使用示例

#### 示例1：快速收集jsmpeg源
```bash
# 收集jsmpeg类型的IPTV源
python makecsv.py --jsmpeg jsmpeg_hosts.csv
```

#### 示例2：指定地区收集
```bash
# 收集河北省的txiptv源
python makecsv.py --txiptv txiptv_hosts.csv --region Hebei
```

#### 示例3：运营商筛选
```bash
# 收集电信运营商的zhgxtv源
python makecsv.py --zhgxtv zhgxtv_hosts.csv --isp Telecom
```

#### 示例4：时间过滤
```bash
# 收集最近3天的jsmpeg源
python makecsv.py --jsmpeg jsmpeg_hosts.csv --days 3
```

#### 示例5：限制翻页数
```bash
# 最多翻页10页，快速获取热门结果
python makecsv.py --txiptv txiptv_hosts.csv --max-pages 10
```

#### 示例6：组合条件搜索
```bash
# 收集北京联通最近7天的数据，最多5页
python makecsv.py --zhgxtv zhgxtv_hosts.csv --region Beijing --isp Unicom --days 7 --max-pages 5
```

### all-z-j-new.py 使用示例

#### 示例1：单文件频道探测
```bash
# 基于jsmpeg源文件进行频道探测
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv
```

#### 示例2：多文件综合探测
```bash
# 同时使用多个源文件进行综合频道探测
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv --zhgxtv zhgxtv_hosts.csv
```

#### 示例3：自定义输出文件名
```bash
# 使用自定义输出文件前缀
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --output my_channels
```

## 🔧 工具详细说明

### makecsv.py - 四引擎IPTV源收集工具

这是主要的数据收集工具，基于四大搜索引擎的IPTV源自动收集系统。

#### 主要特性
- **四引擎并行搜索**：同时使用FOFA、360 Quake、ZoomEye、Hunter四个搜索引擎
- **智能翻页系统**：自动翻页获取全部搜索结果，支持最大翻页数限制
- **智能去重**：自动去除重复的IP地址和端口
- **地区运营商过滤**：支持按省份和运营商精确筛选
- **时间范围控制**：支持指定搜索的时间范围
- **多种服务器类型**：支持jsmpeg、txiptv、zhgxtv三种IPTV服务器类型
- **灵活配置**：支持至少配置一个搜索引擎即可使用

#### 数据处理功能
- **智能去重**：自动移除重复的IP地址
- **同网段优化**：移除同一C段中不同端口的重复主机
- **数据验证**：确保IP地址和端口格式正确
- **统计报告**：显示每个搜索引擎的结果数量

### all-z-j-new.py - IPTV频道探测与测速工具

基于makecsv.py收集的源进行频道探测和测速的专业工具。

#### 主要功能
- **智能IP扫描**：自动扫描同一C段网络中的所有可用IP地址
- **并发测速**：使用多线程和异步技术进行高效的频道可用性检测和网速测试
- **频道标准化**：自动标准化频道名称，特别是CCTV频道的命名规范
- **多格式输出**：生成.txt和.m3u格式的播放列表文件
- **分类整理**：自动将频道分类为央视频道、卫视频道和其他频道
- **智能去重**：自动去除重复的IPTV源，提高数据质量

#### 频道名称标准化规则
工具会自动标准化频道名称：
- `cctv` → `CCTV`
- `中央` → `CCTV`  
- `央视` → `CCTV`
- 移除`高清`、`HD`、`标清`等后缀
- `CCTV1综合` → `CCTV1`
- `CCTV5+体育赛事` → `CCTV5+`

#### 性能特点
- **并发处理**：
  - jsmpeg/zhgxtv模式：最多100个并发线程进行URL可用性检测
  - txiptv模式：最多500个并发会话进行异步处理
  - 测速阶段：50个工作线程并发测试频道速度
- **智能限制**：
  - 每个频道最多保留8个可用源
  - 自动过滤重复频道
  - 按网速排序，优先保留高速源

#### 网络扫描逻辑
1. **C段扫描**：从输入IP自动推导同一C段网络（如192.168.1.1-254）
2. **端口保持**：保持原始端口号不变
3. **协议适配**：根据不同模式调用相应的API接口
4. **容错处理**：自动处理网络异常和超时情况

## 💡 最佳实践

### 1. 快速开始（推荐FOFA Cookie方式）
```bash
# 1. 配置FOFA Cookie（免费）
echo 'FOFA_COOKIE=你的cookie值' > .env

# 2. 快速收集jsmpeg源，限制翻页数
python makecsv.py --jsmpeg jsmpeg_hosts.csv --max-pages 5

# 3. 基于收集的源进行频道探测
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv
```

### 2. 精确搜索工作流程
```bash
# 第一步：收集特定地区和运营商的源
python makecsv.py --txiptv txiptv_hosts.csv --region Hebei --isp Telecom --max-pages 10

# 第二步：进行频道探测和测速
python all-z-j-new.py --txiptv txiptv_hosts.csv --output hebei_telecom
```

### 3. 多源综合探测
```bash
# 第一步：分别收集三种类型的源
python makecsv.py --jsmpeg jsmpeg_hosts.csv --region Shanghai --days 7
python makecsv.py --txiptv txiptv_hosts.csv --region Shanghai --days 7  
python makecsv.py --zhgxtv zhgxtv_hosts.csv --region Shanghai --days 7

# 第二步：使用所有源进行综合频道探测
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv --zhgxtv zhgxtv_hosts.csv --output shanghai_multi
```

### 4. 时间优化搜索策略
```bash
# 只搜索最近3天的新数据，提高结果的时效性
python makecsv.py --jsmpeg jsmpeg_hosts.csv --days 3 --max-pages 8
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --output recent_sources
```

## ⚠️ 注意事项

1. **合法使用**：请确保在合法授权范围内使用本工具
2. **API配额**：付费API有调用次数限制，建议使用max-pages控制消耗
3. **网络环境**：建议在网络环境良好的情况下运行
4. **数据时效性**：IPTV源具有时效性，建议定期更新数据

## 🔍 故障排除

### 常见问题

1. **配置错误**
   - 确保.env文件格式正确
   - 至少配置一个搜索引擎

2. **API调用失败**
   - 检查API密钥是否正确
   - 确认API配额是否充足

3. **无搜索结果**
   - 尝试调整搜索条件
   - 检查网络连接状态

## 📈 性能特点

- **高效并发**：支持多引擎并行搜索
- **智能限制**：自动控制请求频率避免被限制
- **内存优化**：流式处理大量数据
- **容错处理**：自动处理网络异常和超时

## 📄 许可证

本项目仅供学习和研究使用，请遵守相关法律法规。

## 🔄 更新日志

### 最新版本特性
- ✅ 支持自定义最大翻页数限制（--max-pages参数）
- ✅ 优化Quake360 API调用和时间过滤功能
- ✅ 改进配置系统，支持灵活配置（至少一个搜索引擎）
- ✅ 增强错误处理和API速率限制管理
- ✅ 更新页面大小配置：Quake360改为20条/页
- ✅ 完善时间过滤系统，支持各引擎特有的时间参数格式
