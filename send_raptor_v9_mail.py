#!/usr/bin/env python3
"""
猛禽预测 V9 完整版邮件发送
"""
import os
import sys
import datetime
import json
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
load_dotenv(os.path.join(SCRIPT_DIR, '.env'))

from raptor_v9_full_report import generate_v9_html

SMTP_CONFIG = {
    "host": os.getenv("SMTP_HOST", "smtp.163.com"),
    "port": int(os.getenv("SMTP_PORT", "465")),
    "user": os.getenv("SMTP_USER", ""),
    "password": os.getenv("SMTP_PASSWORD", ""),
    "from_name": "猛禽预测"
}

SUBSCRIBERS = [
    "547508119@qq.com",
    "jasonzhouyu@163.com",
    "378279298@qq.com",
    "liu.wh@foxmail.com",
    "3248322249@qq.com"
]

TEST_MODE = False


def send_email(to_email, subject, html_content):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{SMTP_CONFIG['from_name']} <{SMTP_CONFIG['user']}>"
        msg['To'] = to_email
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_CONFIG['host'], SMTP_CONFIG['port'], context=context) as server:
            server.login(SMTP_CONFIG['user'], SMTP_CONFIG['password'])
            server.sendmail(SMTP_CONFIG['user'], to_email, msg.as_string())
        print(f"   ✅ 已发送: {to_email}")
        return True
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False


def main():
    if not SMTP_CONFIG['user'] or not SMTP_CONFIG['password']:
        print("❌ SMTP_USER / SMTP_PASSWORD not configured in .env")
        sys.exit(1)

    target_date = datetime.datetime.now().date()
    date_str = target_date.strftime("%Y-%m-%d")

    print("📊 生成 V9 完整版 HTML...")
    html_file = generate_v9_html(target_date)

    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    subject = f"🦅 猛禽迁徙预测 V9 - {date_str}"

    if TEST_MODE:
        print(f"\n📧 测试模式: 仅发送给 {SMTP_CONFIG['user']}")
        send_email(SMTP_CONFIG['user'], subject, html_content)
    else:
        print(f"\n📧 发送给 {len(SUBSCRIBERS)} 位订阅者...")
        for email in SUBSCRIBERS:
            send_email(email, subject, html_content)

    print("\n✅ 完成")


if __name__ == "__main__":
    main()
