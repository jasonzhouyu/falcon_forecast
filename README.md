# Falcon Forecast（猛禽预报）

中国 8 个监测点的多因子猛禽迁徙评分系统。综合 Open-Meteo 气象数据、eBird 观察记录、地形动力和季节性物候，每日生成 0-100 分的迁徙适宜度评分。

## 工作原理

V9 模型基于以下因子计算每小时评分（0-100）：

| 因子 | 权重 | 说明 |
|------|------|------|
| 风力抬升 | 15 分 | 风速在 15-45 节最佳区间内，站点自适应阈值 |
| 山脊正交抬升 | 15 分 | 风向矢量垂直于山脊走向的分量 |
| 热力学 | 10 分 | 基于 850/925 hPa 层的抬升指数（LI） |
| 逆温惩罚 | -5/°C | 850-925 hPa 温差 |
| 冷锋加成 | +20 分 | 24 小时降温 >5°C 且气压上升 |
| 物候峰值 | x0.3-1.6 | 按站点和季节的月度/旬度矩阵 |
| 历史丰度 | x1.0-1.85 | 站点特异的猛禽密度权重 |
| eBird 乘数 | x0.8-1.2 | 近期观测的空间修正 |
| 幼鸟扩散 | +8 分 | 秋季沿海加分 |

**评级标准：**
- 88-100：不容错过的迁徙盛况
- 75-87：强烈推荐
- 60-74：值得前往
- 40-59：条件一般
- 0-39：条件不佳

## 监测站点

| 站点 | 类型 | 位置 | 坐标 |
|------|------|------|------|
| 都统岩 | 内陆山脊 | 四川崇州 | 30.76°N, 103.42°E |
| 龙泉山 | 内陆山脊 | 四川成都 | 30.56°N, 104.31°E |
| 尧山电视台 | 喀斯特山脊 | 广西桂林 | 25.30°N, 110.38°E |
| 冠头岭 | 海角瓶颈 | 广西北海 | 21.45°N, 109.05°E |
| 九龙山 | 沿海瓶颈 | 浙江平湖 | 29.50°N, 121.50°E |
| 渔洋山 | 湖滨 | 江苏苏州 | 31.20°N, 120.40°E |
| 南汇东滩 | 沿海走廊 | 上海 | 30.90°N, 121.90°E |
| 崇明东滩 | 河口湿地 | 上海 | 31.50°N, 121.90°E |

## 快速开始

### 1. 克隆仓库并安装依赖

```bash
git clone https://github.com/jasonzhouyu/falcon_forecast.git
cd falcon_forecast

pip install requests numpy openmeteo-requests requests-cache retry-requests python-dotenv matplotlib
```

### 2. 配置 API Key

创建 `.env` 文件：

```env
EBIRD_API_KEY=你的密钥
```

在 [ebird.org/api/keygen](https://ebird.org/api/keygen) 免费获取。系统可以在没有 Key 的情况下运行（eBird 乘数默认为 1.0），但接入真实观测数据后预测更准确。

### 3. 运行预测

```bash
# 单个站点，当天
python raptor_v9_runner.py

# 全部 8 个站点，生成完整 HTML 报告
python raptor_v9_full_report.py

# 批量运行所有站点（控制台输出）
python run_all_sites_v9.py
```

### 4. 每日自动化（可选）

```bash
# 设置 cron 定时任务（北京时间 6:00）
0 22 * * * cd /path/to/falcon_forecast && python3 send_raptor_v9_mail.py
```

邮件推送需要在 `send_raptor_v9_mail.py` 中配置 SMTP。

## 项目结构

```
raptor_v9_runner.py        核心评分引擎（V9 模型）
raptor_v9_full_report.py   带 matplotlib 图表的 HTML 报告生成器
run_all_sites_v9.py        全部 8 站点批量运行
send_raptor_v9_mail.py     邮件分发至订阅用户
run_raptor_daily.py        旧版每日工作流
daily_raptor_report.py     简化每日报告
report_formatter.py        报告格式化工具
raptor_species_expanded.py 物种参数（25 种猛禽）
google_form_sync.py        Google Forms 订阅者管理
daily_task.sh              Cron 入口脚本
cron-watchdog.sh           Cron 健康监控
```

## 数据来源

- **[Open-Meteo](https://open-meteo.com/)** — 免费气象 API，提供风速、温度、气压、云量、降水的地面数据及气压层（850/925 hPa）数据。
- **[eBird](https://ebird.org/)** — 各站点 50km 半径内的近期猛禽观察记录。需免费 API Key。

## 示例报告

完整日报（含逐小时评分、7 天趋势、各站点观测策略）见 [example_report.html](example_report.html)。

## 迁徙季节

- **春季**：3-5 月（峰值：4 月中旬）
- **秋季**：9-11 月（峰值：10 月中旬）

超出这些窗口期，无论天气如何，模型均返回低分。

## 许可证

MIT

## 参与贡献

欢迎提交 Issue 和 PR。如果你在中国的猛禽监测点未在列表中，请提交 Issue 并附上坐标和山脊走向——添加新站点非常简单。

## 延伸阅读

- [模型逻辑说明](模型逻辑说明.md)
- [参考文献](references.md)
