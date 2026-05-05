#!/usr/bin/env python3
"""
构建定式trie索引和前缀子树（测试版）

算法：
1. 后序遍历 trie 树
2. 统计每个节点的定式数（有指标数据的节点）
3. 当定式数 >= 阈值时，裁剪为子树文件
4. 子树文件内部递归裁剪

用法：
    python3 scripts/build_joseki_trie.py
"""

import sys
import json
import gzip
from collections import defaultdict
from pathlib import Path

# 添加 weiqi-joseki 路径
WEIQI_JOSEKI_DIR = Path('/root/.openclaw/workspace/weiqi-joseki')
sys.path.insert(0, str(WEIQI_JOSEKI_DIR))

THRESHOLD = 1000  # 裁剪阈值
OUTPUT_DIR = Path('/tmp/joseki-trie-test')


def load_joseki_list():
    """从 weiqi-joseki 数据库加载定式"""
    db_path = Path.home() / '.weiqi-joseki' / 'database.json'
    if not db_path.exists():
        print(f"❌ 数据库不存在: {db_path}")
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
        prob = j.get('probability', 0)
        node = root
        
        for i, coord in enumerate(moves):
            if coord not in node['children']:
                color = 'black' if i % 2 == 0 else 'white'
                node['children'][coord] = {
                    'coord': coord,
                    'color': color,
                    'children': {},
                    'freq': 0,
                    'depth': i + 1
                }
            
            node['children'][coord]['freq'] += freq
            node = node['children'][coord]
        
        # 标记定式节点
        node['leaf'] = True
        node['moves'] = len(moves)
        node['name'] = j.get('id', '')
        node['total_freq'] = freq
        node['prob'] = prob
    
    root['freq'] = sum(j.get('frequency', 0) for j in joseki_list)
    return root


def count_joseki_nodes(node):
    """统计节点下的定式数（有指标数据的节点）"""
    count = 0
    
    # 当前节点是定式（有 leaf 标记或指标数据）
    if node.get('leaf'):
        count += 1
    
    # 递归统计 children（排除已裁剪的）
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
    
    # 定式指标
    if node.get('leaf'):
        result['leaf'] = True
        result['moves'] = node.get('moves')
        result['name'] = node.get('name')
        result['total_freq'] = node.get('total_freq')
        result['prob'] = node.get('prob')
    
    # 裁剪点信息
    if node.get('subtree'):
        result['subtree'] = node['subtree']
    
    # children
    children = node.get('children')
    if children:
        result['children'] = {
            coord: serialize_trie(child)
            for coord, child in sorted(children.items())
        }
    elif node.get('subtree'):
        # 裁剪点，children 为 None
        result['children'] = None
    
    return result


# 统计变量
subtree_files = []


def prune_trie(node, prefix='', threshold=1000, output_dir=None):
    """
    后序遍历裁剪 trie
    """
    children = node.get('children', {})
    if not children:
        return
    
    # 1. 递归处理所有 children
    for coord, child in list(children.items()):
        new_prefix = f'{prefix}-{coord}' if prefix else coord
        prune_trie(child, new_prefix, threshold, output_dir)
    
    # 2. 检查每个 child
    for coord, child in list(children.items()):
        # 跳过已裁剪的
        if child.get('subtree'):
            continue
        
        joseki_count = count_joseki_nodes(child)
        
        if joseki_count >= threshold:
            new_prefix = f'{prefix}-{coord}' if prefix else coord
            filename = f'trie-{new_prefix}.json.gz'
            
            # 导出子树
            export_subtree(child, output_dir / filename, threshold)
            
            # 标记裁剪点
            child['subtree'] = {'file': filename, 'josekiCount': joseki_count}
            child['children'] = None


def export_subtree(node, filepath, threshold=1000):
    """导出子树文件，内部递归裁剪"""
    global subtree_files
    
    # 先裁剪子树内部
    prune_trie(node, prefix='', threshold=threshold, output_dir=filepath.parent)
    
    # 序列化并导出
    with gzip.open(filepath, 'wt', encoding='utf-8') as f:
        json.dump(serialize_trie(node), f, ensure_ascii=False, separators=(',', ':'))
    
    file_size = filepath.stat().st_size
    joseki_count = count_joseki_nodes(node)
    subtree_files.append({
        'prefix': filepath.stem.replace('trie-', ''),
        'file': filepath.name,
        'size': file_size,
        'joseki_count': joseki_count
    })
    print(f"  导出: {filepath.name} ({file_size//1024}KB, {joseki_count}定式)")


def build_index_and_subtrees(joseki_list, output_dir, threshold=1000):
    """构建索引和子树"""
    global subtree_files
    subtree_files = []
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n构建 trie 树...")
    trie = build_trie(joseki_list)
    
    total_joseki = count_joseki_nodes(trie)
    print(f"总定式节点: {total_joseki}")
    
    print("\n开始裁剪...")
    prune_trie(trie, prefix='', threshold=threshold, output_dir=output_dir)
    
    # 导出索引
    print("\n导出索引...")
    index_file = output_dir / 'trie-index.json.gz'
    with gzip.open(index_file, 'wt', encoding='utf-8') as f:
        json.dump(serialize_trie(trie), f, ensure_ascii=False, separators=(',', ':'))
    
    index_size = index_file.stat().st_size
    print(f"  索引大小: {index_size//1024}KB")
    
    return index_size, subtree_files


def main():
    print("=" * 60)
    print("🎯 定式 Trie 索引和子树构建测试")
    print(f"阈值: {THRESHOLD}")
    print("=" * 60)
    
    # 加载定式
    joseki_list = load_joseki_list()
    if not joseki_list:
        return 1
    
    # 构建
    index_size, subtrees = build_index_and_subtrees(joseki_list, OUTPUT_DIR, THRESHOLD)
    
    # 统计结果
    print("\n" + "=" * 60)
    print("📊 结果统计")
    print("=" * 60)
    
    print(f"\n索引文件: trie-index.json.gz ({index_size//1024}KB)")
    
    print(f"\n子树文件数: {len(subtrees)}")
    
    if subtrees:
        # 按大小排序
        sorted_subtrees = sorted(subtrees, key=lambda x: x['size'], reverse=True)
        
        print("\nTop 10 大子树:")
        for item in sorted_subtrees[:10]:
            print(f"  {item['file']}: {item['size']//1024}KB ({item['joseki_count']}定式)")
        
        print("\n最小的5个子树:")
        for item in sorted_subtrees[-5:]:
            print(f"  {item['file']}: {item['size']//1024}KB ({item['joseki_count']}定式)")
        
        # 大小分布
        sizes = [s['size'] for s in subtrees]
        print(f"\n大小分布:")
        print(f"  最大: {max(sizes)//1024}KB")
        print(f"  最小: {min(sizes)//1024}KB")
        print(f"  平均: {sum(sizes)//len(sizes)//1024}KB")
        
        # 总存储
        total_size = index_size + sum(sizes)
        print(f"\n总存储: {total_size//1024//1024}MB")
    
    print(f"\n输出目录: {OUTPUT_DIR}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
