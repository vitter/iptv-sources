// Censys UDPXY 提取器后台脚本
try {
    console.log('🚀 Censys UDPXY 提取器后台脚本已启动');
} catch (error) {
    // Service Worker中console可能不可用，忽略错误
}

// 监听来自内容脚本的消息
if (chrome && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        try {
            console.log('📨 收到消息:', message);
        } catch (e) {
            // 忽略console错误
        }
        
        // 处理ping请求（用于检查扩展上下文）
        if (message && message.action === 'ping') {
            try {
                sendResponse({status: 'pong', timestamp: Date.now()});
                return true;
            } catch (error) {
                // 如果sendResponse失败，返回false
                return false;
            }
        }
        
        // 处理其他消息类型...
        return false;
    });
}

// 扩展安装时的初始化
if (chrome && chrome.runtime && chrome.runtime.onInstalled) {
    chrome.runtime.onInstalled.addListener((details) => {
        try {
            console.log('📦 扩展已安装/更新:', details);
            
            if (details && details.reason === 'install') {
                console.log('🎉 首次安装 Censys UDPXY 提取器');
            } else if (details && details.reason === 'update') {
                console.log('🔄 Censys UDPXY 提取器已更新');
            }
        } catch (error) {
            // 忽略错误，确保扩展能正常工作
        }
    });
}

// 扩展启动时
if (chrome && chrome.runtime && chrome.runtime.onStartup) {
    chrome.runtime.onStartup.addListener(() => {
        try {
            console.log('🌟 Censys UDPXY 提取器随浏览器启动');
        } catch (error) {
            // 忽略错误
        }
    });
}
