#!/usr/bin/env python3
"""
选点题生成脚本
从棋谱生成实战选点题，优先生成恶手题
"""
import os
import sys
import json
import subprocess
import tempfile
import shutil
import re
from datetime import datetime
from pathlib import Path
from jinja2 import Template

sys.path.insert(0, str(Path(__file__).parent))
from common import (
    get_games_by_date, get_game_source,
    batch_export_sgfs, find_sgf_file_by_id, find_original_sgf
)
from config import (
    WEIQI_MOVE_SCRIPT, BASE_PATH,
    SITE_DIR, TEST_SITE_DIR, TEMPLATES_DIR, ensure_dirs
)


def translate_result(result):
    """翻译胜负结果为中文"""
    if not result:
        return ""
    
    result = result.strip()
    
    # 中盘胜 / 认输
    if result == 'B+R' or result == 'B+Resign':
        return "黑中盘胜"
    if result == 'W+R' or result == 'W+Resign':
        return "白中盘胜"
    
    # 超时胜
    if result == 'B+T' or result == 'B+Time':
        return "黑超时胜"
    if result == 'W+T' or result == 'W+Time':
        return "白超时胜"
    
    # 数目胜（如 B+2.5, W+10）
    import re
    match = re.match(r'B\+(\d+\.?\d*)', result)
    if match:
        return f"黑胜{match.group(1)}目"
    match = re.match(r'W\+(\d+\.?\d*)', result)
    if match:
        return f"白胜{match.group(1)}目"
    
    # 其他格式原样返回
    return result


def parse_quiz_output(stdout):
    """解析 quiz.py 的输出，提取统计信息"""
    stats = {
        "total": 0,
        "result": "",
        "phase": {"layout": 0, "middle": 0, "endgame": 0},
        "difficulty": {"easy": 0, "medium": 0, "hard": 0}
    }
    
    for line in stdout.split('\n'):
        line = line.strip()
        
        # 解析胜负结果
        if line.startswith('结果:'):
            raw_result = line.replace('结果:', '').strip()
            stats["result"] = translate_result(raw_result)
        
        # 解析总题数
        if '提取到' in line and '道题目' in line:
            match = re.search(r'提取到\s*(\d+)\s*道题目', line)
            if match:
                stats["total"] = int(match.group(1))
        
        # 解析阶段分布
        if '布局:' in line or '中盘:' in line or '官子:' in line:
            phase_match = re.search(r'布局:\s*(\d+)', line)
            if phase_match:
                stats["phase"]["layout"] = int(phase_match.group(1))
            phase_match = re.search(r'中盘:\s*(\d+)', line)
            if phase_match:
                stats["phase"]["middle"] = int(phase_match.group(1))
            phase_match = re.search(r'官子:\s*(\d+)', line)
            if phase_match:
                stats["phase"]["endgame"] = int(phase_match.group(1))
        
        # 解析难度分布
        if '简单:' in line or '中等:' in line or '困难:' in line:
            diff_match = re.search(r'简单:\s*(\d+)', line)
            if diff_match:
                stats["difficulty"]["easy"] = int(diff_match.group(1))
            diff_match = re.search(r'中等:\s*(\d+)', line)
            if diff_match:
                stats["difficulty"]["medium"] = int(diff_match.group(1))
            diff_match = re.search(r'困难:\s*(\d+)', line)
            if diff_match:
                stats["difficulty"]["hard"] = int(diff_match.group(1))
    
    return stats


def generate_quiz(sgf_path, output_path, quiz_type="blunder"):
    """生成选点题，返回统计信息"""
    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        "python3", str(WEIQI_MOVE_SCRIPT),
        str(sgf_path),
        "-o", str(output_path),
        "-t", quiz_type,
        "-n", "10"  # 最多生成10题
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"     ⚠️  quiz.py错误: {result.stderr[:200]}")
        return {"success": False, "stats": None}
    
    # 解析统计信息
    stats = parse_quiz_output(result.stdout)
    return {"success": True, "stats": stats}


def count_quiz_questions(stats):
    """从统计信息获取题目数量"""
    if stats and "total" in stats:
        return stats["total"]
    return 0


