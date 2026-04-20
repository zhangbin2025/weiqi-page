#!/usr/bin/env python3
"""
棋谱页生成脚本
从weiqi-db读取棋谱，批量导出SGF，生成打谱网页
"""
import os
import sys
import json
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from jinja2 import Template

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    get_games_by_date, get_game_source,
    batch_export_sgfs, find_sgf_file_by_id, translate_result
)
from config import (
    WEIQI_SGF_SCRIPT, BASE_PATH,
    SITE_DIR, TEST_SITE_DIR, TEMPLATES_DIR, ensure_dirs
)


def generate_game_page(sgf_path, output_path, start_move="last"):
    """生成打谱网页
    
    Args:
        sgf_path: SGF文件路径
        output_path: 输出HTML路径
        start_move: 默认跳转手数，"last"表示最后一手，或指定数字
    """
    # weiqi-sgf 支持: replay.py input.sgf output.html --start-move <n|last>
    cmd = [
        "python3", str(WEIQI_SGF_SCRIPT),
        str(sgf_path), str(output_path),
        "--start-move", str(start_move)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def generate_games_for_date(date_str, test_mode=False, sgf_dir=None):
    """生成指定日期的所有棋谱页
    
    Args:
        date_str: 日期
        test_mode: 是否测试模式
        sgf_dir: 外部提供的SGF目录，为None则自动导出
    """
    base_dir = ensure_dirs(test_mode)
    games_dir = base_dir / "games"
    
    print(f"📅 处理日期: {date_str}")
    
    # 获取棋谱列表
    games = get_games_by_date(date_str)
    if not games:
        print(f"⚠️  未找到 {date_str} 的棋谱")
        return []
    
    print(f"📊 找到 {len(games)} 局棋谱")
    
    # 处理SGF目录
    temp_dir = None
    if sgf_dir:
        # 使用外部提供的SGF目录
        temp_dir = Path(sgf_dir)
        print(f"📂 使用外部SGF目录: {temp_dir}")
    else:
        # 批量导出SGF到临时目录
        game_ids = [g.get("id") for g in games if g.get("id")]
        if not game_ids:
            print("⚠️  没有有效的棋谱ID")
            return []
        
        temp_dir = Path(tempfile.mkdtemp(prefix=f"games_{date_str}_"))
        print(f"⏳ 批量导出SGF到: {temp_dir}")
        
        if not batch_export_sgfs(game_ids, temp_dir):
            print("❌ 批量导出失败")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return []
        
        print(f"✅ 成功导出SGF文件")
    
    # 检查导出结果
    sgf_files = list(temp_dir.glob("*.sgf"))
    print(f"📂 找到 {len(sgf_files)} 个SGF文件")
    
    if not sgf_files:
        print("⚠️  没有SGF文件可供处理")
        if not sgf_dir and temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return []
    
    # 处理每局棋谱
    generated = []
    
    for i, game in enumerate(games, 1):
        game_id = game.get("id")
        source = get_game_source(game)
        
        # 创建来源子目录
        date_source_dir = games_dir / date_str / source
        date_source_dir.mkdir(parents=True, exist_ok=True)
        
        # 查找对应的SGF文件
        sgf_path = find_sgf_file_by_id(temp_dir, game_id)
        if not sgf_path:
            print(f"  ❌ 找不到SGF: {game_id}")
            continue
        
        # 生成打谱页
        output_name = f"game_{game_id}.html"
        output_path = date_source_dir / output_name
        
        if generate_game_page(sgf_path, output_path):
            print(f"  ✅ [{i}/{len(games)}] {source}: {output_name}")
            generated.append({
                "id": game_id,
                "source": source,
                "path": f"{BASE_PATH}/games/{date_str}/{source}/{output_name}",
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
    
    # 清理临时目录（仅自动导出时才清理）
    if not sgf_dir and temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"🧹 清理临时文件")
    
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
    
    # 使用有数据的最后一天（最新日期）作为默认日期
    sorted_dates = sorted(all_dates, reverse=True)
    current_date = sorted_dates[0] if sorted_dates else datetime.now().strftime("%Y-%m-%d")
    
    html = template.render(
        dates=sorted_dates,
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
    parser.add_argument("--sgf-dir", help="使用外部SGF目录（避免重复导出）")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎯 棋谱页生成")
    print("=" * 60)
    
    if args.index_only:
        generate_games_index(args.test)
    else:
        generated = generate_games_for_date(args.date, args.test, args.sgf_dir)
        
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
