#!/usr/bin/env python3
"""
定式Trie树数据生成脚本
从 weiqi-joseki 数据库导出定式并生成分桶trie结构

用法:
    python3 scripts/generate_joseki_tree.py [--test]

输出到生产或测试目录:
    - trie-meta.json      元信息
    - trie-index.json.gz  索引（gzip压缩）
    - quiz-*.json.gz      做题模式数据（gzip压缩）
    - buckets/*.json.gz   分桶数据（gzip压缩）
"""

import sys
import json
import os
import gzip
import argparse
from collections import defaultdict
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, str(Path(__file__).parent))
from config import SITE_DIR, TEST_SITE_DIR, WEIQI_JOSEKI_DB_PATH

# 默认配置
MAX_BUCKET_SIZE = 2000  # 每桶最大定式数
MAX_DEPTH = 10          # 最大细分深度


def build_dynamic_buckets(joseki_list, max_bucket_size=MAX_BUCKET_SIZE, max_depth=MAX_DEPTH):
    """动态分桶：迭代方式细分大桶"""
    final_buckets = {}
    
    # 初始按前两着分桶
    pending = defaultdict(list)
    for j in joseki_list:
        moves = j['moves']
        if len(moves) >= 2:
            key = f"{moves[0]}-{moves[1]}"
        elif len(moves) == 1:
            key = moves[0]
        else:
            key = 'unknown'
        pending[key].append(j)
    
    # 迭代处理大桶
    while pending:
        bucket_key, items = pending.popitem()
        
        if len(items) <= max_bucket_size:
            final_buckets[bucket_key] = items
            continue
        
        depth = len(bucket_key.split('-'))
        if depth >= max_depth:
            print(f"警告: {bucket_key} 仍有 {len(items)} 条，达到最大深度")
            final_buckets[bucket_key] = items
            continue
        
        # 按下一着细分
        sub_buckets = defaultdict(list)
        for j in items:
            moves = j['moves']
            if len(moves) > depth:
                sub_key = f"{bucket_key}-{moves[depth]}"
            else:
                sub_key = f"{bucket_key}-end"
            sub_buckets[sub_key].append(j)
        
        for sub_key, sub_items in sub_buckets.items():
            pending[sub_key] = sub_items
    
    return final_buckets


def build_trie(joseki_list, prefix_depth=0):
    """从定式列表构建trie树
    
    prefix_depth: 分桶的前缀深度
    例如 pd-kb 的 prefix_depth=2，表示定式路径前2着已经固定
    trie 从第3着开始构建
    """
    root = {'coord': None, 'children': {}, 'freq': 0}
    
    for j in joseki_list:
        moves = j['moves']
        freq = j.get('frequency', 0)
        prob = j.get('probability', 0)
        node = root
        
        # 从 prefix_depth 开始构建 trie
        for i, coord in enumerate(moves[prefix_depth:], start=prefix_depth):
            if coord not in node['children']:
                color = 'black' if i % 2 == 0 else 'white'
                is_pass = coord == 'tt'
                node['children'][coord] = {
                    'coord': coord,
                    'color': color,
                    'isPass': is_pass,
                    'children': {},
                    'freq': 0,
                    'depth': i + 1  # 第几手
                }
            
            node['children'][coord]['freq'] += freq
            node = node['children'][coord]
        
        node['leaf'] = True
        node['moves'] = len(moves)
        node['name'] = j.get('id', '')
        node['total_freq'] = freq
        node['prob'] = prob
    
    return root


def serialize_trie_node(node):
    """序列化单个trie节点"""
    children = node.get('children', {})
    result = {
        'coord': node.get('coord'),
        'color': node.get('color'),
        'isPass': node.get('isPass', False),
        'freq': node.get('freq', 0),
        'children': sorted(children.keys()),
    }
    
    if node.get('leaf'):
        result['leaf'] = True
        result['moves'] = node.get('moves')
        result['name'] = node.get('name')
        result['total_freq'] = node.get('total_freq')
        result['prob'] = node.get('prob')
    
    return result


def flatten_trie(root):
    """将trie树扁平化为节点字典"""
    nodes = {}
    
    def walk(node, path):
        key = path if path else 'root'
        nodes[key] = serialize_trie_node(node)
        
        for coord, child in node.get('children', {}).items():
            child_path = f"{path}-{coord}" if path else coord
            walk(child, child_path)
    
    walk(root, '')
    return nodes


