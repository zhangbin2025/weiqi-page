/**
 * 野狐围棋前端代理
 * 通过 Cloudflare Worker 代理访问野狐 API
 * 实现棋谱下载的前端化
 */

class FoxwqProxy {
    constructor(options = {}) {
        // 代理服务器地址
        this.proxyUrl = options.proxyUrl || 'https://api.weiqi.lol';
        // 调试模式
        this.debug = options.debug || false;
        // 请求超时（毫秒）
        this.timeout = options.timeout || 30000;
        // 性能统计
        this.perf = {
            total: 0,
            requests: 0,
            startTime: null
        };
    }

    /**
     * 通过代理发送 GET 请求
     */
    async fetch(url, params = {}) {
        const fullUrl = params ? `${url}?${new URLSearchParams(params)}` : url;
        const proxyFullUrl = `${this.proxyUrl}/?url=${encodeURIComponent(fullUrl)}`;
        
        const startTime = performance.now();
        this.perf.requests++;
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.timeout);
            
            const response = await fetch(proxyFullUrl, {
                signal: controller.signal,
                headers: {
                    'Accept': 'application/json'
                }
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const data = await response.json();
            const elapsed = performance.now() - startTime;
            this.perf.total += elapsed;
            
            if (this.debug) {
                console.log(`[FoxwqProxy] ${url} - ${elapsed.toFixed(0)}ms`, data);
            }
            
            return data;
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('请求超时');
            }
            throw error;
        }
    }

    /**
     * 通过昵称查询用户信息
     * @param {string} nickname - 野狐昵称
     * @returns {Promise<Object>} 用户信息
     */
    async queryUserByName(nickname) {
        const url = 'https://newframe.foxwq.com/cgi/QueryUserInfoPanel';
        const params = {
            srcuid: 0,
            username: nickname
        };
        
        const data = await this.fetch(url, params);
        
        if (data.result !== 0) {
            const errorMsg = data.resultstr || data.errmsg || '未知错误';
            throw new Error(`查询用户失败: ${errorMsg}`);
        }
        
        const uid = String(data.uid || '').trim();
        if (!uid) {
            throw new Error('未找到该昵称对应的UID');
        }
        
        return {
            uid: uid,
            nickname: data.username || data.name || data.englishname || nickname,
            dan: data.dan || 0,
            total_win: data.totalwin || 0,
            total_lost: data.totallost || 0,
            total_equal: data.totalequal || 0
        };
    }

    /**
     * 获取棋谱列表
     * @param {string} uid - 用户 UID
     * @param {string} lastcode - 分页参数（默认 "0"）
     * @returns {Promise<Array>} 棋谱列表
     */
    async fetchChessList(uid, lastcode = "0") {
        const url = 'https://h5.foxwq.com/yehuDiamond/chessbook_local/YHWQFetchChessList';
        const params = {
            srcuid: 0,
            dstuid: uid,
            type: 1,
            lastcode: lastcode,
            searchkey: '',
            uin: uid
        };
        
        const data = await this.fetch(url, params);
        
        if (data.result !== 0) {
            const errorMsg = data.resultstr || '获取棋谱列表失败';
            throw new Error(errorMsg);
        }
        
        return data.chesslist || [];
    }

    /**
     * 下载单局 SGF
     * @param {string} chessid - 棋谱 ID
     * @returns {Promise<string>} SGF 内容
     */
    async fetchSGF(chessid) {
        const url = 'https://h5.foxwq.com/yehuDiamond/chessbook_local/YHWQFetchChess';
        const params = {
            chessid: chessid
        };
        
        const data = await this.fetch(url, params);
        
        if (data.result !== 0) {
            throw new Error(`下载棋谱失败: ${data.resultstr || '未知错误'}`);
        }
        
        return data.chess || '';
    }

    /**
     * 格式化段位显示
     */
    static formatDan(danValue) {
        if (danValue >= 100) {
            return `职业${danValue - 100}段`;
        } else if (danValue >= 24) {
            return `业${danValue - 20}段`;
        } else if (danValue >= 20) {
            return `业${danValue - 20}段`;
        } else if (danValue >= 10) {
            return `${danValue - 10}级`;
        } else {
            return `${danValue}级`;
        }
    }

    /**
     * 解析对局结果
     */
    static parseResult(winner, point, reason) {
        if (winner === 0) {
            return "和棋";
        }
        
        const winnerStr = winner === 1 ? "黑胜" : "白胜";
        
        if (reason === 1) {
            if (point > 0) {
                return `${winnerStr} ${point}子`;
            }
            return winnerStr;
        } else if (reason === 2) {
            return `${winnerStr} (超时)`;
        } else if (reason === 3) {
            return `${winnerStr} (中盘)`;
        } else if (reason === 4) {
            return `${winnerStr} (认输)`;
        } else {
            return winnerStr;
        }
    }

    /**
     * 获取性能统计
     */
    getPerf() {
        return {
            requests: this.perf.requests,
            totalTime: this.perf.total,
            avgTime: this.perf.requests > 0 ? this.perf.total / this.perf.requests : 0
        };
    }

    /**
     * 获取 HTML 页面内容（通过代理）
     * @param {string} url - 页面 URL
     * @returns {Promise<string>} HTML 内容
     */
    async fetchHtml(url) {
        const proxyFullUrl = `${this.proxyUrl}/?url=${encodeURIComponent(url)}`;
        
        const startTime = performance.now();
        this.perf.requests++;
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.timeout);
            
            const response = await fetch(proxyFullUrl, {
                signal: controller.signal,
                headers: {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            
            const html = await response.text();
            const elapsed = performance.now() - startTime;
            this.perf.total += elapsed;
            
            if (this.debug) {
                console.log(`[FoxwqProxy] fetchHtml ${url} - ${elapsed.toFixed(0)}ms`);
            }
            
            return html;
        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('请求超时');
            }
            throw error;
        }
    }

    /**
     * 获取野狐公开棋谱列表
     * @param {string|null} date - 日期过滤，格式 'YYYY-MM-DD'，null 表示所有
     * @returns {Promise<Array>} 棋谱列表
     */
    async fetchPublicQipuList(date = null) {
        const LIST_URL = 'https://www.foxwq.com/qipu.html';
        
        const html = await this.fetchHtml(LIST_URL);
        
        // 解析 HTML 提取棋谱链接
        const links = [];
        
        // 使用正则匹配棋谱链接和日期
        // 链接格式: /qipu/newlist/id/123456.html
        // 日期在最后一个 <td> 中
        const rowPattern = /<tr[^>]*>.*?<\/tr>/gs;
        const linkPattern = /<a[^>]*href="(\/qipu\/newlist\/id\/\d+\.html)"[^>]*>/i;
        const titlePattern = /<h4[^>]*>(.*?)<\/h4>/i;
        const datePattern = /<td[^>]*>(\d{4}-\d{2}-\d{2})[^<]*<\/td>\s*<\/tr>/i;
        
        let rowMatch;
        const rowRegex = new RegExp(rowPattern.source, 'gs');
        
        while ((rowMatch = rowRegex.exec(html)) !== null) {
            const rowHtml = rowMatch[0];
            
            // 提取链接
            const linkMatch = rowHtml.match(linkPattern);
            if (!linkMatch) continue;
            
            // 提取标题
            const titleMatch = rowHtml.match(titlePattern);
            const title = titleMatch ? titleMatch[1].replace(/<[^>]+>/g, '').trim() : '未知';
            
            // 提取日期
            const dateMatch = rowHtml.match(datePattern);
            const qipuDate = dateMatch ? dateMatch[1] : '';
            
            // 日期过滤
            if (date && qipuDate !== date) continue;
            
            links.push({
                title: title,
                url: `https://www.foxwq.com${linkMatch[1]}`,
                date: qipuDate
            });
        }
        
        if (this.debug) {
            console.log(`[FoxwqProxy] 找到 ${links.length} 个公开棋谱`);
        }
        
        return links;
    }

    /**
     * 下载公开棋谱的 SGF
     * @param {string} url - 棋谱详情页 URL
     * @returns {Promise<Object>} { sgf, title, date }
     */
    async fetchPublicQipuSgf(url) {
        const html = await this.fetchHtml(url);
        
        // 提取 SGF 内容（以 (;GM[1]FF[4] 开头）
        const sgfStart = html.indexOf('(;GM[1]FF[4]');
        if (sgfStart === -1) {
            throw new Error('无法提取 SGF 内容');
        }
        
        // 从 SGF 开始位置查找第一个 HTML 标签的位置
        const sgfRemainder = html.substring(sgfStart);
        const htmlTagMatch = sgfRemainder.match(/<\/?[a-zA-Z][^>]*>/);
        
        let sgf;
        if (htmlTagMatch) {
            // 截取 SGF 内容（从开头到第一个 HTML 标签之前）
            sgf = sgfRemainder.substring(0, htmlTagMatch.index);
        } else {
            // 备选：使用正则匹配
            const sgfMatch = html.match(/\(;GM\[1\]FF\[4\][\s\S]*?\)\s*\)\s*\)/);
            sgf = sgfMatch ? sgfMatch[0] : '';
        }
        
        // 去除末尾空白
        sgf = sgf.trim();
        
        if (!sgf) {
            throw new Error('SGF 内容为空');
        }
        
        // 提取标题和日期（从页面中）
        const titleMatch = html.match(/<h1[^>]*>(.*?)<\/h1>/i);
        const title = titleMatch ? titleMatch[1].replace(/<[^>]+>/g, '').trim() : '未知';
        
        const dateMatch = html.match(/(\d{4}-\d{2}-\d{2})/);
        const date = dateMatch ? dateMatch[1] : '';
        
        return { sgf, title, date };
    }
}

// 导出（如果支持模块）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = FoxwqProxy;
}
