#!/usr/bin/env python3
"""
每日更新主控脚本
串行执行所有更新任务
"""
import os
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ensure_dirs, SITE_DIR, TEST_SITE_DIR


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
    from config import WEIQI_FOXWQ_SCRIPT, WEIQI_DB_SCRIPT
    
    print(f"\n{'='*60}")
    print(f"🦊 野狐棋谱下载")
    print(f"{'='*60}")
    
    # 1. 下载棋谱
    # weiqi-foxwq 默认下载到 /tmp/foxwq_downloads/日期/
    base_download_dir = Path("/tmp/foxwq_downloads")
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
    
    steps = [
        ("野狐棋谱下载", "foxwq_downloader", date_str, test_mode),
        ("KataGo定式日更", "katago_updater.py"),
        ("棋谱页生成", "generate_games.py", date_str, "--test" if test_mode else ""),
        ("选点题生成", "generate_quiz.py", date_str, "--test" if test_mode else ""),
        ("定式研究页生成", "generate_joseki.py", date_str, "--test" if test_mode else ""),
        ("索引页生成", "generate_index.py", "--test" if test_mode else ""),
        ("公众号文章生成", "generate_article.py", date_str, "--test" if test_mode else ""),
    ]
    
    results = []
    for step_name, script, *args in steps:
        if script == "foxwq_downloader":
            # 特殊处理野狐下载
            date_arg, test_arg = args
            success = download_foxwq_games(date_arg, test_arg)
        else:
            # 过滤空参数
            args = [a for a in args if a]
            success = run_script(script, *args)
        results.append((step_name, success))
        
        if not success:
            print(f"⚠️  {step_name} 失败，继续执行后续步骤...")
    
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
    parser.add_argument("--test", action="store_true", help="测试模式（不推送）")
    
    args = parser.parse_args()
    
    return daily_update(args.date, args.test)


if __name__ == "__main__":
    sys.exit(main())
