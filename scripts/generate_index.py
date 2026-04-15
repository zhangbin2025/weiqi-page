#!/usr/bin/env python3
"""
首页生成脚本
"""
import sys
import json
from pathlib import Path
from jinja2 import Template

sys.path.insert(0, str(Path(__file__).parent))
from config import SITE_DIR, TEST_SITE_DIR, TEMPLATES_DIR, ensure_dirs


def generate_index(test_mode=False):
    """生成首页"""
    base_dir = ensure_dirs(test_mode)
    data_dir = base_dir / "_data"
    
    # 找到最新日期
    latest_date = None
    for f in data_dir.glob("games_*.json"):
        # 从文件名提取日期 games_2026-04-15.json -> 2026-04-15
        date_str = f.stem.replace("games_", "")
        if not latest_date or date_str > latest_date:
            latest_date = date_str
    
    # 如果没有棋谱数据，尝试从选点题或定式找日期
    if not latest_date:
        for f in data_dir.glob("quiz_*.json"):
            date_str = f.stem.replace("quiz_", "")
            if not latest_date or date_str > latest_date:
                latest_date = date_str
    
    if not latest_date:
        for f in data_dir.glob("joseki_*.json"):
            date_str = f.stem.replace("joseki_", "")
            if not latest_date or date_str > latest_date:
                latest_date = date_str
    
    # 统计最新一天的数量
    games_count = 0
    quiz_count = 0
    joseki_count = 0
    
    if latest_date:
        # 统计棋谱
        games_file = data_dir / f"games_{latest_date}.json"
        if games_file.exists():
            try:
                games = json.loads(games_file.read_text())
                games_count = len(games)
            except:
                pass
        
        # 统计选点题（按题目数）
        quiz_file = data_dir / f"quiz_{latest_date}.json"
        if quiz_file.exists():
            try:
                quizzes = json.loads(quiz_file.read_text())
                for q in quizzes:
                    quiz_count += q.get("count", 0)
            except:
                pass
        
        # 统计定式
        joseki_file = data_dir / f"joseki_{latest_date}.json"
        if joseki_file.exists():
            try:
                josekis = json.loads(joseki_file.read_text())
                joseki_count = len(josekis)
            except:
                pass
    
    # 读取模板
    template_path = TEMPLATES_DIR / "index.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    
    # 渲染
    html = template.render(
        games_count=games_count,
        quiz_count=quiz_count,
        joseki_count=joseki_count,
        last_update=latest_date or "暂无数据"
    )
    
    # 保存
    output_path = base_dir / "index.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"✅ 生成首页: {output_path}")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎯 首页生成")
    print("=" * 60)
    
    generate_index(args.test)
    return 0


if __name__ == "__main__":
    sys.exit(main())
