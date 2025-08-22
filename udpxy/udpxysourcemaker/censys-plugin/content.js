// Censys UDPXY 提取器 - 内容脚本 (双模式版本)
console.log('🚀 Censys UDPXY 提取器内容脚本已加载 - 双模式版本');

// 全局变量
let autoCollectEnabled = false;
let pageLoadTimer = null;
let floatingButton = null;
let statusIndicator = null;
let extensionContextValid = true;
let searchPageAutoCollected = false; // 防止搜索页面重复自动收集
let hostPageAutoCollected = false; // 防止主机页面重复自动收集

// 检查扩展上下文是否有效
function isExtensionContextValid() {
    try {
        // 基本检查：chrome对象和关键API是否存在
        if (typeof chrome === 'undefined' || !chrome.storage || !chrome.runtime) {
            return false;
        }
        
        // 尝试访问runtime.id - 这是检查上下文有效性的关键
        try {
            const runtimeId = chrome.runtime.id;
            return !!runtimeId; // 确保runtime.id存在且不为空
        } catch (error) {
            // 如果访问runtime.id抛出异常，说明上下文已失效
            return false;
        }
    } catch (error) {
        console.warn('扩展上下文检查失败:', error);
        return false;
    }
}

// 初始化自动收集状态
async function initializeAutoCollectState() {
    try {
        // 检查扩展上下文是否有效
        if (!isExtensionContextValid()) {
            console.warn('扩展上下文无效，使用默认设置');
            autoCollectEnabled = false; // 使用默认值
            createPageUI(); // 仍然创建UI
            return;
        }
        
        // 尝试从存储获取设置
        try {
            const result = await new Promise((resolve, reject) => {
                chrome.storage.local.get(['autoCollectEnabled'], (result) => {
                    if (chrome.runtime.lastError) {
                        reject(new Error(chrome.runtime.lastError.message));
                    } else {
                        resolve(result);
                    }
                });
            });
            
            autoCollectEnabled = result.autoCollectEnabled || false;
            console.log('📋 初始化自动收集状态:', autoCollectEnabled);
        } catch (storageError) {
            console.warn('读取存储设置失败，使用默认值:', storageError);
            autoCollectEnabled = false;
        }
        
        // 创建页面UI元素
        createPageUI();
        
        // 如果启用了自动收集，立即尝试收集并启动监控
        if (autoCollectEnabled) {
            setTimeout(checkAndAutoCollectHostData, 2000);
            startContextMonitoring(); // 启动上下文监控
        }
    } catch (error) {
        console.warn('初始化过程中出错:', error);
        autoCollectEnabled = false;
        createPageUI();
    }
}

// 创建页面UI元素
function createPageUI() {
    // 如果已存在，先移除
    if (floatingButton) {
        floatingButton.remove();
    }
    if (statusIndicator) {
        statusIndicator.remove();
    }
    
    // 检查是否是主机详情页面
    const isHostPage = window.location.href.match(/\/hosts\/([\d.]+)/);
    
    if (isHostPage) {
        createHostPageUI();
    } else if (window.location.href.includes('platform.censys.io/search')) {
        createSearchPageUI();
    }
}

// 创建主机页面UI
function createHostPageUI() {
    // 创建浮动按钮容器
    const container = document.createElement('div');
    container.id = 'censys-extractor-container';
    container.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 10000;
        display: flex;
        flex-direction: column;
        gap: 8px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    `;
    
    // 创建状态指示器
    statusIndicator = document.createElement('div');
    statusIndicator.style.cssText = `
        background: ${autoCollectEnabled ? '#28a745' : '#6c757d'};
        color: white;
        padding: 8px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        text-align: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        cursor: pointer;
        transition: all 0.3s ease;
        user-select: none;
    `;
    statusIndicator.textContent = autoCollectEnabled ? '🟢 自动收集已启用' : '🔴 自动收集已禁用';
    statusIndicator.title = '点击切换自动收集模式';
    statusIndicator.onclick = toggleAutoCollectFromPage;
    
    // 创建手动收集按钮
    const collectButton = document.createElement('button');
    collectButton.style.cssText = `
        background: linear-gradient(45deg, #007bff, #0056b3);
        color: white;
        border: none;
        padding: 10px 16px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
        user-select: none;
    `;
    collectButton.textContent = '📊 收集数据';
    collectButton.title = '手动收集当前主机数据';
    collectButton.onclick = collectDataFromPage;
    collectButton.onmouseover = () => {
        collectButton.style.transform = 'translateY(-2px)';
        collectButton.style.boxShadow = '0 4px 15px rgba(0,0,0,0.3)';
    };
    collectButton.onmouseout = () => {
        collectButton.style.transform = 'translateY(0)';
        collectButton.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
    };
    
    // 创建统计显示
    const statsDiv = document.createElement('div');
    statsDiv.id = 'censys-stats';
    statsDiv.style.cssText = `
        background: rgba(0,0,0,0.8);
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 11px;
        text-align: center;
        backdrop-filter: blur(10px);
    `;
    updateStatsDisplay(statsDiv);
    
    container.appendChild(statusIndicator);
    container.appendChild(collectButton);
    container.appendChild(statsDiv);
    
    document.body.appendChild(container);
    floatingButton = container;
}

// 创建搜索页面UI
function createSearchPageUI() {
    const container = document.createElement('div');
    container.id = 'censys-extractor-container';
    container.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 10000;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        display: flex;
        flex-direction: column;
        gap: 10px;
    `;
    
    const extractButton = document.createElement('button');
    extractButton.style.cssText = `
        background: linear-gradient(45deg, #28a745, #20c997);
        color: white;
        border: none;
        padding: 10px 16px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
        user-select: none;
    `;
    extractButton.textContent = '📋 提取IP列表';
    extractButton.title = '从搜索结果提取IP列表';
    extractButton.onclick = extractIPsFromPage;
    
    // 创建提取端口按钮（保留手动提取功能）
    const extractPortsButton = document.createElement('div');
    extractPortsButton.style.cssText = `
        background: linear-gradient(45deg, #fd7e14, #e83e8c);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 15px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
        user-select: none;
    `;
    extractPortsButton.textContent = '🔌 手动提取端口';
    extractPortsButton.title = '手动从搜索结果提取IP和HTTP/HTTPS端口';
    extractPortsButton.onclick = extractPortsFromPage;
    
    // 创建下载CSV按钮
    const downloadCsvButton = document.createElement('div');
    downloadCsvButton.style.cssText = `
        background: linear-gradient(45deg, #007bff, #0056b3);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 15px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        transition: all 0.3s ease;
        user-select: none;
    `;
    downloadCsvButton.textContent = '� 导出CSV';
    downloadCsvButton.title = '下载已收集的搜索数据CSV文件';
    downloadCsvButton.onclick = downloadSearchResultsCSV;
    
    // 创建自动收集状态指示器
    const statusIndicator = document.createElement('div');
    statusIndicator.id = 'search-auto-collect-status';
    statusIndicator.style.cssText = `
        background: ${autoCollectEnabled ? '#28a745' : '#6c757d'};
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 12px;
        text-align: center;
        cursor: pointer;
        user-select: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    `;
    statusIndicator.textContent = autoCollectEnabled ? '🟢 自动收集已启用' : '🔴 自动收集已禁用';
    statusIndicator.title = '点击切换自动收集模式';
    statusIndicator.onclick = toggleAutoCollectFromPage;
    
    // 创建统计显示
    const statsDiv = document.createElement('div');
    statsDiv.id = 'censys-search-stats';
    statsDiv.style.cssText = `
        background: rgba(0,0,0,0.8);
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 11px;
        text-align: center;
        backdrop-filter: blur(10px);
    `;
    updateSearchStatsDisplay(statsDiv);
    
    container.appendChild(statusIndicator);
    container.appendChild(extractButton);
    container.appendChild(extractPortsButton);
    container.appendChild(downloadCsvButton);
    container.appendChild(statsDiv);
    document.body.appendChild(container);
    floatingButton = container;
}

// 更新统计显示
async function updateStatsDisplay(statsDiv) {
    try {
        // 检查扩展上下文是否有效
        if (!chrome.storage) {
            statsDiv.textContent = '扩展上下文无效';
            return;
        }
        
        const result = await new Promise((resolve, reject) => {
            chrome.storage.local.get(['hostCache'], (result) => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    resolve(result);
                }
            });
        });
        
        const hostCache = result.hostCache || [];
        statsDiv.textContent = `已收集: ${hostCache.length} 个主机`;
    } catch (error) {
        console.warn('获取统计数据失败:', error);
        statsDiv.textContent = '统计加载失败';
    }
}

// 页面切换自动收集模式
async function toggleAutoCollectFromPage() {
    try {
        // 检查扩展上下文是否有效
        if (!chrome.storage) {
            showPageNotification('扩展上下文无效，请刷新页面', 'error');
            return;
        }
        
        const result = await new Promise((resolve, reject) => {
            chrome.storage.local.get(['autoCollectEnabled'], (result) => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    resolve(result);
                }
            });
        });
        
        const newState = !result.autoCollectEnabled;
        
        // 保存新状态
        await new Promise((resolve, reject) => {
            chrome.storage.local.set({ autoCollectEnabled: newState }, () => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    resolve();
                }
            });
        });
        
        autoCollectEnabled = newState;
        
        // 更新UI
        if (statusIndicator) {
            statusIndicator.style.background = newState ? '#28a745' : '#6c757d';
            statusIndicator.textContent = newState ? '🟢 自动收集已启用' : '🔴 自动收集已禁用';
        }
        
        // 显示提示
        showPageNotification(`自动收集模式已${newState ? '启用' : '禁用'}`, newState ? 'success' : 'info');
        
        // 如果启用了自动收集，立即尝试收集当前页面并启动监控
        if (newState) {
            setTimeout(checkAndAutoCollectHostData, 1000);
            startContextMonitoring(); // 启动上下文监控
        }
        
    } catch (error) {
        console.error('切换自动收集模式失败:', error);
        showPageNotification('设置失败: ' + error.message, 'error');
    }
}

