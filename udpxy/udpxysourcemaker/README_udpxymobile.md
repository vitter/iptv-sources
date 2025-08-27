
# 中国移动UDPXY服务搜索工具

## 工具简介

`udpxymobile.py` 是一个专为中国移动 UDPXY 服务批量搜索设计的 Python 工具，支持 FOFA、Quake360、ZoomEye、Hunter 四大安全搜索引擎 API，自动分页、自动去重，结果统一输出到 txt 文件。

## 最新特性

- **FOFA ASN自动远程获取**：所有中国移动 ASN 号实时从官方地址拉取，无需手动维护
- **全国/省份智能搜索**：支持全国或指定省份（拼音）精准筛选
- **纯API密钥认证**：所有引擎仅支持 API 密钥，不再支持 Cookie
- **查询语句自动拼接**：FOFA 查询语句自动拼接 ASN，全国/省份均支持
- **结果去重与排序**：所有结果自动去重，按 IP 排序输出
- **进度与统计显示**：每步均有详细进度与统计信息

## 安装依赖

```bash
pip install requests python-dotenv
```

## 环境变量配置

在 `.env` 文件或系统环境变量中设置以下 API 密钥：

```bash
FOFA_API_KEY=你的fofa密钥
QUAKE360_TOKEN=你的quake360密钥
ZOOMEYE_API_KEY=你的zoomeye密钥
HUNTER_API_KEY=你的hunter密钥
```

> 未配置的 API 会自动跳过，不影响其他引擎。

## 使用方法

### 基本用法

```bash
# 全国中国移动 UDPXY 服务搜索
python3 udpxymobile.py

# 指定省份（如广东）
python3 udpxymobile.py --region guangdong

# 限制最大页数（默认10页）
python3 udpxymobile.py --max-pages 5

# 指定输出文件名
python3 udpxymobile.py --output my_mobile_udpxy.txt
```

### 参数说明

- `--region`：指定省份（拼音，不区分大小写，如 guangdong、beijing）
- `--max-pages`：最大搜索页数，默认10页
- `--all-pages`：自动获取所有页（慎用，API有速率限制）
- `--output`：输出文件名，默认 `mobile_udpxy.txt`

## 查询语句示例

### FOFA

自动远程获取 ASN 列表，查询语句如下：

全国：
```
"udpxy" && country="CN" && protocol="http" && (asn="9808" || asn="56048" || ...)
```
指定省份：
```
"udpxy" && country="CN" && protocol="http" && (asn="9808" || ...) && region="Guangdong"
```

ASN 列表自动从：
https://raw.githubusercontent.com/vitter/china-mainland-asn/refs/heads/main/asn_txt/cmcc.txt

### Quake360
```
"udpxy" AND country: "China" AND isp: "中国移动" AND protocol: "http"
```
指定省份：
```
"udpxy" AND country: "China" AND province: "Guangdong" AND isp: "中国移动" AND protocol: "http"
```

### ZoomEye
```
app="udpxy" && country="CN" && isp="China Mobile"
```
指定省份：
```
app="udpxy" && country="CN" && isp="China Mobile" && subdivisions="Guangdong"
```

### Hunter
```
protocol.banner="Server: udpxy"&&app="Linux"&&protocol=="http"&&ip.country="CN"&&ip.isp="移动"
```
指定省份：
```
... && ip.province="广东"
```

## 输出格式

txt 文件，每行一个 IP:PORT，自动去重、排序：
```
192.168.1.1:8080
192.168.1.2:4022
...
```

## 进阶用法

```bash
# 搜索北京移动 UDPXY，限制3页，保存到指定文件
python3 udpxymobile.py --region beijing --max-pages 3 --output beijing_mobile.txt

# 搜索广东移动 UDPXY，获取更多数据
python3 udpxymobile.py --region guangdong --max-pages 20 --output guangdong_mobile.txt
```

## 注意事项

1. **API密钥必填**：未配置的引擎自动跳过
2. **API速率限制**：建议合理控制页数，避免频繁请求
3. **FOFA ASN自动拉取**：如远程ASN列表不可用，可手动指定
4. **结果去重**：所有结果自动去重，按IP排序
5. **省份参数**：拼音自动首字母大写，Hunter自动转中文

## 故障排查

- API权限错误：检查密钥是否正确
- API速率限制：降低页数或增加请求间隔
- 无结果：检查密钥和参数
- FOFA ASN拉取失败：检查网络或手动指定ASN

## 许可证

仅供学习和研究使用。
