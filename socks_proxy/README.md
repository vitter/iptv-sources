# FOFA Socks5 代理扫描工具

通过 FOFA 搜索引擎自动查找并测试中国地区的 Socks5 代理服务器。

## ⚠️ 重要提示

**关于代理可用性**: FOFA 搜索出来的公开 socks5 代理大多数可能是：
- 🕷️ **蜜罐服务器** - 用于监控和追踪
- ⏰ **已失效代理** - 配置未及时关闭的旧服务
- 🚫 **受限代理** - 仅允许特定IP或服务访问
- 🐌 **慢速代理** - 带宽限制或网络质量差

**建议**: 
- 仅用于学习和测试目的
- 不要用于生产环境
- 敏感操作请使用付费可信代理服务

## 功能特点

- 🔍 **自动搜索**: 使用 FOFA API 搜索符合条件的 Socks5 代理
- 🌏 **中国地区**: 仅搜索中国境内的代理服务器
- 🔓 **无需认证**: 只查找无需身份验证的代理
- 🧪 **连通性测试**: 可选验证代理是否能访问指定网站
- 📝 **关键词验证**: 支持检查目标网站返回内容中的关键词
- ⚡ **并发处理**: 多线程并发测试，提高效率
- 💾 **结果保存**: 自动保存原始结果和测试通过的代理

## 安装依赖

### 必需依赖

```bash
pip install requests python-dotenv PySocks
```

**注意**: `PySocks` 是测试 socks5 代理的必需库，不是可选的。

## 配置

在项目根目录或当前目录创建 `.env` 文件，配置 FOFA API 凭据：

```env
# FOFA API 配置
FOFA_USER_AGENT=your_user_agent_here
FOFA_API_KEY=your_api_key
```

## 使用方法

### 1. 基础扫描（推荐）

只搜索不测试，快速获取代理列表：

```bash
# 默认爬取10页（每页10条）
python fofa_socks5_scanner.py

# 爬取更多页
python fofa_socks5_scanner.py -page 50
```

这会生成两个文件：
- `socks5_proxies_raw.txt` - 原始代理列表
- `socks5_proxies.txt` - 与原始列表相同（未测试）

### 2. 测试代理连通性

测试基本连接（访问百度测试）：

```bash
# 爬取10页并测试基本连通性
python fofa_socks5_scanner.py -page 10
```

**注意**: 由于大多数公开代理不可用，测试过程可能较慢，成功率低。

### 3. 验证特定网站访问

测试代理是否能访问特定网站：

```bash
# 测试能否访问百度（推荐使用HTTP）
python fofa_socks5_scanner.py -page 10 -check "http://www.baidu.com" -checkWords "百度"

# 也可以使用HTTPS，但可能成功率更低
python fofa_socks5_scanner.py -page 10 -check "https://www.baidu.com" -checkWords "百度"

# 测试能否访问其他网站
python fofa_socks5_scanner.py -page 20 -check "http://httpbin.org/ip" -checkWords "origin"
```

**提示**: 
- HTTP 通常比 HTTPS 成功率更高
- 选择常见的关键词，避免太严格（如 "百度" 比 "百度一下，你就知道" 更好）

### 4. 指定输出文件

```bash
python fofa_socks5_scanner.py -page 30 -o my_proxies.txt
```

### 5. 调整并发数

```bash
# 使用20个线程并发测试（加快速度）
python fofa_socks5_scanner.py -page 10 --max-workers 20
```

## 测试单个代理

使用提供的测试工具验证单个代理：

