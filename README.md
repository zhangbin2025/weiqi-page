# 围棋资源站点生成器

自动化围棋资源站点的生成和维护系统。

## 项目结构

```
.
├── scripts/                    # 核心脚本
│   ├── daily_update.py         # 每日更新主控脚本
│   ├── generate_games.py       # 棋谱页生成
│   ├── generate_quiz.py        # 选点题生成
│   ├── generate_joseki.py      # 定式研究页生成
│   ├── generate_index.py       # 索引页生成
│   ├── generate_article.py     # 公众号文章生成
│   ├── config.py               # 配置文件
│   └── common.py               # 公共模块
├── templates/                  # 模板文件
│   ├── index.html              # 首页模板
│   ├── games_list.html         # 棋谱列表模板
│   ├── quiz_list.html          # 选点题列表模板
│   └── joseki_list.html        # 定式列表模板
└── .env.example                # 环境变量模板
```

## 依赖技能包

- `weiqi-db` - 棋谱数据库
- `weiqi-sgf` - 打谱网页生成
- `weiqi-move` - 选点题生成
- `weiqi-joseki` - 定式数据库
- `weiqi-foxwq` - 野狐棋谱下载

## 快速开始

### 1. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，填入你的 GitHub 用户名
# GITHUB_USERNAME=your-username
```

### 2. 运行测试

```bash
cd scripts
python3 test_runner.py
```

### 3. 测试模式运行

```bash
# 测试指定日期
python3 daily_update.py --date 2026-04-01 --test

# 或运行完整流程
python3 daily_update.py --test
```

### 4. 正式部署

```bash
# 默认处理昨天数据
python3 daily_update.py

# 或指定日期
python3 daily_update.py --date 2026-04-13
```

## 自动化配置

添加 cron 任务实现每日自动更新：

```bash
# 编辑 crontab
crontab -e

# 添加每日6点执行（根据实际路径修改）
0 6 * * * cd /path/to/weiqi-page/scripts && python3 daily_update.py >> /tmp/weiqi-update.log 2>&1
```

## 功能说明

### 棋谱页生成
- 从 `weiqi-db` 读取棋谱
- 按日期和来源分类
- 生成打谱网页（`weiqi-sgf`）

### 选点题生成
- 优先生成恶手题
- 无恶手则跳过该棋谱
- 使用 `weiqi-move` 生成做题页

### 定式研究
- 提取棋谱中的不常见定式
- 使用 `weiqi-joseki` 识别和匹配

### 不常见定式判定
- 基于 weiqi-db 统计
- 识别不常见或稀有定式变化

## 配置参数

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `GITHUB_USERNAME` | GitHub 用户名（必填） | 从 git config 获取 |
| `WEIQI_WORKSPACE` | 工作目录 | 相对路径自动计算 |
| `WEIQI_SKILLS_DIR` | 技能包目录 | 相对路径自动计算 |
| `WEIQI_DB_DIR` | 数据库目录 | `~/.weiqi-db` |
| `WEIQI_JOSEKI_DB_DIR` | 定式数据库目录 | `~/.weiqi-joseki` |

### 公众号文章

```python
WECHAT_ARTICLE = {
    "max_featured_games": 2,   # 推荐棋谱数
    "max_featured_quiz": 1,    # 推荐选点题数
    "max_featured_joseki": 1,  # 推荐定式数
}
```

## 访问标记

- 使用 LocalStorage 记录访问历史
- 已访问链接显示为灰色/打勾
- 支持"未查看"快速筛选

## 资源互通

嵌入 `common.js` 实现：
- 打谱页停留2分钟 → 提示选点题
- 定式页停留30秒 → 提示棋谱搜索

## 测试

```bash
# 运行所有测试
python3 test_runner.py
```

## 注意事项

1. **环境变量**：首次使用需配置 `.env` 文件，复制 `.env.example` 并填入实际值
2. **测试模式**：`--test` 参数会在 `test_site/` 生成文件，不影响正式站点
3. **Git 推送**：目前需要手动推送，后续可配置自动 `git commit & push`

## 隐私与安全

- `.env` 文件包含敏感配置，**不要**提交到 Git
- `.gitignore` 已配置忽略本地数据目录
- 路径使用相对路径或环境变量，避免硬编码系统路径

## 更新日志

### 2026-04-13
- 初始版本发布
- 完成基础框架和核心脚本
- 通过全部测试用例
