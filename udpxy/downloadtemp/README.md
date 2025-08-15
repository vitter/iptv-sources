# IPTV组播文件下载器

## 功能说明

从 https://chinaiptv.pages.dev/ 网站下载三大运营商的组播文件，并按要求处理生成模板文件和配置文件。

## 核心功能

### 1. 智能下载
- 自动解析网站文件列表
- 支持代理访问（HTTP/HTTPS/SOCKS5）
- URL去重避免重复下载
- 文件名去重避免重复处理
- 容错处理和超时控制

### 2. 内容处理
- 过滤保留有流媒体URL的行
- 转换流媒体URL格式：`rtp://` → `http://ipipip/udp/`
- 提取第一个流媒体URL作为配置

### 3. 智能分类
- 自动识别运营商（Mobile/Telecom/Unicom）
- 自动识别省份名称
- 按运营商目录生成模板文件

### 4. 配置生成
- 生成三个运营商的配置文件
- 标准格式：`city file stream`

## 使用方法

### 基本用法
```bash
# 直接下载（可能需要代理）
python3 download.py

# 使用HTTP代理
python3 download.py --proxy http://127.0.0.1:7890

# 使用SOCKS5代理
python3 download.py --proxy socks5://127.0.0.1:1080

# 自定义基础URL
python3 download.py --base-url https://other-site.com/

# 自定义超时时间
python3 download.py --timeout 30
```

### 参数说明
- `--proxy`: 代理服务器地址（HTTP/HTTPS/SOCKS5）
- `--base-url`: 基础URL地址（默认：https://chinaiptv.pages.dev/）
- `--timeout`: 下载超时时间，秒（默认：15）

## 输出结果

### 目录结构
```
├── Mobile/                      # 移动运营商模板目录
│   ├── template_Beijing.txt     # 北京移动模板
│   ├── template_Shanghai.txt    # 上海移动模板
│   └── ...
├── Telecom/                     # 电信运营商模板目录
│   ├── template_Beijing.txt     # 北京电信模板
│   ├── template_Shanghai.txt    # 上海电信模板
│   └── ...
├── Unicom/                      # 联通运营商模板目录
│   ├── template_Beijing.txt     # 北京联通模板
│   ├── template_Shanghai.txt    # 上海联通模板
│   └── ...
├── Mobile_province_list.txt     # 移动配置文件
├── Telecom_province_list.txt    # 电信配置文件
└── Unicom_province_list.txt     # 联通配置文件
```

### 模板文件格式
只保留包含流媒体URL的行，并转换格式：
```
CCTV5,CCTV5体育,http://ipipip/udp/239.253.7.1:1025
CCTV6,CCTV6电影,http://ipipip/udp/239.253.7.2:1025
CCTV13,CCTV13新闻,http://ipipip/udp/239.253.7.5:1025
```

### 配置文件格式
三个字段：`city file stream`
```
city file stream
Beijing Beijing udp/239.253.7.1:1025
Shanghai Shanghai udp/239.253.8.1:1025
Guangdong Guangdong udp/239.253.9.1:1025
```

## 去重机制

### URL去重
- 维护已下载URL集合
- 相同URL只下载一次
- 支持相对URL和绝对URL

### 文件去重
- 维护已处理文件名集合
- 相同文件名只处理一次
- 相同运营商-省份组合会覆盖

### 配置去重
- 相同运营商-省份配置会覆盖旧值
- 确保最新配置生效

## 错误处理

- 网络超时自动重试
- 文件解码错误自动处理
- 无法识别的文件跳过
- 详细的错误日志输出

## 代理支持

### HTTP/HTTPS代理
```bash
python3 download.py --proxy http://127.0.0.1:7890
python3 download.py --proxy https://127.0.0.1:7890
```

### SOCKS代理
```bash
python3 download.py --proxy socks5://127.0.0.1:1080
```

注意：SOCKS代理可能需要安装额外依赖：
```bash
pip install requests[socks]
```

## 统计信息

程序运行结束后会显示详细统计：
- 总文件数和处理成功数
- 跳过的重复文件数
- 各运营商的省份配置数量
- URL去重和文件去重统计

## 注意事项

1. 确保有网络连接，某些地区可能需要代理
2. 程序会自动创建目录结构
3. 同名文件会被覆盖
4. 建议在空目录中运行
5. 文件名需要包含运营商和省份关键字

## 依赖要求

- Python 3.6+
- requests库
- 可选：requests[socks]（用于SOCKS代理）