// 从页面手动收集数据
async function collectDataFromPage() {
    try {
        showPageNotification('正在收集数据...', 'info');
        
        const hostData = await extractHostDataFromDetailPage();
        
        if (hostData) {
            // 检查扩展上下文是否有效
            const contextValid = isExtensionContextValid();
            
            if (contextValid) {
                // 有效上下文：尝试保存到缓存
                try {
                    const result = await new Promise((resolve, reject) => {
                        chrome.storage.local.get(['hostCache'], (result) => {
                            if (chrome.runtime.lastError) {
                                reject(new Error(chrome.runtime.lastError.message));
                            } else {
                                resolve(result);
                            }
                        });
                    });
                    
                    const hostCache = result.hostCache || [];
                    const existingIndex = hostCache.findIndex(item => item.ip === hostData.ip);
                    
                    if (existingIndex !== -1) {
                        hostCache[existingIndex] = hostData;
                    } else {
                        hostCache.push(hostData);
                    }
                    
                    await new Promise((resolve, reject) => {
                        chrome.storage.local.set({ hostCache: hostCache }, () => {
                            if (chrome.runtime.lastError) {
                                reject(new Error(chrome.runtime.lastError.message));
                            } else {
                                resolve();
                            }
                        });
                    });
                    
                    // 更新统计显示
                    const statsDiv = document.getElementById('censys-stats');
                    if (statsDiv) {
                        updateStatsDisplay(statsDiv);
                    }
                    
                    showPageNotification(`✅ 已收集并保存 ${hostData.ip} 的数据`, 'success');
                } catch (storageError) {
                    console.error('保存数据失败:', storageError);
                    showPageNotification(`📊 已收集 ${hostData.ip} 的数据但保存失败：${storageError.message}`, 'info');
                    console.log('收集到的数据:', hostData);
                }
            } else {
                // 无效上下文：仅显示数据
                console.log('📊 收集到主机数据（无法保存）:', hostData);
                showPageNotification(`📊 已收集 ${hostData.ip} 的数据，但无法保存（扩展上下文无效）`, 'info');
            }
        } else {
            showPageNotification('❌ 收集数据失败', 'error');
        }
        
    } catch (error) {
        console.error('收集数据失败:', error);
        if (error.message && error.message.includes('Extension context invalidated')) {
            showPageNotification('⚠️ 扩展上下文失效，请重新加载扩展', 'error');
        } else {
            showPageNotification('❌ 收集数据失败: ' + error.message, 'error');
        }
    }
}

// 从页面提取IP列表
async function extractIPsFromPage() {
    try {
        // 检查扩展上下文是否有效
        if (!chrome.storage) {
            showPageNotification('扩展上下文无效，请刷新页面', 'error');
            return;
        }
        
        showPageNotification('正在提取IP列表...', 'info');
        
        const ips = await extractIPsFromSearchPage();
        
        if (ips && ips.length > 0) {
            // 保存到缓存
            const result = await new Promise((resolve, reject) => {
                chrome.storage.local.get(['ipList'], (result) => {
                    if (chrome.runtime.lastError) {
                        reject(new Error(chrome.runtime.lastError.message));
                    } else {
                        resolve(result);
                    }
                });
            });
            
            const existingIPs = result.ipList || [];
            const newIPs = ips.filter(ip => !existingIPs.includes(ip));
            const allIPs = [...existingIPs, ...newIPs];
            
            await new Promise((resolve, reject) => {
                chrome.storage.local.set({ ipList: allIPs }, () => {
                    if (chrome.runtime.lastError) {
                        reject(new Error(chrome.runtime.lastError.message));
                    } else {
                        resolve();
                    }
                });
            });
            
            showPageNotification(`✅ 提取了 ${newIPs.length} 个新IP，总计 ${allIPs.length} 个`, 'success');
        } else {
            showPageNotification('❌ 未找到IP地址', 'error');
        }
        
    } catch (error) {
        console.error('提取IP失败:', error);
        if (error.message && error.message.includes('Extension context invalidated')) {
            showPageNotification('⚠️ 扩展上下文失效，请重新加载扩展', 'error');
        } else {
            showPageNotification('❌ 提取IP失败: ' + error.message, 'error');
        }
    }
}

// 从页面提取端口数据
async function extractPortsFromPage() {
    try {
        showPageNotification('正在提取端口数据...', 'info');
        
        const result = await extractPortsFromSearchPage();
        
        if (result.success && result.data && result.data.length > 0) {
            // 生成CSV内容
            let csvContent = 'ip,ports\n';
            result.data.forEach(item => {
                csvContent += `"${item.ip}","${item.ports.join('|')}"\n`;
            });
            
            // 创建下载链接
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const filename = `censys_ports_${timestamp}.csv`;
            
            // 创建临时链接进行下载
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            
            showPageNotification(`✅ 已导出 ${result.count || result.data.length} 个主机的端口数据到 ${filename}`, 'success');
        } else {
            console.error('提取端口数据失败:', result);
            
            // 显示详细的错误信息
            let errorMessage = result.message || '未找到端口数据';
            if (result.diagnostic) {
                console.log('📊 诊断信息:', result.diagnostic);
                errorMessage += `\n诊断信息: ${JSON.stringify(result.diagnostic, null, 2)}`;
            }
            
            showPageNotification(`❌ ${errorMessage}`, 'error');
        }
        
    } catch (error) {
        console.error('提取端口数据失败:', error);
        showPageNotification(`❌ 提取端口数据失败: ${error.message}`, 'error');
    }
}

