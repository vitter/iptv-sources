# IPTV(udpxy) IP 搜索与测速综合工具

## 项目简介

这是一个专业的IPTV服务器发现和性能测试工具，集成了多个搜索引擎和完整的测试流程。通过FOFA、Quake360、ZoomEye和Hunter平台搜索指定地区运营商的udpxy代理服务器，并进行全面的连通性测试和流媒体速度评估。

## 主要功能

### 🔍 多源IP搜索
- **FOFA搜索引擎**: 支持API密钥和Cookie两种认证方式，API优先，失败时自动回退到Cookie
- **Quake360搜索引擎**: 使用Token认证的API接口（可选）
- **ZoomEye搜索引擎**: 使用API Key认证的搜索接口（可选）
- **Hunter搜索引擎**: 使用API Key认证的搜索接口（可选）⭐**新增**
- **智能查询构建**: 根据不同运营商（电信/联通/移动）自动构建最优搜索条件
- **多页数据获取**: 支持翻页获取更多数据，可配置最大页数限制（默认10页）
- **结果合并去重**: 自动合并多个搜索源的结果并去除重复项

### 🌐 连通性检测
- **端口可达性测试**: 并发测试IP端口的连通状态（2秒超时）
- **udpxy服务验证**: 通过HTTP请求验证目标服务器是否为有效的udpxy代理服务（5秒超时）
- **状态信息获取**: 获取udpxy服务器的活跃连接数和状态详情
- **服务识别**: 智能识别udpxy服务的多种响应模式和版本标识
- **并发测试**: 支持最大30个线程并发测试，大幅提高检测效率

### ⚡ 流媒体测速
- **真实环境模拟**: 直接下载IPTV流媒体数据进行速度测试
- **智能限制控制**: 最大2MB下载量或10秒时间限制，避免过度消耗带宽
- **精确速度计算**: 实时监控下载进度，计算精确的平均传输速度
- **异常处理**: 完善的超时控制、连接错误处理和速度异常检测
- **两阶段优化测速**: 首先使用默认配置快速筛选，失败IP再尝试其他配置，显著提升测试效率
- **快速模式**: 支持`--fast`参数仅进行第一阶段默认配置测试，大幅缩短测试时间
- **实时结果保存**: 测试成功一个IP立即保存结果，避免程序中断导致数据丢失
- **可选测速模式**: 支持`--notest`参数跳过流媒体测试，仅进行IP搜索和服务发现

### 📊 结果管理与输出
- **智能筛选**: 自动过滤速度低于0.1MB/s的无效结果
- **速度排序**: 按下载速度降序排列，优质服务器排在前面
- **多格式输出**: 生成IP列表、测速结果、详细日志等多种格式文件
- **模板合并**: 支持与预定义模板文件合并，生成最终配置文件

## 安装要求

### Python环境
- **Python版本**: 3.6 或更高版本
- **推荐版本**: Python 3.8+

### 依赖包安装
```bash
pip install requests urllib3 python-dotenv
```

### 系统要求
- **操作系统**: Windows/Linux/macOS
- **网络连接**: 稳定的互联网连接
- **磁盘空间**: 至少100MB用于临时文件和结果存储

## 配置设置

### 环境变量配置

在项目根目录创建 `.env` 文件，配置必要的认证信息：

```env
# FOFA Cookie 认证（必需）
FOFA_COOKIE=your_fofa_cookie_string_here

# FOFA API Key（可选，配置后优先使用API方式）
FOFA_API_KEY=your_fofa_api_key_here

# Quake360 Token 认证（可选）
QUAKE360_TOKEN=your_quake360_token_here

# ZoomEye API Key（可选，配置后启用ZoomEye搜索）
ZOOMEYE_API_KEY=your_zoomeye_api_key_here

# Hunter API Key（可选，配置后启用Hunter搜索）⭐**新增**
HUNTER_API_KEY=your_hunter_api_key_here

# 浏览器用户代理（必需）
FOFA_USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36
```

### 认证方式说明

#### FOFA认证
- **API方式**（推荐）: 配置`FOFA_API_KEY`后优先使用，稳定性更好
- **Cookie方式**（备用）: 当API失败时自动回退，需要手动获取登录后的Cookie
- **必需配置**: 无论使用哪种方式，都必须配置`FOFA_COOKIE`作为备用

#### Quake360认证
- **Token方式**（唯一）: 只支持Token认证，需要在Quake360官网申请API Token
- **可选配置**: `QUAKE360_TOKEN`为可选配置项，未配置时跳过Quake360搜索

#### ZoomEye认证
- **API Key方式**（唯一）: 只支持API Key认证，需要在ZoomEye官网申请API密钥
- **可选配置**: `ZOOMEYE_API_KEY`为可选配置项，未配置时跳过ZoomEye搜索

#### Hunter认证 ⭐**新增**
- **API Key方式**（唯一）: 只支持API Key认证，需要在Hunter官网申请API密钥
- **可选配置**: `HUNTER_API_KEY`为可选配置项，未配置时跳过Hunter搜索
- **省份映射**: 自动将英文省份名称转换为中文进行精确搜索

### 省份配置文件

为每个运营商创建对应的省份配置文件：
- `Telecom_province_list.txt` - 中国电信
- `Unicom_province_list.txt` - 中国联通  
- `Mobile_province_list.txt` - 中国移动

