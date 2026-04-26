#!/usr/bin/env python3
"""
SGF棋手姓名翻译器 - 外译中
解析SGF文件内容，翻译PB/PW字段中的棋手姓名

支持从u-go.net官方数据库更新韩国棋手名称映射
"""
import json
import re
import gzip
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 映射表文件路径
MAPPING_FILE = Path(__file__).parent / "name_mapping.json"

# u-go.net 数据源
UGO_DB_URL = "https://dldb.u-go.net/media/playerdb/archive/playerdb-latest.json.gz"

# 全局映射表缓存
_name_map = {}

# 需要过滤的绰号/称号列表
NICKNAMES = {
    '石佛', '大李', '小李', '神算子', '棋圣', '名人', '本因坊', 
    '棋王', '小姜勋', '本因坊治勳', '第二十五世本因坊'
}

# 繁体到简体映射表（常用字）
TRADITIONAL_TO_SIMPLIFIED = {
    '鍋': '镐', '鎬': '镐', '鎭': '镇', '碩': '硕', '臺': '台', 
    '龍': '龙', '東': '东', '國': '国', '鐘': '钟', '勳': '勋', 
    '暎': '映', '讚': '赞', '瀅': '滢', '燦': '灿', '賢': '贤', 
    '賓': '宾', '寬': '宽', '紋': '纮', '禎': '祯', '薫': '薰',
    '鉉': '铉', '鎮': '镇', '碩': '硕', '龍': '龙', '鐘': '钟',
    '讚': '赞', '瀅': '滢', '禎': '祯', '紋': '纮', '寬': '宽',
    '勳': '勋', '暎': '映', '燦': '灿', '賢': '贤', '賓': '宾',
    '龍': '龙', '東': '东', '國': '国', '鐘': '钟', '讚': '赞',
    '瀅': '滢', '燦': '灿', '賢': '贤', '禎': '祯', '寬': '宽',
    '紋': '纮', '勳': '勋', '暎': '映', '鉉': '铉', '鎭': '镇',
    '碩': '硕', '臺': '台', '龍': '龙'
}


def _load_mapping():
    """加载姓名映射表"""
    global _name_map
    if _name_map:
        return
    
    if MAPPING_FILE.exists():
        try:
            data = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
            _name_map = data.get("names", {})
        except:
            _name_map = {}
    else:
        _name_map = {}


def translate_player_name(name: str) -> str:
    """
    翻译单个棋手姓名
    
    Args:
        name: 原始姓名（如 "Shin Jinseo"）
        
    Returns:
        中文名，未找到则返回原名
    """
    if not name:
        return name
    
    # 已经是中文（含汉字）直接返回
    if re.search(r'[\u4e00-\u9fff]', name):
        return name
    
    _load_mapping()
    
    # 精确匹配
    if name in _name_map:
        return _name_map[name]
    
    # 大小写不敏感匹配
    name_lower = name.lower()
    for key, value in _name_map.items():
        if key.lower() == name_lower:
            return value
    
    return name


def translate_sgf(sgf_content: str) -> str:
    """
    翻译SGF文件内容中的棋手姓名
    
    Args:
        sgf_content: SGF文件内容字符串
        
    Returns:
        翻译后的SGF内容
    """
    if not sgf_content:
        return sgf_content
    
    _load_mapping()
    
    result = sgf_content
    
    # 翻译黑方 PB[...]
    def replace_black(match):
        name = match.group(1)
        translated = translate_player_name(name)
        return f'PB[{translated}]'
    
    # 翻译白方 PW[...]
    def replace_white(match):
        name = match.group(1)
        translated = translate_player_name(name)
        return f'PW[{translated}]'
    
    # 匹配 PB[...] 和 PW[...]
    result = re.sub(r'PB\[([^\]]+)\]', replace_black, result)
    result = re.sub(r'PW\[([^\]]+)\]', replace_white, result)
    
    return result


def is_pure_chinese(name: str) -> bool:
    """检查是否是纯中文名（不含日文假名）"""
    for c in name:
        # 日文假名范围：平假名 \u3040-\u309f，片假名 \u30a0-\u30ff
        if '\u3040' <= c <= '\u309f' or '\u30a0' <= c <= '\u30ff':
            return False
    return True


def contains_bracket(name: str) -> bool:
    """检查是否包含括号注释"""
    return '(' in name or ')' in name


def to_simplified_chinese(name: str) -> str:
    """将繁体中文转换为简体"""
    result = name
    for trad, simp in TRADITIONAL_TO_SIMPLIFIED.items():
        result = result.replace(trad, simp)
    return result