// 显示页面通知
function showPageNotification(message, type = 'info') {
    // 移除已存在的通知
    const existing = document.getElementById('censys-notification');
    if (existing) {
        existing.remove();
    }
    
    const notification = document.createElement('div');
    notification.id = 'censys-notification';
    notification.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        z-index: 10001;
        background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#007bff'};
        color: white;
        padding: 12px 16px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        max-width: 300px;
        word-wrap: break-word;
        animation: slideIn 0.3s ease;
        cursor: pointer;
    `;
    
    // 添加动画样式
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
    
    notification.textContent = message;
    
    // 如果是扩展上下文错误，添加点击重新加载功能
    if (message.includes('扩展') && message.includes('重新加载')) {
        notification.title = '点击尝试重新加载页面';
        notification.onclick = () => {
            window.location.reload();
        };
        notification.style.cursor = 'pointer';
        notification.style.textDecoration = 'underline';
    }
    
    document.body.appendChild(notification);
    
    // 根据消息类型决定显示时长
    const displayTime = type === 'error' ? 8000 : 3000;
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }
    }, displayTime);
}

// 页面加载时初始化
console.log('🔄 开始初始化扩展...');
console.log('Chrome对象状态:', {
    chrome: typeof chrome,
    storage: typeof chrome?.storage,
    runtime: typeof chrome?.runtime,
    runtimeId: chrome?.runtime?.id
});

initializeAutoCollectState();

// 监听来自popup的消息
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log('📨 收到消息:', request);
    
    switch (request.action) {
        case 'ping':
            sendResponse({ success: true, message: '内容脚本运行正常' });
            break;
            
        case 'extractIPs':
            extractIPsFromSearchPage()
                .then(ips => sendResponse({ success: true, ips: ips }))
                .catch(error => sendResponse({ success: false, error: error.message }));
            return true; // 保持消息通道开放
            
        case 'extractPorts':
            extractPortsFromSearchPage()
                .then(result => {
                    if (result.success) {
                        sendResponse({ 
                            success: true, 
                            portsData: result.data || [],
                            count: result.count || 0,
                            diagnostic: result.diagnostic
                        });
                    } else {
                        sendResponse({ 
                            success: false, 
                            message: result.message,
                            diagnostic: result.diagnostic
                        });
                    }
                })
                .catch(error => sendResponse({ 
                    success: false, 
                    error: error.message,
                    diagnostic: { error: error.toString() }
                }));
            return true; // 保持消息通道开放
            
        case 'extractHostData':
            extractHostDataFromDetailPage()
                .then(hostData => sendResponse({ success: true, hostData: hostData }))
                .catch(error => sendResponse({ success: false, error: error.message }));
            return true; // 保持消息通道开放
            
        case 'enableAutoCollect':
            autoCollectEnabled = request.enabled || false;
            console.log(`自动收集${autoCollectEnabled ? '已启用' : '已禁用'}`);
            
            // 保存状态到storage
            chrome.storage.local.set({ autoCollectEnabled: autoCollectEnabled });
            
            // 如果启用自动收集，启动上下文监控
            if (autoCollectEnabled) {
                startContextMonitoring();
            }
            
            sendResponse({ success: true, autoCollectEnabled: autoCollectEnabled });
            
            // 如果启用了自动收集且当前是主机页面，立即尝试收集
            if (autoCollectEnabled) {
                setTimeout(checkAndAutoCollectHostData, 1000);
            }
            break;
            
        default:
            sendResponse({ success: false, error: '未知操作' });
    }
});

// 检测页面类型并自动收集数据
async function checkAndAutoCollectHostData() {
    try {
        // 检查扩展上下文 - 如果无效，仍然尝试数据提取但不保存
        const contextValid = isExtensionContextValid();
        if (!contextValid) {
            console.warn('⚠️ 扩展上下文无效，将尝试数据提取但无法保存');
            showPageNotification('⚠️ 扩展上下文无效，功能受限', 'info');
        }
        
        // 检查是否是主机详情页面
        const isHostPage = window.location.href.match(/\/hosts\/([\d.]+)/);
        // 检查是否是搜索页面
        const isSearchPage = window.location.href.includes('/search') || 
                           window.location.href.includes('search.censys.io');
        
        if (isHostPage && autoCollectEnabled && !hostPageAutoCollected) {
            console.log('📡 检测到主机详情页面，准备自动收集数据...');
            
            // 标记已进行自动收集，防止重复执行
            hostPageAutoCollected = true;
            
            // 延迟收集，确保页面完全加载
            setTimeout(async () => {
                try {
                    const hostData = await extractHostDataFromDetailPage();
                    
                    if (hostData) {
                        if (contextValid) {
                            // 有效上下文：自动保存到缓存
                            const saveSuccess = await saveHostDataToCache(hostData);
                            
                            if (saveSuccess) {
                                // 显示成功通知
                                showPageNotification(`✅ 自动收集 ${hostData.ip} 的数据完成`, 'success');
                                
                                // 更新统计显示
                                const statsDiv = document.getElementById('censys-stats');
                                if (statsDiv) {
                                    updateStatsDisplay(statsDiv);
                                }
                                
                                console.log('✅ 自动收集主机数据完成:', hostData);
                            } else {
                                showPageNotification('❌ 数据保存失败，扩展可能需要重新加载', 'error');
                            }
                        } else {
                            // 无效上下文：仅显示数据但不保存
                            console.log('📊 提取到主机数据（未保存）:', hostData);
                            showPageNotification(`📊 提取到 ${hostData.ip} 的数据，但无法保存（扩展上下文无效）`, 'info');
                        }
                    } else {
                        console.warn('⚠️ 自动收集获取到空数据');
                        showPageNotification('⚠️ 未能获取到主机数据', 'error');
                    }
                } catch (error) {
                    console.error('❌ 自动收集主机数据失败:', error);
                    
                    // 根据错误类型显示不同的提示
                    if (error.message && error.message.includes('Extension context invalidated')) {
                        showPageNotification('⚠️ 扩展上下文失效，请重新加载页面恢复功能', 'error');
                    } else {
                        showPageNotification('❌ 自动收集数据失败', 'error');
                    }
                }
            }, 3000); // 延迟3秒确保页面加载完成
        } else if (isSearchPage && autoCollectEnabled && !searchPageAutoCollected) {
            console.log('🔍 检测到搜索页面，准备自动收集端口数据...');
            
            // 标记已进行自动收集，防止重复执行
            searchPageAutoCollected = true;
            
            // 延迟收集，确保页面完全加载
            setTimeout(async () => {
                try {
                    const result = await extractPortsFromSearchPage();
                    
                    if (result.success && result.data && result.data.length > 0) {
                        if (contextValid) {
                            // 有效上下文：自动保存搜索结果到缓存
                            const saveSuccess = await saveSearchResultsToCache(result.data);
                            
                            if (saveSuccess) {
                                // 显示成功通知
                                showPageNotification(`✅ 自动收集 ${result.data.length} 个主机的端口数据完成`, 'success');
                                
                                // 更新统计显示
                                const statsDiv = document.getElementById('censys-search-stats');
                                if (statsDiv) {
                                    updateSearchStatsDisplay(statsDiv);
                                }
                                
                                console.log('✅ 自动收集搜索数据完成:', result.data);
                            } else {
                                showPageNotification('❌ 搜索数据保存失败，扩展可能需要重新加载', 'error');
                            }
                        } else {
                            // 无效上下文：仅显示数据但不保存
                            console.log('📊 提取到搜索数据（未保存）:', result.data);
                            showPageNotification(`📊 提取到 ${result.data.length} 个主机的端口数据，但无法保存（扩展上下文无效）`, 'info');
                        }
                    } else {
                        console.warn('⚠️ 自动收集搜索页面获取到空数据');
                        showPageNotification('⚠️ 未能获取到搜索端口数据', 'error');
                    }
                } catch (error) {
                    console.error('❌ 自动收集搜索数据失败:', error);
                    
                    // 根据错误类型显示不同的提示
                    if (error.message && error.message.includes('Extension context invalidated')) {
                        showPageNotification('⚠️ 扩展上下文失效，请重新加载页面恢复功能', 'error');
                    } else {
                        showPageNotification('❌ 自动收集搜索数据失败', 'error');
                    }
                }
            }, 5000); // 搜索页面延迟5秒，确保API请求完成
        }
    } catch (contextError) {
        console.error('检查自动收集时发生错误:', contextError);
        // 即使出错也不要影响页面正常功能
        console.log('🔄 尝试继续运行，忽略扩展上下文错误');
    }
}

// 保存搜索结果到缓存
async function saveSearchResultsToCache(searchData) {
    try {
        // 使用全局的扩展上下文检查
        if (!isExtensionContextValid()) {
            console.warn('扩展上下文无效，无法保存搜索数据');
            return false;
        }
        
        const result = await new Promise((resolve, reject) => {
            chrome.storage.local.get(['searchCache'], (result) => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    resolve(result);
                }
            });
        });
        
        const searchCache = result.searchCache || [];
        
        // 添加时间戳和查询信息
        const cacheEntry = {
            timestamp: new Date().toISOString(),
            url: window.location.href,
            query: new URLSearchParams(window.location.search).get('q') || 'default',
            count: searchData.length,
            data: searchData
        };
        
        // 添加到缓存（保留最近10次搜索）
        searchCache.unshift(cacheEntry);
        if (searchCache.length > 10) {
            searchCache.splice(10);
        }
        
        await new Promise((resolve, reject) => {
            chrome.storage.local.set({ searchCache: searchCache }, () => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    resolve();
                }
            });
        });
        
        console.log(`💾 搜索数据已保存到缓存: ${searchData.length} 条记录`);
        return true;
    } catch (error) {
        console.error('保存搜索数据失败:', error);
        
        // 检查是否是扩展上下文失效错误
        if (error.message && (
            error.message.includes('Extension context invalidated') ||
            error.message.includes('cannot access chrome')
        )) {
            console.warn('扩展上下文失效，无法保存搜索数据');
            showPageNotification('⚠️ 扩展上下文失效，请重新加载页面', 'error');
            extensionContextValid = false; // 更新全局状态
        }
        
        return false;
    }
}

// 更新搜索统计显示
async function updateSearchStatsDisplay(statsDiv) {
    try {
        // 检查扩展上下文是否有效
        if (!chrome.storage) {
            statsDiv.textContent = '扩展上下文无效';
            return;
        }
        
        const result = await new Promise((resolve, reject) => {
            chrome.storage.local.get(['searchCache'], (result) => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    resolve(result);
                }
            });
        });
        
        const searchCache = result.searchCache || [];
        const totalEntries = searchCache.length;
        const totalRecords = searchCache.reduce((sum, entry) => sum + (entry.count || 0), 0);
        
        statsDiv.textContent = `已缓存: ${totalEntries} 次搜索，${totalRecords} 条记录`;
    } catch (error) {
        console.warn('获取搜索统计数据失败:', error);
        statsDiv.textContent = '统计加载失败';
    }
}

// 下载搜索结果CSV
async function downloadSearchResultsCSV() {
    try {
        // 检查扩展上下文是否有效
        if (!chrome.storage) {
            showPageNotification('扩展上下文无效，无法访问缓存数据', 'error');
            return;
        }
        
        showPageNotification('正在准备CSV下载...', 'info');
        
        const result = await new Promise((resolve, reject) => {
            chrome.storage.local.get(['searchCache'], (result) => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    resolve(result);
                }
            });
        });
        
        const searchCache = result.searchCache || [];
        
        if (searchCache.length === 0) {
            showPageNotification('❌ 没有可导出的搜索数据', 'error');
            return;
        }
        
        // 获取最新的搜索结果
        const latestSearch = searchCache[0];
        if (!latestSearch.data || latestSearch.data.length === 0) {
            showPageNotification('❌ 最新搜索没有数据可导出', 'error');
            return;
        }
        
        // 生成CSV内容
        let csvContent = 'ip,ports\n';
        latestSearch.data.forEach(item => {
            csvContent += `"${item.ip}","${item.ports.join('|')}"\n`;
        });
        
        // 创建下载链接
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const filename = `censys_search_results_${timestamp}.csv`;
        
        // 创建临时链接进行下载
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        showPageNotification(`✅ 已导出 ${latestSearch.data.length} 条搜索记录到 ${filename}`, 'success');
        
    } catch (error) {
        console.error('下载搜索结果CSV失败:', error);
        showPageNotification('❌ 下载CSV失败: ' + error.message, 'error');
    }
}

// 保存主机数据到缓存
async function saveHostDataToCache(hostData) {
    try {
        // 使用全局的扩展上下文检查
        if (!isExtensionContextValid()) {
            console.warn('扩展上下文无效，无法保存数据');
            return false;
        }
        
        const result = await new Promise((resolve, reject) => {
            chrome.storage.local.get(['hostCache'], (result) => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    resolve(result);
                }
            });
        });
        
        const hostCache = result.hostCache || [];
        const existingIndex = hostCache.findIndex(item => item.ip === hostData.ip);
        
        if (existingIndex !== -1) {
            hostCache[existingIndex] = hostData; // 更新现有数据
            console.log(`🔄 更新主机 ${hostData.ip} 的数据`);
        } else {
            hostCache.push(hostData); // 添加新数据
            console.log(`➕ 添加主机 ${hostData.ip} 的数据`);
        }
        
        await new Promise((resolve, reject) => {
            chrome.storage.local.set({ hostCache: hostCache }, () => {
                if (chrome.runtime.lastError) {
                    reject(new Error(chrome.runtime.lastError.message));
                } else {
                    resolve();
                }
            });
        });
        
        return true;
    } catch (error) {
        console.error('保存主机数据失败:', error);
        
        // 检查是否是扩展上下文失效错误
        if (error.message && (
            error.message.includes('Extension context invalidated') ||
            error.message.includes('cannot access chrome')
        )) {
            console.warn('扩展上下文失效，无法保存数据');
            showPageNotification('⚠️ 扩展上下文失效，请重新加载页面', 'error');
            extensionContextValid = false; // 更新全局状态
        }
        
        return false;
    }
}

// 监听URL变化（SPA应用）
let lastUrl = window.location.href;
new MutationObserver(() => {
    const currentUrl = window.location.href;
    if (currentUrl !== lastUrl) {
        lastUrl = currentUrl;
        console.log('🔄 检测到URL变化:', currentUrl);
        
        // 重置自动收集标志
        searchPageAutoCollected = false;
        hostPageAutoCollected = false;
        
        // 清除之前的定时器
        if (pageLoadTimer) {
            clearTimeout(pageLoadTimer);
        }
        
        // 重新创建UI
        setTimeout(() => {
            createPageUI();
        }, 500);
        
        // 延迟检查新页面的自动收集
        pageLoadTimer = setTimeout(checkAndAutoCollectHostData, 2000);
    }
}).observe(document, { subtree: true, childList: true });

// 页面加载完成时检查
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(checkAndAutoCollectHostData, 2000);
    });
} else {
    setTimeout(checkAndAutoCollectHostData, 2000);
}

// 从搜索页面提取IP列表
async function extractIPsFromSearchPage() {
    console.log('🔍 开始从搜索页面提取IP列表...');
    
    const ips = new Set();
    
    try {
        // 方法1: 从搜索结果链接中提取IP
        const hostLinks = document.querySelectorAll('a[href*="/hosts/"]');
        console.log(`找到 ${hostLinks.length} 个主机链接`);
        
        hostLinks.forEach(link => {
            const href = link.getAttribute('href');
            const ipMatch = href.match(/\/hosts\/([\d.]+)/);
            if (ipMatch && ipMatch[1]) {
                ips.add(ipMatch[1]);
                console.log(`从链接提取IP: ${ipMatch[1]}`);
            }
        });
        
        // 方法2: 从JSON数据中提取IP
        await extractIPsFromJSON(ips);
        
        // 方法3: 从页面文本中提取IP
        extractIPsFromText(ips);
        
        const ipArray = Array.from(ips).filter(ip => isValidIP(ip));
        console.log(`✅ 总共提取到 ${ipArray.length} 个有效IP`);
        
        return ipArray;
        
    } catch (error) {
        console.error('❌ 提取IP时出错:', error);
        throw error;
    }
}

// 从搜索页面提取端口数据
async function extractPortsFromSearchPage() {
    console.log('🔌 开始从搜索页面提取端口数据...');
    console.log('📍 当前页面URL:', window.location.href);
    console.log('📄 页面标题:', document.title);
    
    const portsData = [];
    
    try {
        // 检测页面类型
        const pageType = detectPageType();
        console.log('🏷️ 检测到页面类型:', pageType);
        
        // 获取诊断信息
        const diagnosticInfo = await getDiagnosticInfo();
        console.log('📊 页面诊断信息:', diagnosticInfo);
        
        // 方法1: 从JSON数据中提取IP和端口信息
        console.log('🔍 方法1: 尝试从页面JSON提取数据...');
        await extractPortsFromJSON(portsData);
        console.log(`📋 方法1结果: 提取到 ${portsData.length} 个主机数据`);
        
        // 方法2: 如果JSON提取失败，尝试从页面文本提取
        if (portsData.length === 0) {
            console.log('🔍 方法2: 尝试从页面文本提取数据...');
            extractPortsFromPageText(portsData);
            console.log(`📋 方法2结果: 提取到 ${portsData.length} 个主机数据`);
        }
        
        // 方法3: 如果还是没有数据，尝试从表格或列表元素提取
        if (portsData.length === 0) {
            console.log('🔍 方法3: 尝试从页面元素提取数据...');
            extractPortsFromPageElements(portsData);
            console.log(`📋 方法3结果: 提取到 ${portsData.length} 个主机数据`);
        }
        
        // 等待异步请求完成
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        console.log(`✅ 总共提取到 ${portsData.length} 个主机的端口数据`);
        
        if (portsData.length === 0) {
            console.warn('⚠️ 所有方法都未找到端口数据');
            console.log('📄 页面内容片段:', document.body.textContent.substring(0, 500));
            return {
                success: false,
                message: '未找到端口数据 - 已尝试多种提取方法',
                diagnostic: {
                    ...diagnosticInfo,
                    pageContent: document.body.textContent.substring(0, 500),
                    scriptCount: document.querySelectorAll('script').length,
                    hasSearchResults: document.querySelector('[data-testid="search-result"]') !== null,
                    hasTable: document.querySelector('table') !== null
                }
            };
        }
        
        return {
            success: true,
            count: portsData.length,
            data: portsData, // 返回所有数据，不限制条数
            diagnostic: diagnosticInfo
        };
        
    } catch (error) {
        console.error('❌ 提取端口数据时出错:', error);
        
        const diagnosticInfo = await getDiagnosticInfo();
        return {
            success: false,
            message: error.message,
            diagnostic: {
                ...diagnosticInfo,
                error: error.toString(),
                stack: error.stack
            }
        };
    }
}

// 检测页面类型
function detectPageType() {
    const url = window.location.href;
    const pathname = window.location.pathname;
    
    if (url.includes('search') || pathname.includes('search')) {
        return 'search';
    } else if (url.includes('hosts') || pathname.includes('hosts')) {
        return 'hosts';
    } else if (url.includes('dashboard') || pathname.includes('dashboard')) {
        return 'dashboard';
    } else {
        return 'unknown';
    }
}

// 获取诊断信息
async function getDiagnosticInfo() {
    const info = {
        url: window.location.href,
        title: document.title,
        pageType: detectPageType(),
        scripts: document.querySelectorAll('script').length,
        dataElements: document.querySelectorAll('[data-props], [data-page], [data-next-page]').length,
        hasResults: !!document.querySelector('.result, .host-result, [data-testid*="result"]'),
        networkRequests: [],
        availableAPIs: [],
        censysAPIUrl: ''
    };
    
    // 生成Censys API URL
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('q') || urlParams.get('query');
    
    if (query) {
        info.censysAPIUrl = `https://platform.censys.io/api/search?q=${encodeURIComponent(query)}`;
    } else {
        const defaultQuery = '(host.services.software.product = "udpxy" or web.software.product = "udpxy") and host.location.country = "China"';
        info.censysAPIUrl = `https://platform.censys.io/api/search?q=${encodeURIComponent(defaultQuery)}`;
    }
    
    // 检查可能的API端点
    const scripts = document.querySelectorAll('script');
    for (const script of scripts) {
        const content = script.textContent || script.innerHTML;
        const apiMatches = content.match(/\/api\/[a-zA-Z0-9\/\-_]+/g);
        if (apiMatches) {
            info.availableAPIs.push(...apiMatches);
        }
        
        // 查找GraphQL端点
        const graphqlMatches = content.match(/\/graphql|\/api\/graphql/g);
        if (graphqlMatches) {
            info.availableAPIs.push(...graphqlMatches);
        }
    }
    
    // 去重API列表
    info.availableAPIs = [...new Set(info.availableAPIs)];
    
    // 检查当前可见的网络请求（从开发者工具Performance API）
    if (window.performance && window.performance.getEntriesByType) {
        const entries = window.performance.getEntriesByType('resource');
        info.networkRequests = entries
            .filter(entry => entry.name.includes('censys') || entry.name.includes('/api/'))
            .map(entry => ({
                url: entry.name,
                type: entry.initiatorType,
                duration: entry.duration
            }))
            .slice(-10); // 最近10个请求
    }
    
    return info;
}

