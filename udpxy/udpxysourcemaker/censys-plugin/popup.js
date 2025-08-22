// Censys UDPXY 提取器 - 双模式版本
let extractedData = [];
let ipList = [];
let hostCache = [];
let connected = false;
let currentMode = 'unknown'; // 'search', 'host', 'unknown'

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 插件界面已加载');
    
    // 绑定事件处理器
    setupEventHandlers();
    
    // 检测页面类型和连接状态
    detectPageType();
    
    // 加载保存的数据
    loadSavedData();
});

function setupEventHandlers() {
    // 连接按钮
    document.getElementById('connectBtn').addEventListener('click', connectToPage);
    
    // 搜索页面模式按钮
    document.getElementById('extractIPsBtn').addEventListener('click', extractIPsFromSearch);
    document.getElementById('downloadIPsBtn').addEventListener('click', downloadIPList);
    
    // 主机详情模式按钮
    document.getElementById('autoCollectBtn').addEventListener('click', toggleAutoCollect);
    document.getElementById('downloadCSVBtn').addEventListener('click', downloadHostCSV);
    document.getElementById('clearCacheBtn').addEventListener('click', clearHostCache);
    document.getElementById('viewStatsBtn').addEventListener('click', viewDetailedStats);
}

async function detectPageType() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (!tab || !tab.url) {
            updatePageTypeDisplay('无法检测页面类型');
            return;
        }
        
        const url = tab.url;
        
        if (url.includes('search.censys.io') || url.includes('platform.censys.io/search')) {
            currentMode = 'search';
            updatePageTypeDisplay('🔍 搜索页面模式');
            showSearchMode();
            // 自动连接
            await connectToPage();
        } else if (url.includes('platform.censys.io/hosts/') && url.match(/\/hosts\/[\d.]+/)) {
            currentMode = 'host';
            updatePageTypeDisplay('🖥️ 主机详情模式');
            showHostMode();
            // 自动连接
            await connectToPage();
        } else {
            currentMode = 'unknown';
            updatePageTypeDisplay('❓ 未识别的页面类型');
            hideAllModes();
        }
    } catch (error) {
        console.error('检测页面类型失败:', error);
        updatePageTypeDisplay('页面检测失败');
    }
}

function updatePageTypeDisplay(text) {
    const display = document.getElementById('pageTypeDisplay');
    if (display) {
        display.textContent = text;
    }
}

function showSearchMode() {
    document.getElementById('searchMode').style.display = 'block';
    document.getElementById('hostMode').style.display = 'none';
}

function showHostMode() {
    document.getElementById('searchMode').style.display = 'none';
    document.getElementById('hostMode').style.display = 'block';
}

function hideAllModes() {
    document.getElementById('searchMode').style.display = 'none';
    document.getElementById('hostMode').style.display = 'none';
}

async function connectToPage() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        
        if (!tab) {
            showStatus('❌ 无法获取当前标签页', 'error');
            return;
        }
        
        showStatus('🔗 正在连接到页面...', 'info');
        
        // 尝试ping content script
        const response = await sendMessageWithRetry({ action: 'ping' }, 3);
        
        if (response && response.success) {
            connected = true;
            showStatus('✅ 已成功连接到页面', 'success');
            document.getElementById('connectionStatus').textContent = '已连接';
            document.getElementById('connectionStatus').className = 'status success';
            
            // 连接成功后同步自动收集状态
            await syncAutoCollectState();
            
            updateButtonStates();
        } else {
            throw new Error('连接失败');
        }
    } catch (error) {
        console.error('连接失败:', error);
        connected = false;
        showStatus('❌ 连接失败，请刷新页面后重试', 'error');
        document.getElementById('connectionStatus').textContent = '连接失败';
        document.getElementById('connectionStatus').className = 'status error';
    }
}

// 同步自动收集状态到content script
async function syncAutoCollectState() {
    try {
        const result = await new Promise(resolve => {
            chrome.storage.local.get(['autoCollectEnabled'], resolve);
        });
        
        const autoCollectEnabled = result.autoCollectEnabled || false;
        
        if (autoCollectEnabled) {
            console.log('同步自动收集状态:', autoCollectEnabled);
            await sendMessageWithRetry({ 
                action: 'enableAutoCollect', 
                enabled: autoCollectEnabled 
            }, 1);
        }
    } catch (error) {
        console.warn('同步自动收集状态失败:', error);
    }
}

