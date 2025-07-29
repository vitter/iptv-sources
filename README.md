
# IPTV直播源工具集

一个功能完整的IPTV直播源处理工具集，包含多种获取、测试、分组和优化IPTV频道源的专业工具。

## 🏗️ 项目结构

```
iptv-sources/
├── Hotels/                   # IPTV服务器批量探测工具
├── ISP/                      # 按运营商分组工具  
├── mobileunicast/            # 移动直播源处理工具
└── udpxy/                    # udpxy代理搜索测速工具
```

## 🚀 核心功能

### 📡 多源获取与探测
- **Hotels**: 支持jsmpeg、txiptv、zhgxtv三种IPTV服务器类型的批量探测
- **mobileunicast**: 从27个优质移动网络源下载并合并频道
- **udpxy**: 通过FOFA和Quake360搜索udpxy代理服务器
- **ISP**: 从预定义源列表下载直播源文件

### ⚡ 智能测速与优化
- **并发流媒体测速**: 支持M3U8/HLS和直接流的速度测试
- **超时控制机制**: 优化的超时设置避免长时间等待
- **智能筛选**: 自动过滤无效源，保留高质量频道
- **速度排序**: 按下载速度排序，优先保留最快源

### 🏷️ 智能分组与分类
- **运营商分组**: 基于IP地址识别电信/联通/移动/铁通/教育网/广电网
- **频道类型分组**: 央视/卫视/港澳台/省级/市级/其他六大类
- **双级分组**: 支持运营商+频道类型的二级分组结构
- **频道名标准化**: 自动规范化频道名称格式

### 📄 多格式输出
- **M3U格式**: 标准播放列表，支持group-title分组
- **TXT格式**: 文本格式，支持#genre#分组标记  
- **日志记录**: 详细的下载、测速、查询日志
- **模板合并**: 支持预定义模板的自动合并

## 🛠️ 工具详解

### 🏨 Hotels - IPTV服务器批量探测工具

**适用场景**: 已知IPTV服务器类型，需要批量扫描同网段服务器

**主要特性**:
- 支持三种主流IPTV服务器类型（jsmpeg、txiptv、zhgxtv）
- 智能C段网络扫描（如192.168.1.1-254）
- 异步并发处理，最高500个并发会话
- 自动频道名称标准化（CCTV、卫视等）

**使用方法**:
```bash
# 单模式扫描
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv

# 多模式组合
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --txiptv txiptv_hosts.csv

# 自定义输出
python all-z-j-new.py --jsmpeg jsmpeg_hosts.csv --output my_channels
```

**输出文件**:
- `itvlist.txt` / `itvlist.m3u` - 播放列表文件
- `speed.txt` - 详细测速结果

---

### 🌐 ISP - 按运营商分组工具

**适用场景**: 需要按运营商对IPTV源进行分类管理

**主要特性**:
- 通过API自动识别IP所属运营商（电信/联通/移动/铁通/教育网/广电网/其他/未知）
- 运营商+频道类型双级分组
- 支持--noisp参数跳过运营商查询（类似unicast.py）
- 智能去重查询，相同IP只查询一次

**使用方法**:
```bash
# 正常模式：按运营商和频道类型两级分组
python isp.py --top 20

# 仅按频道类型分组（功能与unicast.py相同）
python isp.py --top 20 --noisp
```

**分组格式**:
- 正常模式: `电信/央视频道,#genre#`
- noisp模式: `央视频道,#genre#`

**输出文件**:
- 正常模式: `output/isp_result.m3u` / `output/isp_result.txt`
- noisp模式: `output/unicast_result.m3u` / `output/unicast_result.txt`
- `isp_query.log` - 运营商查询日志
- `isp_speed.log` - 测速日志

---

### 📱 mobileunicast - 移动直播源处理工具

**适用场景**: 获取和优化移动网络的IPTV直播源

**主要特性**:
- 从27个优质移动网络源自动下载
- 涵盖全国各省移动网络
- 智能频道分类和去重
- 优化的测速算法，3线程并发避免网络拥堵

**使用方法**:
```bash
# 默认每个频道保留前20个最快源
python unicast.py

# 自定义保留源数量
python unicast.py --top 5
```

**数据源覆盖**:
- live.zbds.org (5个源)
- chinaiptv.pages.dev (12个省份源)
- 其他优质源 (10个源)

**输出文件**:
- `output/unicast_result.m3u` / `output/unicast_result.txt`
- `speed.log` - 测速日志
- `txt.tmp` - 汇总临时文件

---

### 🔍 udpxy - udpxy代理搜索测速工具

**适用场景**: 搜索和测试特定地区运营商的udpxy代理服务器

**主要特性**:
- 集成FOFA和Quake360两大搜索引擎
- API密钥优先，Cookie备用的双重认证机制
- 真实流媒体环境测速
- 支持翻页获取大量数据（默认10页限制）

**使用方法**:
```bash
# 基础搜索（默认10页）
python speedtest_integrated_new.py Hebei Telecom

# 指定翻页数
python speedtest_integrated_new.py Shanghai Unicom --max-pages 5
```

**配置要求**:
```env
# .env文件配置
QUAKE360_TOKEN=your_token
FOFA_COOKIE=your_cookie
FOFA_API_KEY=your_api_key  # 可选
FOFA_USER_AGENT=Mozilla/5.0...
```

