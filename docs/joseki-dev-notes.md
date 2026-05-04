# 定式探索工具开发笔记

> 记录开发过程中的设计思路、技术要点、踩坑经验，避免重复犯错。

## 项目背景

**目标**：开发围棋定式探索工具，用户点击选点，逐步探索定式变化。

**数据来源**：weiqi-joseki 技能包的 export 接口，支持 --prefix 参数过滤。

---

## 当前问题（2026-05-04）

### 分桶方案的致命缺陷

**问题描述**：
- 前缀过滤 `pd qc` 导致分桶深度不一致
- 实际分桶键是 `pd-qc-pc-xxx`（4层），而非预期的 `pd-qc`（2层）
- 点击第二着后，需要加载所有前缀��配的分桶，性能极差

**根本原因**：
- 分桶逻辑按前2着分组，但前缀过滤改变了这个假设
- 数据生成脚本和前端逻辑对"分桶深度"理解不一致

**前端痛苦**：
- 点击第二着时，需要遍历 191 个分桶提取第三着
- 每次点击后续着法，都要重新匹配分桶、加载 gz
- 用户反馈："加载太多 gz 包，等待体验太差，根本不想用了"

---

## 新方案设计思路

### 方案A：按首着分桶（推荐）

```
trie-index.json.gz  - 首着列表（pd, qc, dd...）
pd.json.gz          - 所有以 pd 开头的定式 trie
qc.json.gz          - 所有以 qc 开头的定式 trie
...
```

**trie 结构**：
```json
{
  "coord": null,
  "children": {
    "qc": {
      "coord": "qc",
      "children": {
        "pc": { "children": {...}, "freq": 100 },
        "tt": { "leaf": true, "freq": 50 }
      },
      "leaf": true,  // pd-qc 是完整定式
      "freq": 100
    }
  }
}
```

**优点**：
- 前端只需 **2 次 HTTP 请求**（索引 + 首着 trie）
- 点击首着后，所有后续探索都在内存中，无需再请求
- trie 结构简单，直接递归遍历，逻辑清晰
- 一个 trie 约 200-500KB（gzip），27780条定式总共约 1MB

**缺点**：
- 需要重构 generate_joseki_tree.py
- 前端 explore.html 需要重写 trie 遍历逻辑

---

## 踩坑记录

### 错误1：setMoves/setBranches 调用顺序

**问题**：`setMoves()` 会清空 `branches`，导致选点消失。

**修复**：
```javascript
// ❌ 错误顺序
board.setBranches(branches);
board.setMoves(currentMoves, currentIndex);  // 这会清空 branches！

// ✅ 正确顺序
board.setMoves(currentMoves, currentIndex);  // 先设置棋盘
board.setBranches(branches);                  // 再设置选点
```

### 错误2：分桶键计算与前缀深度不匹配

**问题**：
- 前缀 `pd qc` 意味着首着和二着固定
- 前端用 `currentNodePath.slice(0, 2)` 生成分桶键 `pd-qc`
- 但实际分桶是 `pd-qc-pc-xxx`，不存在 `pd-qc`

**教训**：
- 分桶逻辑必须与前端逻辑保持一致
- 有前缀时，分桶深度 = 前缀深度 + 1

### 错误3：从 root children 提取选点

**问题**：
- 分桶 `pd-qc-pc-kd` 的 `root.children` 是第5着（kd）
- 错误地把第5着当作第3着显示

**正确做法**：
- 从分桶键中提取：`pd-qc-pc-xxx` → 第三着是 `pc`
- 或者从 trie nodes 中查找对应路径

### 错误4：概率字段名不一致

**问题**：
- 数据库字段是 `probability`
- Python 代码存储为 `prob`
- 前端读取时混淆

**修复**：统一使用 `prob` 字段名

### 错误5：canvas 坐标转换与 DPR 不匹配

**问题**：
- 高清屏 DPR=2，canvas.width=800（实际像素）
- canvas.style.width=400（显示尺寸）
- 点击坐标转换时，需要考虑 DPR

**修复**：
```javascript
// canvasX/Y 已经是实际像素坐标（通过 rect.width * target.width 计算）
// 所以 canvasToSgf 应使用 canvas.width（实际像素尺寸）
const canvasSize = this.canvas.width; // 不除以 dpr
```

---

## 技术要点

### 1. 棋盘显示范围

- 实际棋盘 19x19，显示右上角 13x13
- `startX = 6, startY = 0`
- 坐标转换：`displayX = x - startX`

### 2. 选点样式

- 黑棋位置：橙色半透明圆圈，边框宽度3
- 白棋位置：蓝色半透明圆圈，边框宽度3
- 脱先（tt）：不在棋盘显示，通过 passBtn 按钮

### 3. leaf 节点含义

- `leaf` 只表示"某个定式到这里结束"
- 有 `children` 时可以继续探索
- 既可以是终点，也可以是中继点

### 4. 数据文件约定

- 数据文件不归档到 Git
- 部署时由脚本生成：`python3 scripts/generate_joseki_tree.py`
- 测试用 `--test` 参数输出到 test_site

---

## 下一步计划

### Phase 1：重构存储方案

1. 修改 `generate_joseki_tree.py`：
   - 按首着分桶，生成 trie 结构
   - 移除复杂的动态分桶逻辑
   
2. 新增 `export_joseki_trie.py`（可选）：
   - 直接调用 weiqi-joseki export
   - 转换为 trie JSON

### Phase 2：重写前端逻辑

1. 修改 `explore.html`：
   - 加载索引 + 首着 trie（2次请求）
   - trie 递归遍历，简化选点逻辑
   
2. 修改 `joseki-board.js`：
   - 优化渲染性能
   - 修复高清屏问题（已修复）

### Phase 3：测试优化

1. 先用小数据测试（prefix `pd qc pc qd qe re rf`）
2. 再用大数据测试（prefix `pd qc`）
3. 最后全量测试（无 prefix）

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `templates/tools/joseki/explore.html` | 探索页面，核心前端逻辑 |
| `templates/tools/joseki/quiz.html` | 做题页面 |
| `templates/tools/joseki/index.html` | 定式工具首页 |
| `assets/js/joseki-board.js` | 棋盘渲染类 |
| `assets/js/board-thumbnail.js` | 缩略图渲染 |
| `assets/css/joseki.css` | 定式工具样式 |
| `scripts/generate_joseki_tree.py` | 数据生成脚本 |

---

## 相关技能包

- **weiqi-joseki**：定式数据库，提供 export 接口
- 路径：`/root/.openclaw/workspace/weiqi-joseki`
- 数据库：`/root/.weiqi-joseki/database.json`
- export 命令：`python3 -m src.cli.commands export --prefix PREFIX --format json -o OUTPUT`