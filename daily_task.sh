#!/bin/bash
# 猛禽预测每日定时任务
cd /root/.openclaw/workspace/猛禽预测

# 生成并发送报告（发送给所有订阅者）
python3 send_raptor_v9_mail.py

echo "✅ 猛禽预测日报完成 $(date)"
