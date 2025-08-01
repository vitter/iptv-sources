# IPTV(udpxy) IP 搜索与测速综合工具

## 项目简介

这是一个专业的IPTV服务器发现和性能测试工具，集成了多个搜索引擎和完整的测试流程。通过FOFA和Quake360平台搜索指定地区运营商的udpxy代理服务器，并进行全面的连通性测试和流媒体速度评估。

## 主要功能

### 🔍 多源IP搜索
- **FOFA搜索引擎**: 支持API密钥和Cookie两种认证方式，API优先，失败时自动回退到Cookie
- **Quake360搜索引擎**: 使用Token认证的API接口
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
# Quake360 Token 认证（必需）
QUAKE360_TOKEN=your_quake360_token_here

# FOFA Cookie 认证（必需）
FOFA_COOKIE=your_fofa_cookie_string_here

# FOFA API Key（可选，配置后优先使用API方式）
FOFA_API_KEY=your_fofa_api_key_here

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
- **必需配置**: `QUAKE360_TOKEN`为必需配置项

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
python speedtest_integrated_new.py <省市> <运营商> [--max-pages 页数]
```

### 命令行参数
- **省市**: 目标搜索的省份或城市名称
- **运营商**: 目标运营商类型（Telecom/Unicom/Mobile）
- **--max-pages**: 可选参数，指定最大翻页数限制（默认10页，防止数据量过大）

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

# 测试不同地区和运营商
python speedtest_integrated_new.py Shanghai Telecom --max-pages 3
python speedtest_integrated_new.py Beijing Unicom --max-pages 8
python speedtest_integrated_new.py Guangzhou Mobile --max-pages 1
```

### 翻页参数说明
- **默认值**: 10页（平衡数据量和处理时间）
- **建议范围**: 1-20页（超过20页可能导致处理时间过长）
- **安全限制**: 程序会在超过50页时警告并询问是否继续
- **页面大小**: FOFA API每页10条，Cookie方式每页10条，Quake360每页10条

### 运行输出示例

```
配置信息:
  地区: hebei
  运营商: telecom
  最大翻页数: 3

✓ 配置验证通过
配置状态:
  FOFA Cookie: ✓
  Quake360 Token: ✓
  → FOFA 将使用Cookie认证
  → Quake360 将使用 Token 认证

开始为 Hebei Telecom 搜索和测试 IP
城市: Hebei, 流地址: udp/239.254.200.45:8008

===============从 FOFA 检索 IP+端口 (使用Cookie认证)===============
搜索查询: "udpxy" && country="CN" && region="Hebei" && ...
最大翻页数限制: 3 页
发送第一次请求获取总数据量...
从连续赋值提取到总数: 503 (变量: aC)
从变量提取到页面大小: 10 (模式: aC\.size\s*=\s*(\d+))
总数据量: 503
总页数: 51, 实际获取页数: 3
第1页提取到 60 个IP
正在获取第 2/3 页数据...
第2页提取到 45 个IP
正在获取第 3/3 页数据...
第3页提取到 38 个IP
FOFA Cookie总共提取到 143 个IP:PORT
去重后共 10 个唯一IP

===============从 Quake360 检索 IP (Hebei)=================
🔑 使用 Quake360 Token 方式搜索
--- Quake360 API 搜索 ---
Quake360 API错误: q5000 - 内部服务器发生错误
  这是Quake360服务器内部错误，可能是临时问题，建议稍后重试

从FOFA和Quake360总共找到 10 个唯一 IP
============IP端口检测，测试 10 个 IP==============
端口可达: 111.224.100.146:8444
  ✓ udpxy服务: 111.224.100.146:8444 (活跃连接: 0, 地址: 192.168.1.2)
端口可达: 106.116.241.38:9999
  ✓ udpxy服务: 106.116.241.38:9999 (活跃连接: 0, 地址: 10.114.147.185)
===============检索完成，找到 4 个可访问 IP，4 个udpxy服务===============

==========开始流媒体测速=================
1/4 测试udpxy服务: 106.116.241.38:9999
  测试流媒体: http://106.116.241.38:9999/udp/239.254.200.45:8008
  ✓ 106.116.241.38:9999 下载完成:
    总大小: 2048.0KB
    总耗时: 2.01秒
    平均速度: 0.996MB/s
==========流媒体测速完成=================
总计: 1 个可用IP, 3 个失败

======本次Hebei组播IP搜索结果=============
0.996 MB/s  106.116.241.38:9999
```

## 输出文件说明

### 目录结构
```
sum/
├── tmp/                          # 临时文件目录
│   └── *_result_fofa_*.txt      # FOFA搜索结果
├── Telecom/                     # 电信结果目录
│   ├── *_sum.ip                 # 所有可访问IP
│   ├── *_uniq.ip               # 去重后的udpxy IP
│   └── *.txt                   # 最终结果文件
├── Unicom/                      # 联通结果目录
└── Mobile/                      # 移动结果目录

template/
├── Telecom/
│   └── template_*.txt          # 电信模板文件
├── Unicom/
└── Mobile/

*_speedtest_*.log               # 测速日志文件
```

