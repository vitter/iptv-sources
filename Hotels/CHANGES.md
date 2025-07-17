# makecsv.py 修改说明

## 主要修改内容

### 1. FOFA API 字段配置修改
- 将字段配置从 `'fields': 'ip,port,host'` 修改为 `'fields': 'ip,host,port,link'`
- 这样返回的JSON数据包含4个字段：[ip, host, port, link]

### 2. FOFA API 数据提取逻辑优化
修改了数据提取逻辑，正确处理FOFA API返回的4字段数据：
- `result[0]` = ip
- `result[1]` = host  
- `result[2]` = port
- `result[3]` = link

如果某些字段为空，会自动补全：
- 如果host为空，从ip和port组合生成
- 如果link为空，从host构建http链接
- 如果ip为空，从host中提取

### 3. Quake360 API 数据提取简化
简化了Quake360的数据提取逻辑：
- 直接使用 `item.get('ip')` 和 `item.get('port')`
- 从ip和port组合生成host和link
- 移除了复杂的嵌套字段查找

### 4. 搜索查询优化
统一了两个搜索引擎的查询参数：
- FOFA: 使用 `&&` 和 `country="CN"`
- Quake360: 使用 `AND` 和 `country:"China"`

### 5. 增加调试信息
在API响应处理中添加了调试输出：
- 显示前3个结果的数据结构
- 便于排查数据格式问题

### 6. 数据量配置调整
- FOFA API: size改为100
- Quake360 API: size改为100
- 移除了shortcuts参数

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
# 单模式
python makecsv.py --jsmpeg jsmpeg.csv

# 多模式
python makecsv.py --jsmpeg jsmpeg.csv --txiptv txiptv.csv --zhgxtv zhgxtv.csv
```

## 去重规则

1. **host字段去重**: 相同的 `ip:port` 只保留一个
2. **C段+端口去重**: 同一个C段(如192.168.1.x)的相同端口只保留一个

例如：
- `192.168.1.1:8080` 和 `192.168.1.2:8080` → 只保留第一个（同C段同端口）
- `192.168.1.1:8080` 和 `192.168.1.2:9999` → 都保留（同C段不同端口）

## 输出格式

生成的CSV包含标准字段：
host,ip,port,protocol,title,domain,country,city,link,org

其中必填字段由搜索引擎提供，其他字段使用默认值。
