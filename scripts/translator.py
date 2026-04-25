#!/usr/bin/env python3
"""
SGF棋手姓名翻译器 - 外译中
解析SGF文件内容，翻译PB/PW字段中的棋手姓名
"""
import json
import re
from pathlib import Path

# 映射表文件路径
MAPPING_FILE = Path(__file__).parent / "name_mapping.json"

# 全局映射表缓存
_name_map = {}

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


if __name__ == "__main__":
    # 测试
    test_sgf = """(;GM[1]FF[4]PB[Shin Jinseo]BR[9d]PW[Park Junghwan]WR[9d]
;B[pd]C[Test])"""
    
    print("原始SGF:")
    print(test_sgf)
    print("\n翻译后:")
    print(translate_sgf(test_sgf))