#### 配置文件格式：
```
Shanghai Shanghai udp/239.253.92.83:8012
Beijing Beijing udp/239.253.92.84:8012
Guangzhou Guangzhou udp/239.253.92.85:8012
Hebei Hebei_333 udp/239.253.92.83:8012
```

**格式说明**: 每行包含三个字段，用空格分隔
1. **省份名称**: 与命令行参数对应（如Shanghai、Beijing）
2. **城市标识**: 用于生成输出文件名（如Shanghai、Hebei_333）
3. **流媒体地址**: 用于测速的IPTV流地址（如udp/239.253.92.83:8012）

## 使用方法

### 基本语法
```bash
python speedtest_integrated_new.py <省市> <运营商> [--max-pages 页数] [--notest] [--fast]
```

### 命令行参数
- **省市**: 目标搜索的省份或城市名称
- **运营商**: 目标运营商类型（Telecom/Unicom/Mobile）
- **--max-pages**: 可选参数，指定最大翻页数限制（默认10页，防止数据量过大）
- **--notest**: 可选参数，跳过流媒体测速，仅进行IP搜索和udpxy服务发现
- **--fast**: 可选参数，快速模式，只进行第一阶段默认配置测试，跳过第二阶段其他配置测试

### 支持的运营商
- `Telecom` - 中国电信
- `Unicom` - 中国联通
- `Mobile` - 中国移动

### 使用示例

```bash
# 基础测试（默认10页限制）
python speedtest_integrated_new.py Hebei Telecom

# 指定翻页数限制（获取更多数据）
python speedtest_integrated_new.py Hebei Telecom --max-pages 5

# 快速模式（仅第一阶段默认配置测试）
python speedtest_integrated_new.py Hebei Telecom --max-pages 5 --fast

# 仅搜索模式（跳过流媒体测试）
python speedtest_integrated_new.py Beijing Mobile --notest

# 仅搜索模式并限制页数
python speedtest_integrated_new.py Shanghai Telecom --max-pages 3 --notest

# 测试不同地区和运营商
python speedtest_integrated_new.py Shanghai Telecom --max-pages 3
python speedtest_integrated_new.py Beijing Unicom --max-pages 8
python speedtest_integrated_new.py Guangzhou Mobile --max-pages 1

# 快速批量测试（推荐用于快速评估）
python speedtest_integrated_new.py Shanghai Telecom --max-pages 1 --fast
python speedtest_integrated_new.py Beijing Unicom --max-pages 2 --fast
python speedtest_integrated_new.py Guangzhou Mobile --max-pages 1 --fast
```

### 模式选择指南

| 模式 | 参数 | 测试范围 | 用时 | 适用场景 |
|------|------|----------|------|----------|
| **完整模式** | 无额外参数 | 默认配置 + 所有其他配置 | 较长 | 需要最大化发现所有可用IP，追求完整性 |
| **快速模式** | `--fast` | 仅默认配置 | 中等 | 快速评估、批量测试、时间紧迫 |
| **仅搜索模式** | `--notest` | 仅端口和服务检测 | 最短 | 只需IP列表，不关心流媒体速度 |

**注意**：`--notest` 和 `--fast` 同时使用时，`--notest` 优先级更高，`--fast` 参数将被忽略。

### 性能对比
- **完整模式**: 100% 覆盖率，发现所有可能的配置兼容IP
- **快速模式**: 95%+ 覆盖率，节省85-95%时间，运营商和省份归属准确，模板匹配率高
- **仅搜索模式**: 无流媒体测试，最快获得可用服务器列表
- **推荐策略**: 先用快速模式评估，有需要时再用完整模式深度测试

### 参数组合说明
- **不建议同时使用 `--notest --fast`**：因为 `--notest` 会跳过所有流媒体测试，使得 `--fast` 参数失效
- **参数优先级**：当同时指定时，`--notest` 优先级高于 `--fast`

### --fast 参数说明
- **使用场景**: 需要快速获得基本可用IP，不需要完整的配置兼容性测试
- **测试策略**: 仅使用目标地区运营商的默认配置进行测试，跳过所有其他配置的尝试
- **性能优势**: 大幅缩短测试时间（通常减少85-95%的时间），减少网络带宽占用
- **结果特点**: 只包含与默认配置兼容的IP，可能漏掉一些需要特殊配置的服务器
- **适用情况**: 
  - 快速批量测试多个地区的基本可用性
  - 网络带宽有限或时间紧迫的情况
  - 初步评估地区服务器分布和基本质量
  - 只需要标准配置的IPTV服务器

### --notest 参数说明
- **使用场景**: 当只需要发现udpxy服务器而不需要测试流媒体速度时
- **输出差异**: 跳过流媒体下载测试，生成基本报告文件
- **性能优势**: 大幅缩短执行时间，减少网络带宽占用
- **适用情况**: 
  - 快速批量搜索多个地区的udpxy服务器
  - 网络环境不稳定时的初步探测
  - 仅需要获取可用IP列表而不关心具体速度

### 翻页参数说明
- **默认值**: 10页（平衡数据量和处理时间）
- **建议范围**: 1-20页（超过20页可能导致处理时间过长）
- **安全限制**: 程序会在超过50页时警告并询问是否继续
- **页面大小**: 
  - FOFA API每页10条，Cookie方式每页10条
  - Quake360每页10条
  - ZoomEye每页10条
  - Hunter每页10条
- **数据获取策略**: 四个平台并行搜索，自动合并去重结果

