#!/usr/bin/env python3
"""
猛禽预测 V9 - 7天完整报告生成与发送
基于 V9 算法: 季节镜像 + 风速自适应 + 历史丰度权重
"""
import os
import sys
import datetime
import subprocess
import json
import smtplib
import re
import math
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# SMTP 配置 - 163邮箱
SMTP_CONFIG = {
    "host": "smtp.163.com",
    "port": 465,
    "user": "jasonzhouyu@163.com",
    "password": "REDACTED_SEE_DOTENV",
    "use_tls": False,
    "from_name": "猛禽预测"
}

# ============== V9 配置 ==============

# 站点配置 (V9)
SITES = [
    {"name": "都统岩", "lat": 30.76, "lon": 103.42, "ro": 30, "base": 0.85, 
     "peak": {3: [0.6, 0.8, 1.0], 4: [1.2, 1.5, 1.3]}, "type": "Ridge"},
    {"name": "龙泉山", "lat": 30.556, "lon": 104.307, "ro": 20, "base": 0.85,
     "peak": {3: [0.7, 0.9, 1.1], 4: [1.3, 1.4, 1.2]}, "type": "Ridge"},
    {"name": "尧山电视台", "lat": 25.3, "lon": 110.38, "ro": 135, "base": 0.9,
     "peak": {3: [0.8, 1.0, 1.3], 4: [1.4, 1.6, 1.5]}, "type": "Karst"},
    {"name": "冠头岭", "lat": 21.45, "lon": 109.05, "ro": 90, "base": 0.9,
     "peak": {3: [0.8, 1.1, 1.4], 4: [1.6, 1.5, 1.2]}, "type": "Coastal"},
    {"name": "九龙山", "lat": 29.5, "lon": 121.5, "ro": 45, "base": 0.8,
     "peak": {3: [0.6, 0.8, 1.0], 4: [1.2, 1.4, 1.2]}, "type": "Ridge"},
    {"name": "渔洋山", "lat": 31.2, "lon": 120.4, "ro": 90, "base": 0.8,
     "peak": {3: [0.6, 0.8, 1.0], 4: [1.1, 1.3, 1.1]}, "type": "Coastal"},
    {"name": "南汇东滩", "lat": 30.9, "lon": 121.9, "ro": 0, "base": 0.75,
     "peak": {3: [0.5, 0.7, 0.9], 4: [1.0, 1.2, 1.0]}, "type": "Wetland"},
    {"name": "崇明东滩", "lat": 31.5, "lon": 121.9, "ro": 0, "base": 0.75,
     "peak": {3: [0.5, 0.7, 0.9], 4: [1.0, 1.2, 1.0]}, "type": "Wetland"},
]

# V9 参数
ABUNDANCE = {"都统岩": 1.2, "龙泉山": 1.45, "尧山电视台": 1.35, "冠头岭": 1.85,
             "九龙山": 1.15, "渔洋山": 1.05, "南汇东滩": 1.1, "崇明东滩": 1.0}
RESIL = {"都统岩": 1.25, "龙泉山": 1.25, "尧山电视台": 1.0}
GEO_BONUS = {"都统岩": 10, "龙泉山": 10, "尧山电视台": 0, "冠头岭": 15}
LOW_WIND = ["都统岩", "龙泉山"]

# ============== V9 核心函数 ==============

def get_season(date_obj):
    return "春" if date_obj.month in [3, 4, 5] else "秋"

def wind_lift_score(v, name):
    vm = 6 if name in LOW_WIND else 8
    if v < vm: return 15 * math.exp(-(vm - v) / 5)
    if 15 <= v <= 30: return 15
    if v > 45: return max(0, 15 - (v - 45) * 1.5)
    if v < 15: return 15 * (v - vm) / (15 - vm)
    return 15 * (1 - (v - 30) / 15)