// 搜索页面功能 - 提取IP列表
async function extractIPsFromSearch() {
    if (!connected) {
        showStatus('❌ 请先连接到页面', 'error');
        return;
    }
    
    if (currentMode !== 'search') {
        showStatus('❌ 此功能仅在搜索页面可用', 'error');
        return;
    }
    
    try {
        showStatus('🔍 正在提取IP列表...', 'info');
        
        const response = await sendMessageWithRetry({ action: 'extractIPs' }, 3);
        
        if (response && response.success && response.ips) {
            const newIPs = response.ips.filter(ip => !ipList.includes(ip));
            ipList = [...ipList, ...newIPs]; // 去重合并
            saveDataToStorage();
            updateStats();
            showStatus(`✅ 成功提取 ${newIPs.length} 个新IP，总计 ${ipList.length} 个`, 'success');
            document.getElementById('downloadIPsBtn').disabled = false;
        } else {
            showStatus('❌ 未找到IP地址', 'error');
        }
    } catch (error) {
        console.error('提取IP失败:', error);
        showStatus('❌ 提取IP失败', 'error');
    }
}

// 主机详情功能 - 收集主机数据
async function collectHostData() {
    if (!connected) {
        showStatus('❌ 请先连接到页面', 'error');
        return;
    }
    
    if (currentMode !== 'host') {
        showStatus('❌ 此功能仅在主机详情页面可用', 'error');
        return;
    }
    
    try {
        showStatus('🖥️ 正在收集主机数据...', 'info');
        
        const response = await sendMessageWithRetry({ action: 'extractHostData' }, 3);
        
        if (response && response.success && response.hostData) {
            handleCollectedHostData(response.hostData, '手动');
        } else {
            showStatus('❌ 无法收集主机数据', 'error');
        }
    } catch (error) {
        console.error('收集主机数据失败:', error);
        showStatus('❌ 收集主机数据失败', 'error');
    }
}

// 切换自动收集模式
async function toggleAutoCollect() {
    try {
        // 获取当前状态
        const result = await new Promise(resolve => {
            chrome.storage.local.get(['autoCollectEnabled'], resolve);
        });
        
        const currentState = result.autoCollectEnabled || false;
        const newState = !currentState;
        
        // 保存新状态
        chrome.storage.local.set({ autoCollectEnabled: newState });
        
        // 更新按钮状态
        updateAutoCollectButton(newState);
        
        showStatus(`${newState ? '✅ 已启用' : '❌ 已禁用'}自动收集模式`, 'success');
        showStatus('💡 刷新页面后生效，或直接使用页面上的浮动按钮', 'info');
        
    } catch (error) {
        console.error('切换自动收集模式失败:', error);
        showStatus('❌ 设置失败', 'error');
    }
}

// 处理收集到的主机数据（通用函数）
function handleCollectedHostData(hostData, source = '手动') {
    // 检查是否已存在相同IP的数据
    const existingIndex = hostCache.findIndex(item => item.ip === hostData.ip);
    if (existingIndex !== -1) {
        hostCache[existingIndex] = hostData; // 更新现有数据
        showStatus(`🔄 已更新主机 ${hostData.ip} 的数据 (${source})`, 'success');
    } else {
        hostCache.push(hostData); // 添加新数据
        showStatus(`✅ 已收集主机 ${hostData.ip} 的数据 (${source})`, 'success');
    }
    
    saveDataToStorage();
    updateStats();
    document.getElementById('downloadCSVBtn').disabled = false;
}

// 处理自动收集的数据
function handleAutoCollectedData(hostData) {
    handleCollectedHostData(hostData, '自动');
}

// 下载IP列表
function downloadIPList() {
    if (ipList.length === 0) {
        showStatus('❌ 没有IP数据可下载', 'error');
        return;
    }
    
    const content = ipList.join('\n');
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `censys_ips_${timestamp}.txt`;
    
    downloadFile(content, filename, 'text/plain');
    showStatus(`💾 已下载 ${ipList.length} 个IP到 ${filename}`, 'success');
}

// 下载主机CSV
function downloadHostCSV() {
    if (hostCache.length === 0) {
        showStatus('❌ 没有主机数据可下载', 'error');
        return;
    }
    
    // CSV头部 - 与censys.py保持一致
    const headers = ['ip', 'port', 'url', 'dns', 'country', 'city', 'province', 'isp'];
    let csvContent = headers.join(',') + '\n';
    
    // 处理每个主机的数据
    hostCache.forEach(host => {
        if (host.ports && host.ports.length > 0) {
            // 为每个端口创建一行
            host.ports.forEach(port => {
                const row = [
                    host.ip || '',
                    port || '',
                    `http://${host.ip}:${port}` || '',
                    host.dns || '',
                    host.country || '',
                    host.city || '',
                    host.province || '',
                    host.isp || ''
                ];
                csvContent += row.map(field => `"${String(field).replace(/"/g, '""')}"`).join(',') + '\n';
            });
        } else {
            // 如果没有端口信息，创建一行基础数据
            const row = [
                host.ip || '',
                '',
                '',
                host.dns || '',
                host.country || '',
                host.city || '',
                host.province || '',
                host.isp || ''
            ];
            csvContent += row.map(field => `"${String(field).replace(/"/g, '""')}"`).join(',') + '\n';
        }
    });
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = `censys_hosts_${timestamp}.csv`;
    
    downloadFile(csvContent, filename, 'text/csv');
    showStatus(`💾 已导出 ${hostCache.length} 个主机数据到 ${filename}`, 'success');
}