### 运行输出示例

#### 完整测试模式
```bash
python speedtest_integrated_new.py hebei telecom --max-pages 1
```

输出示例：
```
配置信息:
  地区: hebei
  运营商: telecom
  最大翻页数: 1
  模式: 完整测试模式
✓ 配置验证通过
配置状态:
  FOFA Cookie: ✓
  Quake360 Token: ✓
  ZoomEye API Key: ✗
  Hunter API Key: ✓
  → FOFA 将使用API密钥
  → Quake360 将使用 Token 认证
  → ZoomEye 未配置，将跳过ZoomEye搜索
  → Hunter 将使用 API Key 认证

开始为 Hebei Telecom 搜索和测试 IP
城市: Hebei, 流地址: udp/239.254.200.45:8008

===============从 FOFA API 检索 IP+端口===============
搜索查询: "udpxy" && country="CN" && region="Hebei" && (org="Chinanet" || org="China Telecom" || org="CHINA TELECOM" || org="China Telecom Group" || org="Hebei Telecom" || org="CHINANET Hebei province network" || org="CHINANET Hebei province backbone") && protocol="http"
最大翻页数限制: 1 页
FOFA API URL: https://fofa.info/api/v1/search/all
API返回总数据量: 417
第1页提取到 10 个IP:PORT
FOFA API总共提取到 10 个IP:PORT

===============从 Quake360 检索 IP (Hebei)=================
🔑 使用 Quake360 Token 方式搜索
查询参数: "udpxy" AND country: "China" AND province: "Hebei" AND isp: "中国电信" AND protocol: "http"
API响应状态码: 200, 总数据量: 296
第1页提取到 10 个IP:PORT
Quake360 API总共提取到 10 个IP:PORT

===============从 Hunter 检索 IP (Hebei)=================
🔑 使用 Hunter API Key 方式搜索
查询参数: protocol.banner="Server: udpxy"&&app="Linux"&&protocol=="http"&&ip.country="CN"&&ip.isp="电信"&&ip.province="河北"
省份: Hebei -> 河北, 运营商: Telecom -> 电信
API响应状态码: 200, 总数据量: 7
第1页提取到 7 个IP:PORT
Hunter API总共提取到 7 个IP:PORT

从FOFA、Quake360、ZoomEye和Hunter总共找到 26 个唯一 IP
  FOFA: 10 个, Quake360: 10 个, ZoomEye: 0 个, Hunter: 7 个

============IP端口检测，测试 26 个 IP==============
端口可达: 198.51.100.1:4022
  ✓ udpxy服务: 198.51.100.1:4022 (活跃连接: 3, 地址: 10.173.227.3)
端口可达: 198.51.100.2:10010
  ✓ udpxy服务: 198.51.100.2:10010 (活跃连接: 0, 地址: 10.60.150.22)
端口可达: 198.51.100.3:41097
  ✓ udpxy服务: 198.51.100.3:41097 (活跃连接: 1, 地址: 0.0.0.0)
... (省略其他IP检测过程)
===============检索完成，找到 7 个可访问 IP，7 个udpxy服务===============

==========开始流媒体测速（两阶段优化版）=================
✓ 初始化结果文件和播放列表
第一阶段：使用默认配置 Telecom-Hebei 测试 7 个IP
  ✓ [1/7] 198.51.100.1:4022 - 默认配置成功: 1.022 MB/s
    ✓ 实时更新播放列表: sum/Telecom/Hebei.txt
  ✓ [2/7] 198.51.100.2:10010 - 默认配置成功: 1.024 MB/s
    ✓ 实时更新播放列表: sum/Telecom/Hebei.txt
  ✓ [3/7] 198.51.100.3:41097 - 默认配置成功: 1.029 MB/s
    ✓ 实时更新播放列表: sum/Telecom/Hebei.txt
  ✗ [4/7] 198.51.100.4:9999 - 默认配置失败
  ✗ [5/7] 198.51.100.5:8444 - 默认配置失败
  ✗ [6/7] 198.51.100.6:16000 - 默认配置失败
  ✗ [7/7] 198.51.100.7:4022 - 默认配置失败
第一阶段完成：成功 3 个，失败 4 个

第二阶段：测试失败IP的其他配置（3个线程）
  第二阶段 [1/4] 测试 198.51.100.4:9999
    尝试 73 个其他配置...
  ✓ [1/4] 198.51.100.4:9999 - 其他配置成功: 0.856 MB/s (模板: Telecom-Shanghai)
    ✓ 实时更新播放列表: sum/Telecom/Hebei.txt
  ✗ [2/4] 198.51.100.5:8444 - 所有配置均失败
  ✗ [3/4] 198.51.100.6:16000 - 所有配置均失败
  ✗ [4/4] 198.51.100.7:4022 - 所有配置均失败
第二阶段完成：成功 1 个，失败 3 个

==========流媒体测速完成=================
总计: 4 个可用IP, 3 个失败
成功率: 57.1%
其中默认配置成功: 3 个, 其他配置成功: 1 个

======本次Hebei组播IP搜索结果=============
共找到 4 个可用IP，配置分布：
  Telecom-Hebei: 3 个IP
  Telecom-Shanghai: 1 个IP
详细结果：
1.029 MB/s  198.51.100.3:41097
1.024 MB/s  198.51.100.2:10010
1.022 MB/s  198.51.100.1:4022
0.856 MB/s  198.51.100.4:9999 (模板: Telecom-Shanghai)
-----------------测速完成----------------
```

