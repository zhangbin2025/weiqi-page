"""
围棋资源站点生成器 - 配置文件
"""
import os
from pathlib import Path

# 基础路径
HOME_DIR = Path.home()
WORKSPACE_DIR = Path("/root/.weiqi-web")
SITE_ROOT = WORKSPACE_DIR / "zhangbin2025.github.io"  # GitHub Pages 根目录
SITE_DIR = SITE_ROOT / "weiqi-page"  # 实际部署到子目录
TEST_SITE_DIR = WORKSPACE_DIR / "test_site" / "weiqi-page"  # 测试模式也使用相同的子目录结构
WEIQI_PAGE_DIR = WORKSPACE_DIR / "weiqi-page"
SCRIPTS_DIR = WEIQI_PAGE_DIR / "scripts"
TEMPLATES_DIR = WEIQI_PAGE_DIR / "templates"

# 技能包路径
SKILLS_DIR = Path("/root/.openclaw/workspace")
WEIQI_DB_SCRIPT = SKILLS_DIR / "weiqi-db/scripts/db.py"
WEIQI_SGF_SCRIPT = SKILLS_DIR / "weiqi-sgf/scripts/replay.py"
WEIQI_MOVE_SCRIPT = SKILLS_DIR / "weiqi-move/scripts/quiz.py"
WEIQI_JOSEKI_DIR = SKILLS_DIR / "weiqi-joseki"  # joseki目录
WEIQI_JOSEKI_SCRIPT = WEIQI_JOSEKI_DIR / "db.py"  # 使用db.py兼容性入口
WEIQI_FOXWQ_SCRIPT = SKILLS_DIR / "weiqi-foxwq/scripts/download_sgf.py"

# 数据存储路径
WEIQI_DB_PATH = HOME_DIR / ".weiqi-db/database.json"
WEIQI_JOSEKI_DB_PATH = HOME_DIR / ".weiqi-joseki/database.json"
KATAGO_CACHE_DIR = HOME_DIR / ".weiqi-joseki/katago-cache"
KATAGO_STATE_FILE = KATAGO_CACHE_DIR / "last_processed.txt"

# KataGo定式更新配置
KATAGO_CONFIG = {
    "min_count": 10,        # 出现10次以上算新定式
    "min_rate": 0,          # 不限制出现概率
    "min_moves": 4,         # 最少4手
    "first_n": 80,          # 每谱提取前80手
    "resume": True,         # 支持断点续传
}

# 公众号文章配置
WECHAT_ARTICLE = {
    "template": "daily_wechat.md",
    "max_featured_games": 2,    # 推荐棋谱数量
    "max_featured_quiz": 1,     # 推荐选点题数量
    "max_featured_joseki": 1,   # 推荐定式数量
}

# 站点配置
SITE_CONFIG = {
    "title": "围棋资源站",
    "subtitle": "zhangbin2025",
    "base_url": "https://zhangbin2025.github.io",
    "sources": ["foxwq", "katago", "yike"],  # 支持的来源
}

# GitHub Pages 部署路径（子目录）
BASE_PATH = "/weiqi-page"

def ensure_dirs(test_mode=False):
    """确保必要的目录存在"""
    base_dir = TEST_SITE_DIR if test_mode else SITE_DIR
    dirs = [
        base_dir / "games",
        base_dir / "quiz",
        base_dir / "joseki",
        base_dir / "assets" / "css",
        base_dir / "assets" / "js",
        base_dir / "_data",
        KATAGO_CACHE_DIR,
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return base_dir

def get_date_dir(base_dir, date_str, source=None):
    """获取日期目录路径"""
    if source:
        return base_dir / date_str / source
    return base_dir / date_str
