#!/usr/bin/env python3
"""
猛禽预测 - 7天完整报告生成与发送（支持多人订阅）
包含≥3星站点的详细观测描述
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

# SMTP 配置 - 163邮箱
SMTP_CONFIG = {
    "host": "smtp.163.com",
    "port": 465,
    "user": "jasonzhouyu@163.com",
    "password": "REDACTED_SEE_DOTENV",
    "use_tls": False,
    "from_name": "猛禽预测"
}

# 8个站点配置
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
    """从 .env 加载 SMTP 配置"""
    env_file = os.path.join(SCRIPT_DIR, ".env")
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key == "SMTP_HOST":
                        SMTP_CONFIG["host"] = value
                    elif key == "SMTP_PORT":
                        SMTP_CONFIG["port"] = int(value)
                    elif key == "SMTP_USER":
                        SMTP_CONFIG["user"] = value
                    elif key == "SMTP_PASSWORD":
                        SMTP_CONFIG["password"] = value

def load_subscribers():
    """加载订阅者列表"""
    subscribers_file = os.path.join(SCRIPT_DIR, "subscribers.json")
    if os.path.exists(subscribers_file):
        with open(subscribers_file, 'r') as f:
            return json.load(f)
    return []

def run_single_prediction(site_index: int, days_diff: int):
    """运行单个站点预测"""
    input_str = f"{site_index + 1}\n{days_diff}\n"
    
    try:
        result = subprocess.run(
            ["python3", RAPTOR_SCRIPT],
            input=input_str,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=SCRIPT_DIR,
            env={**os.environ, "PYTHONPATH": SCRIPT_DIR}
        )
        return result.stdout
    except Exception as e:
        return f"Error: {e}"

def extract_detailed_report(output: str, site_name: str) -> str:
    """提取详细报告，生成观测推荐描述"""
    lines = output.split('\n')
    
    score = 0
    in_section = None
    core_info = []
    weather_info = []
    window_info = []
    strategy_info = []
    
    for line in lines:
        # 核心综述
        if '迁徙适宜度总分' in line:
            match = re.search(r'(\d+)/100', line)
            if match:
                score = int(match.group(1))
        
        # 分段提取
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
            core_info.append(line.strip())
        elif in_section == 'weather' and line.strip():
            if line.strip().startswith(('1.', '2.', '3.', '4.')):
                weather_info.append(line.strip())
        elif in_section == 'window' and line.strip():
            if line.strip().startswith('*'):
                window_info.append(line.strip())
        elif in_section == 'strategy' and line.strip():
            if line.strip().startswith(('1.', '2.', '3.', '-', '•')):
                strategy_info.append(line.strip())
    
    # 只返回 ≥60 分的站点
    if score < 60:
        return None
    
    # 生成推荐描述
    stars = "⭐⭐⭐"
    if score >= 75:
        stars = "⭐⭐⭐⭐"
    if score >= 88:
        stars = "⭐⭐⭐⭐⭐"
    
    desc = f"""
## 🦅 {site_name} 观测推荐

