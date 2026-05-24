#!/usr/bin/env python3
"""
猛禽预测 - 完整报告生成
包含：整体综述 + 当日小时明细 + 7天趋势
"""
import os
import sys
import datetime
import subprocess
import json
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAPTOR_SCRIPT = os.path.join(SCRIPT_DIR, "raptorcast_v4_guilin.py")

# SMTP 配置
SMTP_CONFIG = {
    "host": "smtp.163.com",
    "port": 465,
    "user": "jasonzhouyu@163.com",
    "password": "REDACTED_SEE_DOTENV",
    "from_name": "猛禽预测"
}

# 8个站点
SITES = [
    {"name": "都统岩", "index": 0},
    {"name": "龙泉山", "index": 1},
    {"name": "尧山电视台", "index": 2},
    {"name": "冠头岭", "index": 3},
    {"name": "九龙山", "index": 4},
    {"name": "渔洋山", "index": 5},
    {"name": "南汇东滩", "index": 6},
    {"name": "崇明东滩", "index": 7},
]

def load_smtp_config():
    env_file = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key == "SMTP_PASSWORD":
                        SMTP_CONFIG["password"] = value.strip()

def load_subscribers():
    subscribers_file = os.path.join(SCRIPT_DIR, "subscribers.json")
    if os.path.exists(subscribers_file):
        with open(subscribers_file, 'r') as f:
            return json.load(f)
    return []

def run_prediction(site_index: int, days_diff: int):
    input_str = f"{site_index + 1}\n{days_diff}\n"
    try:
        result = subprocess.run(
            ["python3", RAPTOR_SCRIPT],
            input=input_str,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=SCRIPT_DIR
        )
        return result.stdout
    except:
        return ""

def extract_hourly_detail(output: str) -> dict:
    """提取每小时评分明细 - 返回所有小时评分"""
    lines = output.split('\n')
    hourly = {}
    in_table = False
    
    for line in lines:
        if '动态评分表' in line:
            in_table = True
            continue
        if in_table and '===' in line:
            break
        if in_table and ':00' in line and '|' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 2:
                hour = parts[0].strip()[:5]  # 04:00
                try:
                    score = int(parts[1].strip())
                    hourly[hour] = score
                except:
                    pass
    return hourly

def extract_summary(output: str) -> dict:
    """提取整体综述"""
    lines = output.split('\n')
    summary = {}
    
    for line in lines:
        if '迁徙适宜度总分' in line:
            match = re.search(r'(\d+)/100', line)
            if match:
                summary['score'] = int(match.group(1))
        if '黄金观测窗口' in line:
            match = re.search(r'(\d{2}:\d{2})-(\d{2}:\d{2})', line)
            if match:
                summary['best_time'] = f"{match.group(1)}-{match.group(2)}"
        if '预测强度' in line:
            if '爆发' in line:
                summary['strength'] = '爆发(Massive)'
            elif '集中' in line:
                summary['strength'] = '集中(Heavy)'
            elif '稳定' in line:
                summary['strength'] = '稳定(Moderate)'
            else:
                summary['strength'] = '离散(Low)'
    return summary

def extract_recommendation(output: str, site_name: str) -> str:
    """提取推荐详情"""
    lines = output.split('\n')
    score = 0
    in_section = None
    core = []
    weather = []
    window = []
    strategy = []
    
    for line in lines:
        if '迁徙适宜度总分' in line:
            match = re.search(r'(\d+)/100', line)
            if match:
                score = int(match.group(1))
        
        if '【核心综述】' in line:
            in_section = 'core'
        elif '【动态评分表' in line:
            in_section = None
        elif '【天气专项分析】' in line:
            in_section = 'weather'
        elif '【黄金观测窗口分析】' in line:
            in_section = 'window'
        elif '【专业观测策略】' in line:
            in_section = 'strategy'
        elif '【' in line and '】' in line:
            in_section = None
        
        if in_section == 'core' and line.strip():
            core.append(line.strip())
        elif in_section == 'weather' and line.strip().startswith(('1.', '2.', '3.', '4.')):
            weather.append(line.strip())
        elif in_section == 'window' and line.strip().startswith('*'):
            window.append(line.strip())
        elif in_section == 'strategy' and line.strip().startswith(('1.', '2.', '-', '•')):
            strategy.append(line.strip())
    
    if score < 60:
        return None
    
    # 生成推荐描述
    stars = "⭐⭐⭐" if score >= 60 else ""
    stars = "⭐⭐⭐⭐" if score >= 75 else stars
    stars = "⭐⭐⭐⭐⭐" if score >= 88 else stars
    
    desc = f"""
## 🦅 {site_name} 观测推荐

**评分**: {score}分 {stars}"""
    
    for line in core:
        if '黄金观测窗口' in line:
            match = re.search(r'(\d{2}:\d{2})-(\d{2}:\d{2})', line)
            if match:
                desc += f"\n\n**🕐 黄金时间**: {match.group(1)}-{match.group(2)}"
        if '窗口特征' in line:
            desc += f"\n**📋 特征**: {line.split(':')[-1].strip()}"
        if '预测强度' in line:
            desc += f"\n**📈 强度**: {line.split(':')[-1].strip()}"
    
    if weather[:2]:
        desc += "\n\n**🌤️ 天气分析**:"
        for w in weather[:2]:
            desc += f"\n• {w}"
    
    if strategy[:3]:
        desc += "\n\n**🔭 观测策略**:"
        for s in strategy[:3]:
            s = s.lstrip('-.•123 ')
            desc += f"\n• {s}"
    
    return desc