def calculate_score(site, weather, date_obj):
    name = site["name"]
    season = get_season(date_obj)
    w = weather
    
    # 峰值权重
    m, d = date_obj.month, date_obj.day
    pw = site["peak"][m][2] if d > 20 else site["peak"][m][1] if d > 10 else site["peak"][m][0]
    
    # 基础分
    base = 65 * site["base"] * pw * RESIL.get(name, 1.0) * ABUNDANCE.get(name, 1.0)
    
    # 风力
    wl = wind_lift_score(w["w_spd"], name)
    
    # 海陆风
    sb = 15 if site["type"] == "Coastal" else 0
    
    # 南风
    sw = (1 - abs(w["w_dir"] - 180) / 45) * 10 if 135 <= w["w_dir"] <= 225 else 0
    
    # 地理溢价
    gb = GEO_BONUS.get(name, 0)
    
    # Mega-Raptor
    mg = 10 if season == "春" and name in ["龙泉山", "尧山电视台"] and m == 3 and d >= 20 else 0
    
    # 惩罚
    tp = 4.5 if w["temp"] < 15 and w["w_spd"] > 12 else 0
    cp = 10 if w["cloud"] > 70 and 135 <= w["w_dir"] <= 225 else (25 if w["cloud"] > 85 else 10 if w["cloud"] > 70 else 0)
    pp = min(30, 30 / (1 + math.exp(-6 * (w["precip"] - 0.5)))) if w["precip"] > 0 else 0
    
    score = base + wl + sb + sw + gb + mg - tp - cp - pp
    if w["precip"] > 1: score = 0
    
    return max(0, min(100, int(score)))

def get_rating(score):
    if score >= 88: return "⭐⭐⭐⭐ 推荐"
    elif score >= 75: return "⭐⭐⭐ 值得"
    elif score >= 60: return "⭐⭐ 视情"
    elif score >= 40: return "⭐ 放弃"
    return "❌ 放弃"

def get_weather(lat, lon, date):
    try:
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,precipitation,cloud_cover,wind_speed_10m,wind_direction_10m",
            "timezone": "Asia/Shanghai", "forecast_days": 7
        }
        resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15, verify=False)
        data = resp.json()
        
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        target = date.strftime("%Y-%m-%d")
        
        for i, t in enumerate(times):
            if f"{target}T12:00" in t:
                ws = hourly["wind_speed_10m"][i] / 1.852
                return {
                    "temp": hourly["temperature_2m"][i],
                    "precip": hourly["precipitation"][i],
                    "cloud": hourly["cloud_cover"][i],
                    "w_spd": ws,
                    "w_dir": hourly["wind_direction_10m"][i]
                }
    except:
        pass
    return None

# ============== 主程序 ==============

def main(output_format="dingtalk", send_email=True):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dingtalk", choices=["dingtalk", "console"])
    parser.add_argument("--no-email", action="store_true")
    args = parser.parse_args()
    
    today = datetime.date.today()
    season = get_season(today)
    
    print(f"\n{'='*60}")
    print(f"🦅 猛禽迁徙预测 V9 - {today}")
    print(f"{'='*60}\n")
    
    results = []
    
    for site in SITES:
        print(f"→ {site['name']}...")
        weather = get_weather(site["lat"], site["lon"], today)
        
        if weather:
            score = calculate_score(site, weather, today)
            rating = get_rating(score)
            print(f"   天气: {weather['temp']:.1f}°C, 风速{weather['w_spd']:.0f}kts, 风向{weather['w_dir']}°")
            print(f"   得分: {score}分 {rating}")
            results.append({
                "site": site["name"],
                "score": score,
                "rating": rating,
                "weather": weather
            })
    
    # 汇总表格
    print(f"\n{'='*60}")
    print("📊 今日各站点评分")
    print("="*60)
    print(f"{'站点':<12} {'评分':<8} {'推荐'}")
    print("-"*40)
    for r in results:
        print(f"{r['site']:<12} {r['score']:<8} {r['rating']}")
    
    print("\n✅ V9 预测完成")
    return results

if __name__ == "__main__":
    main()
