# 中国移动UDPXY服务搜索工具

## 功能描述

`udpxymobile.py` 是一个专门用于搜索中国移动运营商的UDPXY服务的工具。它使用4个搜索引擎的API（FOFA、Quake360、ZoomEye、Hunter）来查找符合条件的IP地址和端口，并将结果保存到txt文件中。

## 主要特点

- **纯API搜索**: 使用4个搜索引擎的官方API，稳定可靠
- **专注移动**: 专门搜索中国移动运营商的UDPXY服务
- **省份过滤**: 支持按省份进行精确搜索或全国搜索
- **智能查询**: 全国搜索时穷举所有省份的移动组织名称，避免模糊查询限制
- **结果去重**: 自动去除重复的IP:PORT
- **格式统一**: 输出标准的 `IP:PORT` 格式，每行一个
- **进度显示**: 实时显示搜索进度和结果统计

## 安装依赖

```bash
pip install requests python-dotenv
```

## 环境变量配置

创建 `.env` 文件或设置系统环境变量（所有API密钥都是必需的）：

```bash
# 必需的API配置
FOFA_API_KEY=your_fofa_api_key          # FOFA API密钥
QUAKE360_TOKEN=your_quake360_token      # Quake360 API Token
ZOOMEYE_API_KEY=your_zoomeye_api_key    # ZoomEye API密钥
HUNTER_API_KEY=your_hunter_api_key      # Hunter API密钥
```

**注意**: 程序已经精简，仅使用API方式，不再支持Cookie认证。如果某个API密钥未配置，对应的搜索引擎将被跳过。

## 使用方法

### 基本用法

```bash
# 全国搜索中国移动UDPXY服务
python3 udpxymobile.py

# 指定省份搜索（如广东省）
python3 udpxymobile.py --region guangdong

# 限制搜索页数（默认10页）
python3 udpxymobile.py --max-pages 5

# 指定输出文件名
python3 udpxymobile.py --output my_mobile_udpxy.txt
```

### 组合使用

```bash
# 搜索北京移动的UDPXY服务，限制3页，保存到指定文件
python3 udpxymobile.py --region beijing --max-pages 3 --output beijing_mobile.txt

# 搜索广东移动的UDPXY服务，获取更多数据
python3 udpxymobile.py --region guangdong --max-pages 20 --output guangdong_mobile.txt
```

### 参数说明

- `--region`: 指定省份（拼音小写，如：guangdong, beijing, shanghai）
- `--max-pages`: 最大搜索页数，默认10页，建议根据需要调整
- `--output`: 输出文件名，默认为 `mobile_udpxy.txt`

## 搜索查询语句

各个搜索引擎使用的查询语句：

### Quake360 (示例)
```
"udpxy" AND country: "China" AND isp: "中国移动" AND protocol: "http"
```

### FOFA
全国搜索：穷举所有省份的移动组织名称
```
"udpxy" && country="CN" && (org="Beijing Mobile Communication Company Limited" || org="Beijing Mobile Communications Co." || ... [包含所有31个省份的移动组织]) && protocol="http"
```

省份搜索：
```
"udpxy" && country="CN" && region="Guangdong" && (org="Guangdong Mobile Communication Company Limited" || org="Guangdong Mobile Communications Co." || ...) && protocol="http"
```

### ZoomEye
```
app="udpxy" && country="CN" && isp="China Mobile"
```

### Hunter
```
protocol.banner="Server: udpxy"&&app="Linux"&&protocol=="http"&&ip.country="CN"&&ip.isp="移动"
```

## 输出格式

生成的txt文件格式：
```
192.168.1.1:8080
192.168.1.2:4022
192.168.1.3:5000
...
```

每行一个IP:PORT，按IP地址排序。

## 使用示例

### 示例1: 搜索广东移动UDPXY服务

```bash
python3 udpxymobile.py --region guangdong --max-pages 5
```

输出：
```
============================================================
           中国移动UDPXY服务搜索工具
============================================================
可用搜索引擎: FOFA API, Quake360, ZoomEye Cookie, Hunter
✓ 配置完成
搜索范围: Guangdong
最大页数: 5
输出文件: mobile_udpxy.txt

=============== FOFA 搜索 ===============
查询语句: "udpxy" && country="CN" && region="Guangdong" && ...
FOFA找到 145 个IP:PORT

=============== Quake360 搜索 ===============
查询语句: "udpxy" AND country: "China" AND province: "Guangdong" AND isp: "中国移动" AND protocol: "http"
Quake360找到 67 个IP:PORT

... (其他搜索引擎结果)

总共找到 298 个IP:PORT，去重后 256 个
✓ 结果已保存到: mobile_udpxy.txt
✓ 共保存 256 个IP:PORT
```

### 示例2: 全国搜索

```bash
python3 udpxymobile.py --max-pages 10 --output all_china_mobile.txt
```

## 注意事项

1. **API密钥**: 所有4个搜索引擎都需要有效的API密钥，未配置的引擎将被跳过
2. **API配额**: 各搜索引擎都有API调用限制，建议合理控制搜索页数
3. **搜索频率**: 避免过于频繁的搜索，以免触发API限制
4. **全国搜索优化**: 使用省份穷举替代模糊查询，避免FOFA权限限制
5. **结果验证**: 建议对搜索结果进行验证，确保UDPXY服务可用

## 故障排除

### 常见问题

1. **API权限错误**: 检查API密钥是否正确和有效
2. **API限制**: 如果遇到API限制，可以降低搜索频率或减少页数
3. **无结果**: 检查环境变量配置是否正确，确保至少有一个API密钥可用
4. **查询过长**: 全国搜索的FOFA查询会很长，这是正常的（穷举所有省份）

### 调试方法

查看详细输出信息，脚本会显示：
- 可用的搜索引擎和缺少的配置
- 具体的搜索查询语句（FOFA全国查询会被截断显示）
- 每页的搜索结果数量
- 最终的统计信息

## 许可证

本工具基于原有项目的许可证，仅用于学习和研究目的。