### 结果文件格式

#### IP列表文件 (`*_sum.ip` 和 `*_uniq.ip`)
```
# *_sum.ip - 所有可访问的IP（包括非udpxy服务）
121.20.197.192:9999
110.255.26.128:8088
221.194.78.228:2222

# *_uniq.ip - 经过验证的udpxy服务器IP（去重）
121.20.197.192:9999
110.255.26.128:8088
221.194.78.228:2222
```

#### 测速结果文件 (`*_result_fofa_*.txt`)
```
1.001  221.194.78.228:2222
0.997  110.255.26.128:8088
0.987  121.20.197.192:9999
0.987  120.6.34.143:8088
0.984  101.25.230.162:8001
```

#### 测速日志文件 (`*_speedtest_*.log`)
```
221.194.78.228:2222 1.001 MB/s Size:2097152
110.255.26.128:8088 0.997 MB/s Size:2097152
121.20.197.192:9999 0.987 MB/s Size:2097152
120.6.34.143:8088 0.987 MB/s Size:2097152
101.25.230.162:8001 0.984 MB/s Size:2097152
```

#### 最终合并文件 (`sum/运营商/城市.txt`)
根据模板文件自动生成，将IP地址替换模板中的占位符

## 程序执行流程

1. **初始化阶段**
   - 加载 `.env` 环境变量配置
   - 验证必要参数（FOFA Cookie、Quake360 Token、User Agent）
   - 创建输出目录结构
   - 读取对应运营商的省份配置文件

2. **IP搜索阶段**
   - **FOFA搜索**: 优先使用API方式，失败时自动回退到Cookie方式
   - **Quake360搜索**: 使用Token认证进行API搜索
   - **结果处理**: 自动合并两个平台的搜索结果并去重

3. **连通性验证阶段**
   - **端口测试**: 并发测试所有IP的端口可达性（最大30线程）
   - **服务验证**: 验证可达IP是否为有效的udpxy代理服务
   - **结果保存**: 生成可访问IP列表和udpxy服务器列表

4. **流媒体测速阶段**
   - **并发下载**: 对udpxy服务器进行真实流媒体下载测试（最大3线程）
   - **速度计算**: 实时监控下载进度，计算平均传输速度
   - **异常处理**: 处理连接超时、读取错误等异常情况

5. **结果生成阶段**
   - **结果筛选**: 过滤速度低于0.1MB/s的无效结果
   - **排序输出**: 按速度降序排列，生成多种格式的结果文件
   - **模板合并**: 与预定义模板合并生成最终配置文件

6. **清理阶段**
   - 删除临时文件和测速日志
   - 释放网络连接资源

## 性能特性与参数

### 并发控制策略
- **IP搜索**: 支持FOFA和Quake360平台并发搜索
- **连通性测试**: 最大30个并发线程，快速检测大量IP
- **流媒体测速**: 最大3个并发下载，避免带宽竞争影响测试准确性

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
根据不同运营商自动构建精确的搜索查询条件：
- **电信**: 匹配Chinanet、China Telecom等多种组织标识
- **联通**: 匹配CHINA UNICOM、China169等网络标识  
- **移动**: 匹配China Mobile、移动通信等公司标识

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
# QUAKE360_TOKEN=your_token
# FOFA_COOKIE=your_cookie  
# FOFA_USER_AGENT=your_user_agent
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

#### 4. 无可用IP发现
**问题**: `没有找到可用的udpxy服务器`  
**解决方案**:
- 确认目标地区和运营商是否有相关服务部署
- 检查省份配置文件中的地区名称是否与搜索参数匹配
- 尝试扩大搜索范围或调整搜索条件
- 验证网络环境是否能正常访问目标服务

#### 5. 流媒体测速全部失败
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
端口可达: 121.20.197.192:9999
✓ udpxy服务: 121.20.197.192:9999

# 测速阶段调试信息
测试流媒体: http://121.20.197.192:9999/udp/239.253.92.83:8012
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
- **Token安全**: Quake360使用Token认证，避免账号密码泄露风险
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

### 最新优化 (v2.0)
- **认证方式优化**: 移除了Quake360的Cookie认证方式，简化为Token-only认证
- **FOFA双重认证**: 支持API密钥和Cookie双重认证，API优先，失败时自动回退
- **代码精简**: 移除了约300行冗余的Cookie相关代码，提高了维护性
- **错误处理增强**: 改进了API错误处理和网络异常处理机制

### 性能改进
- **搜索效率**: 优化了搜索查询条件，提高了IP发现的准确性
- **并发优化**: 调整了并发参数，平衡了速度和资源占用
- **内存管理**: 改进了大文件下载的内存使用，避免内存溢出

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

---

**最后更新**: 2025年7月17日  
**版本**: v2.0 - 简化认证机制版本
