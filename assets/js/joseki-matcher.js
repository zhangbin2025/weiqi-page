/**
 * 定式匹配器
 * 用于将着法串与定式库进行匹配
 * 支持按需加载子树，避免一次性加载整棵树
 */

class JosekiMatcher {
    /**
     * 构造函数
     * @param {string} dataPath - 定式库数据路径
     */
    constructor(dataPath = '/assets/data/joseki') {
        this.dataPath = dataPath;
        this.trieRoot = null;
        this.currentNode = null;
        this.currentPath = [];
        
        // 检测环境
        this.isNode = typeof window === 'undefined' && typeof require !== 'undefined';
        
        // Node.js 环境导入依赖
        if (this.isNode) {
            this.fs = require('fs');
            this.zlib = require('zlib');
            this.path = require('path');
        }
    }

    /**
     * 加载 gzip 压缩的 JSON 文件
     * @param {string} url - 文件 URL 或路径
     * @returns {Promise<Object>} 解压后的 JSON 对象
     */
    async loadGzipJson(url) {
        try {
            if (this.isNode) {
                // Node.js 环境：使用 fs 和 zlib
                const compressed = this.fs.readFileSync(url);
                const decompressed = this.zlib.gunzipSync(compressed);
                const jsonStr = decompressed.toString('utf-8');
                return JSON.parse(jsonStr);
            } else {
                // 浏览器环境：使用 fetch 和 pako
                const response = await fetch(url);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const compressed = await response.arrayBuffer();
                const decompressed = pako.ungzip(compressed, { to: 'string' });
                return JSON.parse(decompressed);
            }
        } catch (error) {
            console.error(`[JosekiMatcher] 加载失败: ${url}`, error);
            throw error;
        }
    }

    /**
     * 加载索引（trie 树根节点）
     */
    async loadIndex() {
        if (this.trieRoot) {
            return; // 已加载
        }

        try {
            this.trieRoot = await this.loadGzipJson(`${this.dataPath}/trie-index.json.gz`);
            this.currentNode = this.trieRoot;
            this.currentPath = [];
            console.log('[JosekiMatcher] 索引加载成功');
        } catch (error) {
            console.error('[JosekiMatcher] 索引加载失败:', error);
            throw error;
        }
    }

    /**
     * 加载子树并合并到节点
     * @param {Object} node - trie 树节点
     */
    async loadSubtree(node) {
        if (!node.subtree || node.children) {
            return; // 不是裁剪点或已加载
        }

        try {
            const subtree = await this.loadGzipJson(`${this.dataPath}/${node.subtree.file}`);
            
            // 合并子树的所有字段（覆盖同名字段）
            for (const key in subtree) {
                node[key] = subtree[key];
            }
            
            console.log(`[JosekiMatcher] 子树加载成功: ${node.subtree.file}`);
        } catch (error) {
            console.error(`[JosekiMatcher] 子树加载失败: ${node.subtree.file}`, error);
            throw error;
        }
    }

    /**
     * 匹配单个着法串
     * @param {Array} moves - SGF 坐标数组（如 ['pd', 'qc', 'qd']）
     * @returns {Promise<Object>} 匹配结果
     */
    async matchSequence(moves) {
        // 确保索引已加载
        await this.loadIndex();

        let node = this.trieRoot;
        const matchedPath = [];

        for (let i = 0; i < moves.length; i++) {
            const coord = moves[i];
            
            // 跳过 pass
            if (coord === 'tt' || coord === 'pass') {
                continue;
            }

            // 检查当前节点是否需要加载子树
            if (node.subtree && !node.children) {
                await this.loadSubtree(node);
            }

            // 检查是否有子节点
            if (!node.children) {
                // 无法继续匹配
                return {
                    matched: matchedPath,
                    matchedCount: i,
                    totalCount: moves.length,
                    node: node,
                    complete: false
                };
            }

            // 查找下一个节点
            if (node.children[coord]) {
                node = node.children[coord];
                matchedPath.push(coord);
            } else {
                // 未找到匹配
                return {
                    matched: matchedPath,
                    matchedCount: i,
                    totalCount: moves.length,
                    node: node,
                    complete: false
                };
            }
        }

        // 完全匹配
        return {
            matched: matchedPath,
            matchedCount: moves.length,
            totalCount: moves.length,
            node: node,
            complete: true,
            freq: node.freq,
            moves: node.moves,
            prob: node.prob,
            heat: node.heat,
            winrate_stats: node.winrate_stats
        };
    }

    /**
     * 批量匹配四个角的着法
     * @param {Object} corners - 四个角的着法 {tl: [...], tr: [...], bl: [...], br: [...]}
     * @returns {Promise<Object>} 匹配结果
     */
    async matchFourCorners(corners) {
        // 确保索引已加载
        await this.loadIndex();

        const results = {};

        for (const cornerKey of ['tl', 'tr', 'bl', 'br']) {
            const moves = corners[cornerKey];
            if (!moves || moves.length === 0) {
                results[cornerKey] = {
                    matched: [],
                    complete: false,
                    error: '无着法'
                };
                continue;
            }

            try {
                const result = await this.matchSequence(moves);
                results[cornerKey] = result;
            } catch (error) {
                results[cornerKey] = {
                    matched: [],
                    complete: false,
                    error: error.message
                };
            }
        }

        return results;
    }

    /**
     * 重置到根节点
     */
    reset() {
        this.currentNode = this.trieRoot;
        this.currentPath = [];
    }
}

// 导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = JosekiMatcher;
}
