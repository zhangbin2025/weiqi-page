#!/usr/bin/env python3
"""
不常见定式筛选脚本
基于出现次数中位数判断不常见定式
"""
import os
import sys
import json
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import WEIQI_JOSEKI_SCRIPT, WEIQI_JOSEKI_DIR, WEIQI_JOSEKI_DB_PATH


class RareJosekiDetector:
    """不常见定式检测器 - 可扩展策略"""
    
    def __init__(self, config=None):
        self.config = config or {
            "strategy": "median_threshold",  # 当前使用的中位数策略
            "katago_weight": 0.6,
            "db_weight": 0.4,
        }
    
    def get_all_katago_frequencies(self):
        """获取所有KataGo定式的出现次数"""
        # 从weiqi-joseki数据库读取
        if not WEIQI_JOSEKI_DB_PATH.exists():
            return []
        
        cmd = [
            "python3", str(WEIQI_JOSEKI_SCRIPT),
            "list", "--limit", "10000"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WEIQI_JOSEKI_DIR))
        
        if result.returncode != 0:
            return []
        
        try:
            joseki_list = json.loads(result.stdout)
            # 提取出现次数字段
            counts = []
            for j in joseki_list:
                # TODO: weiqi-joseki 需要添加 occurrence_count 字段
                # 暂时使用其他字段作为替代
                counts.append(100)  # 占位
            return counts
        except:
            return []
    
    def calculate_median(self, values):
        """计算中位数"""
        if not values:
            return 100  # 默认值
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        if n % 2 == 0:
            return (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
        else:
            return sorted_values[n//2]
    
    def is_rare(self, joseki, katago_stats, db_stats=None):
        """
        判断是否为不常见定式
        
        joseki: 定式对象
        katago_stats: {median: 中位数, all_counts: [...]}
        db_stats: 可选，weiqi-db棋谱中的定式统计
        """
        katago_count = joseki.get("katago_count", 0)
        katago_median = katago_stats.get("median", 100)
        
        # 策略1: KataGo出现次数低于中位数
        if katago_count < katago_median:
            return True, f"KataGo出现次数({katago_count})低于中位数({katago_median})"
        
        # 策略2: 预留 - 综合weiqi-db棋谱频率
        # if db_stats:
        #     db_count = joseki.get("db_count", 0)
        #     db_median = db_stats.get("median", 10)
        #     if db_count > 0 and katago_count < 10:
        #         return True, f"实战出现但KataGo罕见"
        
        return False, None
    
    def find_rare_joseki(self, joseki_list):
        """从不常见定式列表中筛选"""
        # 获取KataGo统计
        katago_counts = [j.get("katago_count", 0) for j in joseki_list]
        katago_median = self.calculate_median(katago_counts)
        
        katago_stats = {
            "median": katago_median,
            "all_counts": katago_counts
        }
        
        rare_list = []
        for joseki in joseki_list:
            is_rare, reason = self.is_rare(joseki, katago_stats)
            if is_rare:
                rare_list.append({
                    **joseki,
                    "rare_reason": reason,
                    "strategy": self.config["strategy"]
                })
        
        return rare_list


def main():
    """测试函数"""
    print("=" * 60)
    print("🎯 不常见定式筛选器")
    print("=" * 60)
    
    detector = RareJosekiDetector()
    
    # 示例数据
    test_joseki = [
        {"id": "joseki_001", "katago_count": 5000},
        {"id": "joseki_002", "katago_count": 100},
        {"id": "joseki_003", "katago_count": 50},
        {"id": "joseki_004", "katago_count": 5},
    ]
    
    rare_list = detector.find_rare_joseki(test_joseki)
    
    print(f"\n📊 测试数据:")
    for j in test_joseki:
        print(f"  {j['id']}: count={j['katago_count']}")
    
    print(f"\n🔍 不常见定式 ({len(rare_list)}个):")
    for j in rare_list:
        print(f"  {j['id']}: {j['rare_reason']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