def generate_full_report():
    """生成完整报告"""
    today = datetime.date.today()
    date_str = today.strftime("%Y-%m-%d")
    
    print("=" * 60)
    print(f"🦅 猛禽迁徙预测报告 - {date_str}")
    print("=" * 60)
    
    # 第一部分：各站点今日整体综述
    print("\n📊 收集各站点数据...")
    site_summaries = {}
    hourly_details = {}
    recommendations = []
    
    for site in SITES:
        output = run_prediction(site['index'], 0)
        summary = extract_summary(output)
        site_summaries[site['name']] = summary
        
        hourly = extract_hourly_detail(output)
        hourly_details[site['name']] = hourly
        
        rec = extract_recommendation(output, site['name'])
        if rec:
            recommendations.append(rec)
    
    # 第二部分：7天趋势
    print("📈 生成7天趋势数据...")
    trends = {}
    for site in SITES:
        site_trend = []
        for day in range(7):
            output = run_prediction(site['index'], day)
            summary = extract_summary(output)
            score = summary.get('score', 0)
            day_label = "今天" if day == 0 else "明天" if day == 1 else f"+{day}天"
            site_trend.append(f"{day_label}:{score}")
        trends[site['name']] = site_trend
    
    return date_str, site_summaries, hourly_details, trends, recommendations

