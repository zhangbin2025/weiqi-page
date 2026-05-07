#!/usr/bin/env python3
"""
定式研究页生成脚本（精简版）
使用 weiqi-db + weiqi-joseki discover 接口：
1. query获取指定日期的棋谱列表
2. get批量导出SGF到临时目录
3. discover发现定式（新定式优先+罕见定式）
4. 生成研究网页
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
    get_games_by_date, batch_export_sgfs, get_game_source
)
from config import (
    WEIQI_JOSEKI_DIR, WEIQI_SGF_SCRIPT, BASE_PATH, get_base_path,
    SITE_DIR, TEST_SITE_DIR, TEMPLATES_DIR, ensure_dirs
)


def run_joseki_cli(args, cwd=WEIQI_JOSEKI_DIR):
    """运行 weiqi-joseki CLI 命令"""
    cmd = ["python3", "-m", "src.cli.commands"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))
    return result


def discover_joseki(sgf_dir, sgf_count):
    """
    发现值得研究的定式
    返回: (stats, joseki_list) 元组
    """
    result = run_joseki_cli([
        "discover", str(sgf_dir),
        "--json"
    ])
    
    if result.returncode != 0:
        print(f"❌ discover失败: {result.stderr}")
        return None, []
    
    try:
        # 新接口直接返回数组
        joseki_list = json.loads(result.stdout.strip())
        stats = {"unique_joseki": len(joseki_list)}
        return stats, joseki_list
    except json.JSONDecodeError as e:
        print(f"❌ 解析discover结果失败: {e}")
        return None, []


def generate_sgf_from_moves(tree_sgf, output_path, corner="tr", prefix_len=0):
    """
    根据 tree SGF 生成带元数据的 SGF 文件
    tree_sgf: tree SGF 字符串（从 discover 接口获取）
    """
    if not tree_sgf:
        return False
    
    # 去掉换行符，简化处理
    tree_sgf_oneline = tree_sgf.replace('\n', '')
    
    # 找到着法开始位置（第一个 ;B[ 或 ;W[）
    body_start = tree_sgf_oneline.find(";B[")
    if body_start == -1:
        body_start = tree_sgf_oneline.find(";W[")
    
    sgf_body = tree_sgf_oneline[body_start:] if body_start != -1 else ""
    
    # 角位映射
    corner_map = {
        'tr': '右上角',
        'tl': '左上角',
        'br': '右下角',
        'bl': '左下角'
    }
    corner_name = corner_map.get(corner.lower(), f"{corner.upper()}角")
    
    # 构建新头部 - 纯定式教学视角，不含棋手信息
    header_props = ["CA[utf-8]", "FF[4]", "AP[WeiqiPage]", "SZ[19]", "GM[1]"]
    
    # 定式标题（用于网页标题显示）
    joseki_title = f"实战{corner_name}标准化定式（{prefix_len}手）"
    header_props.append(f"GN[{joseki_title}]")
    
    # 注释（显示在棋盘上方）
    header_props.append(f"C[{joseki_title}]")
    
    sgf = f"(;{' '.join(header_props)}{sgf_body})"
    
    try:
        output_path.write_text(sgf, encoding="utf-8")
        return True
    except Exception as e:
        print(f"❌ 写入SGF失败: {e}")
        return False


def generate_joseki_page(sgf_path, output_path, start_move=0):
    """生成定式研究数据文件（JSON格式）
    
    Args:
        sgf_path: SGF文件路径
        output_path: 输出JSON路径
        start_move: 默认跳转手数
    """
    # weiqi-sgf 新版: replay.py input.sgf --data-only --start-move N -o output.json
    cmd = [
        "python3", str(WEIQI_SGF_SCRIPT),
        str(sgf_path), "--data-only",
        "--start-move", str(start_move),
        "-o", str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0
    return result.returncode == 0


def generate_joseki_for_date(date_str, test_mode=False, sgf_dir=None):
    """生成指定日期的定式研究页
    
    Args:
        date_str: 日期
        test_mode: 是否测试模式
        sgf_dir: 外部提供的SGF目录，为None则自动导出
    """
    base_dir = ensure_dirs(test_mode)
    joseki_dir = base_dir / "joseki" / date_str
    joseki_dir.mkdir(parents=True, exist_ok=True)
    base_path = get_base_path(test_mode)
    
    print(f"📅 处理日期: {date_str}")
    
    # 获取当日棋谱
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
        
        temp_dir = Path(tempfile.mkdtemp(prefix=f"sgf_{date_str}_"))
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
        print("⚠️  没有SGF文件可供分析")
        if not sgf_dir and temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return []
    
    # 发现定式 - limit = 棋谱数 * 4（每盘棋最多4个角）
    sgf_count = len(sgf_files)
    print(f"⏳ 发现定式（分析前80手，最少1手，最多{sgf_count * 4}个）...")
    stats, joseki_list = discover_joseki(temp_dir, sgf_count)
    
    if not joseki_list:
        print("⚠️  未发现有效定式")
        if not sgf_dir and temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return []
    
    if stats:
        print(f"✅ 发现 {stats.get('unique_joseki', 0)} 个唯一定式，显示前 {len(joseki_list)} 个")
    else:
        print(f"✅ 发现 {len(joseki_list)} 个值得研究的定式")
    
    # 生成研究页面
    generated = []
    
    for idx, joseki in enumerate(joseki_list, 1):
        joseki_id = joseki.get("joseki_id", "")
        matched_prefix_len = joseki.get("prefix_len", 0)
        # extracted_moves 现在是 tree SGF 字符串
        tree_sgf = joseki.get("extracted_moves", "")
        prefix_str = joseki.get("prefix", "")  # 用于显示
        move_count = joseki.get("total_moves", 0)
        moves = tree_sgf  # 保持兼容，moves 字段现在放 tree SGF
        frequency = joseki.get("frequency", 0)
        
        # 获取来源信息（从game_info和source_corner）
        game_info = joseki.get("game_info", {})
        corner = joseki.get("source_corner", "tr")
        black_name = game_info.get("black", "未知")
        white_name = game_info.get("white", "未知")
        event_name = game_info.get("event", "")
        
        # 新接口不区分罕见/常见，统一显示
        name = f"{corner.upper()}角定式 {joseki_id}"
        print(f"\n  📖 [{idx}/{len(joseki_list)}] {name} ({move_count}手, 匹配{matched_prefix_len}手, 次数{frequency}) - {black_name} vs {white_name}")
        
        # 生成SGF
        sgf_path = joseki_dir / f"joseki_{idx:03d}.sgf"
        
        # tree_sgf 坐标已统一转换为右上角视角
        # 但标题显示真实来源角位（source_corner）
        if not generate_sgf_from_moves(tree_sgf, sgf_path, corner, matched_prefix_len):
            print(f"     ❌ 生成SGF失败")
            continue
        
        # 生成数据文件
        output_name = f"joseki_{idx:03d}.json"
        output_path = joseki_dir / output_name
        
        if generate_joseki_page(sgf_path, output_path, matched_prefix_len):
            print(f"     ✅ 生成数据: {output_name}")
            
            # 删除临时SGF文件
            try:
                sgf_path.unlink()
            except Exception:
                pass
            
            # 查找对应棋谱路径（根据黑白棋手的名字匹配）
            game_path = ""
            for game in games:
                game_black = game.get("black", "")
                game_white = game.get("white", "")
                if (game_black == black_name and game_white == white_name) or \
                   (game_black in black_name and game_white in white_name) or \
                   (black_name in game_black and white_name in game_white):
                    game_id = game.get("id")
                    game_source = get_game_source(game)
                    game_path = f"{base_path}/replay.html?data={base_path}/games/{date_str}/{game_source}/game_{game_id}.json"
                    break
            
            generated.append({
                "id": f"joseki_{idx:03d}",
                "name": name,
                "path": f"{base_path}/replay.html?data={base_path}/joseki/{date_str}/{output_name}",
                "game_path": game_path if game_path else "",
                "moves": moves,  # 着法序列，用于前端计算
                "move_count": move_count,  # 总手数
                "matched_prefix_len": matched_prefix_len,  # 匹配前缀长度
                "count": frequency,
                "frequency": frequency,  # 出现次数
                "probability": joseki.get("probability", 0),  # 出现概率
                "winrate_stats": joseki.get("winrate_stats"),  # 胜率统计
                "joseki_id": joseki_id,  # 匹配的定式ID
                "corner": corner,
                "black": black_name,
                "white": white_name,
                "event": event_name,
                "date": game_info.get("date", date_str),
            })
        else:
            print(f"     ❌ 生成页面失败")
    
    # 清理临时目录（仅自动导出时才清理）
    if not sgf_dir and temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"\n🧹 清理临时文件")
    
    return generated


def generate_joseki_index(test_mode=False):
    """生成定式列表索引页"""
    base_dir = TEST_SITE_DIR if test_mode else SITE_DIR
    data_dir = base_dir / "_data"
    base_path = get_base_path(test_mode)
    
    date_data = {}
    all_dates = []
    
    for f in data_dir.glob("joseki_*.json"):
        date_str = f.stem.replace("joseki_", "")
        all_dates.append(date_str)
        
        try:
            josekis = json.loads(f.read_text())
            # 添加 probability 字段（如果后端数据中没有）
            for joseki in josekis:
                if "probability" not in joseki:
                    # 从 count 和 total_files 计算，如果没有则设为 0
                    joseki["probability"] = 0.0
                if "moves" not in joseki and "move_count" in joseki:
                    # 兼容旧数据，确保有 moves 字段用于前端计算
                    joseki["moves"] = []
            # 新格式：直接返回所有定式列表，前端进行筛选
            date_data[date_str] = {"joseki_list": josekis}
        except:
            pass
    
    if not date_data:
        print("⚠️  未找到定式数据")
        return False
    
    # 读取模板
    template_path = TEMPLATES_DIR / "joseki_list.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    
    # 使用最新的日期作为当前日期（availableDates 的最后一天，即最新有数据的日期）
    sorted_dates = sorted(all_dates, reverse=True)
    current_date = sorted_dates[0] if sorted_dates else datetime.now().strftime("%Y-%m-%d")
    
    html = template.render(
        dates=sorted_dates,
        current_date=current_date,
        date_data=date_data,
        base_path=base_path
    )
    
    output_path = base_dir / "joseki" / "index.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"✅ 生成定式索引: {output_path}")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="定式研究页生成")
    parser.add_argument("date", help="日期 (YYYY-MM-DD)")
    parser.add_argument("--test", action="store_true", help="生成到测试站点")
    parser.add_argument("--sgf-dir", help="使用外部SGF目录（避免重复导出）")
    args = parser.parse_args()
    
    generated = generate_joseki_for_date(args.date, args.test, args.sgf_dir)
    
    if generated:
        # 保存数据
        base_dir = TEST_SITE_DIR if args.test else SITE_DIR
        data_file = base_dir / "_data" / f"joseki_{args.date}.json"
        data_file.parent.mkdir(parents=True, exist_ok=True)
        data_file.write_text(json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n📄 保存数据: {data_file}")
    
    # 生成索引
    generate_joseki_index(args.test)
    
    return 0 if generated else 1


if __name__ == "__main__":
    sys.exit(main())