def download_ugo_data(cache_file: Optional[Path] = None) -> List[Dict]:
    """
    从u-go.net下载棋手数据库
    
    Args:
        cache_file: 缓存文件路径，如果提供则保存到该文件
        
    Returns:
        棋手数据列表
    """
    print(f"📥 下载u-go.net棋手数据库...")
    print(f"   URL: {UGO_DB_URL}")
    
    try:
        # 下载数据
        with urllib.request.urlopen(UGO_DB_URL, timeout=60) as response:
            data = gzip.decompress(response.read())
            players = json.loads(data)
        
        print(f"✅ 下载成功，共 {len(players)} 条记录")
        
        # 保存缓存
        if cache_file:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(data)
            print(f"💾 缓存已保存: {cache_file}")
        
        return players
    
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        raise


def extract_korean_names(players: List[Dict]) -> Dict[str, str]:
    """
    从u-go.net数据中提取韩国棋手姓名映射
    
    Args:
        players: u-go.net棋手数据列表
        
    Returns:
        韩文到中文的映射字典
    """
    mapping = {}
    skipped_nickname = 0
    skipped_japanese = 0
    skipped_bracket = 0
    
    print("🔍 提取韩国棋手姓名...")
    
    for player in players:
        citizenship = player.get('citizenship', '')
        if citizenship != 'KOR':
            continue
        
        names = player.get('names', [])
        ko_name = None
        zh_names = []
        
        for name_entry in names:
            simplenames = name_entry.get('simplenames', [])
            for sn in simplenames:
                name = sn.get('name', '')
                if not name:
                    continue
                
                # 韩文
                if any('\uac00' <= c <= '\ud7a3' for c in name):
                    ko_name = name
                # 中文（汉字）
                elif any('\u4e00' <= c <= '\u9fff' for c in name):
                    zh_names.append(name)
        
        if not ko_name or not zh_names:
            continue
        
        # 跳过带括号的（如"이상훈(小)"）
        if contains_bracket(ko_name):
            skipped_bracket += 1
            continue
        
        # 过滤绰号和日文混合名
        real_names = []
        for n in zh_names:
            if n in NICKNAMES:
                skipped_nickname += 1
                continue
            if not is_pure_chinese(n):
                skipped_japanese += 1
                continue
            real_names.append(n)
        
        if not real_names:
            continue
        
        # 选择最佳中文名（优先简体）
        best_name = real_names[0]
        for name in real_names:
            # 简体字判断：不包含繁体特有字
            is_simplified = not any(c in name for c in TRADITIONAL_TO_SIMPLIFIED.keys())
            if is_simplified:
                best_name = name
                break
        
        # 转换为简体
        best_name = to_simplified_chinese(best_name)
        
        mapping[ko_name] = best_name
    
    print(f"   ✓ 提取完成: {len(mapping)} 个映射")
    print(f"   • 跳过绰号: {skipped_nickname}")
    print(f"   • 跳过日文混合: {skipped_japanese}")
    print(f"   • 跳过括号注释: {skipped_bracket}")
    
    return mapping


def update_mapping_file(new_mapping: Dict[str, str], merge: bool = True) -> Dict:
    """
    更新name_mapping.json文件
    
    Args:
        new_mapping: 新的映射字典
        merge: 是否合并现有映射（True=合并，False=替换）
        
    Returns:
        更新统计信息
    """
    print(f"\n💾 更新映射表...")
    
    # 读取现有数据
    if MAPPING_FILE.exists():
        try:
            with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {"names": {}}
    else:
        data = {"names": {}}
    
    existing_names = data.get("names", {})
    original_count = len(existing_names)
    
    # 合并或替换
    if merge:
        final_names = dict(existing_names)
        added = 0
        updated = 0
        
        for ko, zh in new_mapping.items():
            if ko not in final_names:
                final_names[ko] = zh
                added += 1
            elif final_names[ko] != zh:
                # 检查现有值是否是绰号，如果是则更新
                if final_names[ko] in NICKNAMES or not is_pure_chinese(final_names[ko]):
                    print(f"   更新: {ko} -> {final_names[ko]} => {zh}")
                    final_names[ko] = zh
                    updated += 1
    else:
        final_names = new_mapping
        added = len(final_names)
        updated = 0
    
    # 移除带括号的条目
    removed = 0
    for ko in list(final_names.keys()):
        if contains_bracket(ko):
            del final_names[ko]
            removed += 1
    
    # 更新数据
    data["names"] = final_names
    data["version"] = f"2.{datetime.now().strftime('%Y%m%d')}"
    data["description"] = "韩国职业棋手韩文转中文映射表（基于u-go.net官方数据）"
    data["source"] = "https://dldb.u-go.net/"
    data["updated"] = datetime.now().isoformat()
    
    # 保存
    with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 更新完成!")
    print(f"   • 原有条目: {original_count}")
    print(f"   • 新增条目: {added}")
    print(f"   • 更新条目: {updated}")
    print(f"   • 移除条目: {removed}")
    print(f"   • 当前总计: {len(final_names)}")
    
    return {
        "original": original_count,
        "added": added,
        "updated": updated,
        "removed": removed,
        "total": len(final_names)
    }


