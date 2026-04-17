#!/usr/bin/env python3
"""
KataGo定式日更脚本
智能日期管理，支持断点续传和遗漏检测
"""
import os
import sys
import json
import subprocess
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import KATAGO_CACHE_DIR, KATAGO_STATE_FILE, WEIQI_JOSEKI_SCRIPT, WEIQI_JOSEKI_DIR, KATAGO_CONFIG


def get_last_processed_date():
    """获取最后处理的日期 - 从缓存目录扫描，确保不遗漏"""
    # 从缓存目录扫描实际下载的棋谱
    cached_dates = []
    for f in KATAGO_CACHE_DIR.glob("*rating.tar.bz2"):
        date_str = f.name.replace("rating.tar.bz2", "")
        cached_dates.append(date_str)
    
    if cached_dates:
        return max(cached_dates)
    
    # 默认：从KataGo数据起始日期开始
    return "2024-01-01"


def check_url_exists(url, timeout=10):
    """检查URL是否存在（KataGo数据是否已上传）"""
    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except:
        return False


def get_date_range():
    """确定需要更新的日期范围"""
    last_processed = get_last_processed_date()
    last_date = datetime.strptime(last_processed, "%Y-%m-%d")
    
    # 计算预期的开始日期
    expected_start = last_date + timedelta(days=1)
    
    # 检查今天数据是否可用
    today = datetime.now()
    today_file = f"{today.strftime('%Y-%m-%d')}rating.tar.bz2"
    today_url = f"https://katagoarchive.org/kata1/ratinggames/{today_file}"
    
    if not check_url_exists(today_url):
        # 今天数据不可用，检查昨天
        today = today - timedelta(days=1)
    
    # 如果最后处理日期已经是最新可用日期，无需更新
    if last_date >= today:
        print(f"✅ 已是最新，最后处理: {last_processed}，最新可用: {today.strftime('%Y-%m-%d')}")
        return None, None
    
    start_date = expected_start.strftime("%Y-%m-%d")
    end_date = today.strftime("%Y-%m-%d")
    
    # 确保开始日期不晚于结束日期
    if expected_start > today:
        print(f"✅ 已是最新，最后处理: {last_processed}，最新可用: {today.strftime('%Y-%m-%d')}")
        return None, None
    
    return start_date, end_date


def find_missing_dates(start_date, end_date):
    """检测遗漏的日期"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    cached_dates = set()
    for f in KATAGO_CACHE_DIR.glob("*rating.tar.bz2"):
        date_str = f.name.replace("rating.tar.bz2", "")
        cached_dates.add(date_str)
    
    missing = []
    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        if date_str not in cached_dates:
            url = f"https://katagoarchive.org/kata1/ratinggames/{date_str}rating.tar.bz2"
            if check_url_exists(url):
                missing.append(date_str)
        current += timedelta(days=1)
    
    return missing


def update_katago_joseki():
    """执行KataGo定式更新"""
    start_date, end_date = get_date_range()
    
    if not start_date:
        return True
    
    print(f"📅 更新范围: {start_date} ~ {end_date}")
    
    # 检测遗漏日期
    missing = find_missing_dates(start_date, end_date)
    if missing:
        print(f"⚠️  发现遗漏日期: {missing}")
    
    # 构建命令（使用 db.py 兼容性入口）
    joseki_dir = WEIQI_JOSEKI_DIR  # weiqi-joseki/ 目录
    
    cmd = [
        "python3", str(WEIQI_JOSEKI_SCRIPT),
        "katago",
        "--start-date", start_date,
        "--end-date", end_date,
        "--min-count", str(KATAGO_CONFIG["min_count"]),
        "--min-rate", str(KATAGO_CONFIG["min_rate"]),
        "--min-moves", str(KATAGO_CONFIG["min_moves"]),
        "--first-n", str(KATAGO_CONFIG["first_n"]),
        "--corner-size", "11",
    ]
    
    # 注意：不使用 --resume，避免进度文件损坏导致跳过下载
    # 每次根据缓存目录实际存在的文件决定更新范围
    
    print(f"🚀 执行: cd {joseki_dir} && {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(joseki_dir))
    
    print(result.stdout)
    if result.stderr:
        print(f"⚠️   stderr: {result.stderr}")
    
    if result.returncode == 0:
        # 更新状态文件（仅作为运行记录，不作为下次起点）
        with open(KATAGO_STATE_FILE, "w") as f:
            f.write(f"# 注意：下次起点以缓存目录最新文件为准\n")
            f.write(f"last_run={datetime.now().isoformat()}\n")
            f.write(f"processed_range={start_date}~{end_date}\n")
            if missing:
                f.write(f"missing_filled={','.join(missing)}\n")
        
        # 显示缓存目录最新日期
        latest_cache = get_last_processed_date()
        print(f"✅ 更新完成: {start_date} ~ {end_date}")
        print(f"📁 缓存最新: {latest_cache}")
        print(f"📅 下次起点: {(datetime.strptime(latest_cache, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')}")
        return True
    else:
        print(f"❌ 更新失败")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("🎯 KataGo定式日更")
    print("=" * 60)
    
    # 确保缓存目录存在
    KATAGO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # 检查并修复损坏的进度文件
    progress_file = KATAGO_CACHE_DIR / "katago-progress.json"
    if progress_file.exists():
        try:
            with open(progress_file) as f:
                data = json.load(f)
            # 检查completed_dates是否为有效列表
            if not isinstance(data.get("completed_dates"), list) or \
               any(not isinstance(d, str) for d in data.get("completed_dates", [])):
                print("⚠️  检测到损坏的进度文件，清除后重新下载")
                progress_file.unlink()
        except (json.JSONDecodeError, IOError):
            print("⚠️  进度文件损坏，清除后重新下载")
            progress_file.unlink()
    
    success = update_katago_joseki()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
