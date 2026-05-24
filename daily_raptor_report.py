#!/usr/bin/env python3
"""
猛禽预测每日运行脚本
自动运行 8 个站点的预测并发送报告到钉钉
"""
import os
import sys
import subprocess
import datetime
import json

# 添加脚本所在目录到 Python 路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RAPTOR_SCRIPT = os.path.join(SCRIPT_DIR, "猛禽预测", "raptorcast_v4_guilin.py")

# 站点列表（对应原脚本中的 HOTSPOTS）
SITES = [
    "都统岩", "龙泉山", "尧山电视台", "冠头岭", 
    "九龙山", "渔洋山", "南汇东滩", "崇明东滩"
]

def run_prediction():
    """运行预测并获取结果"""
    today = datetime.date.today()
    
    # 构建发送给 OpenClaw 的消息
    messages = []
    
    # 简单版本：只运行脚本，让它输出到终端
    # 实际使用时，我们直接从 OpenClaw 调用这个功能
    
    print(f"📅 今天是 {today}")
    print(f"🦅 准备运行 8 个站点的猛禽迁徙预测...")
    
    return True

def format_dingtalk_message(reports: list) -> dict:
    """格式化钉钉消息卡片"""
    # 简化报告格式
    summary = []
    for site, score, status in reports:
        summary.append(f"• **{site}**: {score}分 {status}")
    
    msg = {
        "msgtype": "markdown",
        "markdown": {
            "title": "🦅 猛禽迁徙预测日报",
            "text": f"## 🦅 猛禽迁徙预测日报\n\n**日期**: {datetime.date.today()}\n\n" + "\n".join(summary)
        }
    }
    return msg

if __name__ == "__main__":
    run_prediction()
