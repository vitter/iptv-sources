# makecsv.py 修改说明

## 主要修改内容

### 1. FOFA API 字段配置修改
- 将字段配置从 `'fields': 'ip,port,host'` 修改为 `'fields': 'ip,host,port,link,org'`
- 这样返回的JSON数据包含5个字段：[ip, host, port, link, org]
- 新增org字段用于运营商信息提取

### 2. FOFA API 数据提取逻辑优化
修改了数据提取逻辑，正确处理FOFA API返回的5字段数据：
- `result[0]` = ip
- `result[1]` = host  
- `result[2]` = port
- `result[3]` = link
- `result[4]` = org

如果某些字段为空，会自动补全：
- 如果host为空，从ip和port组合生成
- 如果link为空，从host构建http链接
- 如果ip为空，从host中提取

### 3. Quake360 API 数据提取优化
优化了Quake360的数据提取和翻页逻辑：
- 直接使用 `item.get('ip')` 和 `item.get('port')`
- 从ip和port组合生成host和link
- 移除了复杂的嵌套字段查找
- 实现完整的API翻页功能，支持获取全部数据
- 增强端口范围验证（1-65535）

### 4. 搜索查询优化
统一了两个搜索引擎的查询参数：
- FOFA: 使用 `&&` 和 `country="CN"`，自动添加 `after="YYYY-MM-DD"` 日期限制
- Quake360: 使用 `AND` 和 `country:"China"`

### 5. 增加调试信息
在API响应处理中添加了调试输出：
- 显示前3个结果的数据结构
- 便于排查数据格式问题
- 添加翻页进度显示和数据提取统计

### 6. 数据量配置调整
- FOFA API: size改为100，支持翻页获取全部数据
- Quake360 API: size改为100，支持翻页获取全部数据
- 移除了FOFA API的页数限制，实现完整数据获取

### 7. 日期过滤天数参数化
- 新增 `--days` 命令行参数，支持自定义日期过滤天数
- 默认值为30天，可通过参数指定其他天数
- 修改 `_get_date_filter()` 方法支持动态天数
- 所有搜索查询自动使用指定天数的日期限制

### 8. 翻页获取全部数据优化
- **FOFA API翻页**: 支持自动翻页获取所有数据，不再限制页数
  - 使用 `math.ceil(total_size / page_size)` 计算总页数
  - 自动遍历所有页面，每页100条数据
  - 添加请求间隔避免API限流
- **FOFA Cookie翻页**: 实现完整的Cookie搜索翻页
  - 从HTML页面提取总数据量和页面大小信息
  - 使用正则表达式提取 `bI.total=数量` 和 `bI.size=页面大小`
  - 支持动态页面大小检测和翻页URL构建
  - 优化数据提取精度，避免CSS/JS内容干扰
- **Quake360 API翻页**: 实现完整的API翻页功能
  - 从响应的 `meta.pagination.total` 字段获取总数据量
  - 使用 `math.ceil(total_count / page_size)` 计算总页数
  - 通过修改 `start` 参数实现翻页（`start = (page - 1) * page_size`）
  - 每页100条数据，添加2秒请求间隔避免限流
  - 创建独立的 `_extract_quake360_results()` 方法处理数据提取
- **错误处理**: 增强翻页过程中的异常处理和用户中断支持

### 9. **新增地区和运营商过滤功能** ⭐
- **新增命令行参数**:
  - `--region`: 指定省份，不区分大小写，自动格式化为首字母大写
  - `--isp`: 指定运营商，支持 Telecom/Unicom/Mobile，不区分大小写

- **地区过滤实现**:
  - **FOFA**: 添加 `&& region="{region}"` 条件
  - **Quake360**: 添加 `AND province:"{region}"` 条件

- **运营商过滤实现**:
  - **FOFA运营商过滤**: 基于org字段进行复杂匹配
    - **电信(Telecom)**: 匹配 `Chinanet`、`China Telecom`、`CHINA TELECOM`、`China Telecom Group` 等
    - **移动(Mobile)**: 匹配 `China Mobile Communications Corporation`、省份级移动公司等
    - **联通(Unicom)**: 匹配 `China Unicom`、`CHINA UNICOM China169 Backbone`、省份级联通网络等
  - **Quake360运营商过滤**: 基于isp字段进行中文匹配
    - **电信(Telecom)**: `AND isp:"中国电信"`
    - **移动(Mobile)**: `AND isp:"中国移动"`
    - **联通(Unicom)**: `AND isp:"中国联通"`

- **组合过滤支持**:
  - 可以单独指定地区或运营商
  - 可以同时指定地区和运营商进行精确过滤
  - 如果同时指定，FOFA的运营商过滤会额外匹配省份级运营商组织

