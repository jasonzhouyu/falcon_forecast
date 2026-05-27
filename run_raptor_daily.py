#!/usr/bin/env python3
"""
猛禽预测 - 每日完整报告生成
发送到邮件订阅用户
"""
import subprocess
import smtplib
import json
import os
import re
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(SCRIPT_DIR, '.env'))

SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASSWORD", "")

SITES = [(2,'龙泉山'), (3,'尧山电视台'), (4,'冠头岭'), (5,'九龙山'), (6,'渔洋山'), (7,'南汇东滩'), (8,'崇明东滩')]


def get_report():
    """生成完整报告"""
    report = "="*70 + "\n"
    report += "🦅 猛禽迁徙预测报告\n"
    report += "="*70 + "\n\n"

    for idx, name in SITES:
        result = subprocess.run(
            ['python3', 'raptorcast_v4_guilin.py'],
            input=f'{idx}\n0\n',
            capture_output=True,
            text=True,
            timeout=120,
            cwd=SCRIPT_DIR
        )
        output = result.stdout + result.stderr

        capture = False
        for line in output.split('\n'):
            if '猛禽迁徙学术研判报告' in line and '2026' in line:
                capture = True
            if capture:
                if '【观测策略】' in line:
                    capture = False
                if '==' in line and len(line) > 30:
                    continue
                if '█' in line or '└' in line:
                    continue
                report += line + "\n"
        report += "-"*50 + "\n\n"

    report += "="*70 + "\n"
    report += "📊 8站点未来7天评分汇总\n"
    report += "="*70 + "\n"
    report += "| 站点          | 今天 | 明天 | +2天 | +3天 | +4天 | +5天 | +6天 |\n"
    report += "|" + "-"*14 + "|" + "-"*7 + "|" + "-"*7 + "|" + "-"*7 + "|" + "-"*7 + "|" + "-"*7 + "|" + "-"*7 + "|" + "-"*7 + "|\n"

    for idx, name in SITES:
        row = f"| {name:<12} |"
        for day in range(7):
            result = subprocess.run(
                ['python3', 'raptorcast_v4_guilin.py'],
                input=f'{idx}\n{day}\n',
                capture_output=True,
                text=True,
                timeout=120,
                cwd=SCRIPT_DIR
            )
            match = re.search(r'迁徙适宜度总分.*?(\d+)/100', result.stdout + result.stderr)
            score = match.group(1) if match else "-"
            row += f" {score:>4} |"
        report += row + "\n"

    return report


def send_email(report):
    """发送邮件到订阅用户"""
    subscribers_file = os.path.join(SCRIPT_DIR, "subscribers.json")
    if os.path.exists(subscribers_file):
        with open(subscribers_file, 'r') as f:
            subscribers = json.load(f)
    else:
        subscribers = [SMTP_USER]

    msg = MIMEMultipart('alternative')
    msg['Subject'] = '🦅 猛禽预测报告'
    msg['From'] = SMTP_USER
    msg.attach(MIMEText(report, 'plain', 'utf-8'))

    server = smtplib.SMTP_SSL('smtp.163.com', 465)
    server.login(SMTP_USER, SMTP_PASS)

    for email in subscribers:
        msg['To'] = email
        server.sendmail(SMTP_USER, email, msg.as_string())
        print(f"✅ 发送到: {email}")

    server.quit()


if __name__ == "__main__":
    if not SMTP_USER or not SMTP_PASS:
        print("❌ SMTP_USER / SMTP_PASSWORD not configured in .env")
        sys.exit(1)

    print("生成报告...")
    report = get_report()

    print("发送邮件...")
    send_email(report)

    print("✅ 完成!")
