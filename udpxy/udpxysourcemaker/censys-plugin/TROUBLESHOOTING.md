# 🔧 Censys UDPXY Extractor - 故障排除指南

## ❌ 常见错误及解决方案

### 1. "Could not establish connection. Receiving end does not exist."

这是最常见的错误，表示内容脚本没有正确加载或通信失败。

#### 解决步骤：

**步骤1: 检查页面URL**
- ✅ 确保在正确的Censys页面：`https://platform.censys.io/*`
- ✅ 不要在 `censys.com` 主页或其他子域使用

**步骤2: 重新加载扩展**
1. 打开 `chrome://extensions/`
2. 找到 "Censys UDPXY Extractor"
3. 点击 🔄 刷新按钮
4. 确保扩展状态为 **已启用**

**步骤3: 刷新Censys页面**
1. 在Censys页面按 `F5` 或 `Ctrl+R`
2. 等待页面完全加载
3. 重新尝试扩展功能

**步骤4: 检查开发者工具**
1. 在Censys页面按 `F12` 打开开发者工具
2. 切换到 **Console** 标签
3. 查找 `[Censys Extractor]` 开头的日志
4. 如果没有日志，说明内容脚本未加载

**步骤5: 手动注入脚本**
扩展现在支持自动重试和手动注入：
1. 点击扩展图标
2. 如果看到 "🔄 Content script not ready. Injecting..."
3. 等待自动注入完成
4. 重新尝试功能

### 2. "Please navigate to Censys search page first"

#### 解决方案：
- ❌ 错误URL示例：`https://censys.com/`, `https://censys.io/`
- ✅ 正确URL示例：`https://platform.censys.io/search`, `https://platform.censys.io/hosts/`

### 3. 扩展图标点击无反应

#### 检查清单：
- [ ] 扩展是否正确安装？
- [ ] 开发者模式是否启用？
- [ ] 是否在支持的网站？
- [ ] 是否有错误消息在扩展管理页面？

#### 解决步骤：
1. **重新安装扩展**：
   - 删除现有扩展
   - 重新加载文件夹
   
2. **检查文件完整性**：
   ```bash
   ls -la /path/to/censys-plugin/
   # 应该看到所有必需文件
   ```

3. **检查权限**：
   - 确保文件有读取权限
   - 确保Chrome可以访问文件夹

### 4. 数据提取结果为空

#### 可能原因：
- 页面内容加载不完整
- 页面结构发生变化
- 搜索结果实际为空

#### 解决步骤：

**检查页面内容**：
1. 确保页面显示搜索结果
2. 手动查看是否有IP地址显示
3. 等待页面完全加载

**尝试不同提取模式**：
1. 🔍 **详情页面模式** - 在具体IP页面使用
2. 📊 **当前页面模式** - 在搜索结果列表使用
3. 🤖 **自动搜索模式** - 让扩展自动执行搜索

**手动验证**：
1. 打开开发者工具 (F12)
2. Console中输入：`document.body.textContent.includes('udpxy')`
3. 如果返回 `false`，说明页面确实没有相关内容

### 5. 下载功能不工作

#### 解决步骤：

**检查浏览器设置**：
1. Chrome设置 → 高级 → 下载内容
2. 确保下载位置可写
3. 检查是否阻止了下载

**权限问题**：
1. 确保扩展有下载权限
2. 在 `chrome://extensions/` 中检查权限列表

**手动下载**：
1. 开发者工具 → Console
2. 复制提取的数据
3. 手动保存为文件

### 6. 自动搜索中断

#### 常见原因：
- 网络连接问题
- Censys页面响应慢
- 搜索结果页面结构变化

#### 解决方案：

**降低搜索强度**：
- 减少maxPages参数
- 增加等待时间
- 分批次执行

**检查网络**：
- 确保网络连接稳定
- 避免在网络高峰期使用

**分步操作**：
1. 先手动执行搜索
2. 使用单页提取模式
3. 逐个IP手动访问详情页

## 🔍 调试模式

### 启用详细日志

**在Censys页面按F12**：
```javascript
// 启用详细日志
window.censysExtractorDebug = true;

// 检查扩展状态
console.log('Extension loaded:', window.censysExtractorLoaded);

// 手动触发提取
if (window.extractor) {
    const results = window.extractor.extractFromCurrentPage();
    console.log('Manual extraction results:', results);
}
```

### 手动测试通信

**在popup页面测试**：
```javascript
// 在扩展popup中打开开发者工具
// 手动发送消息测试
chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    chrome.tabs.sendMessage(tabs[0].id, {action: 'ping'}, function(response) {
        console.log('Ping response:', response);
    });
});
```

## 🆘 获取支持

### 收集错误信息

当遇到问题时，请收集以下信息：

1. **Chrome版本**：`chrome://version/`
2. **扩展版本**：在扩展管理页面查看
3. **错误页面URL**：当前出错的页面地址
4. **控制台日志**：F12 → Console的完整输出
5. **具体操作步骤**：详细描述如何重现问题

### 临时解决方案

**如果扩展完全无法工作**：
1. 使用手动复制粘贴方案
2. 回退到Python脚本方案
3. 等待扩展更新

**数据备份**：
- 及时保存已提取的数据
- 使用多种格式备份
- 记录提取时间和来源

---

**💡 提示**：大多数连接问题都可以通过重新加载扩展和刷新页面来解决。如果问题持续存在，可能是Censys网站结构发生了变化，需要更新扩展代码。
