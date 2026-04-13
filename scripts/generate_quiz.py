#!/usr/bin/env python3
"""
选点题生成脚本
从棋谱生成实战选点题，优先生成恶手题
"""
import os
import sys
import json
import subprocess
import re
from datetime import datetime
from pathlib import Path
from jinja2 import Template

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    WEIQI_DB_SCRIPT, WEIQI_MOVE_SCRIPT,
    SITE_DIR, TEST_SITE_DIR, TEMPLATES_DIR, ensure_dirs
)


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


def generate_quiz(sgf_path, output_path, quiz_type="blunder"):
    """生成选点题"""
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
    return result.returncode == 0


def count_quiz_questions(quiz_path):
    """统计选点题数量"""
    try:
        content = quiz_path.read_text()
        # 统计题目数量（根据quiz.html的结构，查找problems数组）
        # 格式: const problems = [{"index": 0, ...}, {"index": 1, ...}];
        match = re.search(r'const problems = (\[.*?\]);', content, re.DOTALL)
        if match:
            try:
                problems = json.loads(match.group(1))
                return len(problems)
            except:
                pass
        # 备选：查找index字段
        questions = re.findall(r'"index":\s*(\d+)', content)
        return len(set(questions))
    except:
        return 0


def find_original_sgf(game_id, date_str, source, black_name, white_name):
    """查找原始SGF文件（优先使用野狐下载的，包含AI数据）"""
    # 野狐下载目录
    foxwq_dir = Path(f"/tmp/foxwq_downloads/{date_str}")
    if foxwq_dir.exists():
        # 使用棋手名字匹配（因为game_id是导入时生成的，和文件名不同）
        for f in foxwq_dir.glob("*.sgf"):
            # 文件名格式: 时间戳_赛事_结果.sgf
            # 需要匹配黑棋和白棋名字
            filename = f.name
            # 简化的匹配：检查文件名是否包含两个棋手的名字
            if black_name in filename and white_name in filename:
                return f
            # 备选：只匹配一个名字
            if black_name in filename or white_name in filename:
                return f
    return None


def generate_quiz_for_date(date_str, test_mode=False):
    """生成指定日期的选点题"""
    base_dir = ensure_dirs(test_mode)
    quiz_dir = base_dir / "quiz"
    
    print(f"📅 处理日期: {date_str}")
    
    # 获取棋谱列表
    games = get_games_by_date(date_str)
    if not games:
        print(f"⚠️  未找到 {date_str} 的棋谱")
        return []
    
    print(f"📊 找到 {len(games)} 局棋谱，开始生成选点题...")
    
    generated = []
    
    for i, game in enumerate(games, 1):
        game_id = game.get("id")
        source = get_game_source(game)
        
        black_name = game.get("black", "")
        white_name = game.get("white", "")
        
        # 优先使用原始SGF文件（包含AI数据）
        sgf_path = find_original_sgf(game_id, date_str, source, black_name, white_name)
        if not sgf_path:
            # 如果没有原始文件，从weiqi-db导出（可能不包含AI数据）
            sgf_path = Path(f"/tmp/quiz_game_{game_id}.sgf")
            if not export_game_sgf(game_id, sgf_path):
                print(f"  ❌ 导出失败: {game_id}")
                continue
        
        # 创建来源子目录
        date_source_dir = quiz_dir / date_str / source
        date_source_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成选点题（恶手类型）
        output_name = f"quiz_{game_id}.html"
        output_path = date_source_dir / output_name
        
        if generate_quiz(sgf_path, output_path, "blunder"):
            # 检查文件是否存在
            if output_path.exists():
                # 统计题目数量
                question_count = count_quiz_questions(output_path)
                
                if question_count > 0:
                    print(f"  ✅ [{i}/{len(games)}] {source}: {output_name} ({question_count}题, 恶手题)")
                    generated.append({
                        "id": game_id,
                        "source": source,
                        "path": f"/quiz/{date_str}/{source}/{output_name}",
                        "black": game.get("black", "未知"),
                        "white": game.get("white", "未知"),
                        "event": game.get("event", ""),
                        "type": "恶手题",
                        "count": question_count
                    })
                else:
                    print(f"  ⏭️  [{i}/{len(games)}] {source}: 无恶手，跳过")
                    output_path.unlink(missing_ok=True)
            else:
                print(f"  ⏭️  [{i}/{len(games)}] {source}: 无恶手，跳过")
        else:
            print(f"  ❌ 生成失败: {game_id}")
        
        # 清理临时文件
        sgf_path.unlink(missing_ok=True)
    
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
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    html = template.render(
        dates=sorted(all_dates, reverse=True),
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
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎯 选点题生成")
    print("=" * 60)
    
    if args.index_only:
        generate_quiz_index(args.test)
    else:
        generated = generate_quiz_for_date(args.date, args.test)
        
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