- **参数验证**:
  - 地区参数自动格式化（首字母大写，其他小写）
  - 运营商参数验证，只接受有效值（Telecom/Unicom/Mobile）
  - 无效参数时显示警告并忽略

### 10. Cookie字符串清理优化
- 新增 `_clean_cookie_string()` 方法
- 自动移除Cookie中的换行符、回车符、制表符
- 清理多余空格，保持Cookie格式正确性

## 使用方法

1. 配置环境变量（.env文件）：
```
FOFA_COOKIE=your_fofa_cookie
FOFA_USER_AGENT=your_user_agent
FOFA_API_KEY=your_api_key（可选）
QUAKE360_TOKEN=your_token
```

2. 运行命令：
```bash
# 基本用法
python makecsv.py --jsmpeg jsmpeg.csv

# 指定天数
python makecsv.py --jsmpeg jsmpeg.csv --days 7

# 指定地区
python makecsv.py --jsmpeg jsmpeg.csv --region beijing
python makecsv.py --jsmpeg jsmpeg.csv --region guangdong

# 指定运营商
python makecsv.py --jsmpeg jsmpeg.csv --isp telecom
python makecsv.py --jsmpeg jsmpeg.csv --isp mobile
python makecsv.py --jsmpeg jsmpeg.csv --isp unicom

# 组合使用（地区+运营商）
python makecsv.py --jsmpeg jsmpeg.csv --region guangdong --isp mobile
python makecsv.py --jsmpeg jsmpeg.csv --region beijing --isp telecom --days 7

# 多模式组合使用
python makecsv.py --jsmpeg jsmpeg.csv --txiptv txiptv.csv --zhgxtv zhgxtv.csv --region shanghai --isp unicom --days 15
```

## 参数说明

- `--jsmpeg`: jsmpeg模式CSV文件路径
- `--txiptv`: txiptv模式CSV文件路径  
- `--zhgxtv`: zhgxtv模式CSV文件路径
- `--days`: 日期过滤天数，搜索最近N天的数据，默认为30天
- `--region`: 指定省份，不区分大小写，格式化为首字母大写其他小写
- `--isp`: 指定运营商 (Telecom/Unicom/Mobile)，不区分大小写，格式化为首字母大写其他小写

## 搜索规则示例

基本搜索（默认30天）：
```
FOFA: title="jsmpeg-streamer" && country="CN" && after="2025-06-21"
Quake360: title:"jsmpeg-streamer" AND country:"China"
```

带地区过滤：
```
FOFA: title="jsmpeg-streamer" && country="CN" && after="2025-06-21" && region="Guangdong"
Quake360: title:"jsmpeg-streamer" AND country:"China" AND province:"Guangdong"
```

带运营商过滤（电信）：
```
FOFA: title="jsmpeg-streamer" && country="CN" && after="2025-06-21" && (org="Chinanet" || org="China Telecom" || org="CHINA TELECOM" || org="China Telecom Group")
Quake360: title:"jsmpeg-streamer" AND country:"China" AND isp:"中国电信"
```

组合过滤（广东电信）：
```
FOFA: title="jsmpeg-streamer" && country="CN" && after="2025-06-21" && region="Guangdong" && (org="Chinanet" || org="China Telecom" || org="CHINA TELECOM" || org="China Telecom Group" || org="Guangdong Telecom" || org="CHINANET Guangdong province network" || org="CHINANET Guangdong province backbone")
Quake360: title:"jsmpeg-streamer" AND country:"China" AND province:"Guangdong" AND isp:"中国电信"
```

## 去重规则

1. **host字段去重**: 相同的 `ip:port` 只保留一个
2. **C段+端口去重**: 同一个C段(如192.168.1.x)的相同端口只保留一个
3. **优先级**: 现有CSV数据 > 新搜索数据

例如：
- `192.168.1.1:8080` 和 `192.168.1.2:8080` → 只保留第一个（同C段同端口）
- `192.168.1.1:8080` 和 `192.168.1.2:9999` → 都保留（同C段不同端口）

## 输出格式

生成的CSV包含标准字段：
host,ip,port,protocol,title,domain,country,city,link,org

其中必填字段由搜索引擎提供，其他字段使用默认值。新增的org字段包含运营商信息。

## 支持的地区名称

地区参数会自动格式化，支持中文省份名称的英文形式，例如：
- beijing → Beijing
- guangdong → Guangdong  
- shanghai → Shanghai
- sichuan → Sichuan

## 支持的运营商

- **telecom / Telecom**: 中国电信及其省份分公司
- **mobile / Mobile**: 中国移动及其省份分公司
- **unicom / Unicom**: 中国联通及其省份分公
