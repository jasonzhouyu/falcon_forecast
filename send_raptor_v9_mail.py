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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# 导入生成脚本的函数
from raptor_v9_full_report import generate_v9_html

# SMTP 配置
SMTP_CONFIG = {
    "host": "smtp.163.com",
    "port": 465,
    "user": "jasonzhouyu@163.com",
    "password": "REDACTED_SEE_DOTENV",
    "from_name": "猛禽预测"
}

# 订阅者列表
SUBSCRIBERS = [
    "547508119@qq.com",
    "jasonzhouyu@163.com",
    "378279298@qq.com",
    "liu.wh@foxmail.com",
    "3248322249@qq.com"
]

# 仅发送给用户（测试模式）
TEST_MODE = False  # 设为 False 则发送给所有订阅者


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
    target_date = datetime.datetime.now().date()
    date_str = target_date.strftime("%Y-%m-%d")
    
    # 生成 HTML
    print("📊 生成 V9 完整版 HTML...")
    html_file = generate_v9_html(target_date)
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    subject = f"🦅 猛禽迁徙预测 V9 - {date_str}"
    
    if TEST_MODE:
        # 只发给自己测试
        print(f"\n📧 测试模式: 仅发送给 jasonzhouyu@163.com")
        send_email("jasonzhouyu@163.com", subject, html_content)
    else:
        # 发送给所有订阅者
        print(f"\n📧 发送给 {len(SUBSCRIBERS)} 位订阅者...")
        for email in SUBSCRIBERS:
            send_email(email, subject, html_content)
    
    print("\n✅ 完成")


if __name__ == "__main__":
    main()
