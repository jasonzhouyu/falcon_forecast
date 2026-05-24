#!/bin/bash
# cron 守护脚本 - 每分钟检查并重启
if ! pgrep -x cron > /dev/null 2>&1; then
    cron
    echo "$(date) - cron restarted" >> /root/.openclaw/workspace/猛禽预测/cron_watchdog.log
fi