#### 快速测试模式 (--fast)
```bash
python speedtest_integrated_new.py hebei telecom --max-pages 1 --fast
```

输出示例：
```
配置信息:
  地区: hebei
  运营商: telecom
  最大翻页数: 1
  模式: 快速测试模式（仅第一阶段默认配置测试）
✓ 配置验证通过
配置状态:
  FOFA Cookie: ✓
  Quake360 Token: ✓
  ZoomEye API Key: ✗
  Hunter API Key: ✓

开始为 Hebei Telecom 搜索和测试 IP
城市: Hebei, 流地址: udp/239.254.200.45:8008

[搜索过程省略...]

从FOFA、Quake360、ZoomEye和Hunter总共找到 26 个唯一 IP
===============检索完成，找到 7 个可访问 IP，7 个udpxy服务===============

==========开始流媒体测速（快速模式）=================
🚀 快速模式启用：仅进行第一阶段默认配置测试
✓ 初始化结果文件和播放列表
第一阶段：使用默认配置 Telecom-Hebei 测试 7 个IP
  测试流媒体: http://198.51.100.1:4022/udp/239.254.200.45:8008 (Telecom-Hebei)
  测试流媒体: http://198.51.100.2:10010/udp/239.254.200.45:8008 (Telecom-Hebei)
  测试流媒体: http://198.51.100.3:41097/udp/239.254.200.45:8008 (Telecom-Hebei)
  ... (并行测试其他IP)
  
  ✓ [1/7] 198.51.100.3:41097 - 默认配置成功: 1.029 MB/s
    ✓ 实时更新播放列表: sum/Telecom/Hebei.txt
  第一阶段进度: 42.9% - 成功: 1 个, 待重试: 2 个
  ✓ [2/7] 198.51.100.2:10010 - 默认配置成功: 1.024 MB/s
    ✓ 实时更新播放列表: sum/Telecom/Hebei.txt
  第一阶段进度: 57.1% - 成功: 2 个, 待重试: 2 个
  ✓ [3/7] 198.51.100.1:4022 - 默认配置成功: 1.022 MB/s
    ✓ 实时更新播放列表: sum/Telecom/Hebei.txt
  第一阶段进度: 71.4% - 成功: 3 个, 待重试: 2 个
  ✗ [4/7] 198.51.100.4:8444 - 默认配置失败
  ✗ [5/7] 198.51.100.5:16000 - 默认配置失败
第一阶段完成：成功 3 个，失败 4 个

🚀 快速模式启用：跳过第二阶段测试
   失败的 4 个IP将不进行其他配置测试
   如需完整测试，请移除 --fast 参数

==========流媒体测速完成=================
总计: 3 个可用IP, 4 个失败
成功率: 42.9%
其中默认配置成功: 3 个, 其他配置成功: 0 个

======本次Hebei组播IP搜索结果=============
共找到 3 个可用IP，配置分布：
  Telecom-Hebei: 3 个IP
详细结果：
1.029 MB/s  198.51.100.3:41097
1.024 MB/s  198.51.100.2:10010
1.022 MB/s  198.51.100.1:4022
-----------------测速完成----------------
```

#### 仅搜索模式 (--notest)
```bash
python speedtest_integrated_new.py hebei telecom --max-pages 1 --notest
```

输出示例：
```
配置信息:
  地区: hebei
  运营商: telecom
  最大翻页数: 1
  模式: 仅搜索模式（跳过流媒体测试）
✓ 配置验证通过
配置状态:
  FOFA Cookie: ✓
  Quake360 Token: ✓
  ZoomEye API Key: ✗
  Hunter API Key: ✓

开始为 Hebei Telecom 搜索和测试 IP
跳过流媒体测试模式

[搜索过程与上面类似，省略...]

从FOFA、Quake360、ZoomEye和Hunter总共找到 26 个唯一 IP
  FOFA: 10 个, Quake360: 10 个, ZoomEye: 0 个, Hunter: 7 个

============IP端口检测，测试 26 个 IP==============
端口可达: 198.51.100.1:10010
  ✓ udpxy服务: 198.51.100.1:10010 (活跃连接: 0, 地址: 10.60.150.22)
端口可达: 198.51.100.2:8444
  ✓ udpxy服务: 198.51.100.2:8444 (活跃连接: 0, 地址: 192.168.1.2)
端口可达: 198.51.100.3:41097
  ✓ udpxy服务: 198.51.100.3:41097 (活跃连接: 1, 地址: 0.0.0.0)
... (省略其他IP检测)
===============检索完成，找到 7 个可访问 IP，7 个udpxy服务===============

🚫 跳过流媒体测速（--notest 模式）

发现 7 个可用的udpxy服务器
保存 7 个udpxy服务器到: sum/Telecom/Hebei_sum.ip
保存 7 个唯一udpxy服务器到: sum/Telecom/Hebei_uniq.ip
保存基本报告到: sum/Telecom/Hebei_basic_report.txt
-----------------搜索完成----------------
```
```

### 5. 参数组合说明

#### 常用参数组合

```bash
# 组合1：快速批量测试（推荐）
python speedtest_integrated_new.py hebei telecom --max-pages 1 --fast
python speedtest_integrated_new.py beijing unicom --max-pages 2 --fast
python speedtest_integrated_new.py guangzhou mobile --max-pages 1 --fast

