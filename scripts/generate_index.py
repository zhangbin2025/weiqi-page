#!/usr/bin/env python3
"""
首页生成脚本
"""
import sys
import json
from pathlib import Path
from jinja2 import Template

sys.path.insert(0, str(Path(__file__).parent))
from config import SITE_DIR, TEST_SITE_DIR, TEMPLATES_DIR, ensure_dirs, WEIQI_PAGE_DIR


def normalize_event_name(event):
    """赛事名归一化，用于去重"""
    if not event:
        return ""
    import re
    # 移除年份、届数、日期等变化部分
    # 如 "第28届LG杯世界棋王赛" -> "LG杯"
    # "2024围甲联赛" -> "围甲"
    event = re.sub(r'第\d+届', '', event)
    event = re.sub(r'\d{4}', '', event)
    event = re.sub(r'\d+月\d+日', '', event)
    event = re.sub(r'[\(\)（）]', '', event)
    # 提取核心名称（取最长部分）
    parts = [p.strip() for p in event.split() if len(p.strip()) >= 2]
    if parts:
        # 返回最长的部分作为核心赛事名
        return max(parts, key=len)
    return event.strip()


def is_similar_event(e1, e2):
    """判断两个赛事名是否相似"""
    if not e1 or not e2:
        return False
    e1, e2 = e1.lower(), e2.lower()
    # 完全相同
    if e1 == e2:
        return True
    # 包含关系
    if e1 in e2 or e2 in e1:
        return True
    # 编辑距离 <= 2（简单实现）
    if len(e1) > 3 and len(e2) > 3:
        # 如果前3个字符相同，认为是相似
        if e1[:3] == e2[:3]:
            return True
    return False


def count_unique_events(games):
    """计算唯一赛事数"""
    normalized = [normalize_event_name(g.get('event', '')) for g in games]
    normalized = [e for e in normalized if e]  # 过滤空值
    
    unique = []
    for e in normalized:
        if not any(is_similar_event(e, u) for u in unique):
            unique.append(e)
    return len(unique)


def calc_match_rate(joseki):
    """计算定式匹配度"""
    move_count = joseki.get('move_count', 0)
    matched = joseki.get('matched_prefix_len', 0)
    return matched / move_count if move_count > 0 else 0