**输出文件**:
- `sum/运营商/*_uniq.ip` - udpxy服务器列表
- `sum/运营商/*.txt` - 测速结果文件
- `*_speedtest_*.log` - 详细测速日志

## 📊 功能对比表

| 工具 | 数据源 | 测速方式 | 分组方式 | 适用场景 |
|------|--------|----------|----------|----------|
| **Hotels** | IP段扫描 | 并发测速 | 频道类型 | 已知服务器批量扫描 |
| **ISP** | 预定义源 | 并发测速 | 运营商+频道类型 | 运营商分类管理 |
| **mobileunicast** | 27个移动源 | 优化测速 | 频道类型 | 移动网络源优化 |
| **udpxy** | 搜索引擎 | 真实流测速 | 速度排序 | udpxy代理发现 |

## 🔧 安装与配置

### 环境要求
- **Python**: 3.6+ (推荐3.8+)
- **操作系统**: Windows/Linux/macOS
- **网络**: 稳定的互联网连接

### 依赖安装
```bash
# 基础依赖
pip install requests

# udpxy工具额外依赖
pip install urllib3 python-dotenv

# Hotels工具额外依赖
pip install aiohttp
```

### 快速开始

1. **克隆项目**
```bash
git clone https://github.com/vitter/iptv-sources.git
cd iptv-sources
```

2. **选择合适的工具**
```bash
# 移动网络源处理（推荐新手）
cd mobileunicast
python unicast.py --top 10

# 运营商分组处理
cd ISP  
python isp.py --top 15

# udpxy代理搜索（需要API配置）
cd udpxy
python speedtest_integrated_new.py Beijing Telecom
```

## 📈 性能优化建议

### 并发参数调优
- **Hotels**: jsmpeg/zhgxtv最大100线程，txiptv最大500并发
- **ISP**: 测速8线程，运营商查询2线程（避免API限制）
- **mobileunicast**: 测速3线程（避免网络拥堵）
- **udpxy**: 连通性测试30线程，流媒体测速3线程

### 超时设置优化
- **连通性测试**: 2-5秒
- **流媒体测速**: 8-12秒
- **API查询**: 8-30秒
- **总任务超时**: 120秒

### 数据量控制
- **测速数据限制**: 2MB或10秒（先达到者为准）
- **保留源数量**: 3-20个（推荐5-10个）
- **翻页限制**: 1-20页（推荐3-10页）

## 🔍 使用场景指南

### 场景1: 首次建立IPTV源库
**推荐流程**:
1. 使用 `mobileunicast` 获取基础移动源
2. 使用 `ISP` 工具对源进行运营商分类
3. 使用 `udpxy` 搜索特定地区的代理服务器

### 场景2: 已有服务器批量扫描
**推荐工具**: `Hotels`
- 准备CSV格式的服务器列表
- 选择对应的服务器类型（jsmpeg/txiptv/zhgxtv）
- 进行批量扫描和测速
- 结合makecsv.py使用可生成更新CSV列表文件，通过FOFA和Quake360搜索

### 场景3: 按运营商维护源库
**推荐工具**: `ISP`
- 定期运行更新源库
- 使用双级分组便于管理
- 通过日志监控源质量变化

### 场景4: 特定地区代理发现
**推荐工具**: `udpxy`
- 配置FOFA和Quake360认证
- 选择目标地区和运营商
- 获取可用的udpxy代理列表

## 🐛 常见问题与解决

### 网络连接问题
```bash
# 检查网络连接
ping fofa.info
ping quake.360.cn

# 检查DNS解析
nslookup live.zbds.org
```

### API认证问题
```bash
# 检查环境变量
cat .env

# 验证FOFA Cookie
curl -H "Cookie: $FOFA_COOKIE" "https://fofa.info"

# 验证Quake360 Token
curl -H "X-QuakeToken: $QUAKE360_TOKEN" "https://quake.360.cn/api/v3/user/info"
```

### 测速异常处理
- **全部测速失败**: 检查网络带宽和防火墙设置
- **速度过慢**: 调整并发数或超时时间
- **内存不足**: 减少保留源数量或分批处理

### 输出文件异常
- **编码问题**: 确保使用UTF-8编码
- **格式错误**: 检查播放器兼容性
- **文件损坏**: 清理临时文件重新运行

## 📝 开发与贡献

### 代码规范
- 遵循PEP8代码风格
- 添加详细的注释和文档字符串
- 确保异常处理和日志记录完整

### 测试建议
- 在不同网络环境下测试
- 验证各种边界情况处理
- 确保大数据量处理的稳定性

### 贡献指南
1. Fork项目并创建特性分支
2. 完成开发并添加必要测试
3. 提交Pull Request并描述修改内容

## 📄 许可证

本项目采用MIT开源许可证。详细信息请查看各子目录的LICENSE文件。

## ⚠️ 免责声明

- 本工具集仅供学习和技术研究使用
- 使用前请确保遵守相关网站的使用条款和法律法规
- 请合理使用API接口，避免对服务提供商造成负担
- 作者不对使用工具可能产生的任何问题承担责任

## 🔗 相关链接

- **项目主页**: https://github.com/vitter/iptv-sources
- **问题反馈**: https://github.com/vitter/iptv-sources/issues
- **开发文档**: 查看各子目录的README.md文件

---

**最后更新**: 2025年7月29日  
**当前版本**: v2.0  
**维护状态**: 积极维护中

⭐ 如果这个工具集对您有帮助，请给个Star支持一下！
