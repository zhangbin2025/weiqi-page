#!/usr/bin/env python3
"""
定式Trie树数据生成脚本 v2.0
按前缀裁剪,生成索引和子树文件

用法:
    python3 scripts/generate_joseki_tree.py [--test] [--threshold 1000]

输出目录结构:
    trie-index.json.gz    索引trie
    trie-{prefix}.json.gz 前缀子树文件
"""

import sys
import json
import gzip
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import SITE_DIR, TEST_SITE_DIR

DEFAULT_THRESHOLD = 1000


def load_joseki_list():
    """从数据库加载定式"""
    db_path = Path.home() / '.weiqi-joseki' / 'database.json'
    if not db_path.exists():
        print(f"数据库不存在: {db_path}")
        return []

    print(f"加载数据库: {db_path}")
    with open(db_path) as f:
        data = json.load(f)

    joseki_list = data.get('joseki_list', [])
    print(f"定式数量: {len(joseki_list)}")
    return joseki_list


def build_trie(joseki_list):
    """构建完整 trie 树"""
    root = {'coord': None, 'children': {}, 'freq': 0}

    for j in joseki_list:
        moves = j['moves']
        if not moves:
            continue

        freq = j.get('frequency', 0)
        node = root

        for i, coord in enumerate(moves):
            if coord not in node['children']:
                color = 'black' if i % 2 == 0 else 'white'
                node['children'][coord] = {
                    'coord': coord,
                    'color': color,
                    'children': {},
                    'freq': 0
                }

            node['children'][coord]['freq'] += freq
            node = node['children'][coord]

        node['leaf'] = True
        node['moves'] = len(moves)
        node['name'] = j.get('id', '')
        node['total_freq'] = freq
        node['prob'] = j.get('probability', 0)

    root['freq'] = sum(j.get('frequency', 0) for j in joseki_list)
    return root


def count_joseki_nodes(node):
    """统计节点下的定式数"""
    count = 0
    if node.get('leaf'):
        count += 1

    children = node.get('children')
    if children:
        for child in children.values():
            count += count_joseki_nodes(child)

    return count


def serialize_trie(node):
    """序列化 trie 节点"""
    result = {
        'coord': node.get('coord'),
        'color': node.get('color'),
        'freq': node.get('freq', 0),
    }

    if node.get('leaf'):
        result['leaf'] = True
        result['moves'] = node.get('moves')
        result['total_freq'] = node.get('total_freq')
        result['prob'] = node.get('prob')

    if node.get('subtree'):
        result['subtree'] = node['subtree']

    children = node.get('children')
    if children:
        result['children'] = {
            coord: serialize_trie(child)
            for coord, child in sorted(children.items())
        }
    elif node.get('subtree'):
        result['children'] = None

    return result


stats = {'subtree_files': [], 'difficulty': {'easy': 0, 'medium': 0, 'hard': 0}}


def prune_trie(node, prefix, threshold, output_dir):
    """后序遍历裁剪 trie"""
    children = node.get('children', {})
    if not children:
        return

    for coord, child in list(children.items()):
        new_prefix = f'{prefix}-{coord}' if prefix else coord
        prune_trie(child, new_prefix, threshold, output_dir)

    for coord, child in list(children.items()):
        if child.get('subtree'):
            continue

        joseki_count = count_joseki_nodes(child)

        if joseki_count >= threshold:
            new_prefix = f'{prefix}-{coord}' if prefix else coord
            filename = f'trie-{new_prefix}.json.gz'

            export_subtree(child, filename, threshold, output_dir)

            child['subtree'] = {'file': filename, 'josekiCount': joseki_count}
            child['children'] = None


def export_subtree(node, filename, threshold, output_dir):
    """导出子树文件"""
    prune_trie(node, '', threshold, output_dir)
    collect_difficulty(node)

    filepath = output_dir / filename
    with gzip.open(filepath, 'wt', encoding='utf-8') as f:
        json.dump(serialize_trie(node), f, ensure_ascii=False, separators=(',', ':'))

    file_size = filepath.stat().st_size
    joseki_count = count_joseki_nodes(node)
    stats['subtree_files'].append({
        'prefix': filename.replace('trie-', '').replace('.json.gz', ''),
        'size': file_size,
        'count': joseki_count
    })
    print(f"  导出: {filename} ({file_size//1024}KB, {joseki_count}定式)")


def collect_difficulty(node):
    """收集难度统计"""
    if node.get('leaf'):
        moves = node.get('moves', 0)
        if moves <= 10:
            stats['difficulty']['easy'] += 1
        elif moves <= 20:
            stats['difficulty']['medium'] += 1
        else:
            stats['difficulty']['hard'] += 1

    children = node.get('children')
    if children:
        for child in children.values():
            collect_difficulty(child)