def generate_index(test_mode=False):
    """生成首页"""
    base_dir = ensure_dirs(test_mode)
    data_dir = base_dir / "_data"
    
    # 找到最新日期
    latest_date = None
    for f in data_dir.glob("games_*.json"):
        date_str = f.stem.replace("games_", "")
        if not latest_date or date_str > latest_date:
            latest_date = date_str
    
    # 如果没有棋谱数据，尝试从选点题或定式找日期
    if not latest_date:
        for f in data_dir.glob("quiz_*.json"):
            date_str = f.stem.replace("quiz_", "")
            if not latest_date or date_str > latest_date:
                latest_date = date_str
    
    if not latest_date:
        for f in data_dir.glob("joseki_*.json"):
            date_str = f.stem.replace("joseki_", "")
            if not latest_date or date_str > latest_date:
                latest_date = date_str
    
    # 统计数据初始化
    games_count = 0
    games_events = 0
    games_sources = 0
    games_data = []
    
    quiz_count = 0
    quiz_phase = {"layout": 0, "middle": 0, "endgame": 0}
    quiz_level = {"职业": 0, "高段": 0, "普通": 0}  # 三级划分
    
    joseki_count = 0
    joseki_hot = 0
    joseki_hit = 0
    joseki_complex = 0
    joseki_list = []
    
    if latest_date:
        # 统计棋谱
        games_file = data_dir / f"games_{latest_date}.json"
        if games_file.exists():
            try:
                games_data = json.loads(games_file.read_text())
                games_count = len(games_data)
                games_events = count_unique_events(games_data)
                # 统计来源数量
                sources = set()
                for game in games_data:
                    source = game.get("source", "其他")
                    sources.add(source)
                games_sources = len(sources)
            except:
                pass
        
        # 统计选点题（按题目数）
        quiz_file = data_dir / f"quiz_{latest_date}.json"
        if quiz_file.exists():
            try:
                quizzes = json.loads(quiz_file.read_text())
                for q in quizzes:
                    count = q.get("count", 0)
                    quiz_count += count
                    stats = q.get("stats", {})
                    phase = stats.get("phase", {})
                    game_level = stats.get("game_level", "普通")
                    quiz_phase["layout"] += phase.get("layout", 0)
                    quiz_phase["middle"] += phase.get("middle", 0)
                    quiz_phase["endgame"] += phase.get("endgame", 0)
                    # 按等级统计题目数（三级）
                    if game_level in quiz_level:
                        quiz_level[game_level] += count
                    else:
                        quiz_level["普通"] += count
            except:
                pass
        
        # 统计定式
        joseki_file = data_dir / f"joseki_{latest_date}.json"
        if joseki_file.exists():
            try:
                joseki_list = json.loads(joseki_file.read_text())
                joseki_count = len(joseki_list)
                
                # 计算热门排名：匹配>=8手的定式，按库出现次数降序，次数相同按匹配度降序
                candidates8 = [j for j in joseki_list if j.get("matched_prefix_len", 0) >= 8]
                sorted_by_freq = sorted(candidates8, key=lambda j: (
                    j.get("frequency", 0),
                    calc_match_rate(j)
                ), reverse=True)
                top3_hot_keys = set()
                for j in sorted_by_freq[:3]:
                    key = j.get("joseki_id") or ",".join(j.get("moves", []))
                    top3_hot_keys.add(key)
                
                # 分类统计
                for j in joseki_list:
                    prefix_len = j.get("matched_prefix_len", 0)
                    rate = calc_match_rate(j)
                    key = j.get("joseki_id") or ",".join(j.get("moves", []))
                    
                    # 热门: 前缀>=8 + 库出现次数前3名
                    if prefix_len >= 8 and key in top3_hot_keys:
                        joseki_hot += 1
                    
                    # 命中: 前缀>=8 + 匹配度100%
                    if prefix_len >= 8 and rate >= 1:
                        joseki_hit += 1
                    
                    # 复杂: 前缀>=12
                    if prefix_len >= 12:
                        joseki_complex += 1
            except:
                pass
    
    # 读取模板
    template_path = TEMPLATES_DIR / "index.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    
    # 渲染
    from config import get_base_path
    base_path = get_base_path(test_mode)
    html = template.render(
        games_count=games_count,
        games_events=games_events,
        games_sources=games_sources,
        quiz_count=quiz_count,
        quiz_phase=quiz_phase,
        quiz_level=quiz_level,
        joseki_count=joseki_count,
        joseki_hot=joseki_hot,
        joseki_hit=joseki_hit,
        joseki_complex=joseki_complex,
        last_update=latest_date or "暂无数据",
        base_path=base_path
    )
    
    # 保存
    output_path = base_dir / "index.html"
    output_path.write_text(html, encoding="utf-8")
    print(f"✅ 生成首页: {output_path}")
    
    # 复制记谱工具到站点
    import shutil
    from config import WEIQI_RECORDER_PATH, WEIQI_SGF_TEMPLATE, SKILLS_DIR
    
    # 添加 quiz 模板路径
    WEIQI_QUIZ_TEMPLATE = SKILLS_DIR / "weiqi-move/templates/quiz.html"
    
    tools_dst = base_dir / "tools"
    recorder_dst = tools_dst / "recorder.html"
    
    if WEIQI_RECORDER_PATH.exists():
        tools_dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WEIQI_RECORDER_PATH, recorder_dst)
        print(f"✅ 复制记谱工具: {recorder_dst}")
    else:
        print(f"⚠️ 警告: 未找到记谱工具: {WEIQI_RECORDER_PATH}")
    
    # 复制打谱模板到站点（支持 JSON 数据加载）
    replay_dst = base_dir / "replay.html"
    if WEIQI_SGF_TEMPLATE.exists():
        shutil.copy2(WEIQI_SGF_TEMPLATE, replay_dst)
        print(f"✅ 复制打谱模板: {replay_dst}")
    else:
        print(f"⚠️ 警告: 未找到打谱模板: {WEIQI_SGF_TEMPLATE}")
    
    # 复制做题模板到站点（支持 JSON 数据加载）
    quiz_dst = base_dir / "quiz.html"
    if WEIQI_QUIZ_TEMPLATE.exists():
        shutil.copy2(WEIQI_QUIZ_TEMPLATE, quiz_dst)
        print(f"✅ 复制做题模板: {quiz_dst}")
    else:
        print(f"⚠️ 警告: 未找到做题模板: {WEIQI_QUIZ_TEMPLATE}")
    
    # 获取 Git commit hash (短格式) - 提前获取，供后续模板替换使用
    import subprocess
    try:
        git_hash = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=WEIQI_PAGE_DIR,
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
    except:
        git_hash = 'dev'
    
    # 复制棋手查询工具到站点
    player_src = TEMPLATES_DIR / "tools" / "player.html"
    player_dst = tools_dst / "player.html"
    
    if player_src.exists():
        tools_dst.mkdir(parents=True, exist_ok=True)
        pq_content = player_src.read_text(encoding='utf-8')
        pq_content = pq_content.replace('{{GIT_HASH}}', git_hash)
        pq_content = pq_content.replace('{{ base_path }}', base_path)
        player_dst.write_text(pq_content, encoding='utf-8')
        print(f"✅ 复制棋手查询工具: {player_dst} (git:{git_hash})")
    else:
        print(f"⚠️ 警告: 未找到棋手查询工具: {player_src}")
    
    # 复制云比赛查询工具目录到站点
    yunbisai_src_dir = TEMPLATES_DIR / "tools" / "yunbisai"
    yunbisai_dst_dir = tools_dst / "yunbisai"
    
    if yunbisai_src_dir.exists():
        yunbisai_dst_dir.mkdir(parents=True, exist_ok=True)
        # 复制目录下所有文件
        for src_file in yunbisai_src_dir.glob("*.html"):
            dst_file = yunbisai_dst_dir / src_file.name
            content = src_file.read_text(encoding='utf-8')
            content = content.replace('{{GIT_HASH}}', git_hash)
            content = content.replace('{{ base_path }}', base_path)
            dst_file.write_text(content, encoding='utf-8')
            print(f"✅ 复制云比赛页面: {dst_file.name} (git:{git_hash})")
        print(f"✅ 复制云比赛查询工具目录完成")
    else:
        print(f"⚠️ 警告: 未找到云比赛查询工具目录: {yunbisai_src_dir}")
    
    # 复制对手分析工具目录到站点
    opponent_src_dir = TEMPLATES_DIR / "tools" / "opponent"
    opponent_dst_dir = tools_dst / "opponent"
    
    if opponent_src_dir.exists():
        opponent_dst_dir.mkdir(parents=True, exist_ok=True)
        # 复制目录下所有文件
        for src_file in opponent_src_dir.glob("*.html"):
            dst_file = opponent_dst_dir / src_file.name
            content = src_file.read_text(encoding='utf-8')
            content = content.replace('{{GIT_HASH}}', git_hash)
            content = content.replace('{{ base_path }}', base_path)
            dst_file.write_text(content, encoding='utf-8')
            print(f"✅ 复制对手分析页面: {dst_file.name} (git:{git_hash})")
        print(f"✅ 复制对手分析工具目录完成")
    else:
        print(f"⚠️ 警告: 未找到对手分析工具目录: {opponent_src_dir}")
    
    # 复制棋谱抓取工具到站点
    fetcher_src = TEMPLATES_DIR / "tools" / "fetcher.html"
    fetcher_dst = tools_dst / "fetcher.html"
    
    if fetcher_src.exists():
        tools_dst.mkdir(parents=True, exist_ok=True)
        content = fetcher_src.read_text(encoding='utf-8')
        content = content.replace('{{GIT_HASH}}', git_hash)
        content = content.replace('{{ base_path }}', base_path)
        fetcher_dst.write_text(content, encoding='utf-8')
        print(f"✅ 复制棋谱抓取工具: {fetcher_dst} (git:{git_hash})")
    else:
        print(f"⚠️ 警告: 未找到棋谱抓取工具: {fetcher_src}")
    
    # 复制定式工具目录到站点
    joseki_src_dir = TEMPLATES_DIR / "tools" / "joseki"
    joseki_dst_dir = tools_dst / "joseki"
    
    if joseki_src_dir.exists():
        joseki_dst_dir.mkdir(parents=True, exist_ok=True)
        for src_file in joseki_src_dir.glob("*.html"):
            dst_file = joseki_dst_dir / src_file.name
            content = src_file.read_text(encoding='utf-8')
            content = content.replace('{{GIT_HASH}}', git_hash)
            content = content.replace('{{ base_path }}', base_path)
            dst_file.write_text(content, encoding='utf-8')
            print(f"✅ 复制定式工具页面: {dst_file.name} (git:{git_hash})")
        print(f"✅ 复制定式工具目录完成")
    else:
        print(f"⚠️ 警告: 未找到定式工具目录: {joseki_src_dir}")
    
    # 复制对弈工具目录到站点
    from config import WEIQI_PLAY_DIR
    
    play_src_dir = WEIQI_PLAY_DIR
    play_dst_dir = tools_dst / "play"
    
    if play_src_dir.exists():
        play_dst_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制 index.html 并重命名为 game.html
        src_index = play_src_dir / "index.html"
        dst_game = play_dst_dir / "game.html"
        if src_index.exists():
            content = src_index.read_text(encoding='utf-8')
            # 替换绝对路径为相对路径
            content = content.replace('src="/index.js"', 'src="./index.js"')
            dst_game.write_text(content, encoding='utf-8')
            print(f"✅ 复制对弈页面: {dst_game.name}")
        
        # 复制 index.js 并替换路径
        src_js = play_src_dir / "index.js"
        dst_js = play_dst_dir / "index.js"
        if src_js.exists():
            content = src_js.read_text(encoding='utf-8')
            # 替换所有绝对路径为相对路径
            # Worker 路径：/assets/worker-xxx.js -> ./assets/worker-xxx.js
            content = content.replace('"/assets/', '"./assets/')
            # 模型路径：/models/ -> ../models/（Worker 在 assets/ 子目录，需要上一级）
            content = content.replace('"/models/', '"../models/')
            content = content.replace("'/models/", "'../models/")
            # 同时替换 ./models/ 为 ../models/（因为 Worker 在 assets/ 子目录）
            content = content.replace('"./models/', '"../models/')
            content = content.replace("'./models/", "'../models/")
            # 结束对局后跳转到 index.html（去掉“是否开始新对局”的对话框）
            content = content.replace(
                'setTimeout(()=>{confirm("是否开始新对局？")&&C()},500)',
                "window.location.href='index.html'"
            )
            dst_js.write_text(content, encoding='utf-8')
            print(f"✅ 复制对弈 JS: {dst_js.name}")
        
        # 复制 assets 目录（包含 worker.js）
        assets_src = play_src_dir / "assets"
        assets_dst = play_dst_dir / "assets"
        if assets_src.exists():
            if assets_dst.exists():
                shutil.rmtree(assets_dst)
            shutil.copytree(assets_src, assets_dst)
            print(f"✅ 复制对弈资源: {assets_dst}")
        
        # 复制 models 目录
        models_src = play_src_dir / "models"
        models_dst = play_dst_dir / "models"
        if models_src.exists():
            if models_dst.exists():
                shutil.rmtree(models_dst)
            shutil.copytree(models_src, models_dst)
            print(f"✅ 复制模型文件: {models_dst}")
        
        # 复制 tfjs 目录
        tfjs_src = play_src_dir / "tfjs"
        tfjs_dst = play_dst_dir / "tfjs"
        if tfjs_src.exists():
            if tfjs_dst.exists():
                shutil.rmtree(tfjs_dst)
            shutil.copytree(tfjs_src, tfjs_dst)
            print(f"✅ 复制 TensorFlow.js 文件: {tfjs_dst}")
        
        print(f"✅ 复制对弈工具目录完成")
    else:
        print(f"⚠️ 警告: 未找到对弈工具目录: {play_src_dir}")
    
    # 复制对弈工具模板文件到站点
    play_templates_src = TEMPLATES_DIR / "tools" / "play"
    play_templates_dst = tools_dst / "play"
    
    if play_templates_src.exists():
        for src_file in play_templates_src.glob("*.html"):
            # 跳过 game.html，因为已经从 dist 复制了
            if src_file.name == "game.html":
                continue
            dst_file = play_templates_dst / src_file.name
            content = src_file.read_text(encoding='utf-8')
            content = content.replace('{{ base_path }}', base_path)
            dst_file.write_text(content, encoding='utf-8')
            print(f"✅ 复制对弈工具页面: {dst_file.name}")
    else:
        print(f"⚠️ 警告: 未找到对弈工具模板目录: {play_templates_src}")
    
    # 复制认证页面到站点
    auth_src = TEMPLATES_DIR / "auth.html"
    auth_dst = base_dir / "auth.html"
    
    if auth_src.exists():
        auth_content = auth_src.read_text(encoding='utf-8')
        auth_content = auth_content.replace('{{GIT_HASH}}', git_hash)
        auth_content = auth_content.replace('{{base_path}}', base_path)
        auth_dst.write_text(auth_content, encoding='utf-8')
        print(f"✅ 复制认证页面: {auth_dst}")
    else:
        print(f"⚠️ 警告: 未找到认证页面: {auth_src}")
    
    # 复制认证管理页面到站点
    admin_src = TEMPLATES_DIR / "auth" / "admin.html"
    admin_dst = base_dir / "auth" / "admin.html"
    
    if admin_src.exists():
        admin_content = admin_src.read_text(encoding='utf-8')
        admin_content = admin_content.replace('{{GIT_HASH}}', git_hash)
        admin_content = admin_content.replace('{{base_path}}', base_path)
        admin_dst.parent.mkdir(parents=True, exist_ok=True)
        admin_dst.write_text(admin_content, encoding='utf-8')
        print(f"✅ 复制认证管理页面: {admin_dst}")
    else:
        print(f"⚠️ 警告: 未找到认证管理页面: {admin_src}")
    
    # 复制认证工具 JS 到站点 (assets/js/)
    assets_js_src = WEIQI_PAGE_DIR / "assets" / "js" / "auth.js"
    assets_js_dst = base_dir / "assets" / "js" / "auth.js"
    
    if assets_js_src.exists():
        assets_js_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(assets_js_src, assets_js_dst)
        print(f"✅ 复制认证工具 JS: {assets_js_dst}")
    else:
        print(f"⚠️ 警告: 未找到认证工具 JS: {assets_js_src}")
    
    # 复制缩略图绘制 JS 到站点 (assets/js/)
    thumbnail_js_src = WEIQI_PAGE_DIR / "assets" / "js" / "board-thumbnail.js"
    thumbnail_js_dst = base_dir / "assets" / "js" / "board-thumbnail.js"
    
    if thumbnail_js_src.exists():
        thumbnail_js_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(thumbnail_js_src, thumbnail_js_dst)
        print(f"✅ 复制缩略图 JS: {thumbnail_js_dst}")
    else:
        print(f"⚠️ 警告: 未找到缩略图 JS: {thumbnail_js_src}")
    
    # 复制定式棋盘 JS 到站点 (assets/js/)
    joseki_js_src = WEIQI_PAGE_DIR / "assets" / "js" / "joseki-board.js"
    joseki_js_dst = base_dir / "assets" / "js" / "joseki-board.js"
    
    if joseki_js_src.exists():
        joseki_js_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(joseki_js_src, joseki_js_dst)
        print(f"✅ 复制定式棋盘 JS: {joseki_js_dst}")
    else:
        print(f"⚠️ 警告: 未找到定式棋盘 JS: {joseki_js_src}")
    
    # 复制定式样式 CSS 到站点 (assets/css/)
    joseki_css_src = WEIQI_PAGE_DIR / "assets" / "css" / "joseki.css"
    joseki_css_dst = base_dir / "assets" / "css" / "joseki.css"
    
    if joseki_css_src.exists():
        joseki_css_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(joseki_css_src, joseki_css_dst)
        print(f"✅ 复制定式样式 CSS: {joseki_css_dst}")
    else:
        print(f"⚠️ 警告: 未找到定式样式 CSS: {joseki_css_src}")
    
    # 生成定式Trie树数据
    from generate_joseki_tree import generate_joseki_tree
    generate_joseki_tree(test_mode)
    
    # 复制公众号二维码图片到站点 (assets/images/)
    public_img_src = WEIQI_PAGE_DIR / "assets" / "images" / "public.jpg"
    public_img_dst = base_dir / "assets" / "images" / "public.jpg"
    
    if public_img_src.exists():
        public_img_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(public_img_src, public_img_dst)
        print(f"✅ 复制公众号二维码: {public_img_dst}")
    else:
        print(f"⚠️ 警告: 未找到公众号二维码: {public_img_src}")
    
    # 复制 favicon 目录到站点 (assets/favicon/)
    favicon_src_dir = WEIQI_PAGE_DIR / "assets" / "favicon"
    favicon_dst_dir = base_dir / "assets" / "favicon"
    
    if favicon_src_dir.exists():
        favicon_dst_dir.mkdir(parents=True, exist_ok=True)
        for favicon_file in favicon_src_dir.glob("*"):
            if favicon_file.is_file():
                shutil.copy2(favicon_file, favicon_dst_dir / favicon_file.name)
        print(f"✅ 复制 favicon 目录: {favicon_dst_dir}")
    else:
        print(f"⚠️ 警告: 未找到 favicon 目录: {favicon_src_dir}")
    
    # 生成根目录跳转页
    from config import WORKSPACE_DIR, SITE_ROOT
    redirect_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0;url=./weiqi-page/">
    <title>围棋智能助手</title>
</head>
<body>
    <p>正在跳转至 <a href="./weiqi-page/">围棋智能助手</a>...</p>
</body>
</html>"""
    if test_mode:
        # 测试模式：在 test_site/ 根目录生成跳转页
        test_root = WORKSPACE_DIR / "test_site"
        test_root.mkdir(parents=True, exist_ok=True)
        root_index = test_root / "index.html"
    else:
        # 生产模式：在 GitHub Pages 根目录生成跳转页
        SITE_ROOT.mkdir(parents=True, exist_ok=True)
        root_index = SITE_ROOT / "index.html"
    root_index.write_text(redirect_html, encoding="utf-8")
    print(f"✅ 生成根目录跳转页: {root_index}")
    
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎯 首页生成")
    print("=" * 60)
    
    generate_index(args.test)
    return 0


if __name__ == "__main__":
    sys.exit(main())
