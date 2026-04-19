#!/usr/bin/env python3
"""
每日更新主控脚本（统一SGF导出版）
串行执行所有更新任务，SGF只导出一次共享使用
"""
import os
import sys
import subprocess
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ensure_dirs, WEIQI_DB_SCRIPT
from common import get_games_by_date, batch_export_sgfs


def run_script(script_name, *args):
    """运行子脚本"""
    script_path = Path(__file__).parent / script_name
    cmd = ["python3", str(script_path)] + list(args)
    
    print(f"\n{'='*60}")
    print(f"🚀 执行: {script_name}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd)
    return result.returncode == 0


def download_foxwq_games(date_str, test_mode=False):
    """下载野狐棋谱并导入weiqi-db"""
    from config import WEIQI_FOXWQ_SCRIPT
    
    print(f"\n{'='*60}")
    print(f"🦊 野狐棋谱下载")
    print(f"{'='*60}")
    
    # 1. 下载棋谱
    # 使用临时目录，避免硬编码路径
    import tempfile
    base_download_dir = Path(tempfile.gettempdir()) / "foxwq_downloads"
    date_download_dir = base_download_dir / date_str
    
    # 确保目录存在
    base_download_dir.mkdir(parents=True, exist_ok=True)
    
    # 设置下载目录环境变量
    env = os.environ.copy()
    env["FOXWQ_DOWNLOAD_DIR"] = str(base_download_dir)
    
    cmd_download = [
        "python3", str(WEIQI_FOXWQ_SCRIPT),
        date_str
    ]
    
    print(f"📥 下载日期: {date_str}")
    print(f"📁 下载目录: {date_download_dir}")
    result = subprocess.run(cmd_download, capture_output=True, text=True, env=env)
    print(result.stdout)
    if result.stderr:
        print(f"⚠️  stderr: {result.stderr}")
    
    if result.returncode != 0:
        print(f"❌ 下载失败")
        return False
    
    # 检查下载目录是否存在SGF文件
    if not date_download_dir.exists():
        print(f"⚠️  下载目录不存在: {date_download_dir}")
        return False
    
    sgf_files = list(date_download_dir.glob("*.sgf"))
    if not sgf_files:
        print(f"⚠️  未找到SGF文件（可能是当日无棋谱或下载失败）")
        return False
    
    print(f"📊 找到 {len(sgf_files)} 个SGF文件")
    
    # 2. 导入weiqi-db
    print(f"\n📥 导入weiqi-db...")
    cmd_import = [
        "python3", str(WEIQI_DB_SCRIPT),
        "add", "--dir", str(date_download_dir),
        "--tag", f"来源:野狐",
        "--tag", f"日期:{date_str}",
        "--conflict", "skip"
    ]
    
    result = subprocess.run(cmd_import, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(f"⚠️  stderr: {result.stderr}")
    
    if result.returncode == 0:
        print(f"✅ 导入完成")
        return True
    else:
        print(f"❌ 导入失败")
        return False


def export_sgfs_once(date_str):
    """统一导出SGF，返回临时目录路径"""
    print(f"\n{'='*60}")
    print(f"📦 统一导出SGF")
    print(f"{'='*60}")
    
    # 获取棋谱列表
    games = get_games_by_date(date_str)
    if not games:
        print(f"⚠️  未找到 {date_str} 的棋谱")
        return None
    
    print(f"📊 找到 {len(games)} 局棋谱")
    
    game_ids = [g.get("id") for g in games if g.get("id")]
    if not game_ids:
        print("⚠️  没有有效的棋谱ID")
        return None
    
    # 创建临时目录
    temp_dir = Path(tempfile.mkdtemp(prefix=f"daily_{date_str}_"))
    print(f"⏳ 批量导出SGF到: {temp_dir}")
    
    if not batch_export_sgfs(game_ids, temp_dir):
        print("❌ 批量导出失败")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None
    
    # 检查导出结果
    sgf_files = list(temp_dir.glob("*.sgf"))
    print(f"✅ 成功导出 {len(sgf_files)} 个SGF文件")
    
    if not sgf_files:
        print("⚠️  没有SGF文件")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return None
    
    return temp_dir


def daily_update(date_str=None, test_mode=False):
    """执行每日更新"""
    if date_str is None:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    print("=" * 60)
    print("🎯 围棋资源站 - 每日更新")
    print(f"📅 日期: {date_str}")
    print(f"🧪 测试模式: {test_mode}")
    print("=" * 60)
    
    # 确保目录存在
    ensure_dirs(test_mode)
    
    # 1. 下载野狐棋谱并导入
    foxwq_success = download_foxwq_games(date_str, test_mode)
    if not foxwq_success:
        print(f"⚠️  野狐下载失败，继续执行...")
    
    # 2. 统一导出SGF（供后续三个任务共享）
    sgf_dir = export_sgfs_once(date_str)
    if not sgf_dir:
        print("❌ SGF导出失败，无法继续生成页面")
        return 1
    
    test_flag = "--test" if test_mode else ""
    sgf_dir_flag = f"--sgf-dir={sgf_dir}"
    
    # 4. 生成页面（共享SGF目录）
    steps = [
        ("棋谱页生成", "generate_games.py", date_str, test_flag, sgf_dir_flag),
        ("选点题生成", "generate_quiz.py", date_str, test_flag, sgf_dir_flag),
        ("定式研究页生成", "generate_joseki.py", date_str, test_flag, sgf_dir_flag),
        ("索引页生成", "generate_index.py", test_flag),
        ("公众号文章生成", "generate_article.py", date_str, test_flag),
    ]
    
    results = [
        ("野狐棋谱下载", foxwq_success),
    ]
    
    for step_name, script, *args in steps:
        # 过滤空参数
        args = [a for a in args if a]
        success = run_script(script, *args)
        results.append((step_name, success))
        
        if not success:
            print(f"⚠️  {step_name} 失败，继续执行后续步骤...")
    
    # 5. 清理临时SGF目录
    print(f"\n{'='*60}")
    print(f"🧹 清理临时文件")
    print(f"{'='*60}")
    shutil.rmtree(sgf_dir, ignore_errors=True)
    print(f"✅ 已清理: {sgf_dir}")
    
    # 汇总报告
    print("\n" + "=" * 60)
    print("📊 更新报告")
    print("=" * 60)
    
    for step_name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"  {status}: {step_name}")
    
    all_success = all(s for _, s in results)
    
    if all_success and not test_mode:
        print("\n🚀 准备部署到 GitHub Pages...")
        # TODO: git commit & push
        # 目前只在测试完成后手动部署
    
    return 0 if all_success else 1


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="围棋资源站每日更新")
    parser.add_argument("--date", help="指定日期 (YYYY-MM-DD)，默认昨天")
    parser.add_argument("--dates", help="指定多个日期，逗号分隔 (2026-04-01,2026-04-02)")
    parser.add_argument("--start-date", help="起始日期 (YYYY-MM-DD)，与 --end-date 配合使用")
    parser.add_argument("--end-date", help="结束日期 (YYYY-MM-DD)，与 --start-date 配合使用")
    parser.add_argument("--test", action="store_true", help="测试模式（不推送）")
    
    args = parser.parse_args()
    
    # 收集所有日期
    dates = []
    
    if args.dates:
        # 逗号分隔的日期列表
        dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    elif args.start_date and args.end_date:
        # 日期范围
        try:
            start = datetime.strptime(args.start_date, "%Y-%m-%d")
            end = datetime.strptime(args.end_date, "%Y-%m-%d")
            if start > end:
                print(f"❌ 起始日期不能晚于结束日期")
                return 1
            current = start
            while current <= end:
                dates.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)
        except ValueError as e:
            print(f"❌ 日期格式错误: {e}")
            return 1
    elif args.date:
        # 单日
        dates = [args.date]
    else:
        # 默认昨天
        dates = [(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")]
    
    print(f"📅 计划更新 {len(dates)} 天: {', '.join(dates)}")
    
    # 逐日执行
    all_success = True
    for date_str in dates:
        result = daily_update(date_str, args.test)
        if result != 0:
            all_success = False
            print(f"⚠️  {date_str} 更新失败，继续执行后续日期...")
    
    print(f"\n{'='*60}")
    print(f"📊 全部完成，共处理 {len(dates)} 天")
    print(f"{'='*60}")
    
    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