def generate_quiz_for_date(date_str, test_mode=False, sgf_dir=None):
    """生成指定日期的选点题
    
    Args:
        date_str: 日期
        test_mode: 是否测试模式
        sgf_dir: 外部提供的SGF目录，为None则自动导出
    """
    base_dir = ensure_dirs(test_mode)
    quiz_dir = base_dir / "quiz"
    
    print(f"📅 处理日期: {date_str}")
    
    # 获取棋谱列表
    games = get_games_by_date(date_str)
    if not games:
        print(f"⚠️  未找到 {date_str} 的棋谱")
        return []
    
    print(f"📊 找到 {len(games)} 局棋谱，开始生成选点题...")
    
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
        
        temp_dir = Path(tempfile.mkdtemp(prefix=f"quiz_{date_str}_"))
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
        
        black_name = game.get("black", "")
        white_name = game.get("white", "")
        
        # 优先使用原始SGF文件（包含AI数据）
        sgf_path = find_original_sgf(game_id, date_str, black_name, white_name)
        
        if not sgf_path:
            # 如果没有原始文件，从批量导出的文件中查找
            sgf_path = find_sgf_file_by_id(temp_dir, game_id)
        
        if not sgf_path:
            print(f"  ❌ 找不到SGF: {game_id}")
            continue
        
        # 创建来源子目录
        date_source_dir = quiz_dir / date_str / source
        date_source_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成选点题（恶手类型）
        output_name = f"quiz_{game_id}.html"
        output_path = date_source_dir / output_name
        
        quiz_result = generate_quiz(sgf_path, output_path, "blunder")
        if quiz_result["success"]:
            # 检查文件是否存在
            if output_path.exists():
                stats = quiz_result.get("stats", {})
                question_count = count_quiz_questions(stats)
                
                if question_count > 0:
                    print(f"  ✅ [{i}/{len(games)}] {source}: {output_name} ({question_count}题)")
                    generated.append({
                        "id": game_id,
                        "source": source,
                        "path": f"{BASE_PATH}/quiz/{date_str}/{source}/{output_name}",
                        "game_path": f"{BASE_PATH}/games/{date_str}/{source}/game_{game_id}.html",
                        "black": game.get("black", "未知"),
                        "white": game.get("white", "未知"),
                        "event": game.get("event", ""),
                        "result": stats.get("result", ""),
                        "count": question_count,
                        "stats": stats
                    })
                else:
                    print(f"  ⏭️  [{i}/{len(games)}] {source}: 无恶手，跳过")
                    output_path.unlink(missing_ok=True)
            else:
                print(f"  ⏭️  [{i}/{len(games)}] {source}: 无恶手，跳过")
        else:
            print(f"  ❌ 生成失败: {game_id}")
    
    # 清理临时目录（仅自动导出时才清理）
    if not sgf_dir and temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"🧹 清理临时文件")
    
    return generated


def generate_quiz_index(test_mode=False):
    """生成选点题列表索引页"""
    base_dir = TEST_SITE_DIR if test_mode else SITE_DIR
    data_dir = base_dir / "_data"
    
    date_data = {}
    all_dates = []
    
    for f in data_dir.glob("quiz_*.json"):
        date_str = f.stem.replace("quiz_", "")
        all_dates.append(date_str)
        
        try:
            quizzes = json.loads(f.read_text())
            sources = {}
            for quiz in quizzes:
                source = quiz.get("source", "其他")
                if source not in sources:
                    sources[source] = []
                sources[source].append(quiz)
            date_data[date_str] = sources
        except:
            pass
    
    if not date_data:
        print("⚠️  未找到选点题数据")
        return False
    
    # 读取模板
    template_path = TEMPLATES_DIR / "quiz_list.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    
    # 使用有数据的最后一天（最新日期）作为默认日期
    sorted_dates = sorted(all_dates, reverse=True)
    current_date = sorted_dates[0] if sorted_dates else datetime.now().strftime("%Y-%m-%d")
    
    html = template.render(
        dates=sorted_dates,
        current_date=current_date,
        date_data=date_data
    )
    
    output_path = base_dir / "quiz" / "index.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"✅ 生成选点题索引: {output_path}")
    return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="生成实战选点题")
    parser.add_argument("date", help="日期 (YYYY-MM-DD)")
    parser.add_argument("--test", action="store_true", help="测试模式")
    parser.add_argument("--index-only", action="store_true", help="仅生成索引")
    parser.add_argument("--sgf-dir", help="使用外部SGF目录（避免重复导出）")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎯 选点题生成")
    print("=" * 60)
    
    if args.index_only:
        generate_quiz_index(args.test)
    else:
        generated = generate_quiz_for_date(args.date, args.test, args.sgf_dir)
        
        total_questions = sum(q.get("count", 0) for q in generated)
        print(f"\n📈 生成完成: {len(generated)} 份棋谱, {total_questions} 道题目")
        
        # 保存索引
        base_dir = TEST_SITE_DIR if args.test else SITE_DIR
        index_file = base_dir / "_data" / f"quiz_{args.date}.json"
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index_file.write_text(json.dumps(generated, ensure_ascii=False, indent=2))
        
        # 生成列表页
        generate_quiz_index(args.test)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
