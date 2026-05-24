#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
猛禽预测报告固定格式输出
"""

def format_raptor_report(sites_data):
    """固定格式输出猛禽预测报告"""
    
    lines = []
    lines.append("=" * 60)
    lines.append("🦅 猛禽迁徙学术研判报告")
    lines.append("=" * 60)
    lines.append(f"报告时间：2026年3月21日")
    lines.append("")
    
    # 筛选>20分的站点
    filtered = [s for s in sites_data if s.get('score', 0) > 20]
    
    for i, site in enumerate(filtered, 1):
        lines.append(f"#### {i}. {site['name']} | {site['score']}分")
        lines.append("")
        lines.append(f"**【核心综述**")
        lines.append(f"- 迁徙适宜度：{site['score']}/100")
        lines.append(f"- 黄金窗口：{site.get('window', '')}")
        lines.append(f"- 预测强度：{site.get('strength', '')}")
        
        lines.append("")
        lines.append(f"**【动态评分表】")
        lines.append("| 时刻 | 评分 | 鹰柱% | 风速 | 风向 | LI | ΔT |")
        lines.append("|---|---|---|---|---|---|---|---|")
        
        for hour in site.get('hourly', []):
            lines.append(f"| {hour['hour']} | {hour['score']} | {hour.get('kettle', '0%') | {hour.get('wind', '') | {hour.get('windDir', '') | {hour.get('li', ''} | {hour.get('dt', ''} |")
        
        lines.append("")
        lines.append(f"【天气专项分析】")
        for w in site.get('weather', []):
            lines.append(f"- {w}")
        
        lines.append("")
        lines.append(f"【观测策略】
- 黄金窗口：{site.get('window', '')
- 搜索高度：500-800m 迎风坡")
        lines.append("")
    
    # 8站点7天汇总
    lines.append("### 8站点7天汇总")
    lines.append("| 站点 | 今天 | 明天 | +2天 | +3天 | +4天 | +5天 | +6天 |")
    lines.append("|---|---|---|---|---|---|---|---|--- |")
    
    for site in sites_data:
        row = f"| {site['name']} |"
        for d in site.get('days', []):
            row += f" {d} |"
        lines.append(row)
    
    lines.append("")
    lines.append("### 参考文献")
    lines.append("- Newton, I. (2008). 《鸟类迁徙生态学")
    lines.append("- Kerlinger, P. (1989). 《迁徙猛禽的飞行策略")
    lines.append("- Alerstam, T. (2003). 《鸟类迁徙生物学》
    lines.append("- Gill, F. (1995). 《鸟类学")
    lines.append("")
    lines.append("祝您观鸟愉快！")
    
    return "\n".join(lines)

# 测试
if __name__ == "__main__":
    test_data = [
        {
            "name": "冠头岭",
            "score": 66,
            "window": "14:00-16:00",
            "strength": "稳定",
            "hourly": [
                {"hour": "14:00", "score": 66, "kettle": "0%", "wind": "18.6kts", "windDir": "197°", "li": "1.2", "dt": "-2.0",
            "hourly": [],
            "weather": ["逆温层风险: ΔT=-2.0℃", "地形升力效率: 0%", "风速适宜度: 18.6kts"]
        }
    ]
    
    print(format_raptor_report(test_data))
