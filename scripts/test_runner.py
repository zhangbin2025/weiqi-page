#!/usr/bin/env python3
"""
测试脚本 - 验证各模块功能
"""
import os
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / ".." / "scripts"))

from config import ensure_dirs, TEST_SITE_DIR


def test_katago_updater():
    """测试KataGo定式更新器"""
    print("\n" + "="*60)
    print("🧪 测试: KataGo定式更新器")
    print("="*60)
    
    from katago_updater import get_last_processed_date, get_date_range, check_url_exists
    
    # 测试日期读取
    last_date = get_last_processed_date()
    print(f"✅ 最后处理日期: {last_date}")
    
    # 测试日期范围计算
    start, end = get_date_range()
    if start and end:
        print(f"✅ 更新范围: {start} ~ {end}")
    else:
        print(f"✅ 已是最新，无需更新")
    
    # 测试URL检查（使用一个已知存在的日期）
    test_url = "https://katagoarchive.org/kata1/ratinggames/2026-04-01rating.tar.bz2"
    exists = check_url_exists(test_url)
    print(f"✅ URL检查: {test_url} -> {'存在' if exists else '不存在'}")
    
    return True


def test_rare_joseki_detector():
    """测试不常见定式检测器"""
    print("\n" + "="*60)
    print("🧪 测试: 不常见定式检测器")
    print("="*60)
    
    from find_rare_joseki import RareJosekiDetector
    
    detector = RareJosekiDetector()
    
    # 测试数据
    test_joseki = [
        {"id": "joseki_001", "katago_count": 5000},
        {"id": "joseki_002", "katago_count": 100},
        {"id": "joseki_003", "katago_count": 50},
        {"id": "joseki_004", "katago_count": 5},
    ]
    
    rare_list = detector.find_rare_joseki(test_joseki)
    
    print(f"测试数据: {len(test_joseki)} 个定式")
    for j in test_joseki:
        print(f"  {j['id']}: count={j['katago_count']}")
    
    print(f"\n不常见定式: {len(rare_list)} 个")
    for j in rare_list:
        print(f"  {j['id']}: {j['rare_reason']}")
    
    # 验证中位数计算正确
    # 数据 [5, 50, 100, 5000] 中位数 = (50+100)/2 = 75
    # 小于75的: 5, 50
    assert len(rare_list) == 2, f"预期2个不常见定式，实际{len(rare_list)}"
    
    print("✅ 测试通过")
    return True


def test_index_generator():
    """测试索引生成器"""
    print("\n" + "="*60)
    print("🧪 测试: 索引生成器")
    print("="*60)
    
    # 创建测试数据
    test_date = "2026-04-01"
    base_dir = ensure_dirs(test_mode=True)
    data_dir = base_dir / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建测试数据文件
    test_games = [
        {"id": "1", "source": "foxwq", "black": "柯洁", "white": "申真谞", "path": "/games/test/foxwq/game_001.html"},
        {"id": "2", "source": "katago", "black": "AI-A", "white": "AI-B", "path": "/games/test/katago/game_002.html"},
    ]
    
    games_file = data_dir / f"games_{test_date}.json"
    games_file.write_text(json.dumps(test_games))
    
    print(f"✅ 创建测试数据: {games_file}")
    
    # 测试索引生成
    from generate_index import generate_index
    success = generate_index("games", test_mode=True)
    
    if success:
        index_file = base_dir / "games" / "index.html"
        print(f"✅ 索引文件生成: {index_file}")
        
        # 验证文件内容
        content = index_file.read_text()
        assert "foxwq" in content, "索引文件应包含foxwq来源"
        assert "katago" in content, "索引文件应包含katago来源"
        print("✅ 索引内容验证通过")
    
    return success