// 从JSON数据中提取IP
async function extractIPsFromJSON(ipsSet) {
    try {
        // 查找页面中的JSON数据
        const scripts = document.querySelectorAll('script');
        
        for (const script of scripts) {
            const content = script.textContent || script.innerHTML;
            
            // 查找不同格式的JSON数据
            const jsonPatterns = [
                /window\.__INITIAL_STATE__\s*=\s*({.*?});/s,
                /window\.__NUXT__\s*=\s*({.*?});/s,
                /"results":\s*(\[.*?\])/s,
                /"hosts":\s*(\[.*?\])/s
            ];
            
            for (const pattern of jsonPatterns) {
                const match = content.match(pattern);
                if (match) {
                    try {
                        const data = JSON.parse(match[1]);
                        extractIPsFromObject(data, ipsSet);
                    } catch (parseError) {
                        console.warn('JSON解析失败:', parseError);
                    }
                }
            }
        }
        
        // 查找data属性中的JSON
        const dataElements = document.querySelectorAll('[data-props], [data-page]');
        dataElements.forEach(element => {
            ['data-props', 'data-page'].forEach(attr => {
                const dataAttr = element.getAttribute(attr);
                if (dataAttr) {
                    try {
                        const decodedData = dataAttr.replace(/&quot;/g, '"').replace(/&amp;/g, '&');
                        const data = JSON.parse(decodedData);
                        extractIPsFromObject(data, ipsSet);
                    } catch (parseError) {
                        console.warn('Data属性JSON解析失败:', parseError);
                    }
                }
            });
        });
        
    } catch (error) {
        console.warn('从JSON提取IP时出错:', error);
    }
}

