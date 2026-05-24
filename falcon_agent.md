# 猛禽预测 Agent (falcon_agent)

## 项目信息
- **项目目录**: 猛禽预测
- **缩写**: falcon
- **技术栈**: Python + eBird API + 和风天气
- **目标**: 猛禽迁徙观测预测日报

## 当前状态
- **最后更新**: 2026-04-08
- **状态**: 需迁移到 OpenClaw cron

## 待办
- [x] 创建 Agent 配置文件 falcon_agent.md
- [x] 迁移定时任务到 OpenClaw cron
- [ ] 配置邮件订阅

## 核心文件
- `send_raptor_v9_mail.py` - 邮件发送主程序
- `raptor_v9_full_report.py` - 报告生成
- `daily_task.sh` - 定时任务脚本
- `subscribers.json` - 订阅者列表

## 定时任务
- Cron ID: `e290d5ef-bff3-413c-8ea9-3266ec327d02`
- 调度: 每天 6:00 (Asia/Shanghai)
- 状态: ✅ 已迁移