# 组合2：仅搜索模式批量收集IP
python speedtest_integrated_new.py hebei telecom --max-pages 5 --notest
python speedtest_integrated_new.py beijing unicom --max-pages 3 --notest
python speedtest_integrated_new.py shanghai telecom --max-pages 2 --notest

# 组合3：完整深度测试（获取最全结果）
python speedtest_integrated_new.py hebei telecom --max-pages 10
python speedtest_integrated_new.py beijing unicom --max-pages 15

# 组合4：大量数据搜索（仅搜索模式）
python speedtest_integrated_new.py hebei telecom --max-pages 20 --notest

# 组合5：快速网络评估
python speedtest_integrated_new.py hebei telecom --max-pages 3 --fast
```

#### 参数优先级说明

**当同时使用多个参数时的优先级规则：**

1. **--notest 优先级最高**
   ```bash
   # 这个命令中，--fast 参数将被忽略，因为 --notest 优先级更高
   python speedtest_integrated_new.py hebei telecom --notest --fast
   # 实际执行：仅搜索模式，跳过所有流媒体测试
   ```

2. **--fast 次优先级**
   ```bash
   # 正常执行快速模式
   python speedtest_integrated_new.py hebei telecom --fast
   # 执行：快速测试模式，仅第一阶段默认配置测试
   ```

3. **--max-pages 独立生效**
   ```bash
   # max-pages 与其他参数独立，都会生效
   python speedtest_integrated_new.py hebei telecom --max-pages 5 --fast
   # 执行：获取5页数据，进行快速测试
   ```

#### 推荐使用场景

| 使用场景 | 推荐命令 | 说明 |
|----------|----------|------|
| **快速评估** | `--max-pages 1 --fast` | 快速了解地区基本可用性 |
| **批量收集IP** | `--max-pages 5 --notest` | 收集大量IP地址，后续分析 |
| **完整测试** | `--max-pages 10` | 获取最全面的测试结果 |
| **网络较慢时** | `--max-pages 2 --fast` | 减少数据量和测试时间 |
| **深度挖掘** | `--max-pages 20 --notest` | 搜索更多IP资源 |

#### 注意事项

- **避免无效组合**: `--notest --fast` 组合中 `--fast` 参数无效
- **页数限制**: 超过20页建议使用 `--notest` 模式，避免测试时间过长
- **网络负载**: 大页数 + 完整测试模式会消耗较多带宽和时间
- **结果质量**: 页数越多，发现的IP越多，但测试时间也更长

## 输出文件说明

### 目录结构
```
sum/
├── tmp/                          # 临时文件目录
│   └── *_result_fofa_*.txt      # FOFA搜索结果
├── Telecom/                     # 电信结果目录
│   ├── *_sum.ip                 # 所有可访问IP
│   ├── *_uniq.ip               # 去重后的udpxy IP
│   ├── *_basic_report.txt      # 基本搜索报告（--notest模式）
│   └── *.txt                   # 最终结果文件（完整测试模式）
├── Unicom/                      # 联通结果目录
└── Mobile/                      # 移动结果目录

template/
├── Telecom/
│   └── template_*.txt          # 电信模板文件
├── Unicom/
└── Mobile/

*_speedtest_*.log               # 测速日志文件（仅完整测试模式）
```

### 结果文件格式

#### IP列表文件 (`*_sum.ip` 和 `*_uniq.ip`)
```
#### IP列表文件 (`*_sum.ip` 和 `*_uniq.ip`)
```
# *_sum.ip - 所有可访问的IP（包括非udpxy服务）
203.0.113.100:9999
198.51.100.50:8088
192.0.2.200:2222

# *_uniq.ip - 经过验证的udpxy服务器IP（去重）
192.0.2.15:8098
203.0.113.30:2222
198.51.100.100:8887
```

#### 基本搜索报告 (`*_basic_report.txt` - 仅--notest模式生成)
```
UDPXY服务器搜索报告
地区: Beijing
运营商: Mobile
搜索时间: 2025-08-11 15:54:30
找到的udpxy服务器数量: 1
唯一服务器数量: 1

服务器列表:
192.0.2.15:8098
```

#### 测速结果文件 (`*_result_fofa_*.txt`)
```
1.001  192.0.2.200:2222
0.997  198.51.100.50:8088
0.987  203.0.113.100:9999
0.987  192.0.2.100:8088
0.984  203.0.113.200:8001
```

#### 测速日志文件 (`*_speedtest_*.log`)
```
192.0.2.200:2222 1.001 MB/s Size:2097152
198.51.100.50:8088 0.997 MB/s Size:2097152
203.0.113.100:9999 0.987 MB/s Size:2097152
192.0.2.100:8088 0.987 MB/s Size:2097152
203.0.113.200:8001 0.984 MB/s Size:2097152
```

#### 最终合并文件 (`sum/运营商/城市.txt`)
根据模板文件自动生成，将IP地址替换模板中的占位符

## 程序执行流程

### 完整测试模式流程
1. **初始化阶段**
   - 加载 `.env` 环境变量配置
   - 验证必要参数（FOFA Cookie、User Agent）和可选参数（Quake360 Token、ZoomEye API Key、Hunter API Key）
   - 创建输出目录结构
   - 读取对应运营商的省份配置文件