// 从JSON数据中提取端口信息
async function extractPortsFromJSON(portsDataArray) {
    try {
        console.log('🔍 开始查找页面中的JSON数据...');
        
        // 首先尝试直接调用API
        const apiSuccess = await fetchCensysAPIData(portsDataArray);
        
        if (apiSuccess) {
            console.log('✅ 通过API成功获取数据');
            return;
        }
        
        console.log('⚠️ API调用失败，尝试从页面提取数据...');
        
        // 查找页面中的JSON数据
        const scripts = document.querySelectorAll('script');
        console.log(`📄 找到 ${scripts.length} 个script标签`);
        
        for (const script of scripts) {
            const content = script.textContent || script.innerHTML;
            
            // 查找不同格式的JSON数据
            const jsonPatterns = [
                /window\.__INITIAL_STATE__\s*=\s*({.*?});/s,
                /window\.__NUXT__\s*=\s*({.*?});/s,
                /window\.__NEXT_DATA__\s*=\s*({.*?});/s,
                /"results":\s*(\[.*?\])/s,
                /"hosts":\s*(\[.*?\])/s,
                /"hits":\s*(\[.*?\])/s,
                /({.*?"host".*?"services".*?})/s
            ];
            
            for (const pattern of jsonPatterns) {
                const match = content.match(pattern);
                if (match) {
                    try {
                        console.log('🎯 找到JSON数据，长度:', match[1].length);
                        const data = JSON.parse(match[1]);
                        extractPortsFromObject(data, portsDataArray);
                    } catch (parseError) {
                        console.warn('JSON解析失败:', parseError);
                    }
                }
            }
        }
        
        // 查找data属性中的JSON
        const dataElements = document.querySelectorAll('[data-props], [data-page], [data-next-page]');
        console.log(`🏷️ 找到 ${dataElements.length} 个data属性元素`);
        
        dataElements.forEach(element => {
            ['data-props', 'data-page', 'data-next-page'].forEach(attr => {
                const dataAttr = element.getAttribute(attr);
                if (dataAttr) {
                    try {
                        console.log(`📋 处理${attr}属性，长度:`, dataAttr.length);
                        const decodedData = dataAttr.replace(/&quot;/g, '"').replace(/&amp;/g, '&');
                        const data = JSON.parse(decodedData);
                        extractPortsFromObject(data, portsDataArray);
                    } catch (parseError) {
                        console.warn(`${attr}JSON解析失败:`, parseError);
                    }
                }
            });
        });
        
    } catch (error) {
        console.warn('从JSON提取端口信息时出错:', error);
    }
}

// 从页面文本提取端口信息
function extractPortsFromPageText(portsDataArray) {
    try {
        console.log('📄 开始从页面文本提取端口信息...');
        const pageText = document.body.textContent || document.body.innerText;
        
        // 查找IP地址模式
        const ipPattern = /\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b/g;
        const ipMatches = pageText.match(ipPattern);
        
        if (ipMatches) {
            console.log(`🔍 在页面文本中找到 ${ipMatches.length} 个IP地址`);
            
            // 为每个IP创建基础记录
            const uniqueIPs = [...new Set(ipMatches)].filter(ip => isValidIP(ip));
            
            uniqueIPs.forEach(ip => {
                // 查找与该IP相关的端口信息
                const ipContext = extractIPContext(pageText, ip);
                const ports = extractPortsFromContext(ipContext);
                
                if (ports.length > 0) {
                    portsDataArray.push({
                        ip: ip,
                        ports: ports
                    });
                    console.log(`📄 从文本为 ${ip} 提取到端口: ${ports.join(', ')}`);
                }
            });
        }
        
    } catch (error) {
        console.warn('从页面文本提取端口信息时出错:', error);
    }
}

// 从页面元素提取端口信息
function extractPortsFromPageElements(portsDataArray) {
    try {
        console.log('🔗 开始从页面元素提取端口信息...');
        
        // 查找表格中的数据
        const tables = document.querySelectorAll('table');
        tables.forEach((table, index) => {
            console.log(`📊 处理表格 ${index + 1}/${tables.length}`);
            extractPortsFromTable(table, portsDataArray);
        });
        
        // 查找列表中的数据
        const lists = document.querySelectorAll('ul, ol');
        lists.forEach((list, index) => {
            if (list.textContent.includes('.') && list.textContent.match(/\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/)) {
                console.log(`📋 处理列表 ${index + 1}/${lists.length}`);
                extractPortsFromList(list, portsDataArray);
            }
        });
        
        // 查找特定的搜索结果容器
        const searchResults = document.querySelectorAll('[data-testid*="result"], [class*="result"], [class*="search"], [class*="host"]');
        searchResults.forEach((result, index) => {
            if (result.textContent.includes('.') && result.textContent.match(/\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/)) {
                console.log(`🎯 处理搜索结果 ${index + 1}/${searchResults.length}`);
                extractPortsFromElement(result, portsDataArray);
            }
        });
        
    } catch (error) {
        console.warn('从页面元素提取端口信息时出错:', error);
    }
}

// 提取IP地址的上下文文本
function extractIPContext(text, ip) {
    const ipIndex = text.indexOf(ip);
    if (ipIndex === -1) return '';
    
    const start = Math.max(0, ipIndex - 200);
    const end = Math.min(text.length, ipIndex + ip.length + 200);
    
    return text.substring(start, end);
}

// 从上下文文本中提取端口
function extractPortsFromContext(context) {
    const ports = [];
    
    // 查找端口模式
    const portPatterns = [
        /port[:\s]+(\d{1,5})/gi,
        /(\d{1,5})\s*\/\s*(tcp|udp|http|https)/gi,
        /:(\d{1,5})\b/g,
        /\b(\d{2,5})\b/g // 通用数字模式（较宽松）
    ];
    
    portPatterns.forEach(pattern => {
        const matches = context.match(pattern);
        if (matches) {
            matches.forEach(match => {
                const portMatch = match.match(/(\d{1,5})/);
                if (portMatch) {
                    const port = parseInt(portMatch[1]);
                    if (port >= 1 && port <= 65535 && !ports.includes(port)) {
                        ports.push(port);
                    }
                }
            });
        }
    });
    
    return ports;
}

// 从表格中提取端口信息
function extractPortsFromTable(table, portsDataArray) {
    const rows = table.querySelectorAll('tr');
    
    rows.forEach(row => {
        const cells = row.querySelectorAll('td, th');
        let ip = null;
        const ports = [];
        
        cells.forEach(cell => {
            const text = cell.textContent || cell.innerText;
            
            // 查找IP地址
            const ipMatch = text.match(/\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b/);
            if (ipMatch && isValidIP(ipMatch[0])) {
                ip = ipMatch[0];
            }
            
            // 查找端口信息
            const extractedPorts = extractPortsFromContext(text);
            ports.push(...extractedPorts);
        });
        
        if (ip && ports.length > 0) {
            const uniquePorts = [...new Set(ports)];
            portsDataArray.push({
                ip: ip,
                ports: uniquePorts
            });
            console.log(`📊 从表格为 ${ip} 提取到端口: ${uniquePorts.join(', ')}`);
        }
    });
}

// 从列表中提取端口信息
function extractPortsFromList(list, portsDataArray) {
    const items = list.querySelectorAll('li');
    
    items.forEach(item => {
        const text = item.textContent || item.innerText;
        const ipMatch = text.match(/\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b/);
        
        if (ipMatch && isValidIP(ipMatch[0])) {
            const ip = ipMatch[0];
            const ports = extractPortsFromContext(text);
            
            if (ports.length > 0) {
                portsDataArray.push({
                    ip: ip,
                    ports: ports
                });
                console.log(`📋 从列表为 ${ip} 提取到端口: ${ports.join(', ')}`);
            }
        }
    });
}

// 从通用元素中提取端口信息
function extractPortsFromElement(element, portsDataArray) {
    const text = element.textContent || element.innerText;
    const ipMatch = text.match(/\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b/);
    
    if (ipMatch && isValidIP(ipMatch[0])) {
        const ip = ipMatch[0];
        const ports = extractPortsFromContext(text);
        
        if (ports.length > 0) {
            portsDataArray.push({
                ip: ip,
                ports: ports
            });
            console.log(`🎯 从元素为 ${ip} 提取到端口: ${ports.join(', ')}`);
        }
    }
}

