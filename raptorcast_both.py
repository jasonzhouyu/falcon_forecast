#!/usr/bin/env python3
"""
猛禽预测报告 - 双版本（Open-Meteo + 和风）
"""
import os
import sys
import subprocess
import smtplib
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SCRIPT_DIR = "/root/.openclaw/workspace/猛禽预测"

def run_script(script_name):
    """运行Python脚本并返回输出"""
    result = subprocess.run(
        ["python3", script_name],
        capture_output=True,
        text=True,
        timeout=300,
        cwd=SCRIPT_DIR
    )
    return result.stdout + result.stderr

def send_email(to_email, subject, content):
    """发送邮件"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = 'jasonzhouyu@163.com'
        msg['To'] = to_email
        
        text_part = MIMEText(content, 'plain', 'utf-8')
        msg.attach(text_part)
        
        server = smtplib.SMTP_SSL('smtp.163.com', 465)
        server.login('jasonzhouyu@163.com', 'REDACTED_SEE_DOTENV')
        server.sendmail('jasonzhouyu@163.com', to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"发送失败: {e}")
        return False

def main():
    print("=" * 60)
    print("🦅 猛禽预测报告 - 双版本")
    print("=" * 60)
    
    # 运行两个版本
    print("\n📡 运行 Open-Meteo 版本...")
    openmeteo_result = run_script("raptorcast_v4_guilin.py")
    
    print("📡 运行 和风天气 版本...")
    hefeng_result = run_script("raptorcast_hefeng.py")
    
    # 合并报告
    report = f"""
======================================================================
🦅 猛禽迁徙预测报告（双版本交叉参考）
报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}
======================================================================

======================================================================
📡 版本一: Open-Meteo 气象预报
======================================================================
{openmeteo_result[:5000]}

======================================================================
📡 版本二: 和风天气 24小时预报
======================================================================
{hefeng_result[:5000]}

======================================================================
📊 版本对比说明
======================================================================
- Open-Meteo版: 使用专业气象参数（LI、CAPE、850hPa风场等），评分更精确
- 和风版: 使用和风API，便于交叉验证
======================================================================
"""
    
    # 发送到所有订阅者
    subscribers_file = os.path.join(SCRIPT_DIR, "subscribers.json")
    if os.path.exists(subscribers_file):
        with open(subscribers_file, 'r') as f:
            subscribers = json.load(f)
    else:
        subscribers = ["jasonzhouyu@163.com"]
    
    print(f"\n📧 发送到 {len(subscribers)} 位订阅者...")
    
    for email in subscribers:
        subject = f"🦅 猛禽预测报告 - {datetime.now().strftime('%Y-%m-%d')}"
        if send_email(email, subject, report):
            print(f"  ✅ {email}")
    
    print("\n✅ 完成!")

if __name__ == "__main__":
    main()
