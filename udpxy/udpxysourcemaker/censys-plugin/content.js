// Censys UDPXY 提取器 - 内容脚本 (双模式版本)
console.log('🚀 Censys UDPXY 提取器内容脚本已加载 - 双模式版本');

// 全局变量
let autoCollectEnabled = false;
let pageLoadTimer = null;
let floatingButton = null;
let statusIndicator = null;
let extensionContextValid = true;

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
        
        // 如果启用了自动收集，立即尝试收集
        if (autoCollectEnabled) {
            setTimeout(checkAndAutoCollectHostData, 2000);
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
    
    container.appendChild(extractButton);
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
        
        // 如果启用了自动收集，立即尝试收集当前页面
        if (newState) {
            setTimeout(checkAndAutoCollectHostData, 1000);
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

// 检测页面类型并自动收集主机数据
async function checkAndAutoCollectHostData() {
    try {
        // 检查扩展上下文 - 如果无效，仍然尝试数据提取但不保存
        const contextValid = isExtensionContextValid();
        if (!contextValid) {
            console.warn('扩展上下文无效，将尝试数据提取但无法保存');
        }
        
        // 检查是否是主机详情页面
        const isHostPage = window.location.href.match(/\/hosts\/([\d.]+)/);
        
        if (isHostPage && autoCollectEnabled) {
            console.log('📡 检测到主机详情页面，准备自动收集数据...');
            
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
        }
    } catch (contextError) {
        console.error('检查自动收集时发生错误:', contextError);
        showPageNotification('⚠️ 扩展功能异常，请重新加载页面', 'error');
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
            isp: ''
        };
        
        // 首先尝试从API获取JSON数据
        await extractHostDataFromAPI(hostData);
        
        // 如果API数据不完整，再从页面JSON提取
        await extractHostDataFromJSON(hostData);
        
        // 如果JSON提取不完整，尝试从页面文本提取
        extractHostDataFromPageText(hostData);
        
        console.log('✅ 主机数据提取完成:', hostData);
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
            const jsonData = await response.json();
            console.log('✅ API响应数据:', jsonData);
            
            // 从API响应中提取数据
            extractHostFieldsFromAPIResponse(jsonData, hostData);
        } else {
            console.warn(`API请求失败: ${response.status} ${response.statusText}`);
        }
        
    } catch (error) {
        console.warn('从API获取主机数据时出错:', error);
    }
}

// 从API响应中提取主机字段
function extractHostFieldsFromAPIResponse(data, hostData) {
    if (!data || typeof data !== 'object') return;
    
    try {
        // 处理Censys API的标准响应格式
        let hostInfo = data;
        
        // 如果响应包含host字段，使用host数据
        if (data.host) {
            hostInfo = data.host;
        }
        
        // 提取DNS信息
        if (hostInfo.dns && hostInfo.dns.names && Array.isArray(hostInfo.dns.names) && hostInfo.dns.names.length > 0) {
            hostData.dns = hostInfo.dns.names[0];
            console.log(`API提取DNS: ${hostData.dns}`);
        }
        
        // 提取地理位置信息
        if (hostInfo.location) {
            const location = hostInfo.location;
            if (location.country && !hostData.country) {
                hostData.country = location.country;
                console.log(`API提取国家: ${hostData.country}`);
            }
            if (location.city && !hostData.city) {
                hostData.city = location.city;
                console.log(`API提取城市: ${hostData.city}`);
            }
            if ((location.province || location.state || location.region) && !hostData.province) {
                hostData.province = location.province || location.state || location.region;
                console.log(`API提取省份: ${hostData.province}`);
            }
        }
        
        // 提取ISP信息
        if (hostInfo.whois && hostInfo.whois.network && hostInfo.whois.network.name && !hostData.isp) {
            hostData.isp = hostInfo.whois.network.name;
            console.log(`API提取ISP: ${hostData.isp}`);
        }
        
        // 提取服务和端口信息
        if (hostInfo.services && Array.isArray(hostInfo.services)) {
            hostInfo.services.forEach(service => {
                if (service.port && typeof service.port === 'number') {
                    // 检查是否是udpxy服务
                    const isUdpxy = checkIfUdpxyServiceFromAPI(service);
                    if (isUdpxy && !hostData.ports.includes(service.port)) {
                        hostData.ports.push(service.port);
                        console.log(`API提取UDPXY端口: ${service.port}`);
                    }
                }
            });
        }
        
        console.log('API数据提取完成，当前hostData:', hostData);
        
    } catch (error) {
        console.warn('解析API响应数据时出错:', error);
    }
}

// 检查API响应中的服务是否是udpxy
function checkIfUdpxyServiceFromAPI(service) {
    if (!service || typeof service !== 'object') return false;
    
    // 检查software字段
    if (service.software && Array.isArray(service.software)) {
        for (const sw of service.software) {
            if (sw && typeof sw === 'object') {
                const vendor = (sw.vendor || '').toLowerCase();
                const product = (sw.product || '').toLowerCase();
                if (vendor.includes('udpxy') || product.includes('udpxy')) {
                    console.log(`发现UDPXY服务 - vendor: ${sw.vendor}, product: ${sw.product}`);
                    return true;
                }
            }
        }
    }
    
    // 检查其他可能的字段
    const fieldsToCheck = ['service_name', 'banner', 'title'];
    for (const field of fieldsToCheck) {
        const value = service[field] || '';
        if (typeof value === 'string' && value.toLowerCase().includes('udpxy')) {
            console.log(`在${field}中发现UDPXY: ${value}`);
            return true;
        }
    }
    
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
setInterval(() => {
    const currentContextValid = isExtensionContextValid();
    
    // 只在状态发生变化时处理
    if (extensionContextValid && !currentContextValid) {
        console.warn('⚠️ 检测到扩展上下文失效，停止后台操作');
        
        // 清理定时器
        if (pageLoadTimer) {
            clearTimeout(pageLoadTimer);
            pageLoadTimer = null;
        }
        
        // 禁用自动收集
        autoCollectEnabled = false;
        
        // 显示通知（只显示一次）
        showPageNotification('⚠️ 扩展上下文失效，功能已停用，请重新加载页面', 'error');
        
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
}, 10000); // 每10秒检查一次（降低频率）