// 直接调用Censys API获取数据
async function fetchCensysAPIData(portsDataArray) {
    try {
        console.log('🌐 开始调用Censys API...');
        
        // 从当前页面URL中提取查询参数
        const currentUrl = window.location.href;
        let baseQuery = '';
        
        if (currentUrl.includes('search.censys.io')) {
            // 检查URL中是否有查询参数
            const urlParams = new URLSearchParams(window.location.search);
            const query = urlParams.get('q') || urlParams.get('query');
            
            if (query) {
                baseQuery = query;
            } else {
                // 使用默认的UDPXY查询
                baseQuery = '(host.services.software.product = "udpxy" or web.software.product = "udpxy") and host.location.country = "China"';
            }
        } else {
            // 使用默认查询
            baseQuery = '(host.services.software.product = "udpxy" or web.software.product = "udpxy") and host.location.country = "China"';
        }
        
        let totalFetched = 0;
        let currentPage = 1;
        const pageSize = 100; // Censys API通常每页最多100条
        let hasMorePages = true;
        
        while (hasMorePages) {
            // 构建分页API URL
            const apiUrl = `https://platform.censys.io/api/search?q=${encodeURIComponent(baseQuery)}&page=${currentPage}&per_page=${pageSize}`;
            console.log(`📡 API请求URL (第${currentPage}页):`, apiUrl);
            
            // 发送API请求
            const response = await fetch(apiUrl, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                    'User-Agent': navigator.userAgent,
                    'Referer': window.location.href,
                    'Origin': window.location.origin
                },
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                const jsonData = await response.json();
                console.log(`📊 API响应数据 (第${currentPage}页):`, jsonData);
                
                // 检查是否有更多数据
                const currentPageData = jsonData.result?.hits || jsonData.hits || jsonData.results || [];
                const totalHits = jsonData.result?.total || jsonData.total_hits || jsonData.total || 0;
                
                console.log(`📈 第${currentPage}页: 获取到 ${currentPageData.length} 条数据，总计 ${totalHits} 条`);
                
                // 从API响应中提取端口数据
                const beforeCount = portsDataArray.length;
                extractPortsFromObject(jsonData, portsDataArray);
                const afterCount = portsDataArray.length;
                
                totalFetched += afterCount - beforeCount;
                console.log(`🔄 第${currentPage}页提取完成: 新增 ${afterCount - beforeCount} 条数据，累计 ${totalFetched} 条`);
                
                // 检查是否还有更多页面
                if (currentPageData.length === 0 || 
                    currentPageData.length < pageSize || 
                    totalFetched >= totalHits) {
                    hasMorePages = false;
                    console.log(`✅ 所有页面获取完成，总计提取 ${totalFetched} 条数据`);
                } else {
                    currentPage++;
                    // 添加延迟避免请求过快
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            } else {
                console.warn(`❌ API请求失败 (第${currentPage}页):`, response.status, response.statusText);
                hasMorePages = false;
                
                // 如果是第一页就失败，返回false
                if (currentPage === 1) {
                    return false;
                }
            }
        }
        
        console.log(`🎉 API数据获取完成: 总共获取 ${totalFetched} 条数据`);
        return totalFetched > 0;
        
    } catch (error) {
        console.warn('🚫 API请求出错:', error);
        return false;
    }
}

// 递归提取对象中的IP
function extractIPsFromObject(obj, ipsSet) {
    if (!obj || typeof obj !== 'object') return;
    
    // 如果是数组，遍历每个元素
    if (Array.isArray(obj)) {
        obj.forEach(item => extractIPsFromObject(item, ipsSet));
        return;
    }
    
    // 查找包含IP的字段
    Object.keys(obj).forEach(key => {
        const value = obj[key];
        
        if (typeof value === 'string') {
            if (key === 'ip' || key === 'host' || key === 'address') {
                if (isValidIP(value)) {
                    ipsSet.add(value);
                    console.log(`从JSON字段 ${key} 提取IP: ${value}`);
                }
            }
        } else if (typeof value === 'object') {
            extractIPsFromObject(value, ipsSet);
        }
    });
}

// 递归提取对象中的端口信息
function extractPortsFromObject(obj, portsDataArray) {
    if (!obj || typeof obj !== 'object') return;
    
    console.log('🔍 分析JSON数据结构:', Object.keys(obj));
    
    // 如果是数组，遍历每个元素
    if (Array.isArray(obj)) {
        console.log(`📋 处理数组，包含 ${obj.length} 个元素`);
        obj.forEach(item => extractPortsFromObject(item, portsDataArray));
        return;
    }
    
    // 检查Censys API响应的标准结构
    if (obj.result && obj.result.hits) {
        console.log('🎯 发现Censys API标准结构 - result.hits');
        extractPortsFromObject(obj.result.hits, portsDataArray);
        return;
    }
    
    if (obj.hits && Array.isArray(obj.hits)) {
        console.log('🎯 发现hits数组结构');
        extractPortsFromObject(obj.hits, portsDataArray);
        return;
    }
    
    if (obj.results && Array.isArray(obj.results)) {
        console.log('🎯 发现results数组结构');
        extractPortsFromObject(obj.results, portsDataArray);
        return;
    }
    
    // 查找主机对象结构
    let ip = null;
    let services = null;
    
    // 多种可能的IP字段
    if (obj.ip) {
        ip = obj.ip;
    } else if (obj.host && obj.host.ip) {
        ip = obj.host.ip;
    } else if (obj.host_ip) {
        ip = obj.host_ip;
    } else if (obj.address) {
        ip = obj.address;
    }
    
    // 多种可能的服务字段
    if (obj.services) {
        services = obj.services;
    } else if (obj.host && obj.host.services) {
        services = obj.host.services;
    } else if (obj.ports) {
        services = obj.ports;
    }
    
    if (ip && isValidIP(ip) && services && Array.isArray(services)) {
        console.log(`🔍 分析主机 ${ip} 的服务数据`);
        const httpPorts = [];
        
        services.forEach(service => {
            let port = null;
            let protocol = null;
            
            // 获取端口号
            if (typeof service === 'number') {
                port = service;
            } else if (service.port) {
                port = service.port;
            } else if (service.port_number) {
                port = service.port_number;
            }
            
            // 获取协议
            if (service.protocol) {
                protocol = service.protocol.toLowerCase();
            } else if (service.service_name) {
                protocol = service.service_name.toLowerCase();
            } else if (service.transport_protocol) {
                protocol = service.transport_protocol.toLowerCase();
            }
            
            // 只根据JSON中明确的protocol字段判断是否是HTTP/HTTPS端口
            const isHttpPort = (
                protocol === 'http' || 
                protocol === 'https'
            );
            
            if (port && isHttpPort) {
                httpPorts.push(port);
                console.log(`✅ 从主机 ${ip} 提取 ${protocol || 'HTTP'} 端口: ${port}`);
            }
        });
        
        if (httpPorts.length > 0) {
            // 检查是否已存在该IP的数据
            const existingEntry = portsDataArray.find(entry => entry.ip === ip);
            if (existingEntry) {
                // 合并端口，去重
                existingEntry.ports = [...new Set([...existingEntry.ports, ...httpPorts])];
                console.log(`🔄 更新主机 ${ip} 的端口列表: ${existingEntry.ports.join(', ')}`);
            } else {
                const newEntry = {
                    ip: ip,
                    ports: [...new Set(httpPorts)]
                };
                portsDataArray.push(newEntry);
                console.log(`➕ 添加主机 ${ip} 的端口数据: ${newEntry.ports.join(', ')}`);
            }
        }
    }
    
    // 递归搜索其他对象
    Object.keys(obj).forEach(key => {
        const value = obj[key];
        if (typeof value === 'object' && value !== null) {
            extractPortsFromObject(value, portsDataArray);
        }
    });
}

// 从页面文本中提取IP
function extractIPsFromText(ipsSet) {
    const pageText = document.body.textContent || document.body.innerText;
    const ipPattern = /\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b/g;
    const matches = pageText.match(ipPattern);
    
    if (matches) {
        matches.forEach(ip => {
            if (isValidIP(ip)) {
                ipsSet.add(ip);
                console.log(`从页面文本提取IP: ${ip}`);
            }
        });
    }
}

// 从主机详情页面提取数据
async function extractHostDataFromDetailPage() {
    console.log('🖥️ 开始从主机详情页面提取数据...');
    
    try {
        // 从URL中获取IP
        const urlMatch = window.location.href.match(/\/hosts\/([\d.]+)/);
        if (!urlMatch || !urlMatch[1]) {
            throw new Error('无法从URL中提取IP地址');
        }
        
        const ip = urlMatch[1];
        console.log(`正在提取主机 ${ip} 的详情数据`);
        
        const hostData = {
            ip: ip,
            ports: [],
            dns: '',
            country: '',
            city: '',
            province: '',
            isp: '',
            _apiError: false // 标记API是否出错
        };
        
        // 首先尝试从API获取JSON数据
        const apiSuccess = await extractHostDataFromAPI(hostData);
        
        // 如果API失败，记录错误并检查是否应该继续
        if (!apiSuccess || hostData._apiError) {
            console.warn('⚠️ API调用失败或返回无效数据，将尝试从页面提取数据');
            
            // 如果API明确失败，可以选择直接返回null或继续尝试页面提取
            // 这里我们先继续尝试页面提取，但会更严格地验证最终数据
        }
        
        // 如果API数据不完整，再从页面JSON提取
        await extractHostDataFromJSON(hostData);
        
        // 如果JSON提取不完整，尝试从页面文本提取
        extractHostDataFromPageText(hostData);
        
        console.log('✅ 主机数据提取完成:', hostData);
        
        // 验证数据完整性 - 只有获取到有效信息才返回数据
        const hasValidData = (
            hostData.ports.length > 0 ||  // 有端口信息
            hostData.dns ||               // 有DNS信息
            hostData.country ||           // 有国家信息
            hostData.city ||              // 有城市信息
            hostData.province ||          // 有省份信息
            hostData.isp                  // 有ISP信息
        );
        
        // 如果API出错且没有从其他途径获取到有效数据，返回null
        if (hostData._apiError && !hasValidData) {
            console.warn('❌ API出错且没有获取到任何有效的主机信息，返回null');
            return null;
        }
        
        if (!hasValidData) {
            console.warn('⚠️ 未获取到任何有效的主机信息，返回null');
            return null;
        }
        
        // 清理内部标志，准备返回数据
        delete hostData._apiError;
        
        return hostData;
        
    } catch (error) {
        console.error('❌ 提取主机数据时出错:', error);
        throw error;
    }
}

