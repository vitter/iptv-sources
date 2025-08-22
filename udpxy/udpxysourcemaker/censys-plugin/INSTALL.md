# 🚀 Censys UDPXY Extractor - Installation Guide

## ✅ Quick Installation

### 1. Open Chrome Extensions
Type in address bar: `chrome://extensions/`

### 2. Enable Developer Mode
Toggle **Developer mode** in the top-right corner

### 3. Load Extension
1. Click **Load unpacked**
2. Select folder: `/home/vitter/github/iptv-sources/udpxy/udpxysourcemaker/censys-plugin`
3. Click **Select Folder**

### 4. Verify Installation
- **Censys UDPXY 提取器** appears in extensions list
- Blue-purple gradient icon appears in toolbar
- Status shows **Enabled**

## 🎯 Usage Guide

### 🚀 Quick Start
1. Visit https://platform.censys.io and login
2. Navigate to search page (not homepage)
3. Click extension icon in toolbar
4. Choose extraction mode

### 📊 Three Extraction Modes

#### Mode 1: Current Page Extraction
- **Location**: Censys search results page
- **Action**: Click "📊 提取当前页面" (Extract Current Page)
- **Result**: Get IP list from current page

#### Mode 2: Details Page Extraction
- **Location**: Click specific IP from search results
- **Action**: Click "🔍 提取详情页面" (Extract Details Page)
- **Result**: Get detailed JSON data

#### Mode 3: Auto Batch Extraction
- **Location**: Search page
- **Action**: Click "🤖 自动搜索提取" (Auto Search Extract)
- **Result**: Auto-execute multiple queries with deep extraction

### 🔍 Recommended Search Query
```
(host.services.software.product = "udpxy" or web.software.product = "udpxy") and host.location.country = "China"
```

### 📥 Download Formats

#### Enhanced CSV (udpxy_results_*.csv)
14 detailed fields: IP, Port, Country, City, Province, Organization, ISP, ASN, Service_Name, Software_Product, Software_Version, HTTP_Title, Last_Seen, Extraction_Time

#### M3U Playlist (udpxy_servers_*.m3u)
Standard M3U format for IPTV players

#### IP List (udpxy_ips_*.txt)
Simple IP:Port format for batch processing

## 🐛 Troubleshooting

### Common Issues

**1. "Could not establish connection"**
- Extension auto-attempts to fix this
- Watch status messages for repair progress
- If auto-fix fails, refresh page and retry

**2. "请先导航到Censys搜索页面" (Navigate to Censys search page)**
- Ensure you're on `https://platform.censys.io/*`
- Don't use on `censys.com` homepage

**3. "此页面未找到详细数据" (No detailed data found)**
- Ensure you're on correct page type
- Check page fully loaded
- Try refresh and re-extract

## 📋 Version Info

### v1.1.0 - Chinese Localized
- ✅ Complete Chinese interface
- ✅ Enhanced connection recovery
- ✅ Smart retry logic
- ✅ Detailed CSV fields
- ✅ Multiple search query support

---

**Important**: Use responsibly, follow Censys ToS, data for legitimate research only.

## ✅ 安装步骤

### 1. 打开 Chrome 扩展管理页面
- 在 Chrome 地址栏输入: `chrome://extensions/`
- 或者菜单: **更多工具** → **扩展程序**

### 2. 启用开发者模式
- 点击右上角的 **开发者模式** 开关
- 确保开关为蓝色(开启状态)

### 3. 加载扩展
- 点击 **加载已解压的扩展程序** 按钮
- 选择文件夹: `/home/vitter/github/iptv-sources/udpxy/udpxysourcemaker/censys-plugin`
- 点击 **选择文件夹**

### 4. 验证安装
- 扩展列表中应显示 **Censys UDPXY Extractor**
- 状态应为 **已启用**
- 浏览器工具栏出现蓝紫色渐变圆形图标

## 🎯 使用方法 (增强版)

### 准备工作
1. 访问 https://platform.censys.io
2. 使用你的账户正常登录
3. 确保可以正常访问搜索功能

### 🔍 主要搜索语句
扩展现在支持更精确的搜索语句：
```
(host.services.software.product = "udpxy" or web.software.product = "udpxy") and host.location.country = "China"
```

