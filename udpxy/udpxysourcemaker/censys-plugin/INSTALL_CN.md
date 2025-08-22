# 🚀 Censys UDPXY 提取器 - 中文版安装指南

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
- 扩展列表中应显示 **Censys UDPXY 提取器**
- 状态应为 **已启用**
- 浏览器工具栏出现蓝紫色渐变圆形图标

## 🎯 使用方法 (中文界面)

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
3. 点击 **📊 提取当前页面**
4. 提取当前搜索结果页面的IP列表

#### 模式二：IP详情页面提取
1. 点击搜索结果中的具体IP链接
2. 进入详情页面 (如: `https://platform.censys.io/hosts/221.233.156.10?at_time=...`)
3. 点击扩展图标
4. 点击 **🔍 提取详情页面**
5. 提取详细的JSON数据和元信息

#### 模式三：自动批量提取
1. 在搜索页面点击扩展图标
2. 点击 **🤖 自动搜索提取**
3. 自动执行多个预设查询并深度提取每个IP的详细信息

### 📈 界面说明

#### 统计信息面板
- **发现IP**: 已发现的唯一 IP 地址数量
- **页面数**: 已处理的页面数量  
- **用时**: 从开始提取到现在的用时

#### 状态提示
- 🔄 **内容脚本未就绪，正在注入...** - 正在修复连接
- 🔄 **重试 1/3...** - 正在重试连接
- 🔍 **正在提取当前页面数据...** - 正在提取数据
- ✅ **在此页面发现 5 个IP** - 提取成功
- ❌ **请先导航到Censys搜索页面** - 需要切换页面

### 📥 下载格式

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

## 🐛 故障排除

### 常见问题

**1. "❌ 连接错误: Could not establish connection"**
- 扩展会自动尝试修复此问题
- 观察状态提示中的修复进度
- 如果自动修复失败，刷新页面后重试

**2. "❌ 请先导航到Censys搜索页面"**
- 确保在正确的URL: `https://platform.censys.io/*`
- 不要在主页 `censys.com` 使用扩展

**3. "ℹ️ 此页面未找到详细数据"**
- 确保在IP详情页面使用详情提取功能
- 检查页面是否完全加载
- 尝试刷新页面后重新提取

## 🔄 版本特性

### v1.1.0 (当前中文版)
- ✅ 完整中文界面和提示信息
- ✅ 支持精确的中国UDPXY搜索语句
- ✅ IP详情页面深度数据提取
- ✅ 智能连接检测和自动修复
- ✅ 14个详细CSV字段

---

**⚠️ 重要提示**: 
- 使用合理的请求频率，避免对Censys服务器造成压力
- 提取的数据仅供合法研究和个人使用
