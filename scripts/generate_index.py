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


def normalize_event_name(event):
    """赛事名归一化，用于去重"""
    if not event:
        return ""
    import re
    # 移除年份、届数、日期等变化部分
    # 如 "第28届LG杯世界棋王赛" -> "LG杯"
    # "2024围甲联赛" -> "围甲"
    event = re.sub(r'第\d+届', '', event)
    event = re.sub(r'\d{4}', '', event)
    event = re.sub(r'\d+月\d+日', '', event)
    event = re.sub(r'[\(\)（）]', '', event)
    # 提取核心名称（取最长部分）
    parts = [p.strip() for p in event.split() if len(p.strip()) >= 2]
    if parts:
        # 返回最长的部分作为核心赛事名
        return max(parts, key=len)
    return event.strip()


def is_similar_event(e1, e2):
    """判断两个赛事名是否相似"""
    if not e1 or not e2:
        return False
    e1, e2 = e1.lower(), e2.lower()
    # 完全相同
    if e1 == e2:
        return True
    # 包含关系
    if e1 in e2 or e2 in e1:
        return True
    # 编辑距离 <= 2（简单实现）
    if len(e1) > 3 and len(e2) > 3:
        # 如果前3个字符相同，认为是相似
        if e1[:3] == e2[:3]:
            return True
    return False


def count_unique_events(games):
    """计算唯一赛事数"""
    normalized = [normalize_event_name(g.get('event', '')) for g in games]
    normalized = [e for e in normalized if e]  # 过滤空值
    
    unique = []
    for e in normalized:
        if not any(is_similar_event(e, u) for u in unique):
            unique.append(e)
    return len(unique)


def calc_match_rate(joseki):
    """计算定式匹配度"""
    move_count = joseki.get('move_count', 0)
    matched = joseki.get('matched_prefix_len', 0)
    return matched / move_count if move_count > 0 else 0


def generate_index(test_mode=False):
    """生成首页"""
    base_dir = ensure_dirs(test_mode)
    data_dir = base_dir / "_data"
    
    # 找到最新日期
    latest_date = None
    for f in data_dir.glob("games_*.json"):
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
    
    # 统计数据初始化
    games_count = 0
    games_events = 0
    games_sources = 0
    games_data = []
    
    quiz_count = 0
    quiz_phase = {"layout": 0, "middle": 0, "endgame": 0}
    quiz_difficulty = {"easy": 0, "medium": 0, "hard": 0}
    
    joseki_count = 0
    joseki_hot = 0
    joseki_hit = 0
    joseki_rare = 0
    joseki_list = []
    
    if latest_date:
        # 统计棋谱
        games_file = data_dir / f"games_{latest_date}.json"
        if games_file.exists():
            try:
                games_data = json.loads(games_file.read_text())
                games_count = len(games_data)
                games_events = count_unique_events(games_data)
                # 统计来源数量
                sources = set()
                for game in games_data:
                    source = game.get("source", "其他")
                    sources.add(source)
                games_sources = len(sources)
            except:
                pass
        
        # 统计选点题（按题目数）
        quiz_file = data_dir / f"quiz_{latest_date}.json"
        if quiz_file.exists():
            try:
                quizzes = json.loads(quiz_file.read_text())
                for q in quizzes:
                    count = q.get("count", 0)
                    quiz_count += count
                    stats = q.get("stats", {})
                    phase = stats.get("phase", {})
                    difficulty = stats.get("difficulty", {})
                    quiz_phase["layout"] += phase.get("layout", 0)
                    quiz_phase["middle"] += phase.get("middle", 0)
                    quiz_phase["endgame"] += phase.get("endgame", 0)
                    quiz_difficulty["easy"] += difficulty.get("easy", 0)
                    quiz_difficulty["medium"] += difficulty.get("medium", 0)
                    quiz_difficulty["hard"] += difficulty.get("hard", 0)
            except:
                pass
        
        # 统计定式
        joseki_file = data_dir / f"joseki_{latest_date}.json"
        if joseki_file.exists():
            try:
                joseki_list = json.loads(joseki_file.read_text())
                joseki_count = len(joseki_list)
                
                # 计算库概率排名（前3名）
                sorted_by_prob = sorted(joseki_list, key=lambda j: j.get("probability", 0), reverse=True)
                top3_keys = set()
                for j in sorted_by_prob[:3]:
                    key = j.get("joseki_id") or ",".join(j.get("moves", []))
                    top3_keys.add(key)
                
                # 计算匹配度排名（最后5名）
                sorted_by_rate = sorted(joseki_list, key=calc_match_rate, reverse=True)
                bottom5_keys = set()
                for j in sorted_by_rate[-5:]:
                    key = j.get("joseki_id") or ",".join(j.get("moves", []))
                    bottom5_keys.add(key)
                
                # 分类统计
                for j in joseki_list:
                    prefix_len = j.get("matched_prefix_len", 0)
                    rate = calc_match_rate(j)
                    key = j.get("joseki_id") or ",".join(j.get("moves", []))
                    
                    # 热门: 前缀>=8 + 库概率前3
                    if prefix_len >= 8 and key in top3_keys:
                        joseki_hot += 1
                    
                    # 命中: 前缀>=8 + 匹配度100%
                    if prefix_len >= 8 and rate >= 1:
                        joseki_hit += 1
                    
                    # 罕见: 前缀<4 + 匹配度最后5名
                    if prefix_len < 4 and key in bottom5_keys:
                        joseki_rare += 1
            except:
                pass
    
    # 读取模板
    template_path = TEMPLATES_DIR / "index.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    
    # 渲染
    html = template.render(
        games_count=games_count,
        games_events=games_events,
        games_sources=games_sources,
        quiz_count=quiz_count,
        quiz_phase=quiz_phase,
        quiz_difficulty=quiz_difficulty,
        joseki_count=joseki_count,
        joseki_hot=joseki_hot,
        joseki_hit=joseki_hit,
        joseki_rare=joseki_rare,
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