### 📊 三种提取模式

#### 模式一：搜索结果页面提取
1. 在 Censys 搜索页面执行搜索
2. 点击扩展图标
3. 点击 **📊 Extract Current Page**
4. 提取当前搜索结果页面的IP列表

#### 模式二：IP详情页面提取 (新功能)
1. 点击搜索结果中的具体IP链接
2. 进入详情页面 (如: `https://platform.censys.io/hosts/221.233.156.10?at_time=...`)
3. 点击扩展图标
4. 点击 **🔍 Extract Detail Page**
5. 提取详细的JSON数据和元信息

#### 模式三：自动批量提取
1. 在搜索页面点击扩展图标
2. 点击 **🤖 Auto Search & Extract**
3. 自动执行多个预设查询并深度提取每个IP的详细信息

### � 下载格式

#### CSV 增强格式 (udpxy_results_*.csv)
```csv
IP,Port,Country,City,Province,Organization,ISP,ASN,Service_Name,Software_Product,Software_Version,HTTP_Title,Last_Seen,Extraction_Time
"221.233.156.10","4022","China","Beijing","Beijing","China Telecom","CHINANET","4134","HTTP","udpxy","1.0.25","UDPXY Status","2024-08-21","2024-08-21T08:10:27.252Z"
```

#### M3U 播放列表格式 (udpxy_servers_*.m3u)
```m3u
#EXTM3U
#EXTINF:-1,UDPXY-221.233.156.10:4022
http://221.233.156.10:4022/udp/
```

#### 简洁IP列表 (udpxy_ips_*.txt)
```
221.233.156.10:4022
122.142.189.89:4022
```

## 🔧 工作流程说明

### 完整数据提取流程
1. **搜索阶段**: 使用增强搜索语句定位中国的UDPXY服务器
2. **列表提取**: 从搜索结果页面提取IP链接列表
3. **详情获取**: 自动访问每个IP的详情页面
4. **JSON解析**: 从详情页面提取完整的JSON数据
5. **数据整合**: 合并所有信息生成完整的CSV文件

### 数据字段说明
- **IP**: 服务器IP地址
- **Port**: UDPXY服务端口 (通常为4022)
- **Country/City/Province**: 地理位置信息
- **Organization**: 组织名称
- **ISP**: 互联网服务提供商
- **ASN**: 自治系统号
- **Service_Name**: 服务类型 (通常为HTTP)
- **Software_Product**: 软件产品 (udpxy)
- **Software_Version**: 软件版本
- **HTTP_Title**: HTTP页面标题
- **Last_Seen**: 最后检测时间
- **Extraction_Time**: 数据提取时间

## 🐛 故障排除

### 常见问题

**1. 详情页面提取失败**
- 确保在正确的IP详情页面 (URL包含 `/hosts/IP地址`)
- 等待页面完全加载后再提取
- 检查页面是否包含JSON数据

**2. 自动搜索中断**
- 网络连接问题：检查网络稳定性
- 页面加载超时：增加等待时间
- Censys限制：避免过于频繁的请求

**3. 数据不完整**
- 某些字段可能在页面中不存在
- 扩展会尝试多种方式提取数据
- 空字段会显示为空字符串

### 调试信息
打开浏览器开发者工具 (F12) → Console 标签，查看以 `[Censys Extractor]` 开头的详细日志。

## 🔄 版本特性

### v1.1.0 (当前增强版)
- ✅ 支持精确的中国UDPXY搜索语句
- ✅ IP详情页面深度数据提取
- ✅ JSON数据解析和字段映射
- ✅ 14个详细CSV字段
- ✅ 自动化批量详情提取
- ✅ 增强的错误处理和重试机制

## 📞 使用技巧

1. **最佳搜索语句**: 使用主要搜索语句可获得最精确的中国UDPXY服务器结果
2. **批量处理**: 自动模式会处理多页结果并深度提取每个IP
3. **数据验证**: 扩展会验证IP格式和去除重复项
4. **导出建议**: CSV格式最适合数据分析，M3U格式可直接用于IPTV播放器

---

**⚠️ 重要提示**: 
- 使用合理的请求频率，避免对Censys服务器造成压力
- 详情页面提取需要更多时间，请耐心等待
- 提取的数据仅供合法研究和个人使用