```bash
python test_single_proxy.py <IP> <端口>

# 示例
python test_single_proxy.py 222.138.59.70 5555
```

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-page` | FOFA 结果爬取页数（每页 10 条） | 10 |
| `-check` | 验证代理的目标URL | 无（不测试） |
| `-checkWords` | URL返回内容应包含的关键词 | 无 |
| `--max-workers` | 并发测试线程数 | 10 |
| `-o, --output` | 输出文件路径 | socks5_proxies.txt |

## 输出文件

程序会生成两个文件：

1. **原始结果文件** (`socks5_proxies_raw.txt`):
   - 包含所有从 FOFA 搜索到的代理
   - 未经过连通性测试
   - 每行一个 IP:端口

2. **最终结果文件** (`socks5_proxies.txt`):
   - 如果使用了 `-check` 参数，则只包含测试通过的代理
   - 如果未使用 `-check` 参数，则与原始结果相同
   - 每行一个 IP:端口

## FOFA 搜索语句

程序使用的固定搜索语句：

```
protocol=="socks5" && "Version:5 Method:No Authentication(0x00)" && country="CN"
```

含义：
- `protocol=="socks5"`: 协议为 socks5
- `"Version:5 Method:No Authentication(0x00)"`: 版本5，无需认证
- `country="CN"`: 中国地区

## 使用场景

### 1. 快速收集代理列表（推荐）

不进行连通性测试，快速收集大量代理IP用于后续分析：

```bash
python fofa_socks5_scanner.py -page 100 -o all_proxies.txt
```

### 2. 寻找可用代理

小批量爬取并严格测试（注意：成功率可能很低）：

```bash
python fofa_socks5_scanner.py -page 20 --max-workers 20
```

### 3. 特定网站测试

测试哪些代理能访问特定服务：

```bash
python fofa_socks5_scanner.py -page 30 -check "http://example.com" -checkWords "关键词"
```

## 实际测试结果

根据实际测试，从 FOFA 搜索的 socks5 代理：

- ✅ **能搜索到**: 约 9,000+ 个公开代理
- ⚠️ **能连接但不传输数据**: 约 40-60%
- ✅ **真正可用**: 通常 3-8% (使用HTTP测试)
- 🐌 **响应速度**: 可用的代理通常延迟 150-500ms

**典型错误**:
- `Connection not allowed by ruleset` - 代理规则限制（最常见）
- `Connection closed unexpectedly` - 代理关闭连接
- `连接超时` - 代理不响应
- `连接重置` - 代理拒绝连接
- `HTTP 200但无关键词` - 能访问但返回内容不符

**成功案例**:
```
测试命令: python fofa_socks5_scanner.py -page 2 -check "http://www.baidu.com" -checkWords "百度"
结果: 20个代理中找到1个可用 (5%成功率)
可用代理: 222.138.59.70:5555 (278ms响应时间)
```

## 故障排查

### "未找到 FOFA_USER_AGENT 环境变量"

确保在 `.env` 文件中配置了 `FOFA_USER_AGENT`。

### "未找到 FOFA_API_KEY 环境变量"

确保在 `.env` 文件中配置了 `FOFA_API_KEY`。

### "No module named 'socks'"

需要安装 PySocks：

```bash
pip install PySocks
```

### 搜索结果为空

- 检查 FOFA API 配置是否正确
- 检查 API 配额是否用尽
- 尝试减少爬取页数

### 所有代理测试都失败

这是正常的！公开的 socks5 代理大多数不可用。建议：
- 增加爬取页数 (`-page` 参数)
- 不进行测试，直接使用原始列表
- 使用其他代理来源或付费服务

## 代理使用示例

获取代理后，可以这样使用：

### Python requests

```python
import requests

proxies = {
    'http': 'socks5://222.138.59.70:5555',
    'https': 'socks5://222.138.59.70:5555'
}

response = requests.get('http://example.com', proxies=proxies, timeout=10)
print(response.text)
```

### curl

```bash
curl --socks5 222.138.59.70:5555 http://example.com
```

## 高级用法

### 批量测试已有代理列表

```python
#!/usr/bin/env python3
import sys
from fofa_socks5_scanner import FofaSocks5Scanner

# 读取代理列表
with open('my_proxies.txt', 'r') as f:
    proxies = [line.strip() for line in f if line.strip()]

# 创建扫描器（不搜索，只测试）
scanner = FofaSocks5Scanner(
    check_url="https://www.baidu.com",
    check_words="百度"
)

# 测试代理
working = scanner.test_all_proxies(proxies)
scanner.save_results(working)
```

## 参考

- 参考实现: [port2380scan.py](../../mytest/2380/port2380scan.py)
- FOFA 官网: https://fofa.info
- FOFA API 文档: https://fofa.info/api
- PySocks 文档: https://github.com/Anorov/PySocks

## 许可证

与项目保持一致
