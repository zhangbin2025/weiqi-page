#!/usr/bin/env python3
"""
围棋页面生成器 - 公共模块
包含三个脚本共用的函数
"""
import json
import subprocess
from pathlib import Path

# 技能包路径
SKILLS_DIR = Path("/root/.openclaw/workspace")
WEIQI_DB_SCRIPT = SKILLS_DIR / "weiqi-db/scripts/db.py"


def run_db_cmd(args):
    """运行 weiqi-db 命令"""
    cmd = ["python3", str(WEIQI_DB_SCRIPT)] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def get_games_by_date(date_str):
    """从weiqi-db获取指定日期的棋谱列表"""
    result = run_db_cmd(["query", "--date", date_str])
    
    if result.returncode != 0:
        print(f"❌ 查询失败: {result.stderr}")
        return []
    
    try:
        data = json.loads(result.stdout)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "games" in data:
            return data["games"]
        return []
    except json.JSONDecodeError:
        return []


def get_game_source(game):
    """从标签中解析棋谱来源"""
    tags = game.get("tags", [])
    for tag in tags:
        if tag.startswith("来源:"):
            return tag.replace("来源:", "")
    return "其他"


def batch_export_sgfs(game_ids, output_dir):
    """批量导出SGF文件到指定目录"""
    if not game_ids:
        return False
    
    ids_str = ",".join(game_ids)
    result = run_db_cmd(["get", "--ids", ids_str, "-d", str(output_dir)])
    return result.returncode == 0


def find_sgf_file_by_id(sgf_dir, game_id):
    """
    根据game_id查找对应的SGF文件
    文件名格式: [日期]_[赛事]_黑方_vs_白方_[ID后6位].sgf
    """
    # 文件名只包含ID后6位
    id_suffix = game_id[-6:] if len(game_id) >= 6 else game_id
    
    for f in sgf_dir.glob("*.sgf"):
        # 检查文件名是否以 ID后6位.sgf 结尾
        if f.name.endswith(f"_{id_suffix}.sgf"):
            return f
    
    return None


def translate_result(result):
    """翻译比赛结果为中文"""
    if not result:
        return "未知"
    
    result = result.strip()
    
    # 中盘胜
    if result in ["B+R", "B+Resign"]:
        return "黑中盘胜"
    if result in ["W+R", "W+Resign"]:
        return "白中盘胜"
    
    # 时间胜
    if "B+Time" in result:
        return "黑时间胜"
    if "W+Time" in result:
        return "白时间胜"
    
    # 数目胜
    if result.startswith("B+"):
        try:
            score = result[2:].strip()
            if score.replace(".", "").isdigit():
                return f"黑胜{score}目"
        except:
            pass
        return "黑胜"
    
    if result.startswith("W+"):
        try:
            score = result[2:].strip()
            if score.replace(".", "").isdigit():
                return f"白胜{score}目"
        except:
            pass
        return "白胜"
    
    # 和棋
    if result == "Draw" or result == "Jigo":
        return "和棋"
    
    return result


def find_original_sgf(game_id, date_str, black_name, white_name):
    """
    查找原始SGF文件（优先使用野狐下载的，包含AI数据）
    用于generate_quiz
    """
    # 野狐下载目录
    foxwq_dir = Path(f"/tmp/foxwq_downloads/{date_str}")
    if foxwq_dir.exists():
        # 使用棋手名字匹配（因为game_id是导入时生成的，和文件名不同）
        for f in foxwq_dir.glob("*.sgf"):
            filename = f.name
            # 简化的匹配：检查文件名是否包含两个棋手的名字
            if black_name in filename and white_name in filename:
                return f
            # 备选：只匹配一个名字
            if black_name in filename or white_name in filename:
                return f
    return None