// 从API获取主机详情数据
async function extractHostDataFromAPI(hostData) {
    try {
        console.log(`🌐 正在从API获取主机 ${hostData.ip} 的数据...`);
        
        // 构建API URL - 使用用户提供的正确端点格式
        const apiUrl = `https://platform.censys.io/hosts/${hostData.ip}?_data=routes/hosts.$id`;
        
        const response = await fetch(apiUrl, {
            method: 'GET',
            headers: {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': navigator.userAgent
            },
            credentials: 'include' // 包含cookie
        });
        
        if (response.ok) {
            try {
                const jsonData = await response.json();
                console.log('✅ API响应数据:', jsonData);
                
                // 检查响应是否包含有效的主机数据
                if (!jsonData || typeof jsonData !== 'object') {
                    console.warn('❌ API返回无效的JSON数据');
                    hostData._apiError = true;
                    return false;
                }
                
                // 检查是否是错误响应
                if (jsonData.error || jsonData.message) {
                    console.warn('❌ API返回错误:', jsonData.error || jsonData.message);
                    hostData._apiError = true;
                    return false;
                }
                
                // 从API响应中提取数据
                const extractedData = extractHostFieldsFromAPIResponse(jsonData, hostData);
                
                if (!extractedData) {
                    console.warn('❌ API响应中没有有效的主机数据');
                    hostData._apiError = true;
                    return false;
                }
                
                return true;
                
            } catch (parseError) {
                console.warn('❌ 解析API响应JSON失败:', parseError);
                hostData._apiError = true;
                return false;
            }
        } else {
            console.warn(`❌ API请求失败: ${response.status} ${response.statusText}`);
            
            // 尝试读取错误响应
            try {
                const errorText = await response.text();
                console.warn('错误响应内容:', errorText);
            } catch (e) {
                console.warn('无法读取错误响应');
            }
            
            hostData._apiError = true;
            return false;
        }
        
    } catch (error) {
        console.warn('❌ 从API获取主机数据时出错:', error);
        hostData._apiError = true;
        return false;
    }
}

// 从API响应中提取主机字段
function extractHostFieldsFromAPIResponse(data, hostData) {
    if (!data || typeof data !== 'object') {
        console.warn('❌ API响应数据无效');
        return false;
    }
    
    let hasExtractedData = false; // 标记是否提取到有效数据
    
    try {
        // 处理Censys API的标准响应格式
        let hostInfo = data;
        
        // 如果响应包含host字段，使用host数据
        if (data.host) {
            hostInfo = data.host;
        }
        
        // 检查是否包含基本的主机信息
        if (!hostInfo || typeof hostInfo !== 'object') {
            console.warn('❌ API响应中没有有效的主机信息');
            return false;
        }
        
        // 提取DNS信息
        if (hostInfo.dns && hostInfo.dns.names && Array.isArray(hostInfo.dns.names) && hostInfo.dns.names.length > 0) {
            hostData.dns = hostInfo.dns.names[0];
            console.log(`API提取DNS: ${hostData.dns}`);
            hasExtractedData = true;
        }
        
        // 提取地理位置信息
        if (hostInfo.location) {
            const location = hostInfo.location;
            if (location.country && !hostData.country) {
                hostData.country = location.country;
                console.log(`API提取国家: ${hostData.country}`);
                hasExtractedData = true;
            }
            if (location.city && !hostData.city) {
                hostData.city = location.city;
                console.log(`API提取城市: ${hostData.city}`);
                hasExtractedData = true;
            }
            if ((location.province || location.state || location.region) && !hostData.province) {
                hostData.province = location.province || location.state || location.region;
                console.log(`API提取省份: ${hostData.province}`);
                hasExtractedData = true;
            }
        }
        
        // 提取ISP信息
        if (hostInfo.whois && hostInfo.whois.network && hostInfo.whois.network.name && !hostData.isp) {
            hostData.isp = hostInfo.whois.network.name;
            console.log(`API提取ISP: ${hostData.isp}`);
            hasExtractedData = true;
        }
        
        // 提取服务和端口信息 - 只提取真正的UDPXY服务端口
        if (hostInfo.services && Array.isArray(hostInfo.services)) {
            const initialPortCount = hostData.ports.length;
            hostInfo.services.forEach(service => {
                if (service.port && typeof service.port === 'number') {
                    // 检查是否是UDPXY服务（而不是仅仅检查HTTP/HTTPS协议）
                    const isUdpxyService = checkIfUdpxyServiceFromAPI(service);
                    
                    if (isUdpxyService) {
                        if (!hostData.ports.includes(service.port)) {
                            hostData.ports.push(service.port);
                            console.log(`API提取UDPXY端口: ${service.port} (协议: ${service.protocol || 'unknown'})`);
                            
                            // 打印UDPXY服务的详细信息用于调试
                            if (service.software && Array.isArray(service.software)) {
                                service.software.forEach(sw => {
                                    if (sw.vendor && sw.vendor.toLowerCase().includes('udpxy') || 
                                        sw.product && sw.product.toLowerCase().includes('udpxy')) {
                                        console.log(`  └─ UDPXY软件信息: vendor="${sw.vendor}", product="${sw.product}"`);
                                    }
                                });
                            }
                        }
                    } else {
                        // 调试：记录非UDPXY服务（但不添加到端口列表）
                        console.log(`API跳过非UDPXY端口: ${service.port} (协议: ${service.protocol || 'unknown'})`);
                    }
                }
            });
            
            // 如果提取到了新的UDPXY端口，标记为有效数据
            if (hostData.ports.length > initialPortCount) {
                hasExtractedData = true;
            }
        }
        
        console.log(`API数据提取完成，提取到有效数据: ${hasExtractedData}, 当前hostData:`, hostData);
        return hasExtractedData;
        
    } catch (error) {
        console.warn('❌ 解析API响应数据时出错:', error);
        return false;
    }
}

// 检查API响应中的服务是否是udpxy
function checkIfUdpxyServiceFromAPI(service) {
    if (!service || typeof service !== 'object') {
        console.log(`🔍 UDPXY检查: 服务对象无效`);
        return false;
    }
    
    console.log(`🔍 UDPXY检查: 正在检查端口 ${service.port} 的服务`);
    
    // 检查software字段
    if (service.software && Array.isArray(service.software)) {
        console.log(`🔍 UDPXY检查: 发现 ${service.software.length} 个软件条目`);
        
        for (const sw of service.software) {
            if (sw && typeof sw === 'object') {
                const vendor = (sw.vendor || '').toLowerCase();
                const product = (sw.product || '').toLowerCase();
                
                console.log(`🔍 UDPXY检查: 软件信息 - vendor: "${sw.vendor}", product: "${sw.product}"`);
                
                if (vendor.includes('udpxy') || product.includes('udpxy')) {
                    console.log(`✅ UDPXY检查: 在软件信息中发现UDPXY - vendor: ${sw.vendor}, product: ${sw.product}`);
                    return true;
                }
            }
        }
    } else {
        console.log(`🔍 UDPXY检查: 没有software字段或不是数组`);
    }
    
    // 检查其他可能的字段
    const fieldsToCheck = ['service_name', 'banner', 'title', 'http_title'];
    for (const field of fieldsToCheck) {
        const value = service[field] || '';
        if (typeof value === 'string' && value.toLowerCase().includes('udpxy')) {
            console.log(`✅ UDPXY检查: 在${field}中发现UDPXY: ${value}`);
            return true;
        }
    }
    
    console.log(`❌ UDPXY检查: 端口 ${service.port} 不是UDPXY服务`);
    console.log(`📋 UDPXY检查: 服务详细信息:`, JSON.stringify(service, null, 2));
    
    return false;
}

// 从JSON数据中提取主机详情
async function extractHostDataFromJSON(hostData) {
    try {
        const scripts = document.querySelectorAll('script');
        
        for (const script of scripts) {
            const content = script.textContent || script.innerHTML;
            
            // 查找包含主机数据的JSON
            const jsonPatterns = [
                /window\.__INITIAL_STATE__\s*=\s*({.*?});/s,
                /window\.__NUXT__\s*=\s*({.*?});/s,
                /"host":\s*({.*?})/s,
                /"location":\s*({.*?})/s,
                /"services":\s*(\[.*?\])/s
            ];
            
            for (const pattern of jsonPatterns) {
                const match = content.match(pattern);
                if (match) {
                    try {
                        const data = JSON.parse(match[1]);
                        extractHostFieldsFromObject(data, hostData);
                    } catch (parseError) {
                        console.warn('JSON解析失败:', parseError);
                    }
                }
            }
        }
        
        // 查找data属性
        const dataElements = document.querySelectorAll('[data-props], [data-page], [data-host]');
        dataElements.forEach(element => {
            ['data-props', 'data-page', 'data-host'].forEach(attr => {
                const dataAttr = element.getAttribute(attr);
                if (dataAttr) {
                    try {
                        const decodedData = dataAttr.replace(/&quot;/g, '"').replace(/&amp;/g, '&');
                        const data = JSON.parse(decodedData);
                        extractHostFieldsFromObject(data, hostData);
                    } catch (parseError) {
                        console.warn('Data属性JSON解析失败:', parseError);
                    }
                }
            });
        });
        
    } catch (error) {
        console.warn('从JSON提取主机数据时出错:', error);
    }
}