// 清空主机缓存
function clearHostCache() {
    if (confirm('确认要清空所有收集的主机数据吗？')) {
        hostCache = [];
        saveDataToStorage();
        updateStats();
        updateButtonStates();
        showStatus('✅ 已清空主机缓存', 'success');
    }
}

// 查看详细统计
function viewDetailedStats() {
    const statsWindow = window.open('', '_blank', 'width=600,height=500,scrollbars=yes');
    
    // 生成详细统计报告
    let html = `
    <!DOCTYPE html>
    <html>
    <head>
        <title>Censys UDPXY 提取器 - 详细统计</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; margin-bottom: 30px; }
            .section { margin-bottom: 30px; }
            .section h2 { color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 5px; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { padding: 8px 12px; text-align: left; border: 1px solid #ddd; }
            th { background: #f8f9fa; font-weight: 600; }
            tr:nth-child(even) { background: #f8f9fa; }
            .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
            .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }
            .stat-number { font-size: 24px; font-weight: bold; margin-bottom: 5px; }
            .stat-label { font-size: 14px; opacity: 0.9; }
            .export-btn { background: #28a745; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; }
            .export-btn:hover { background: #218838; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎯 Censys UDPXY 提取器 - 详细统计报告</h1>
            
            <div class="section">
                <h2>📊 总体统计</h2>
                <div class="stat-grid">
                    <div class="stat-card">
                        <div class="stat-number">${ipList.length}</div>
                        <div class="stat-label">IP列表总数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${hostCache.length}</div>
                        <div class="stat-label">主机缓存总数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${hostCache.filter(h => h.ports && h.ports.length > 0).length}</div>
                        <div class="stat-label">有UDPXY服务的主机</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">${hostCache.reduce((total, h) => total + (h.ports ? h.ports.length : 0), 0)}</div>
                        <div class="stat-label">UDPXY端口总数</div>
                    </div>
                </div>
            </div>
    `;
    
    if (hostCache.length > 0) {
        html += `
            <div class="section">
                <h2>🖥️ 主机详情列表</h2>
                <button class="export-btn" onclick="exportTableToCSV()">💾 导出CSV</button>
                <table id="hostTable">
                    <thead>
                        <tr>
                            <th>IP地址</th>
                            <th>DNS</th>
                            <th>国家</th>
                            <th>城市</th>
                            <th>省份</th>
                            <th>ISP</th>
                            <th>UDPXY端口</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        hostCache.forEach(host => {
            html += `
                <tr>
                    <td>${host.ip || ''}</td>
                    <td>${host.dns || ''}</td>
                    <td>${host.country || ''}</td>
                    <td>${host.city || ''}</td>
                    <td>${host.province || ''}</td>
                    <td>${host.isp || ''}</td>
                    <td>${(host.ports && host.ports.length > 0) ? host.ports.join(', ') : '无'}</td>
                </tr>
            `;
        });
        
        html += `
                    </tbody>
                </table>
            </div>
        `;
    }
    
    if (ipList.length > 0) {
        html += `
            <div class="section">
                <h2>📋 IP列表</h2>
                <button class="export-btn" onclick="exportIPList()">💾 导出TXT</button>
                <div style="max-height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; background: #f8f9fa; font-family: monospace;">
                    ${ipList.map(ip => `<div>${ip}</div>`).join('')}
                </div>
            </div>
        `;
    }
    
    html += `
            <div class="section">
                <h2>ℹ️ 使用说明</h2>
                <ul>
                    <li><strong>自动收集：</strong>启用后访问主机页面会自动收集数据</li>
                    <li><strong>页面按钮：</strong>在Censys页面上会显示浮动按钮，可直接操作</li>
                    <li><strong>数据导出：</strong>支持CSV格式，与censys.py脚本兼容</li>
                    <li><strong>持久化：</strong>所有数据会自动保存，关闭浏览器后不会丢失</li>
                </ul>
            </div>
        </div>
        
        <script>
            function exportTableToCSV() {
                const headers = ['ip', 'port', 'url', 'dns', 'country', 'city', 'province', 'isp'];
                const hostData = ${JSON.stringify(hostCache)};
                
                let csvContent = headers.join(',') + '\n';
                
                hostData.forEach(host => {
                    if (host.ports && host.ports.length > 0) {
                        host.ports.forEach(port => {
                            const row = [
                                host.ip || '',
                                port || '',
                                'http://' + host.ip + ':' + port || '',
                                host.dns || '',
                                host.country || '',
                                host.city || '',
                                host.province || '',
                                host.isp || ''
                            ];
                            csvContent += row.map(field => '"' + String(field).replace(/"/g, '""') + '"').join(',') + '\n';
                        });
                    } else {
                        const row = [
                            host.ip || '', '', '', host.dns || '', host.country || '', 
                            host.city || '', host.province || '', host.isp || ''
                        ];
                        csvContent += row.map(field => '"' + String(field).replace(/"/g, '""') + '"').join(',') + '\n';
                    }
                });
                
                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement('a');
                const url = URL.createObjectURL(blob);
                link.setAttribute('href', url);
                link.setAttribute('download', 'censys_data_' + new Date().toISOString().replace(/[:.]/g, '-') + '.csv');
                link.click();
            }
            
            function exportIPList() {
                const ipData = ${JSON.stringify(ipList)};
                const content = ipData.join('\n');
                const blob = new Blob([content], { type: 'text/plain;charset=utf-8;' });
                const link = document.createElement('a');
                const url = URL.createObjectURL(blob);
                link.setAttribute('href', url);
                link.setAttribute('download', 'censys_ips_' + new Date().toISOString().replace(/[:.]/g, '-') + '.txt');
                link.click();
            }
        </script>
    </body>
    </html>
    `;
    
    statsWindow.document.write(html);
    statsWindow.document.close();
}

// 通用下载函数
function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    
    chrome.downloads.download({
        url: url,
        filename: filename,
        saveAs: false
    }, (downloadId) => {
        if (chrome.runtime.lastError) {
            console.error('下载失败:', chrome.runtime.lastError);
            showStatus('❌ 下载失败', 'error');
        } else {
            console.log('下载开始，ID:', downloadId);
        }
        URL.revokeObjectURL(url);
    });
}

// 发送消息并重试
async function sendMessageWithRetry(message, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            
            // 检查是否需要注入内容脚本
            try {
                await chrome.tabs.sendMessage(tab.id, { action: 'ping' });
            } catch (pingError) {
                console.log(`尝试 ${i + 1}: 注入内容脚本`);
                await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    files: ['content.js']
                });
                // 等待脚本加载
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
            
            const response = await chrome.tabs.sendMessage(tab.id, message);
            return response;
        } catch (error) {
            console.warn(`消息发送失败 (尝试 ${i + 1}/${maxRetries}):`, error);
            if (i === maxRetries - 1) {
                throw error;
            }
            await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
        }
    }
}

// 保存数据到存储
function saveDataToStorage() {
    chrome.storage.local.set({
        ipList: ipList,
        hostCache: hostCache
    });
}

// 加载保存的数据
function loadSavedData() {
    chrome.storage.local.get(['ipList', 'hostCache', 'autoCollectEnabled'], (result) => {
        if (result.ipList) {
            ipList = result.ipList;
        }
        if (result.hostCache) {
            hostCache = result.hostCache;
        }
        
        // 加载自动收集设置
        const autoCollectEnabled = result.autoCollectEnabled || false;
        updateAutoCollectButton(autoCollectEnabled);
        
        updateStats();
        updateButtonStates();
    });
}

// 更新自动收集按钮状态
function updateAutoCollectButton(enabled) {
    const button = document.getElementById('autoCollectBtn');
    if (button) {
        if (enabled) {
            button.textContent = '🟢 自动收集已启用';
            button.classList.add('active');
        } else {
            button.textContent = '🤖 自动收集模式';
            button.classList.remove('active');
        }
    }
}

// 更新统计信息
function updateStats() {
    document.getElementById('ipCount').textContent = ipList.length;
    document.getElementById('hostCount').textContent = hostCache.length;
}

// 更新按钮状态
function updateButtonStates() {
    document.getElementById('downloadIPsBtn').disabled = ipList.length === 0;
    document.getElementById('downloadCSVBtn').disabled = hostCache.length === 0;
}

// 显示状态信息
function showStatus(message, type = 'info') {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;
    
    // 3秒后清除状态
    setTimeout(() => {
        statusDiv.textContent = '';
        statusDiv.className = 'status';
    }, 3000);
}