def collect_leaves(node, path='', leaves=None):
    """收集所有定式叶子节点"""
    if leaves is None:
        leaves = {'easy': [], 'medium': [], 'hard': []}
    
    if node.get('leaf'):
        moves = node.get('moves', 0)
        if moves <= 10:
            difficulty = 'easy'
        elif moves <= 20:
            difficulty = 'medium'
        else:
            difficulty = 'hard'
        
        leaves[difficulty].append({
            'path': path,
            'moves': moves,
            'freq': node.get('total_freq', 0),
            'prob': node.get('prob', 0)
        })
    
    children = node.get('children')
    if children:
        for coord, child in children.items():
            child_path = f'{path}-{coord}' if path else coord
            collect_leaves(child, child_path, leaves)
    
    return leaves





def build(output_dir, threshold):
    """构建索引和子树"""
    global stats
    stats = {'subtree_files': [], 'difficulty': {'easy': 0, 'medium': 0, 'hard': 0}}

    output_dir.mkdir(parents=True, exist_ok=True)

    # 清理旧文件
    for f in output_dir.glob('*.gz'):
        f.unlink()

    joseki_list = load_joseki_list()
    if not joseki_list:
        return False

    print("\n构建 trie 树...")
    trie = build_trie(joseki_list)

    total = count_joseki_nodes(trie)
    print(f"总定式节点: {total}")

    # 先收集做题数据（在裁剪前，确保遍历所有节点）
    print("\n收集做题数据...")
    quiz_leaves = collect_leaves(trie)
    for difficulty, items in quiz_leaves.items():
        print(f"  {difficulty}: {len(items)}题")

    print("\n开始裁剪...")
    prune_trie(trie, '', threshold, output_dir)

    collect_difficulty(trie)

    print("\n导出索引...")
    index_file = output_dir / 'trie-index.json.gz'
    with gzip.open(index_file, 'wt', encoding='utf-8') as f:
        json.dump(serialize_trie(trie), f, ensure_ascii=False, separators=(',', ':'))

    index_size = index_file.stat().st_size
    print(f"  索引大小: {index_size//1024}KB")

    # 导出做题数据
    print("\n导出做题数据...")
    for difficulty, items in quiz_leaves.items():
        if not items:
            continue
        
        items.sort(key=lambda x: x['freq'], reverse=True)
        filename = f'quiz-{difficulty}.json.gz'
        filepath = output_dir / filename
        
        with gzip.open(filepath, 'wt', encoding='utf-8') as f:
            json.dump({'leaves': items, 'count': len(items)}, f, ensure_ascii=False, separators=(',', ':'))
        
        file_size = filepath.stat().st_size
        print(f"  导出: {filename} ({file_size//1024}KB, {len(items)}题)")

    # 导出元信息
    meta = {
        'version': '2.0',
        'threshold': threshold,
        'total': total,
        'subtrees': len(stats['subtree_files']),
        'difficulty': stats['difficulty'],
        'indexSize': index_size
    }

    with open(output_dir / 'trie-meta.json', 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 统计
    print("\n结果统计:")
    print(f"  索引: {index_size//1024}KB")
    print(f"  子树: {len(stats['subtree_files'])}个")

    if stats['subtree_files']:
        sizes = [s['size'] for s in stats['subtree_files']]
        print(f"  子树大小: {min(sizes)//1024}KB - {max(sizes)//1024}KB")
        print(f"  总存储: {(index_size + sum(sizes))//1024//1024}MB")

    print(f"  难度: 初{stats['difficulty']['easy']} 中{stats['difficulty']['medium']} 高{stats['difficulty']['hard']}")

    return True


def generate_joseki_tree(test_mode=False, threshold=DEFAULT_THRESHOLD):
    """生成定式 Trie 树数据（供其他模块调用）"""
    base_dir = TEST_SITE_DIR if test_mode else SITE_DIR
    output_dir = base_dir / "assets" / "data" / "joseki"
    return build(output_dir, threshold)


def main():
    parser = argparse.ArgumentParser(description='生成定式Trie树数据')
    parser.add_argument('--test', action='store_true', help='测试模式')
    parser.add_argument('--threshold', type=int, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    print("=" * 50)
    print("定式Trie树数据生成 v2.0")
    print(f"阈值: {args.threshold}")
    print("=" * 50)

    success = generate_joseki_tree(args.test, args.threshold)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())