// 从对象中提取主机字段
function extractHostFieldsFromObject(obj, hostData) {
    if (!obj || typeof obj !== 'object') return;
    
    // 递归查找所需字段
    function findFields(data, path = '') {
        if (!data || typeof data !== 'object') return;
        
        if (Array.isArray(data)) {
            data.forEach((item, index) => findFields(item, `${path}[${index}]`));
            return;
        }
        
        Object.keys(data).forEach(key => {
            const value = data[key];
            const currentPath = path ? `${path}.${key}` : key;
            
            if (typeof value === 'string' || typeof value === 'number') {
                // 提取DNS信息
                if ((key === 'dns' || key === 'hostname' || key === 'name') && !hostData.dns) {
                    hostData.dns = String(value);
                    console.log(`提取DNS: ${value} (路径: ${currentPath})`);
                }
                
                // 提取地理位置信息
                if (key === 'country' && !hostData.country) {
                    hostData.country = String(value);
                    console.log(`提取国家: ${value} (路径: ${currentPath})`);
                }
                
                if (key === 'city' && !hostData.city) {
                    hostData.city = String(value);
                    console.log(`提取城市: ${value} (路径: ${currentPath})`);
                }
                
                if ((key === 'province' || key === 'state' || key === 'region') && !hostData.province) {
                    hostData.province = String(value);
                    console.log(`提取省份: ${value} (路径: ${currentPath})`);
                }
                
                // 提取ISP信息
                if ((key === 'isp' || key === 'organization' || key === 'org' || key === 'asn_name') && !hostData.isp) {
                    hostData.isp = String(value);
                    console.log(`提取ISP: ${value} (路径: ${currentPath})`);
                }
                
                // 提取端口信息
                if (key === 'port' && typeof value === 'number' && value > 0) {
                    if (!hostData.ports.includes(value)) {
                        hostData.ports.push(value);
                        console.log(`提取端口: ${value} (路径: ${currentPath})`);
                    }
                }
            } else if (typeof value === 'object') {
                findFields(value, currentPath);
            }
        });
    }
    
    findFields(obj);
    
    // 特殊处理services数组，查找udpxy相关服务
    if (obj.services && Array.isArray(obj.services)) {
        obj.services.forEach(service => {
            if (service.port && typeof service.port === 'number') {
                // 检查是否是udpxy服务
                const isUdpxy = checkIfUdpxyService(service);
                if (isUdpxy && !hostData.ports.includes(service.port)) {
                    hostData.ports.push(service.port);
                    console.log(`从services提取UDPXY端口: ${service.port}`);
                }
            }
        });
    }
}

// 检查是否是udpxy服务
function checkIfUdpxyService(service) {
    if (!service || typeof service !== 'object') return false;
    
    // 检查software字段
    if (service.software && Array.isArray(service.software)) {
        for (const sw of service.software) {
            if (sw && typeof sw === 'object') {
                const vendor = sw.vendor || '';
                const product = sw.product || '';
                if (vendor.toLowerCase().includes('udpxy') || product.toLowerCase().includes('udpxy')) {
                    return true;
                }
            }
        }
    }
    
    // 检查其他字段
    const fields = ['service_name', 'banner', 'title', 'http_title'];
    for (const field of fields) {
        const value = service[field] || '';
        if (typeof value === 'string' && value.toLowerCase().includes('udpxy')) {
            return true;
        }
    }
    
    return false;
}

// 从页面文本提取主机数据
function extractHostDataFromPageText(hostData) {
    try {
        const pageText = document.body.textContent || document.body.innerText;
        
        // 如果某些字段仍为空，尝试从页面文本提取
        if (!hostData.dns) {
            const dnsMatch = pageText.match(/DNS:\s*([^\s\n,]+\.[a-zA-Z]{2,})/i) ||
                            pageText.match(/Hostname:\s*([^\s\n,]+\.[a-zA-Z]{2,})/i);
            if (dnsMatch) {
                hostData.dns = dnsMatch[1];
                console.log(`从文本提取DNS: ${hostData.dns}`);
            }
        }
        
        if (!hostData.country) {
            const countryMatch = pageText.match(/Country:\s*([^\n,]+)/i) ||
                               pageText.match(/Location:\s*([^,\n]+),/i);
            if (countryMatch) {
                hostData.country = countryMatch[1].trim();
                console.log(`从文本提取国家: ${hostData.country}`);
            }
        }
        
        if (!hostData.isp) {
            const ispMatch = pageText.match(/ISP:\s*([^\n,]+)/i) ||
                            pageText.match(/Organization:\s*([^\n,]+)/i) ||
                            pageText.match(/ASN:\s*[^\s]*\s+([^\n,]+)/i);
            if (ispMatch) {
                hostData.isp = ispMatch[1].trim();
                console.log(`从文本提取ISP: ${hostData.isp}`);
            }
        }
        
        // 提取端口信息（查找udpxy相关端口）
        const portMatches = pageText.match(/udpxy.*?(\d{1,5})|(\d{1,5}).*?udpxy/gi);
        if (portMatches) {
            portMatches.forEach(match => {
                const portMatch = match.match(/(\d{1,5})/);
                if (portMatch) {
                    const port = parseInt(portMatch[1]);
                    if (port >= 1 && port <= 65535 && !hostData.ports.includes(port)) {
                        hostData.ports.push(port);
                        console.log(`从文本提取UDPXY端口: ${port}`);
                    }
                }
            });
        }
        
    } catch (error) {
        console.warn('从页面文本提取数据时出错:', error);
    }
}

// 验证IP地址格式
function isValidIP(ip) {
    if (!ip || typeof ip !== 'string') return false;
    
    const parts = ip.split('.');
    if (parts.length !== 4) return false;
    
    return parts.every(part => {
        const num = parseInt(part, 10);
        return num >= 0 && num <= 255 && String(num) === part;
    });
}

// 检查扩展上下文并尝试重连（简化版）
function checkExtensionContext() {
    return new Promise((resolve) => {
        // 简单检查，避免Service Worker复杂交互
        if (!chrome || !chrome.runtime || !chrome.runtime.id) {
            resolve(false);
            return;
        }
        
        try {
            // 尝试访问runtime.id，这是最简单的检查方式
            const runtimeId = chrome.runtime.id;
            resolve(!!runtimeId);
        } catch (error) {
            resolve(false);
        }
    });
}

// 重新初始化扩展功能
async function reinitializeExtension() {
    console.log('🔄 尝试重新初始化扩展功能...');
    
    const isContextValid = await checkExtensionContext();
    if (!isContextValid) {
        showPageNotification('扩展上下文已失效，请重新加载页面恢复功能', 'error');
        return false;
    }
    
    try {
        // 重新创建页面UI
        await createPageUI();
        // 重新初始化自动收集状态
        await initializeAutoCollectState();
        
        showPageNotification('扩展功能已重新初始化', 'success');
        return true;
    } catch (error) {
        console.error('重新初始化失败:', error);
        showPageNotification('重新初始化失败，请手动重新加载页面', 'error');
        return false;
    }
}

console.log('✅ Censys UDPXY 提取器内容脚本初始化完成 - 双模式版本（增强错误处理）');

// 定期检查扩展上下文（降低频率，避免过度检查）
let contextCheckCount = 0;
let contextCheckInterval = null;

// 只在需要时启动上下文检查
function startContextMonitoring() {
    if (contextCheckInterval) return; // 避免重复启动
    
    contextCheckInterval = setInterval(() => {
        const currentContextValid = isExtensionContextValid();
        
        // 只在状态发生变化时处理
        if (extensionContextValid && !currentContextValid) {
            console.warn('⚠️ 检测到扩展上下文失效，停止后台操作');
            
            // 清理定时器
            if (pageLoadTimer) {
                clearTimeout(pageLoadTimer);
                pageLoadTimer = null;
            }
            
            // 停止上下文检查（避免重复警告）
            if (contextCheckInterval) {
                clearInterval(contextCheckInterval);
                contextCheckInterval = null;
            }
            
            // 禁用自动收集
            autoCollectEnabled = false;
            
            // 显示通知（只显示一次）
            if (contextCheckCount < 3) { // 最多显示3次通知
                showPageNotification('⚠️ 扩展上下文失效，功能已停用，请重新加载页面', 'error');
            }
            
            // 更新全局状态
            extensionContextValid = false;
        } else if (!extensionContextValid && currentContextValid) {
            // 上下文恢复了（可能是页面刷新后）
            console.log('✅ 扩展上下文已恢复');
            extensionContextValid = true;
            
            // 重新初始化
            setTimeout(() => {
                initializeAutoCollectState();
            }, 1000);
        }
        
        contextCheckCount++;
        
        // 如果检查次数过多，降低检查频率
        if (contextCheckCount > 20) {
            clearInterval(contextCheckInterval);
            contextCheckInterval = setInterval(arguments.callee, 30000); // 改为30秒一次
        }
    }, 10000); // 每10秒检查一次
}