def test_article_generator():
    """测试公众号文章生成器"""
    print("\n" + "="*60)
    print("🧪 测试: 公众号文章生成器")
    print("="*60)
    
    test_date = "2026-04-01"
    base_dir = ensure_dirs(test_mode=True)
    data_dir = base_dir / "_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建测试数据
    test_games = [
        {"id": "1", "source": "foxwq", "black": "柯洁", "white": "申真谞", 
         "result": "黑中盘胜", "event": "LG杯", "path": "/games/test/foxwq/game_001.html"},
    ]
    test_quiz = [
        {"game_id": "1", "source": "foxwq", "count": 5, "type": "blunder"},
    ]
    
    (data_dir / f"games_{test_date}.json").write_text(json.dumps(test_games))
    (data_dir / f"quiz_{test_date}.json").write_text(json.dumps(test_quiz))
    
    # 生成文章
    from generate_article import generate_article
    article = generate_article(test_date, test_mode=True)
    
    # 验证文章内容
    assert "柯洁" in article, "文章应包含棋手名"
    assert "LG杯" in article, "文章应包含赛事名"
    assert "zhangbin2025.github.io" in article, "文章应包含站点链接"
    
    print("✅ 文章内容验证通过")
    
    article_file = base_dir / "articles" / f"article_{test_date}.md"
    print(f"✅ 文章文件: {article_file}")
    
    return True


def test_weiqi_db_connection():
    """测试weiqi-db连接"""
    print("\n" + "="*60)
    print("🧪 测试: weiqi-db 连接")
    print("="*60)
    
    import subprocess
    from config import WEIQI_DB_SCRIPT
    
    # 检查脚本是否存在
    if not WEIQI_DB_SCRIPT.exists():
        print(f"❌ weiqi-db脚本不存在: {WEIQI_DB_SCRIPT}")
        return False
    
    print(f"✅ weiqi-db脚本存在: {WEIQI_DB_SCRIPT}")
    
    # 检查数据库文件
    from config import WEIQI_DB_PATH
    if WEIQI_DB_PATH.exists():
        db_size = WEIQI_DB_PATH.stat().st_size
        print(f"✅ weiqi-db数据库存在: {WEIQI_DB_PATH} ({db_size/1024:.1f} KB)")
    else:
        print(f"⚠️  weiqi-db数据库不存在（首次运行）: {WEIQI_DB_PATH}")
    
    return True


def test_weiqi_joseki_connection():
    """测试weiqi-joseki连接"""
    print("\n" + "="*60)
    print("🧪 测试: weiqi-joseki 连接")
    print("="*60)
    
    import subprocess
    from config import WEIQI_JOSEKI_SCRIPT, WEIQI_JOSEKI_DB_PATH
    
    # 检查脚本
    if not WEIQI_JOSEKI_SCRIPT.exists():
        print(f"❌ weiqi-joseki脚本不存在: {WEIQI_JOSEKI_SCRIPT}")
        return False
    
    print(f"✅ weiqi-joseki脚本存在: {WEIQI_JOSEKI_SCRIPT}")
    
    # 检查数据库
    if WEIQI_JOSEKI_DB_PATH.exists():
        db_size = WEIQI_JOSEKI_DB_PATH.stat().st_size
        print(f"✅ weiqi-joseki数据库存在: {WEIQI_JOSEKI_DB_PATH} ({db_size/1024:.1f} KB)")
    else:
        print(f"⚠️  weiqi-joseki数据库不存在（首次运行）: {WEIQI_JOSEKI_DB_PATH}")
    
    return True


def run_all_tests():
    """运行所有测试"""
    print("="*60)
    print("🧪 围棋资源站 - 测试套件")
    print("="*60)
    
    tests = [
        ("weiqi-db连接", test_weiqi_db_connection),
        ("weiqi-joseki连接", test_weiqi_joseki_connection),
        ("KataGo更新器", test_katago_updater),
        ("不常见定式检测", test_rare_joseki_detector),
        ("索引生成器", test_index_generator),
        ("公众号文章生成", test_article_generator),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results.append((name, False))
    
    # 汇总
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"  {status}: {name}")
    
    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\n总计: {passed}/{total} 通过")
    
    return all(s for _, s in results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