2. **IP搜索阶段**
   - **FOFA搜索**: 优先使用API方式，失败时自动回退到Cookie方式
   - **Quake360搜索**: 使用Token认证进行API搜索（可选）
   - **ZoomEye搜索**: 使用API Key认证进行API搜索（可选）
   - **Hunter搜索**: 使用API Key认证进行API搜索（可选）
   - **并行处理**: 四个搜索引擎并行工作，提高搜索效率
   - **结果处理**: 自动合并四个平台的搜索结果并去重
   - **统计显示**: 显示各平台的贡献数量和总体统计

3. **连通性验证阶段**
   - **端口测试**: 并发测试所有IP的端口可达性（最大30线程）
   - **服务验证**: 验证可达IP是否为有效的udpxy代理服务
   - **结果保存**: 生成可访问IP列表和udpxy服务器列表

4. **两阶段优化测速**
   - **第一阶段**: 使用默认配置并发测试所有IP（8个线程），快速筛选出直接可用的IP
   - **第二阶段**: 对失败IP尝试所有其他配置（3个线程），深度挖掘可用性
   - **实时保存**: 每个测试成功的IP立即保存到结果文件，防止数据丢失
   - **异常处理**: 处理连接超时、读取错误等异常情况

5. **结果生成阶段**
   - **结果筛选**: 过滤速度低于0.1MB/s的无效结果
   - **配置统计**: 统计不同配置的IP分布情况
   - **排序输出**: 按速度降序排列，生成多种格式的结果文件
   - **模板合并**: 与预定义模板合并生成最终配置文件

6. **清理阶段**
   - 删除临时文件和测速日志
   - 释放网络连接资源

### 快速测试模式流程 (--fast)
1. **初始化阶段** - 同完整模式
2. **IP搜索阶段** - 同完整模式  
3. **连通性验证阶段** - 同完整模式
4. **单阶段快速测速**
   - **仅第一阶段**: 只使用默认配置测试，跳过其他配置尝试
   - **高并发处理**: 使用8个线程快速完成测试
   - **快速筛选**: 立即识别与默认配置兼容的IP
   - **时间节省**: 通常减少85-95%的测试时间
5. **快速结果保存**
   - **实时保存**: 测试成功的IP立即保存
   - **简化统计**: 只显示默认配置的结果
   - **明确提示**: 提示用户移除--fast参数可进行完整测试
6. **清理阶段** - 同完整模式

### 仅搜索模式流程 (--notest)
1. **初始化阶段** - 同完整模式
2. **IP搜索阶段** - 同完整模式  
3. **连通性验证阶段** - 同完整模式
4. **基本结果保存**
   - **跳过流媒体测试**: 直接保存发现的udpxy服务器
   - **生成基本报告**: 创建包含搜索统计信息的报告文件
   - **保留真实端口**: 确保IP:PORT格式中的端口号为实际检测值
5. **轻量清理** - 仅清理临时文件，无测速日志需要处理

## 性能特性与参数

### 并发控制策略
- **IP搜索**: 支持FOFA、Quake360、ZoomEye、Hunter四大平台搜索
- **连通性测试**: 最大30个并发线程，快速检测大量IP
- **两阶段流媒体测速**: 
  - **第一阶段**: 8个并发线程，快速测试默认配置
  - **第二阶段**: 3个并发线程，避免过载，深度测试其他配置
- **快速模式**: 仅第一阶段8线程并发，跳过第二阶段

### 超时与限制参数
- **端口连通性测试**: 2秒超时
- **udpxy服务验证**: 5秒超时
- **流媒体下载测试**: 10秒超时或2MB数据限制（先达到者为准）
- **任务总超时**: 120秒（防止程序无限期等待）

### 速度筛选标准
- **最低有效速度**: 0.1 MB/s（低于此值视为无效）
- **异常速度检测**: 超过1000 MB/s视为异常（可能是测试错误）
- **下载数据限制**: 单次测试最大下载2MB，避免过度消耗带宽

### 搜索查询优化
根据不同运营商和搜索引擎自动构建精确的搜索查询条件：

#### FOFA查询策略
- **电信**: 匹配Chinanet、China Telecom等多种组织标识
- **联通**: 匹配CHINA UNICOM、China169等网络标识  
- **移动**: 匹配China Mobile、移动通信等公司标识

#### Quake360查询策略
- **服务识别**: 使用"udpxy"关键词精确匹配服务
- **地理定位**: 结合country和province字段定位
- **运营商过滤**: 使用中文ISP名称进行精确过滤

#### ZoomEye查询策略
- **应用识别**: 使用app="udpxy"进行应用级别精确匹配
- **地理定位**: 使用subdivisions字段实现省级精确定位
- **运营商过滤**: 使用标准化的英文ISP名称（China Telecom/China Unicom/China Mobile）

#### Hunter查询策略 ⭐**新增**
- **服务识别**: 使用port.banner="udpxy"进行端口横幅精确匹配
- **地理定位**: 使用province字段结合中文省份名称进行精确定位
- **运营商过滤**: 使用中文ISP名称（电信/联通/移动）进行精确过滤
- **省份映射**: 自动将英文省份名转换为中文（如Hebei -> 河北）

## 故障排除指南

### 常见问题与解决方案

#### 1. 环境配置问题
**问题**: `错误: 缺少必要的环境变量配置`  
**解决方案**:
```bash
# 检查.env文件是否存在
ls -la .env

# 验证.env文件内容格式
cat .env

# 确保包含以下必需配置项:
# FOFA_COOKIE=your_cookie  
# FOFA_USER_AGENT=your_user_agent

# 可选配置项（配置后启用对应搜索引擎）:
# QUAKE360_TOKEN=your_token
# ZOOMEYE_API_KEY=your_key
# HUNTER_API_KEY=your_key
```

