/**
 * 统一认证工具函数
 * 提供 Token 管理和带认证的请求
 */

// API 基础地址
// 直接访问 API 服务器（支持 HTTPS）
const API_BASE = 'https://1.14.205.137:9801';
const TOKEN_KEY = 'weiqi_token';

/**
 * 获取 Token（从 localStorage）
 * @returns {string} Token 或空字符串
 */
function getToken() {
    return localStorage.getItem(TOKEN_KEY) || '';
}

/**
 * 保存 Token
 * @param {string} token 
 */
function saveToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

/**
 * 清除 Token
 */
function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
}

/**
 * 检查是否有 Token
 * @returns {boolean}
 */
function hasToken() {
    return !!getToken();
}

/**
 * 跳转到认证页面
 * @param {string} returnUrl - 认证成功后返回的页面（默认当前页面）
 */
function redirectToAuth(returnUrl) {
    const url = returnUrl || window.location.href;
    const encodedReturnUrl = encodeURIComponent(url);
    window.location.href = `/weiqi-page/auth.html?return=${encodedReturnUrl}`;
}

/**
 * 带认证的 Fetch 请求
 * 自动添加 Token 到请求头，自动处理 401 错误
 * 
 * @param {string} url - 请求地址
 * @param {object} options - fetch 选项
 * @returns {Promise<Response|null>} 如果返回 null 表示已跳转
 */
async function fetchWithAuth(url, options = {}) {
    const token = getToken();
    
    // 添加认证头
    const headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };
    
    try {
        const response = await fetch(url, {
            ...options,
            headers
        });
        
        // 401/403 跳转到认证页面
        if (response.status === 401 || response.status === 403) {
            // 清除无效的 Token
            clearToken();
            redirectToAuth(window.location.href);
            return null;
        }
        
        return response;
    } catch (error) {
        console.error('请求失败:', error);
        throw new Error('网络请求失败，请检查网络连接');
    }
}

/**
 * 验证 Token 是否有效
 * @param {string} token 
 * @returns {Promise<boolean>}
 */
async function validateToken(token) {
    try {
        const response = await fetch(`${API_BASE}/api/status`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        return response.ok;
    } catch {
        return false;
    }
}

/**
 * 初始化页面（自动检查 Token）
 * 如果页面需要 Token 但用户没有，自动跳转
 * 
 * @param {boolean} requireAuth - 是否强制需要 Token
 * @returns {boolean} 是否有 Token
 */
function initAuth(requireAuth = true) {
    if (requireAuth && !hasToken()) {
        redirectToAuth();
        return false;
    }
    return true;
}
