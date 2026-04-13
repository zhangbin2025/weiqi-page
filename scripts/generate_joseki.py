#!/usr/bin/env python3
"""
定式研究页生成脚本
使用 weiqi-joseki 技能包接口：
1. identify识别四角定式
2. 识别出的用8way获取ruld方向
3. 未识别的用extract提取
4. 通过list获取所有定式信息
5. 反查手数和出现次数，<10手废弃
6. 未识别定式<10手废弃，否则优先显示（出现次数0，罕见标注）
7. 识别出的定式按出现次数排序（少的在前）
"""
import os
import re
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from jinja2 import Template

sys.path.insert(0, str(Path(__file__).parent))
from config import (
    WEIQI_DB_SCRIPT, WEIQI_JOSEKI_DIR, WEIQI_SGF_SCRIPT,
    SITE_DIR, TEST_SITE_DIR, TEMPLATES_DIR, ensure_dirs
)


def run_joseki_cli(args, cwd=WEIQI_JOSEKI_DIR):
    """运行 weiqi-joseki CLI 命令"""
    cmd = ["python3", "-m", "scripts.cli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))
    return result


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


def get_all_joseki_info():
    """获取所有定式的信息（ID、手数、出现次数）
    返回: {joseki_id: {"moves": int, "count": int, "category": str}, ...}
    """
    result = run_joseki_cli(["list", "--limit", "999999"])
    if result.returncode != 0:
        print(f"⚠️ list命令失败: {result.stderr[:100]}")
        return {}
    
    info_map = {}
    # 解析输出: ID 分类 手数 次数 概率 名称
    lines = result.stdout.strip().split('\n')
    for line in lines[2:]:  # 跳过表头和分隔线
        parts = line.split()
        if len(parts) >= 4:
            joseki_id = parts[0]
            try:
                moves = int(parts[2])
                count = int(parts[3])
                category = parts[1] if len(parts) > 1 else ""
                info_map[joseki_id] = {
                    "moves": moves,
                    "count": count,
                    "category": category
                }
            except ValueError:
                continue
    
    return info_map


def identify_corners(sgf_path):
    """识别四角定式
    返回: {"tl": {...}, "tr": {...}, "bl": {...}, "br": {...}}
    每个角的值: {"joseki_id": str, "name": str, "similarity": float} 或 None
    """
    result = run_joseki_cli([
        "identify", "--sgf-file", str(sgf_path),
        "--top-k", "1", "--output", "json"
    ])
    
    if result.returncode != 0:
        print(f"     ⚠️ identify失败: {result.stderr[:100]}")
        return {}
    
    try:
        data = json.loads(result.stdout.strip())
        identified = {}
        for corner in ["tl", "tr", "bl", "br"]:
            matches = data.get(corner, [])
            if matches and len(matches) > 0:
                best = matches[0]
                identified[corner] = {
                    "joseki_id": best.get("id"),
                    "name": best.get("name"),
                    "similarity": best.get("similarity", 0)
                }
            else:
                identified[corner] = None
        return identified
    except json.JSONDecodeError:
        return {}


def extract_corner(sgf_path, corner, first_n=80):
    """从SGF提取指定角的定式序列
    返回: (着法数, 输出SGF内容) 或 (0, "")
    """
    result = run_joseki_cli([
        "extract", "--sgf-file", str(sgf_path),
        "--corner", corner,
        "--first-n", str(first_n)
    ])
    
    if result.returncode != 0:
        return 0, ""
    
    output = result.stdout.strip()
    if not output or output.startswith("(;") is False:
        return 0, ""
    
    # 解析着法数
    moves = re.findall(r';[BW]\[[a-z]{2}\]', output)
    return len(moves), output


def generate_ruld_sgf(joseki_id, output_path):
    """生成ruld方向的SGF"""
    result = run_joseki_cli([
        "8way", joseki_id,
        "--direction", "ruld",
        "--output", str(output_path)
    ])
    return result.returncode == 0


def generate_joseki_page(sgf_path, output_path):
    """生成定式研究网页"""
    # 使用绝对路径指定输出文件，确保文件名正确
    cmd = [
        "python3", str(WEIQI_SGF_SCRIPT),
        str(sgf_path), str(output_path)  # 直接指定输出文件路径
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def generate_joseki_for_date(date_str, test_mode=False):
    """生成指定日期的定式研究页"""
    base_dir = ensure_dirs(test_mode)
    joseki_dir = base_dir / "joseki" / date_str
    joseki_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📅 处理日期: {date_str}")
    
    # 获取当日棋谱
    games = get_games_by_date(date_str)
    if not games:
        print(f"⚠️  未找到 {date_str} 的棋谱")
        return []
    
    print(f"📊 找到 {len(games)} 局棋谱")
    
    # 获取所有定式库信息
    print(f"⏳ 获取定式库信息...")
    joseki_info_map = get_all_joseki_info()
    print(f"✅ 定式库共 {len(joseki_info_map)} 个定式")
    
    # 收集所有定式（四角分别处理），使用字典去重
    all_items = {}  # {joseki_id: {"type": "db"/"extract", "corner": str, "joseki_id": str/None, ...}}
    
    for i, game in enumerate(games, 1):
        game_id = game.get("id")
        print(f"  🔍 [{i}/{len(games)}] 分析棋谱: {game.get('black')} vs {game.get('white')}")
        
        # 导出SGF
        sgf_path = Path(f"/tmp/joseki_game_{game_id}.sgf")
        if not export_game_sgf(game_id, sgf_path):
            print(f"     ❌ 导出SGF失败")
            continue
        
        # 1. identify识别四角定式
        identified = identify_corners(sgf_path)
        
        for corner in ["tl", "tr", "bl", "br"]:
            corner_info = identified.get(corner)
            
            if corner_info:
                # 2. 识别出的定式
                joseki_id = corner_info["joseki_id"]
                info = joseki_info_map.get(joseki_id)
                
                if info:
                    # 5. 反查手数和出现次数，<10手废弃
                    if info["moves"] < 10:
                        print(f"     ⏭️  {corner.upper()}: {joseki_id} 仅{info['moves']}手，废弃")
                        continue
                    
                    # 使用joseki_id去重，保留出现次数更少的
                    if joseki_id in all_items:
                        if info["count"] < all_items[joseki_id]["count"]:
                            all_items[joseki_id] = {
                                "type": "db",
                                "corner": corner,
                                "joseki_id": joseki_id,
                                "name": corner_info["name"],
                                "similarity": corner_info["similarity"],
                                "moves": info["moves"],
                                "count": info["count"],
                                "game": game,
                                "source": get_game_source(game)
                            }
                    else:
                        all_items[joseki_id] = {
                            "type": "db",
                            "corner": corner,
                            "joseki_id": joseki_id,
                            "name": corner_info["name"],
                            "similarity": corner_info["similarity"],
                            "moves": info["moves"],
                            "count": info["count"],
                            "game": game,
                            "source": get_game_source(game)
                        }
                    print(f"     ✅ {corner.upper()}: {joseki_id} ({info['moves']}手, 次数{info['count']})")
                else:
                    print(f"     ⚠️  {corner.upper()}: {joseki_id} 未在库中找到信息")
            else:
                # 3. 未识别的用extract提取
                move_count, sgf_content = extract_corner(sgf_path, corner, first_n=80)
                
                if move_count == 0:
                    continue
                
                # 6. 未识别定式<10手废弃，否则优先显示（出现次数0，罕见标注）
                if move_count < 10:
                    print(f"     ⏭️  {corner.upper()}: 提取到{move_count}手，废弃")
                    continue
                
                # 保存临时SGF文件
                tmp_sgf_path = Path(f"/tmp/extracted_{game_id}_{corner}.sgf")
                tmp_sgf_path.write_text(sgf_content, encoding="utf-8")
                
                # 使用组合key去重：游戏ID + 角
                extract_key = f"extract_{game_id}_{corner}"
                all_items[extract_key] = {
                    "type": "extract",
                    "corner": corner,
                    "joseki_id": None,
                    "name": f"{corner.upper()}角新定式",
                    "similarity": 0,
                    "moves": move_count,
                    "count": 0,
                    "game": game,
                    "source": get_game_source(game),
                    "tmp_sgf_path": str(tmp_sgf_path)
                }
                print(f"     🆕 {corner.upper()}: 新定式 ({move_count}手, 罕见)")
        
        # 清理临时文件
        sgf_path.unlink(missing_ok=True)
    
    if not all_items:
        print(f"⚠️  未收集到有效定式")
        return []
    
    print(f"\n📚 共收集 {len(all_items)} 个唯一定式")
    
    # 转为列表
    items_list = list(all_items.values())
    
    # 7. 排序：未识别定式优先（罕见），然后识别出的按出现次数排序（少的在前）
    items_list.sort(key=lambda x: (
        0 if x["type"] == "extract" else 1,  # extract优先
        x["count"] if x["type"] == "db" else 0,  # db按次数排序
        -x["moves"]  # 手数多的优先
    ))
    
    # 取前50个
    selected_items = items_list[:50]
    print(f"🎯 筛选出 {len(selected_items)} 个定式进行研究")
    
    # 生成研究页面
    generated = []
    
    for idx, item in enumerate(selected_items, 1):
        joseki_id = item["joseki_id"]
        joseki_name = item["name"]
        print(f"\n  📖 [{idx}/{len(selected_items)}] 处理定式: {joseki_name or '新定式'}")
        
        # 生成输出路径
        output_name = f"joseki_{idx:03d}.html"
        output_path = joseki_dir / output_name
        
        if item["type"] == "db" and joseki_id:
            # 2. 识别出的用8way获取ruld方向
            sgf_path = joseki_dir / f"joseki_{idx:03d}.sgf"
            if not generate_ruld_sgf(joseki_id, sgf_path):
                print(f"     ❌ 生成SGF失败")
                continue
        else:
            # 使用extract提取的SGF
            sgf_path = Path(item["tmp_sgf_path"])
        
        # 生成网页
        if generate_joseki_page(sgf_path, output_path):
            print(f"     ✅ 生成页面: {output_name}")
            
            game = item["game"]
            generated.append({
                "id": joseki_id or f"new_{idx}",
                "name": joseki_name,
                "path": f"/joseki/{date_str}/{output_name}",
                "moves": item["moves"],
                "count": item["count"],
                "corner": item["corner"],
                "is_rare": item["type"] == "extract" or item["count"] < 100,
                "is_new": item["type"] == "extract",
                "black": game.get('black', '未知'),
                "white": game.get('white', '未知'),
                "event": game.get('event', ''),
            })
        else:
            print(f"     ❌ 生成页面失败")
    
    # 清理extract的临时文件
    for item in selected_items:
        if item.get("tmp_sgf_path"):
            Path(item["tmp_sgf_path"]).unlink(missing_ok=True)
    
    return generated


def generate_joseki_index(test_mode=False):
    """生成定式列表索引页"""
    base_dir = TEST_SITE_DIR if test_mode else SITE_DIR
    data_dir = base_dir / "_data"
    
    date_data = {}
    all_dates = []
    
    for f in data_dir.glob("joseki_*.json"):
        date_str = f.stem.replace("joseki_", "")
        all_dates.append(date_str)
        
        try:
            josekis = json.loads(f.read_text())
            # 按新定式和AI定式分组
            categories = {"new": [], "ai": []}
            for joseki in josekis:
                if joseki.get("is_new"):
                    categories["new"].append(joseki)
                else:
                    categories["ai"].append(joseki)
            date_data[date_str] = categories
        except:
            pass
    
    if not date_data:
        print("⚠️  未找到定式数据")
        return False
    
    # 读取模板
    template_path = TEMPLATES_DIR / "joseki_list.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    
    # 使用最新的日期作为当前日期
    sorted_dates = sorted(all_dates, reverse=True)
    current_date = sorted_dates[0] if sorted_dates else datetime.now().strftime("%Y-%m-%d")
    
    html = template.render(
        dates=sorted_dates,
        current_date=current_date,
        date_data=date_data
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
    args = parser.parse_args()
    
    generated = generate_joseki_for_date(args.date, args.test)
    
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
