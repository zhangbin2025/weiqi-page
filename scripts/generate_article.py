#!/usr/bin/env python3
"""
公众号文章生成脚本
生成每日精选文章并推送
"""
import os
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import SITE_DIR, TEST_SITE_DIR, ensure_dirs


ARTICLE_TEMPLATE = """# 每日围棋精选 | {date}

## 【今日推荐】

{featured_games}

## 【实战选点】

{featured_quiz}

## 【定式发现】

{featured_joseki}

## 【数据看板】

📊 今日新增棋谱：**{total_games}** 局
🎯 今日新增选点题：**{total_quiz}** 题  
📚 今日定式发现：**{total_joseki}** 个

{source_breakdown}

## 【访问入口】

🔗 **https://zhangbin2025.github.io/{date}/**

---

*围棋资源站 - 每日更新，精进棋艺*
"""


def load_data(base_dir, date_str):
    """加载当日数据"""
    data_dir = base_dir / "_data"
    
    games = []
    quiz = []
    joseki = []
    
    games_file = data_dir / f"games_{date_str}.json"
    quiz_file = data_dir / f"quiz_{date_str}.json"
    joseki_file = data_dir / f"joseki_{date_str}.json"
    
    if games_file.exists():
        games = json.loads(games_file.read_text())
    if quiz_file.exists():
        quiz = json.loads(quiz_file.read_text())
    if joseki_file.exists():
        joseki = json.loads(joseki_file.read_text())
    
    return games, quiz, joseki


def select_featured(items, max_count=1):
    """挑选推荐内容"""
    if not items:
        return []
    
    # 简单策略：前N个
    return items[:max_count]


def format_game_card(game):
    """格式化棋谱卡片"""
    return f"""### {game.get('black', '黑方')} vs {game.get('white', '白方')}

- **结果**: {game.get('result', '未知')}
- **来源**: {game.get('source', '未知')}
- **赛事**: {game.get('event', '一般对局')}

> [查看完整棋谱](https://zhangbin2025.github.io{game.get('path', '')})
"""


def format_quiz_card(quiz):
    """格式化选点题卡片"""
    total_count = sum(q.get('count', 0) for q in quiz) if isinstance(quiz, list) else quiz.get('count', 0)
    return f"""### 今日选点题 ({total_count}道)

包含实战中的恶手局面，挑战你的判断力！

> [开始做题](https://zhangbin2025.github.io/quiz/{quiz[0].get('date', 'today') if isinstance(quiz, list) and quiz else 'today'}/)
"""


def format_joseki_card(joseki):
    """格式化定式卡片"""
    return f"""### 不常见定式发现

从今日棋谱中发现了不常见的定式变化，值得研究。

> [查看详情](https://zhangbin2025.github.io/joseki/{joseki[0].get('date', 'today') if isinstance(joseki, list) and joseki else 'today'}/)
"""


def generate_article(date_str, test_mode=False):
    """生成公众号文章"""
    base_dir = TEST_SITE_DIR if test_mode else SITE_DIR
    
    # 加载数据
    games, quiz, joseki = load_data(base_dir, date_str)
    
    print(f"📊 数据概览:")
    print(f"  棋谱: {len(games)} 局")
    print(f"  选点题: {len(quiz)} 份")
    print(f"  定式: {len(joseki)} 个")
    
    # 挑选推荐内容
    featured_games = select_featured(games, 2)
    featured_quiz = select_featured(quiz, 1)
    featured_joseki = select_featured(joseki, 1)
    
    # 来源分布统计
    source_stats = {}
    for g in games:
        s = g.get('source', 'unknown')
        source_stats[s] = source_stats.get(s, 0) + 1
    
    source_breakdown = "\n".join([f"- {s}: {n}局" for s, n in source_stats.items()])
    
    # 渲染文章
    article = ARTICLE_TEMPLATE.format(
        date=date_str,
        featured_games="\n\n".join(format_game_card(g) for g in featured_games) if featured_games else "今日暂无推荐棋谱",
        featured_quiz=format_quiz_card(featured_quiz) if featured_quiz else "今日暂无选点题",
        featured_joseki=format_joseki_card(featured_joseki) if featured_joseki else "今日暂无新定式",
        total_games=len(games),
        total_quiz=sum(q.get('count', 0) for q in quiz) if quiz else 0,
        total_joseki=len(joseki),
        source_breakdown=source_breakdown if source_breakdown else "暂无数据来源统计"
    )
    
    # 保存文章
    article_dir = base_dir / "articles"
    article_dir.mkdir(exist_ok=True)
    article_file = article_dir / f"article_{date_str}.md"
    article_file.write_text(article, encoding="utf-8")
    
    print(f"\n✅ 文章已保存: {article_file}")
    
    return article


def publish_article(article):
    """发布到微信公众号（权限开放后实现）"""
    print("\n📤 公众号推送")
    print("=" * 60)
    print("[MOCK] 文章已准备就绪，等待推送权限开放...")
    print("=" * 60)
    
    # TODO: 接入微信API
    # 需要用户后续开放权限
    
    return True


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="生成公众号文章")
    parser.add_argument("date", help="日期 (YYYY-MM-DD)")
    parser.add_argument("--test", action="store_true", help="测试模式")
    parser.add_argument("--publish", action="store_true", help="直接推送")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("📝 公众号文章生成")
    print("=" * 60)
    
    article = generate_article(args.date, args.test)
    
    if args.publish:
        publish_article(article)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