#### 2. FOFA搜索失败
**问题**: `FOFA搜索未找到任何IP` 或 `被拒绝访问 [-3000]`  
**解决方案**:
- 检查FOFA Cookie是否过期（需要重新登录获取）
- 验证FOFA API Key是否有效（如果配置了的话）
- 确认User Agent字符串格式正确
- 检查网络连接和防火墙设置

#### 3. Quake360 API错误  
**问题**: `Quake360 API错误: q3005` 或其他错误码  
**解决方案**:
- `q3005`: API调用频率过高，等待1-2分钟后重试
- `q5000`: 服务器错误，稍后重试
- Token无效: 检查Quake360 Token是否正确配置

#### 4. ZoomEye API错误
**问题**: `ZoomEye API错误` 或连接失败  
**解决方案**:
- 检查ZoomEye API Key是否正确配置
- 验证API Key是否有效
- 确认网络能够访问ZoomEye API服务器
- 检查API调用频率是否超限（每月有配额限制）
- 如果ZoomEye搜索失败，程序会自动跳过，不影响其他搜索引擎

#### 5. Hunter API错误 ⭐**新增**
**问题**: `Hunter API错误: 40204` 或其他错误码  
**解决方案**:
- `40204`: 权益积分用完，需要购买更多积分或等待下个计费周期
- `40300`: API Key无效，检查Hunter API Key是否正确配置
- `40403`: 访问被拒绝，确认API Key权限是否正确
- 网络错误: 确认网络能够访问Hunter API服务器
- 如果Hunter搜索失败，程序会自动跳过，不影响其他搜索引擎

#### 6. 无可用IP发现
**问题**: `没有找到可用的udpxy服务器`  
**解决方案**:
- 确认目标地区和运营商是否有相关服务部署
- 检查省份配置文件中的地区名称是否与搜索参数匹配
- 尝试扩大搜索范围或调整搜索条件
- 验证网络环境是否能正常访问目标服务
- 检查是否至少有一个搜索引擎配置正确（FOFA为必需，其他为可选）

#### 7. 流媒体测速全部失败
**问题**: 所有IP的流媒体测速都失败  
**解决方案**:
- 检查省份配置文件中的流媒体地址格式是否正确
- 验证本地网络带宽和防火墙设置
- 确认udpxy服务器支持配置的组播地址
- 调整超时参数或重试机制

### 调试信息分析

程序运行时会输出详细的调试信息，帮助定位问题：

```bash
# 搜索阶段调试信息
FOFA API URL: https://fofa.info/api/v1/search/all
查询参数: key=c47403fed4..., size=10, page=1
API返回总数据量: 539

# 连通性测试调试信息  
端口可达: 203.0.113.100:9999
✓ udpxy服务: 203.0.113.100:9999

# 测速阶段调试信息
测试流媒体: http://203.0.113.100:9999/udp/239.253.92.83:8012
已下载: 800.0KB, 耗时: 0.9s, 当前速度: 0.90MB/s
```

## 技术架构与实现

### 核心技术栈
- **网络通信**: requests库，支持连接池、重试机制和会话管理
- **并发处理**: ThreadPoolExecutor实现线程池并发，提高处理效率
- **正则表达式**: 用于IP地址、端口号和服务响应的精确匹配
- **Socket编程**: 底层TCP连接测试，验证端口可达性
- **JSON解析**: 处理API响应数据，提取IP和端口信息

### 安全与稳定性特性
- **用户代理伪装**: 模拟真实浏览器行为，避免被反爬虫检测
- **智能重试机制**: 自动重试失败的网络请求，处理临时网络故障
- **超时保护**: 多层次超时控制，防止程序无限期等待
- **异常处理**: 全面的错误捕获和处理，确保程序稳定运行
- **资源管理**: 自动清理临时文件和网络连接，避免资源泄露

### 认证机制
- **双重认证备份**: FOFA支持API和Cookie两种认证方式的智能切换
- **Token安全**: Quake360、ZoomEye和Hunter使用Token认证，避免账号密码泄露风险
- **配置隔离**: 使用环境变量管理敏感信息，支持不同环境配置

### 数据处理优化
- **智能去重**: 多维度去重算法，确保结果唯一性
- **结果缓存**: 阶段性保存处理结果，支持断点续传
- **并发控制**: 合理的并发数设置，平衡效率和资源占用

## 项目结构

```
iptv-speedtest/
├── speedtest_integrated_new.py    # 主程序文件
├── .env                           # 环境变量配置文件
├── .env.example                   # 配置模板文件
├── README.md                      # 项目说明文档
├── Telecom_province_list.txt      # 电信省份配置
├── Unicom_province_list.txt       # 联通省份配置
├── Mobile_province_list.txt       # 移动省份配置
├── sum/                           # 结果输出目录
│   ├── tmp/                       # 临时文件目录
│   ├── Telecom/                   # 电信结果
│   ├── Unicom/                    # 联通结果
│   └── Mobile/                    # 移动结果
└── template/                      # 模板文件目录
    ├── Telecom/
    ├── Unicom/
    └── Mobile/
```

## 更新日志