def export_bucket_files(buckets, output_dir):
    """导出分桶文件"""
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'buckets'), exist_ok=True)
    
    # 元信息
    meta = {
        'version': '1.0',
        'total': sum(len(v) for v in buckets.values()),
        'buckets': len(buckets),
        'maxBucketSize': MAX_BUCKET_SIZE,
        'difficultyStats': {'easy': 0, 'medium': 0, 'hard': 0},
        'bucketFiles': {}
    }
    
    # 索引
    index = {
        'firstMoves': defaultdict(list),
        'bucketIndex': {},
        'secondMoves': {}  # 新增：每个首着的二着列表
    }
    
    # 按难度收集叶子
    leaves_by_difficulty = {'easy': [], 'medium': [], 'hard': []}
    
    # 收集每个首着的二着信息
    first_move_second_moves = defaultdict(lambda: defaultdict(int))
    
    for bucket_key, items in sorted(buckets.items()):
        # 计算分桶深度
        prefix_depth = len(bucket_key.split('-'))
        
        trie = build_trie(items, prefix_depth)
        flat_nodes = flatten_trie(trie)
        
        # 提取叶子节点
        leaves = []
        for key, node in flat_nodes.items():
            if node.get('leaf'):
                moves_count = node.get('moves')
                difficulty = 'easy' if moves_count <= 10 else ('medium' if moves_count <= 20 else 'hard')
                meta['difficultyStats'][difficulty] += 1
                leaves.append({
                    'path': key,
                    'moves': moves_count,
                    'freq': node.get('total_freq'),
                    'difficulty': difficulty
                })
                leaves_by_difficulty[difficulty].append({
                    'bucket': bucket_key,
                    'path': key,
                    'moves': moves_count,
                    'freq': node.get('total_freq')
                })
        
        # 桶数据
        bucket_data = {
            'prefix': bucket_key,
            'prefixDepth': prefix_depth,
            'nodes': flat_nodes,
            'leaves': leaves,
            'stats': {
                'total': len(items),
                'leaves': len(leaves),
                'movesRange': [
                    min(len(j['moves']) for j in items),
                    max(len(j['moves']) for j in items)
                ]
            }
        }
        
        # 写入gzip压缩文件
        filename = f"{bucket_key}.json.gz"
        filepath = os.path.join(output_dir, 'buckets', filename)
        with gzip.open(filepath, 'wt', encoding='utf-8') as f:
            json.dump(bucket_data, f, ensure_ascii=False)
        
        # 更新索引
        parts = bucket_key.split('-')
        first_move = parts[0]
        
        index['firstMoves'][first_move].append(bucket_key)
        index['bucketIndex'][bucket_key] = {
            'file': filename,
            'count': len(leaves),
            'movesRange': bucket_data['stats']['movesRange'],
            'prefixDepth': prefix_depth
        }
        
        meta['bucketFiles'][bucket_key] = {
            'file': filename,
            'count': len(leaves),
            'movesRange': bucket_data['stats']['movesRange']
        }
        
        # 收集二着信息（仅深度2的分桶）
        if prefix_depth == 2 and len(parts) >= 2:
            second_move = parts[1]
            # 统计该二着出现的定式数和频率
            for j in items:
                first_move_second_moves[first_move][second_move] += 1
    
    # 合并二着信息到索引
    for first_move, second_dict in first_move_second_moves.items():
        index['secondMoves'][first_move] = [
            {'coord': sm, 'count': count}
            for sm, count in sorted(second_dict.items(), key=lambda x: x[1], reverse=True)
        ]
    
    # 导出做题模式文件
    for difficulty, leaves in leaves_by_difficulty.items():
        quiz_file = os.path.join(output_dir, f'quiz-{difficulty}.json.gz')
        with gzip.open(quiz_file, 'wt', encoding='utf-8') as f:
            json.dump({'leaves': leaves, 'count': len(leaves)}, f, ensure_ascii=False)
    
    # 导出索引
    index['firstMoves'] = dict(index['firstMoves'])
    index_file = os.path.join(output_dir, 'trie-index.json.gz')
    with gzip.open(index_file, 'wt', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False)
    
    # 导出元信息
    meta_file = os.path.join(output_dir, 'trie-meta.json')
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    
    return meta


def generate_joseki_tree(test_mode=False):
    """生成定式Trie树数据"""
    # 确定输出目录
    base_dir = TEST_SITE_DIR if test_mode else SITE_DIR
    output_dir = base_dir / "assets" / "data" / "joseki"
    
    print(f"加载数据库: {WEIQI_JOSEKI_DB_PATH}")
    
    if not WEIQI_JOSEKI_DB_PATH.exists():
        print(f"❌ 数据库不存在: {WEIQI_JOSEKI_DB_PATH}")
        return False
    
    with open(WEIQI_JOSEKI_DB_PATH) as f:
        db = json.load(f)
    
    joseki_list = db.get('joseki_list', [])
    print(f"总定式数: {len(joseki_list)}")
    
    if len(joseki_list) == 0:
        print("❌ 定式库为空")
        return False
    
    print("\n开始动态分桶...")
    buckets = build_dynamic_buckets(joseki_list)
    
    # 统计
    sizes = [len(v) for v in buckets.values()]
    print(f"分桶数: {len(buckets)}")
    print(f"最大桶: {max(sizes)}, 最小桶: {min(sizes)}, 平均: {sum(sizes)/len(sizes):.1f}")
    
    print(f"\n导出到: {output_dir}")
    meta = export_bucket_files(buckets, str(output_dir))
    
    print(f"\n导出完成:")
    print(f"  总定式: {meta['total']}")
    print(f"  分桶数: {meta['buckets']}")
    print(f"  难度分布: 初级={meta['difficultyStats']['easy']}, "
          f"中级={meta['difficultyStats']['medium']}, "
          f"高级={meta['difficultyStats']['hard']}")
    
    # 文件大小统计
    total_size = 0
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))
    print(f"  总存储: {total_size//1024}KB")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='生成定式Trie树数据')
    parser.add_argument('--test', action='store_true', help='测试模式')
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎯 定式Trie树数据生成")
    print("=" * 60)
    
    success = generate_joseki_tree(args.test)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