**评分**: {score}分 {stars}"""

    # 黄金观测时间
    for line in core_info:
        if '黄金观测窗口' in line:
            match = re.search(r'(\d{2}:\d{2})-(\d{2}:\d{2})', line)
            if match:
                desc += f"\n\n**🕐 黄金观测时间**: {match.group(1)} - {match.group(2)}"
            break
    
    # 窗口特征
    for line in core_info:
        if '窗口特征' in line:
            features = line.split(':')[-1].strip()
            desc += f"\n\n**📋 窗口特征**: {features.replace(' | ', ' | ')}"
            break
    
    # 预测强度
    for line in core_info:
        if '预测强度' in line:
            strength = line.split(':')[-1].strip()
            desc += f"\n**📈 预测强度**: {strength}"
            break
    
    # 天气条件
    if weather_info:
        desc += "\n\n**🌤️ 天气分析**:"
        for w in weather_info[:4]:
            # 简化每行
            w = w.split(':')[0] + ':' + ':'.join(w.split(':')[1:]) if ':' in w else w
            desc += f"\n• {w}"
    
    # 观测策略
    if strategy_info:
        desc += "\n\n**🔭 观测策略**:"
        for s in strategy_info[:5]:
            # 简化策略
            s = s.lstrip('-.• ')
            desc += f"\n• {s}"

    return desc

def extract_scores_from_output(output: str) -> dict:
    """从输出中提取评分信息"""
    result = {"score": "N/A", "status": "无数据", "best_time": "N/A", "kettle": "N/A"}
    
    match = re.search(r'迁徙适宜度总分:\s*(\d+)/100', output)
    if match:
        score = int(match.group(1))
        result["score"] = str(score)
        
        if score >= 88:
            result["status"] = "⭐⭐⭐⭐⭐ 爆发"
        elif score >= 75:
            result["status"] = "⭐⭐⭐⭐ 推荐"
        elif score >= 60:
            result["status"] = "⭐⭐⭐ 值得"
        elif score >= 40:
            result["status"] = "⭐⭐ 视情"
        else:
            result["status"] = "⭐ 放弃"
    
    match = re.search(r'黄金观测窗口:\s*(\d{2}:\d{2})-(\d{2}:\d{2})', output)
    if match:
        result["best_time"] = f"{match.group(1)}-{match.group(2)}"
    
    match = re.search(r'鹰柱(\d+)%', output)
    if match:
        result["kettle"] = match.group(1) + "%"
    
    return result

def generate_7day_report():
    """生成7天完整报告"""
    today = datetime.date.today()
    all_data = {}
    recommendations = []  # 存储推荐观测点详情
    
    print("=" * 80)
    print(f"🦅 猛禽迁徙预测 7 天完整报告 - {today}")
    print("=" * 80)
    
    for site in SITES:
        print(f"\n正在预测: {site['name']}...")
        site_data = {}
        
        for day_offset in range(7):
            target_date = today + datetime.timedelta(days=day_offset)
            date_str = target_date.strftime("%m-%d")
            day_label = "今天" if day_offset == 0 else "明天" if day_offset == 1 else f"第{day_offset+1}天"
            
            output = run_single_prediction(site['index'], day_offset)
            scores = extract_scores_from_output(output)
            
            site_data[date_str] = {
                "label": day_label,
                "score": scores["score"],
                "status": scores["status"],
                "best_time": scores["best_time"],
                "kettle": scores["kettle"]
            }
            
            print(f"  {date_str} ({day_label}): {scores['score']}分 {scores['status']}")
            
            # 只在今天(day_offset=0)时提取推荐详情
            if day_offset == 0:
                score = int(scores["score"]) if scores["score"].isdigit() else 0
                if score >= 60:
                    detail = extract_detailed_report(output, site['name'])
                    if detail:
                        recommendations.append(detail)
        
        all_data[site['name']] = site_data
    
    return today, all_data, recommendations

def format_dingtalk_message(date_str: str, all_data: dict) -> str:
    """生成钉钉 Markdown 格式消息"""
    lines = [f"## 🦅 猛禽迁徙预测 7 天报告 ({date_str})", ""]
    lines.append("### 各站点每日评分")
    lines.append("")
    
    header = "| 站点 |"
    for i in range(7):
        d = datetime.date.today() + datetime.timedelta(days=i)
        label = "今天" if i == 0 else "明天" if i == 1 else f"{d.month}/{d.day}"
        header += f" {label} |"
    lines.append(header)
    
    separator = "| --- |" + " --- |" * 7
    lines.append(separator)
    
    for site_name, site_data in all_data.items():
        row = f"| **{site_name}** |"
        for day_offset in range(7):
            d = datetime.date.today() + datetime.timedelta(days=day_offset)
            date_key = d.strftime("%m-%d")
            if date_key in site_data:
                s = site_data[date_key]
                row += f" {s['score']}{s['status'][0]} |"
            else:
                row += " - |"
        lines.append(row)
    
    lines.append("")
    lines.append("### 📊 汇总")
    
    best_score = 0
    best_info = ""
    
    for site_name, site_data in all_data.items():
        for date_key, data in site_data.items():
            score = int(data['score']) if data['score'].isdigit() else 0
            if score > best_score:
                best_score = score
                best_info = f"{site_name} ({date_key})"
    
    if best_score > 0:
        lines.append(f"- **最佳观测**: {best_info}，{best_score}分")
    
    today_str = datetime.date.today().strftime("%m-%d")
    if today_str in all_data.get("冠头岭", {}):
        today_data = all_data["冠头岭"][today_str]
        lines.append(f"- **今日冠头岭**: {today_data['score']}分 {today_data['status']}")
    
    return "\n".join(lines)

def format_email_html(date_str: str, all_data: dict, recommendations: list) -> str:
    """生成 HTML 邮件格式"""
    html = f"""
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; }}
        h2 {{ color: #2E7D32; }}
        h3 {{ color: #558B2F; }}
        .recommendation {{ background: #f0f9ff; border-left: 4px solid #1890ff; padding: 15px; margin: 20px 0; }}
        .recommendation h3 {{ color: #1890ff; margin-top: 0; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: center; }}
        th {{ background-color: #4CAF50; color: white; }}
        .score-high {{ color: #d32f2f; font-weight: bold; }}
        .score-mid {{ color: #f57c00; }}
        .score-low {{ color: #757575; }}
        .best {{ background-color: #fff3cd; }}
        .legend {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h2>🦅 猛禽迁徙预测 7 天报告</h2>
    <p><strong>日期:</strong> {date_str}</p>
"""
    
    # 添加推荐观测点详情
    if recommendations:
        html += """
    <h2>🌟 今日推荐观测</h2>
"""
        for rec in recommendations:
            # 把 markdown 转为简单 HTML
            rec_html = rec.replace('## ', '<h3>').replace('\n\n', '</h3>')
            rec_html = rec_html.replace('**', '<strong>').replace('**', '</strong>')
            rec_html = rec_html.replace('\n- ', '<br>• ')
            rec_html = rec_html.replace('\n', '<br>')
            html += f'    <div class="recommendation">{rec_html}</div>'
    
    html += """
    <h2>📊 各站点 7 天评分</h2>
    <table>
        <tr><th>站点</th>
"""
    
    for i in range(7):
        d = datetime.date.today() + datetime.timedelta(days=i)
        label = "今天" if i == 0 else "明天" if i == 1 else f"{d.month}/{d.day}"
        html += f"<th>{label}</th>"
    html += "</tr>"
    
    for site_name, site_data in all_data.items():
        html += f"<tr><td><strong>{site_name}</strong></td>"
        for day_offset in range(7):
            d = datetime.date.today() + datetime.timedelta(days=day_offset)
            date_key = d.strftime("%m-%d")
            if date_key in site_data:
                s = site_data[date_key]
                score = s['score']
                score_int = int(score) if score.isdigit() else 0
                
                if score_int >= 60:
                    css_class = "score-high"
                elif score_int >= 40:
                    css_class = "score-mid"
                else:
                    css_class = "score-low"
                
                is_best = (site_name == "冠头岭" and day_offset == 0)
                best_attr = ' class="best"' if is_best else ''
                
                html += f'<td{best_attr} class="{css_class}">{score}{s["status"][0]}</td>'
            else:
                html += "<td>-</td>"
        html += "</tr>"
    
    html += """
    </table>
    
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
    """发送邮件到单个收件人"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'🦅 猛禽迁徙预测 7 天报告 - {date_str}'
        msg['From'] = SMTP_CONFIG["user"]  # 纯邮箱地址，避免 QQ 退信
        msg['To'] = to_email
        
        text_content = f"""
猛禽迁徙预测 7 天报告 - {date_str}

数据已生成，请查看 HTML 邮件获取完整表格。

数据来源: Open-Meteo 气象预报 + eBird 实时观测
"""
        
        html_part = MIMEText(html_content, 'html', 'utf-8')
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        if SMTP_CONFIG["port"] == 465:
            server = smtplib.SMTP_SSL(SMTP_CONFIG["host"], SMTP_CONFIG["port"])
        else:
            server = smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"])
            if SMTP_CONFIG.get("use_tls", True):
                server.starttls()
        
        server.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])
        server.sendmail(SMTP_CONFIG["user"], to_email, msg.as_string())
        server.quit()
        
        return True
        
    except Exception as e:
        print(f"❌ 发送到 {to_email} 失败: {e}")
        return False

def send_to_all_subscribers(date_str: str, html_content: str):
    """发送给所有订阅者"""
    subscribers = load_subscribers()
    
    if not subscribers:
        print("⚠️ 没有订阅者")
        return
    
    success_count = 0
    for email in subscribers:
        print(f"📧 发送到: {email}...")
        if send_email(email, date_str, html_content):
            success_count += 1
    
    print(f"\n✅ 发送完成: {success_count}/{len(subscribers)} 成功")

if __name__ == "__main__":
    load_smtp_config()
    
    output_format = "dingtalk"
    send_email_flag = True
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--output":
            output_format = sys.argv[2] if len(sys.argv) > 2 else "dingtalk"
        elif sys.argv[1] == "--no-email":
            send_email_flag = False
    
    today, all_data, recommendations = generate_7day_report()
    date_str = today.strftime("%Y-%m-%d")
    
    if output_format == "dingtalk":
        dingtalk_msg = format_dingtalk_message(date_str, all_data)
        print("\n---DINGTALK_START---\n")
        print(dingtalk_msg)
        print("\n---DINGTALK_END---\n")
    
    # 生成 HTML（包含推荐详情）
    email_html = format_email_html(date_str, all_data, recommendations)
    html_file = os.path.join(SCRIPT_DIR, f"raptor_report_{date_str}.html")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(email_html)
    print(f"✅ HTML 已保存: {html_file}")
    
    # 打印推荐详情预览
    if recommendations:
        print("\n" + "=" * 60)
        print("📋 今日推荐观测详情（将包含在邮件中）:")
        print("=" * 60)
        for rec in recommendations:
            print(rec)
            print("-" * 40)
    
    # 发送邮件
    if send_email_flag:
        print("\n📧 开始发送给订阅者...")
        send_to_all_subscribers(date_str, email_html)
    
    print("\n✅ 完成!")
