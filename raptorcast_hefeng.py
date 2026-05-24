#!/usr/bin/env python3
"""
猛禽预测 - 和风天气版
简化版，使用和风24小时预报API
"""
import os
import sys
import requests
from datetime import datetime, timedelta

# 配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SCRIPT_DIR, ".env")

# 和风API配置
QWEATHER_CONFIG = {
    "host": "jf4up53552.re.qweatherapi.com",
    "key": "c5a8be4e8a08409bb5bb9ae7b6e8ae01"
}

# 8个站点
SITES = [
    {"name": "都统岩", "lat": 23.5, "lon": 108.4, "city": "101300501"},  # 百色
    {"name": "龙泉山", "lat": 30.3, "lon": 120.1, "city": "101210101"},  # 杭州
    {"name": "尧山电视台", "lat": 25.3, "lon": 110.5, "city": "101300501"},  # 桂林
    {"name": "冠头岭", "lat": 21.9, "lon": 108.6, "city": "101300101"},  # 南宁
    {"name": "九龙山", "lat": 30.5, "lon": 121.1, "city": "101210101"},  # 杭州
    {"name": "渔洋山", "lat": 31.1, "lon": 120.4, "city": "101210401"},  # 苏州
    {"name": "南汇东滩", "lat": 31.0, "lon": 121.9, "city": "101020600"},  # 浦东
    {"name": "崇明东滩", "lat": 31.5, "lon": 121.9, "city": "101020600"},  # 浦东
]

def get_weather_24h(city_id):
    """获取24小时预报"""
    url = f"https://{QWEATHER_CONFIG['host']}/v7/weather/24h"
    params = {"location": city_id, "key": QWEATHER_CONFIG["key"]}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data.get("code") == "200":
            return data.get("hourly", [])
    except Exception as e:
        print(f"获取天气失败: {e}")
    return []

def calculate_raptor_score(hourly_data):
    """计算猛禽迁徙评分（简化版）"""
    # 和风数据：temp, windScale, windDir, precip, cloud, humidity, pressure
    results = []
    
    for h in hourly_data:
        hour = int(h.get("fxTime", "0").split("T")[1].split(":")[0])
        
        try:
            temp = int(h.get("temp", 15))
            wind_scale = int(h.get("windScale", "3").split("-")[0])
            precip = float(h.get("precip", 0))
            cloud = int(h.get("cloud", 50))
            humidity = int(h.get("humidity", 60))
        except:
            continue
        
        score = 60  # 基础分
        
        # 温度评分 (5-25度最佳)
        if 5 <= temp <= 25:
            score += 15
        elif 0 <= temp < 5 or 25 < temp <= 30:
            score += 5
        else:
            score -= 10
        
        # 风速评分 (3-5级最佳)
        if wind_scale <= 3:
            score += 15
        elif wind_scale <= 5:
            score += 5
        elif wind_scale >= 7:
            score -= 15
        
        # 降水评分
        if precip == 0:
            score += 10
        elif precip < 5:
            score += 0
        else:
            score -= 20
        
        # 云量评分 (20-60%最佳)
        if 20 <= cloud <= 60:
            score += 5
        
        # 湿度评分
        if 40 <= humidity <= 70:
            score += 5
        
        # 时段加分 (下午最佳)
        if 14 <= hour <= 17:
            score += 10
        
        score = max(0, min(100, score))
        
        results.append({
            "hour": hour,
            "temp": temp,
            "windScale": wind_scale,
            "windDir": h.get("windDir", ""),
            "text": h.get("text", ""),
            "cloud": cloud,
            "score": score
        })
    
    return results

def get_score_level(score):
    if score >= 88:
        return "⭐⭐⭐⭐⭐ 爆发", "极佳"
    elif score >= 75:
        return "⭐⭐⭐⭐ 推荐", "优秀"
    elif score >= 60:
        return "⭐⭐⭐ 值得", "良好"
    elif score >= 40:
        return "⭐⭐ 视情", "一般"
    else:
        return "⭐ 放弃", "较差"

def generate_report():
    print("=" * 70)
    print("🦅 猛禽迁徙预测报告（和风天气版）")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    
    all_results = []
    
    for site in SITES:
        print(f"\n📍 {site['name']}")
        print("-" * 50)
        
        hourly_data = get_weather_24h(site["city"])
        
        if not hourly_data:
            print("  ❌ 无法获取天气数据")
            continue
        
        results = calculate_raptor_score(hourly_data)
        
        # 找出最佳时段
        results.sort(key=lambda x: x["score"], reverse=True)
        best = results[0]
        
        level, desc = get_score_level(best["score"])
        
        print(f"  🏆 今日最佳: {best['hour']:02d}:00")
        print(f"     评分: {best['score']}分 {level}")
        print(f"     温度: {best['temp']}°C | 风力: {best['windScale']}级 | {best['text']}")
        
        all_results.append({
            "name": site["name"],
            "best_score": best["score"],
            "best_hour": best["hour"],
            "level": level,
            "results": results
        })
    
    # 汇总
    print("\n" + "=" * 70)
    print("📊 各站点评分汇总")
    print("=" * 70)
    print(f"{'站点':<15} {'最佳时段':<10} {'评分':<10} {'等级'}")
    print("-" * 50)
    
    all_results.sort(key=lambda x: x["best_score"], reverse=True)
    for i, r in enumerate(all_results, 1):
        print(f"{r['name']:<15} {r['best_hour']:02d}:00     {r['best_score']:<10} {r['level'].split()[0]}")
    
    # 最佳观测点
    if all_results:
        best_site = all_results[0]
        print(f"\n🏆 推荐观测点: {best_site['name']} (评分 {best_site['best_score']}分)")
    
    print("\n数据来源: 和风天气24小时预报")

if __name__ == "__main__":
    generate_report()