def update_from_ugo(cache_dir: Optional[Path] = None, merge: bool = True) -> Dict:
    """
    从u-go.net更新棋手名称映射表（主入口）
    
    Args:
        cache_dir: 缓存目录，如果提供则保存下载的数据
        merge: 是否合并现有映射
        
    Returns:
        更新统计信息
    """
    print("=" * 60)
    print("🔄 从u-go.net更新韩国棋手名称映射")
    print("=" * 60)
    
    # 下载数据
    cache_file = None
    if cache_dir:
        cache_file = cache_dir / f"playerdb_{datetime.now().strftime('%Y%m%d')}.json"
    
    players = download_ugo_data(cache_file)
    
    # 提取映射
    mapping = extract_korean_names(players)
    
    # 更新文件
    stats = update_mapping_file(mapping, merge=merge)
    
    # 显示示例
    print("\n📋 示例映射（前10个）:")
    for i, (ko, zh) in enumerate(sorted(mapping.items())[:10]):
        print(f"   {ko} -> {zh}")
    
    print("\n" + "=" * 60)
    print("✨ 更新完成!")
    print("=" * 60)
    
    return stats


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="韩国棋手名称翻译器 - 支持从u-go.net更新映射表",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 翻译SGF文件
  python3 translator.py translate input.sgf output.sgf
  
  # 从u-go.net更新映射表（合并模式）
  python3 translator.py update
  
  # 从u-go.net更新映射表（替换模式，保留缓存）
  python3 translator.py update --replace --cache-dir /tmp/ugo_cache
  
  # 仅下载数据到缓存，不更新
  python3 translator.py download --cache-dir /tmp/ugo_cache
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # translate 命令
    translate_parser = subparsers.add_parser('translate', help='翻译SGF文件')
    translate_parser.add_argument('input', help='输入SGF文件路径')
    translate_parser.add_argument('output', nargs='?', help='输出SGF文件路径（默认覆盖输入）')
    
    # update 命令
    update_parser = subparsers.add_parser('update', help='从u-go.net更新映射表')
    update_parser.add_argument('--replace', action='store_true', 
                               help='替换现有映射（默认合并）')
    update_parser.add_argument('--cache-dir', type=Path, 
                               help='缓存目录，保存下载的数据')
    
    # download 命令
    download_parser = subparsers.add_parser('download', help='仅下载u-go.net数据')
    download_parser.add_argument('--cache-dir', type=Path, required=True,
                                 help='缓存目录')
    
    # stats 命令
    stats_parser = subparsers.add_parser('stats', help='显示映射表统计')
    
    args = parser.parse_args()
    
    if args.command == 'translate':
        # 翻译SGF
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"❌ 文件不存在: {input_path}")
            return 1
        
        sgf_content = input_path.read_text(encoding='utf-8')
        translated = translate_sgf(sgf_content)
        
        output_path = Path(args.output) if args.output else input_path
        output_path.write_text(translated, encoding='utf-8')
        
        print(f"✅ 翻译完成: {output_path}")
        return 0
    
    elif args.command == 'update':
        # 更新映射表
        try:
            stats = update_from_ugo(
                cache_dir=args.cache_dir,
                merge=not args.replace
            )
            return 0
        except Exception as e:
            print(f"❌ 更新失败: {e}")
            return 1
    
    elif args.command == 'download':
        # 仅下载
        try:
            cache_file = args.cache_dir / f"playerdb_{datetime.now().strftime('%Y%m%d')}.json.gz"
            players = download_ugo_data(cache_file)
            print(f"✅ 数据已保存: {cache_file}")
            return 0
        except Exception as e:
            print(f"❌ 下载失败: {e}")
            return 1
    
    elif args.command == 'stats':
        # 显示统计
        _load_mapping()
        print(f"📊 映射表统计")
        print(f"   文件: {MAPPING_FILE}")
        print(f"   条目数: {len(_name_map)}")
        
        if _name_map:
            # 姓氏统计
            from collections import Counter
            surnames = [name[0] for name in _name_map.keys() if name]
            counts = Counter(surnames)
            print(f"\n   前10姓氏:")
            for surname, count in counts.most_common(10):
                print(f"      {surname}: {count}人")
        
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
