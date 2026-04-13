#!/usr/bin/env python3
"""
棋谱页生成脚本
从weiqi-db读取棋谱，生成打谱网页
"""
import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from jinja2 import Template

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    WEIQI_DB_SCRIPT, WEIQI_SGF_SCRIPT,
    SITE_DIR, TEST_SITE_DIR, TEMPLATES_DIR, ensure_dirs
)


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


def get_games_by_date(date_str):
    """从weiqi-db获取指定日期的棋谱"""
    cmd = [
        "python3", str(WEIQI_DB_SCRIPT),
        "query", "--date", date_str
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
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


def export_game_sgf(game_id, output_path):
    """导出棋谱SGF文件"""
    cmd = [
        "python3", str(WEIQI_DB_SCRIPT),
        "get", "--id", game_id, "-o", str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def generate_game_page(sgf_path, output_path):
    """生成打谱网页"""
    cmd = [
        "python3", str(WEIQI_SGF_SCRIPT),
        str(sgf_path), "-o", str(output_path.parent)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def generate_games_for_date(date_str, test_mode=False):
    """生成指定日期的所有棋谱页"""
    base_dir = ensure_dirs(test_mode)
    games_dir = base_dir / "games"
    
    print(f"📅 处理日期: {date_str}")
    
    # 获取棋谱列表
    games = get_games_by_date(date_str)
    if not games:
        print(f"⚠️  未找到 {date_str} 的棋谱")
        return []
    
    print(f"📊 找到 {len(games)} 局棋谱")
    
    generated = []
    
    for i, game in enumerate(games, 1):
        game_id = game.get("id")
        source = get_game_source(game)
        
        # 创建来源子目录
        date_source_dir = games_dir / date_str / source
        date_source_dir.mkdir(parents=True, exist_ok=True)
        
        # 导出SGF
        sgf_path = Path(f"/tmp/game_{game_id}.sgf")
        if not export_game_sgf(game_id, sgf_path):
            print(f"  ❌ 导出失败: {game_id}")
            continue
        
        # 生成打谱页
        output_name = f"game_{game_id}.html"
        output_path = date_source_dir / output_name
        
        if generate_game_page(sgf_path, output_path):
            print(f"  ✅ [{i}/{len(games)}] {source}: {output_name}")
            generated.append({
                "id": game_id,
                "source": source,
                "path": f"/games/{date_str}/{source}/{output_name}",
                "black": game.get("black", "未知"),
                "white": game.get("white", "未知"),
                "black_rank": game.get("black_rank", ""),
                "white_rank": game.get("white_rank", ""),
                "result": game.get("result", ""),
                "result_cn": translate_result(game.get("result", "")),
                "event": game.get("event", ""),
            })
        else:
            print(f"  ❌ 生成失败: {game_id}")
        
        # 清理临时文件
        sgf_path.unlink(missing_ok=True)
    
    return generated


def generate_games_index(test_mode=False):
    """生成棋谱列表索引页"""
    base_dir = TEST_SITE_DIR if test_mode else SITE_DIR
    data_dir = base_dir / "_data"
    
    # 收集所有日期的数据
    date_data = {}
    all_dates = []
    
    for f in data_dir.glob("games_*.json"):
        date_str = f.stem.replace("games_", "")
        all_dates.append(date_str)
        
        try:
            games = json.loads(f.read_text())
            sources = {}
            for game in games:
                source = game.get("source", "其他")
                if source not in sources:
                    sources[source] = []
                sources[source].append(game)
            date_data[date_str] = sources
        except:
            pass
    
    if not date_data:
        print("⚠️  未找到棋谱数据")
        return False
    
    # 读取模板
    template_path = TEMPLATES_DIR / "games_list.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    html = template.render(
        dates=sorted(all_dates, reverse=True),
        current_date=current_date,
        date_data=date_data
    )
    
    output_path = base_dir / "games" / "index.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"✅ 生成棋谱索引: {output_path}")
    return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="生成棋谱打谱页")
    parser.add_argument("date", help="日期 (YYYY-MM-DD)")
    parser.add_argument("--test", action="store_true", help="测试模式")
    parser.add_argument("--index-only", action="store_true", help="仅生成索引")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎯 棋谱页生成")
    print("=" * 60)
    
    if args.index_only:
        generate_games_index(args.test)
    else:
        generated = generate_games_for_date(args.date, args.test)
        
        print(f"\n📈 生成完成: {len(generated)} 局棋谱")
        
        # 保存索引
        base_dir = TEST_SITE_DIR if args.test else SITE_DIR
        index_file = base_dir / "_data" / f"games_{args.date}.json"
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.write_text(json.dumps(generated, ensure_ascii=False, indent=2))
        
        # 生成列表页
        generate_games_index(args.test)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
