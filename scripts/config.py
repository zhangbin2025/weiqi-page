"""
围棋资源站点生成器 - 配置文件
支持环境变量配置，避免硬编码敏感信息
"""
import os
from pathlib import Path

# 尝试加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv 未安装时跳过

# 基础路径 - 使用环境变量或基于脚本位置计算
HOME_DIR = Path.home()
SCRIPT_DIR = Path(__file__).parent.resolve()
WEIQI_PAGE_DIR = SCRIPT_DIR.parent  # scripts/ 的父目录

# 工作目录：优先使用环境变量，其次使用相对路径
WORKSPACE_DIR = Path(os.getenv("WEIQI_WORKSPACE", WEIQI_PAGE_DIR.parent))

# GitHub 用户名 - 必须配置，用于生成站点链接
# 优先从 .env 文件加载，其次尝试 git config
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
if not GITHUB_USERNAME or " " in GITHUB_USERNAME:
    # 尝试从 git config 获取（排除带空格的名称，那通常是用户全名而非用户名）
    import subprocess
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, check=True
        )
        git_name = result.stdout.strip()
        # 如果 git name 包含空格，尝试使用 git remote url 解析
        if " " in git_name:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, check=True
            )
            remote_url = result.stdout.strip()
            # 从 https://github.com/username/repo.git 或 git@github.com:username/repo.git 解析用户名
            import re
            match = re.search(r'github\.com[/:]([^/]+)', remote_url)
            if match:
                git_name = match.group(1)
        GITHUB_USERNAME = git_name
    except Exception as e:
        GITHUB_USERNAME = "your-username"  # 占位符，需要手动配置
        print(f"⚠️ 警告: 无法自动获取 GitHub 用户名，请在 .env 文件中配置 GITHUB_USERNAME")
        print(f"   错误: {e}")

SITE_ROOT = WORKSPACE_DIR / f"{GITHUB_USERNAME}.github.io"  # GitHub Pages 根目录
SITE_DIR = SITE_ROOT / "weiqi-page"  # 实际部署到子目录
TEST_SITE_DIR = WORKSPACE_DIR / "test_site" / "weiqi-page"  # 测试模式也使用相同的子目录结构
SCRIPTS_DIR = WEIQI_PAGE_DIR / "scripts"
TEMPLATES_DIR = WEIQI_PAGE_DIR / "templates"

# 技能包路径 - 优先使用环境变量，其次使用相对路径
SKILLS_DIR = Path(os.getenv("WEIQI_SKILLS_DIR", WEIQI_PAGE_DIR.parent.parent / "skills"))
WEIQI_DB_SCRIPT = SKILLS_DIR / "weiqi-db/scripts/db.py"
WEIQI_SGF_SCRIPT = SKILLS_DIR / "weiqi-sgf/scripts/replay.py"
WEIQI_MOVE_SCRIPT = SKILLS_DIR / "weiqi-move/scripts/quiz.py"
WEIQI_JOSEKI_DIR = SKILLS_DIR / "weiqi-joseki"  # joseki目录
WEIQI_JOSEKI_SCRIPT = WEIQI_JOSEKI_DIR / "db.py"  # 使用db.py兼容性入口
WEIQI_FOXWQ_SCRIPT = SKILLS_DIR / "weiqi-foxwq/scripts/download_sgf.py"

# 记谱工具路径 - 优先使用环境变量，其次在工作区查找
WEIQI_RECORDER_PATH = Path(os.getenv("WEIQI_RECORDER_PATH", WORKSPACE_DIR.parent / ".openclaw/workspace/weiqi-recorder/assets/weiqi_recorder.html"))

# 数据存储路径 - 使用环境变量或默认家目录
WEIQI_DB_DIR = Path(os.getenv("WEIQI_DB_DIR", HOME_DIR / ".weiqi-db"))
WEIQI_JOSEKI_DB_DIR = Path(os.getenv("WEIQI_JOSEKI_DB_DIR", HOME_DIR / ".weiqi-joseki"))
WEIQI_DB_PATH = WEIQI_DB_DIR / "database.json"
WEIQI_JOSEKI_DB_PATH = WEIQI_JOSEKI_DB_DIR / "database.json"

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
    "subtitle": GITHUB_USERNAME,
    "base_url": f"https://{GITHUB_USERNAME}.github.io",
    "sources": ["foxwq", "yike"],  # 支持的来源
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
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return base_dir

def get_date_dir(base_dir, date_str, source=None):
    """获取日期目录路径"""
    if source:
        return base_dir / date_str / source
    return base_dir / date_str