def format_email_html(date_str, site_summaries, hourly_details, trends, recommendations):
    """生成完整HTML邮件"""
    
    # 找出最佳站点
    best_site = max(site_summaries.items(), key=lambda x: x[1].get('score', 0))
    
    html = f"""
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; max-width: 800px; }}
        h2 {{ color: #2E7D32; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
        h3 {{ color: #558B2F; }}
        .section {{ margin: 25px 0; }}
        .recommendation {{ background: #f0f9ff; border-left: 4px solid #1890ff; padding: 15px; margin: 15px 0; }}
        table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: center; font-size: 13px; }}
        th {{ background-color: #4CAF50; color: white; }}
        .score-high {{ color: #d32f2f; font-weight: bold; }}
        .score-mid {{ color: #f57c00; }}
        .score-low {{ color: #757575; }}
        .best-row {{ background-color: #fff3cd; }}
        .trend {{ font-size: 12px; color: #666; }}
        .legend {{ background: #f5f5f5; padding: 15px; border-radius: 5px; font-size: 13px; }}
    </style>
</head>
<body>
    <h2>🦅 猛禽迁徙预测报告 {date_str}</h2>
    
    <!-- 第一部分：整体综述 -->
    <div class="section">
        <h3>📊 第一部分：整体综述</h3>
        <p><strong>今日最佳观测点</strong>: {best_site[0]} ({best_site[1].get('score', 0)}分)</p>
        
        <table>
            <tr><th>监测点</th><th>评分</th><th>推荐度</th><th>黄金时间</th><th>预测强度</th></tr>
"""
    
    for name, summary in site_summaries.items():
        score = summary.get('score', 0)
        best_time = summary.get('best_time', '-')
        strength = summary.get('strength', '-')
        
        if score >= 60:
            css = 'score-high'
            level = '⭐⭐⭐ 值得'
        elif score >= 40:
            css = 'score-mid'
            level = '⭐⭐ 视情'
        else:
            css = 'score-low'
            level = '⭐ 放弃'
        
        is_best = (name == best_site[0])
        row_class = 'best-row' if is_best else ''
        
        html += f"""            <tr class="{row_class}">
                <td><strong>{name}</strong></td>
                <td class="{css}">{score}</td>
                <td>{level}</td>
                <td>{best_time}</td>
                <td>{strength}</td>
            </tr>
"""
    
    html += """        </table>
    </div>
    
    <!-- 第二部分：当日到小时明细 -->
    <div class="section">
        <h3>⏰ 第二部分：当日到小时明细 (04:00-20:00)</h3>
        
        <table>
            <tr>
                <th>监测点</th>
                <th>04:00</th><th>05:00</th><th>06:00</th><th>07:00</th>
                <th>08:00</th><th>09:00</th><th>10:00</th><th>11:00</th>
                <th>12:00</th><th>13:00</th><th>14:00</th><th>15:00</th>
                <th>16:00</th><th>17:00</th><th>18:00</th><th>19:00</th><th>20:00</th>
            </tr>
"""
    
    # 解析每小时数据
    for name, hourly in hourly_details.items():
        html += f"<tr><td><strong>{name}</strong></td>"
        
        # hourly 是一个 dict: {'04:00': 66, '05:00': 49, ...}
        # 输出 04:00-20:00 每小时
        for hour in range(4, 21):
            h = f"{hour:02d}:00"
            score = hourly.get(h, 0)
            if score >= 60:
                css = 'score-high'
            elif score >= 40:
                css = 'score-mid'
            else:
                css = 'score-low'
            html += f'<td class="{css}">{score if score > 0 else "-"}</td>'
        
        html += "</tr>"
    
    html += """        </table>
    </div>
    
    <!-- 第三部分：未来7天趋势 -->
    <div class="section">
        <h3>📈 第三部分：未来7天趋势</h3>
        <table>
            <tr><th>监测点</th>
"""
    
    # 表头
    for day in range(7):
        label = "今天" if day == 0 else "明天" if day == 1 else f"+{day}天"
        html += f"<th>{label}</th>"
    html += "</tr>"
    
    # 数据行
    for name, trend in trends.items():
        html += f"<tr><td><strong>{name}</strong></td>"
        for t in trend:
            day_label, score_str = t.split(':')
            try:
                score = int(score_str)
                if score >= 60:
                    css = 'score-high'
                elif score >= 40:
                    css = 'score-mid'
                else:
                    css = 'score-low'
                html += f'<td class="{css}">{score}</td>'
            except:
                html += '<td>-</td>'
        html += "</tr>"
    
    html += """        </table>
    </div>
"""
    
    # 推荐观测详情
    if recommendations:
        html += """
    <div class="section">
        <h3>🌟 今日推荐观测详情</h3>
"""
        for rec in recommendations:
            # 简化 markdown 转 HTML
            rec_html = rec.replace('## ', '<h4>').replace('\n\n', '</h4>')
            rec_html = rec_html.replace('**', '<strong>').replace('**', '</strong>')
            rec_html = rec_html.replace('\n- ', '<br>• ')
            rec_html = rec_html.replace('\n', '<br>')
            html += f'    <div class="recommendation">{rec_html}</div>'
        
        html += "    </div>"
    
    html += """
    <div class="legend">
    <h3>📊 评分说明</h3>
    <ul>
        <li>⭐⭐⭐⭐⭐ 爆发 (≥88分) - 不可错过的迁徙高峰</li>
        <li>⭐⭐⭐⭐ 推荐 (≥75分) - 动力条件优秀</li>
        <li>⭐⭐⭐ 值得 (≥60分) - 适合常规观测</li>
        <li>⭐⭐ 视情 (≥40分) - 效率可能较低</li>
        <li>⭐ 放弃 (<40分) - 建议不前往</li>
    </ul>
    </div>
    
    <p><em>数据来源: Open-Meteo 气象预报 + eBird 实时观测</em></p>
</body>
</html>
"""
    return html

def send_email(to_email: str, date_str: str, html_content: str) -> bool:
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🦅 猛禽迁徙预测报告 - {date_str}'
        msg['From'] = SMTP_CONFIG["user"]
        msg['To'] = to_email
        
        text_content = f"""
猛禽迁徙预测报告 - {date_str}

包含三部分：
1. 整体综述
2. 当日到小时明细  
3. 未来7天趋势

请查看 HTML 邮件获取完整内容。
"""
        
        html_part = MIMEText(html_content, 'html', 'utf-8')
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        server = smtplib.SMTP_SSL(SMTP_CONFIG["host"], SMTP_CONFIG["port"])
        server.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])
        server.sendmail(SMTP_CONFIG["user"], to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ 发送到 {to_email} 失败: {e}")
        return False

if __name__ == "__main__":
    load_smtp_config()
    
    # 生成报告
    date_str, site_summaries, hourly_details, trends, recommendations = generate_full_report()
    
    # 生成 HTML
    html_content = format_email_html(date_str, site_summaries, hourly_details, trends, recommendations)
    
    # 保存
    html_file = os.path.join(SCRIPT_DIR, f"raptor_full_report_{date_str}.html")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✅ HTML 已保存: {html_file}")
    
    # 检查是否只发送给指定用户
    single_recipient = None
    if len(sys.argv) > 1 and sys.argv[1] == "--to":
        single_recipient = sys.argv[2]
    
    if single_recipient:
        print(f"\n📧 发送给指定用户: {single_recipient}")
        if send_email(single_recipient, date_str, html_content):
            print("✅ 发送成功!")
    else:
        # 发送给所有订阅者
        subscribers = load_subscribers()
        print(f"\n📧 发送给 {len(subscribers)} 位订阅者...")
        for email in subscribers:
            if send_email(email, date_str, html_content):
                print(f"  ✅ {email}")
    
    print("\n✅ 完成!")