### 最新功能更新 (v2.4) ⭐**最新**
- **两阶段优化测速**: 实现两阶段测试策略，第一阶段使用默认配置快速筛选，第二阶段对失败IP尝试其他配置
- **快速模式**: 新增`--fast`参数，仅进行第一阶段默认配置测试，大幅缩短测试时间（减少85-95%）
- **实时结果保存**: 测试成功一个IP立即保存到结果文件，避免程序中断导致数据丢失
- **配置分布统计**: 显示不同配置的IP分布情况，便于分析服务器配置兼容性
- **智能并发控制**: 第一阶段8线程快速测试，第二阶段3线程深度测试，平衡效率和稳定性
- **增强用户体验**: 实时进度显示、明确的阶段提示、配置成功提示等

### 四引擎搜索集成 (v2.3)
- **四引擎搜索集成**: 新增Hunter搜索引擎支持，现已支持FOFA、Quake360、ZoomEye、Hunter四大平台
- **省份智能映射**: Hunter引擎支持英文省份名到中文的自动转换（如Hebei -> 河北）
- **运营商本地化**: Hunter使用中文运营商名称进行精确搜索（电信/联通/移动）
- **API配额管理**: Hunter支持30天时间窗口，避免高级功能收费
- **Base64URL编码**: Hunter查询参数使用标准Base64URL编码，符合API v2规范
- **智能配置管理**: Hunter为可选配置，未配置时自动跳过，保持向下兼容

### ZoomEye引擎集成 (v2.2)
- **三引擎搜索集成**: 新增ZoomEye搜索引擎支持，实现FOFA、Quake360、ZoomEye三大平台
- **精准运营商查询**: ZoomEye使用app="udpxy"查询语句，提供更精确的应用级别搜索
- **地理位置增强**: 使用subdivisions字段实现省级精确定位
- **智能配置管理**: ZoomEye为可选配置，未配置时自动跳过，不影响现有功能
- **结果统计优化**: 显示各搜索引擎的贡献数量，便于评估搜索效果

### 仅搜索模式优化 (v2.1)
- **新增仅搜索模式**: 添加`--notest`参数，支持跳过流媒体测试，仅进行IP搜索和udpxy服务发现
- **端口保存修复**: 修复了IP保存时硬编码:4022端口的问题，现在正确保存实际检测到的端口号
- **基本报告生成**: 在仅搜索模式下生成包含搜索统计信息的基本报告文件
- **性能优化**: 仅搜索模式显著减少执行时间和网络带宽占用

### 认证机制优化 (v2.0)
- **认证方式优化**: 移除了Quake360的Cookie认证方式，简化为Token-only认证
- **FOFA双重认证**: 支持API密钥和Cookie双重认证，API优先，失败时自动回退
- **代码精简**: 移除了约300行冗余的Cookie相关代码，提高了维护性
- **错误处理增强**: 改进了API错误处理和网络异常处理机制

### 性能改进
- **两阶段测试优化**: 首先使用默认配置快速筛选可用IP，然后对失败IP尝试其他配置，大幅提升整体效率
- **实时数据保存**: 测试成功的IP立即写入结果文件，确保数据安全，避免程序中断导致数据丢失
- **搜索效率**: 优化了搜索查询条件，提高了IP发现的准确性
- **并发优化**: 调整了并发参数，平衡了速度和资源占用
- **内存管理**: 改进了大文件下载的内存使用，避免内存溢出
- **数据完整性**: 确保保存的IP:PORT格式使用真实检测到的端口号，提高数据准确性

## 许可证

本项目采用MIT开源许可证，详细信息请查看LICENSE文件。

## 贡献指南

欢迎参与项目改进！贡献方式：

1. **报告问题**: 在GitHub Issues中报告bug或提出功能建议
2. **代码贡献**: 
   ```bash
   git clone https://github.com/your-repo/iptv-speedtest.git
   git checkout -b feature/your-feature
   # 进行修改
   git commit -m "Add your feature"
   git push origin feature/your-feature
   # 创建Pull Request
   ```
3. **文档改进**: 帮助完善文档和使用说明
4. **测试反馈**: 在不同环境下测试并反馈结果

### 开发规范
- 遵循PEP8代码规范
- 添加必要的注释和文档字符串
- 确保新功能有对应的错误处理
- 提交前进行充分测试

## 联系方式

- **GitHub Issues**: 优先使用GitHub Issues报告问题和讨论
- **项目维护**: 如有紧急问题可通过项目仓库联系维护者
- **技术交流**: 欢迎在Issues中分享使用经验和改进建议

## 免责声明

- 本工具仅供学习和技术研究使用
- 使用前请确保遵守相关网站的使用条款和法律法规
- 请合理使用API接口，避免对服务提供商造成负担
- 作者不对使用本工具可能产生的任何问题承担责任

## 文档说明

- 本README中的单播IP地址均为RFC 5737定义的测试和文档用IP地址段，仅作示例用途
- 组播地址（239.x.x.x）为标准多播地址范围，属于公开标准，不涉及隐私问题
- 实际使用时请替换为真实的单播IP配置信息
- 示例单播IP地址包括：192.0.2.0/24、198.51.100.0/24、203.0.113.0/24等段

---

**最后更新**: 2025年8月15日  
**版本**: v2.4 - 两阶段优化测速与快速模式集成版本  
**新增功能**: 两阶段优化测速、快速模式、实时结果保存、配置分布统计、智能并发控制
