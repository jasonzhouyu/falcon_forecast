#!/usr/bin/env python3
"""
猛禽迁徙预测模型 V5 - 物理增强版
基于 Spaar 1997 滑翔力学理论
"""
import datetime
import math
import json
import requests
import numpy as np

# ============== V5 核心参数 ==============

# 地理类型分类
SITE_TYPES = {
    "Ridge": ["都统岩", "龙泉山", "九龙山"],
    "Karst": ["尧山电视台"],
    "Coastal": ["冠头岭", "渔洋山"],
    "Wetland": ["南汇东滩", "崇明东滩"]
}

# V5 物理参数
V5_PARAMS = {
    # 风速阈值 (kts)
    "V_MIN": 8,           # 最低有效风速
    "V_OPT_MIN": 15,      # 最佳风速下限
    "V_OPT_MAX": 30,      # 最佳风速上限
    "V_MAX": 45,          # 最大容忍风速
    
    # 指数衰减参数
    "TAU": 5,             # 衰减时间常数
    
    # 热力补偿参数
    "WSTAR_LOW_WIND_THRESHOLD": 6,  # 低风速阈值 (kts)
    "THERMAL_COMPENSATION": 0.8,    # 热力补偿系数
    
    # 海气温差参数
    "SST_DELTA_T_OPTIMAL": 3,      # 最佳海气温差 (°C)
}

def get_site_type(site_name):
    """获取站点地理类型"""
    for site_type, sites in SITE_TYPES.items():
        if site_name in sites:
            return site_type
    return "Ridge"  # 默认

def calculate_wind_lift_score_v5(w_spd, site_type):
    """
    V5 风速升力得分 - 指数衰减 + 饱和区间
    基于 Spaar 1997 滑翔力学
    """
    V = w_spd  # kts
    
    if V < V5_PARAMS["V_MIN"]:
        # 指数级衰减
        score = 15 * math.exp(-(V5_PARAMS["V_MIN"] - V) / V5_PARAMS["TAU"])
    elif V5_PARAMS["V_OPT_MIN"] <= V <= V5_PARAMS["V_OPT_MAX"]:
        # 饱和区间
        score = 15
    elif V > V5_PARAMS["V_MAX"]:
        # 过强风
        score = max(0, 15 - (V - V5_PARAMS["V_MAX"]) * 1.5)
    else:
        # 线性过渡区
        if V < V5_PARAMS["V_OPT_MIN"]:
            score = 15 * (V - V5_PARAMS["V_MIN"]) / (V5_PARAMS["V_OPT_MIN"] - V5_PARAMS["V_MIN"])
        else:
            score = 15 * (1 - (V - V5_PARAMS["V_OPT_MAX"]) / (V5_PARAMS["V_MAX"] - V5_PARAMS["V_OPT_MAX"]))
    
    return max(0, min(15, score))

def calculate_thermal_convection_v5(temp_2m, temp_850hPa, w_spd):
    """
    V5 热力对流参数 W* (Convective Velocity Scale)
    W* = g * z_i * (theta_v - theta_v_env) / theta_v
    
    简化版本: 利用 2m 与 850hPa 温差近似
    """
    # 简化: 假设抬升指数与温差成正比
    delta_theta = temp_2m - temp_850hPa
    
    if delta_theta < 0:
        # 负值表示不稳定大气
        W_star = abs(delta_theta) * 0.5
    else:
        W_star = 0
    
    # 低风速时热力补偿
    if w_spd < V5_PARAMS["WSTAR_LOW_WIND_THRESHOLD"] and W_star > 2:
        compensation = min(5, (W_star - 2) * V5_PARAMS["THERMAL_COMPENSATION"])
    else:
        compensation = 0
    
    return W_star, compensation

def calculate_sea_breeze_index_v5(site_type, temp_2m, sst=None):
    """
    V5 海陆风指数
    仅适用于滨海站点
    """
    if site_type != "Coastal":
        return 0
    
    # 如果没有 SST 数据，使用经验估计
    if sst is None:
        # 假设海温比气温低 2-3°C
        sst = temp_2m - 2.5
    
    delta_t = temp_2m - sst
    
    if 2 <= delta_t <= 5:
        # 最佳海陆风条件
        return 15
    elif delta_t > 5:
        # 过大的温差可能导致不稳定
        return 10
    elif delta_t > 0:
        return 5 * delta_t / 2
    else:
        return 0

def calculate_ridge_cosine_correction(w_dir, ridge_orient):
    """
    V5 山脊风向 cos(θ) 修正
    θ 为风向与山脊线夹角
    """
    theta = abs(w_dir - ridge_orient) % 180
    if theta > 90:
        theta = 180 - theta
    
    # cos 修正: 0° 时为 1, 90° 时为 0
    cos_correction = math.cos(math.radians(theta))
    return cos_correction

def calculate_altitude_correction(site_name, pressure):
    """
    V5 海拔修正
    高海拔站点需要调整气压层
    """
    high_altitude_sites = ["都统岩"]  # 约 1500m
    
    if site_name in high_altitude_sites:
        # 对于高海拔站点，气压偏低是正常的
        # 如果气压 > 900hPa，说明可能在低气压系统影响下
        if pressure < 900:
            return 1.1  # 低气压有利于上升
        return 1.0
    return 1.0

def calculate_spring_south_wind_boost(w_dir, site_type, season):
    """
    V5 春季南风权重增强
    春季猛禽更依赖顺风抬升
    """
    if season != "春":
        return 0
    
    if site_type not in ["Ridge", "Karst"]:
        return 0
    
    # 南风范围: 135° - 225°
    if 135 <= w_dir <= 225:
        # 计算南风分量
        southness = 1 - abs(w_dir - 180) / 45
        return southness * 10  # 最多 +10 分
    return 0

# ============== 主计算函数 ==============

def calculate_v5_score(site, weather_data, date_obj, season):
    """
    V5 评分计算
    """
    name = site["name"]
    site_type = get_site_type(name)
    
    # 提取气象数据
    temp_2m = weather_data.get("temp_2m", 15)
    w_spd = weather_data.get("w_spd", 10)  # kts
    w_dir = weather_data.get("w_dir", 180)
    cloud = weather_data.get("cloud", 50)
    precip = weather_data.get("precip", 0)
    pressure = weather_data.get("pressure", 1013)
    temp_850hPa = weather_data.get("temp_850hPa", 10)
    
    # === V5 核心计算 ===
    
    # 1. 基础分数
    baseline = site.get("baseline", {}).get(season, 0.85)
    peak_weight = get_peak_weight_v5(site, date_obj, season)
    base_score = 65 * baseline * peak_weight
    
    # 2. V5 风速升力得分
    wind_lift_score = calculate_wind_lift_score_v5(w_spd, site_type)
    
    # 3. V5 热力对流补偿
    W_star, thermal_compensation = calculate_thermal_convection_v5(
        temp_2m, temp_850hPa, w_spd
    )
    
    # 4. V5 海陆风指数
    sea_breeze_score = calculate_sea_breeze_index_v5(
        site_type, temp_2m, 
        sst=weather_data.get("sst")
    )
    
    # 5. V5 山脊 cos(θ) 修正
    ridge_cosine = calculate_ridge_cosine_correction(
        w_dir, site.get("ridge_orient", 90)
    )
    
    # 6. V5 海拔修正
    altitude_factor = calculate_altitude_correction(name, pressure)
    
    # 7. V5 春季南风增强
    south_wind_boost = calculate_spring_south_wind_boost(w_dir, site_type, season)
    
    # === 传统因子 ===
    
    # 逆温层检测
    delta_T = temp_850hPa - (temp_2m - 6.5 * 2.5)  # 近似
    inversion_penalty = 0
    if delta_T > 0:
        inversion_penalty = min(15, delta_T * 5)
    
    # 云量惩罚 (区分低云/高云 - V5 改进)
    cloud_penalty = 0
    if cloud > 85:
        cloud_penalty = 25
    elif cloud > 70:
        cloud_penalty = 10
    
    # 降水惩罚 (V5 改进 - 不再直接清零)
    precip_penalty = 0
    if precip > 0.1:
        precip_penalty = 30
    elif precip > 0.03:
        precip_penalty = 15
    
    # 侧风警告
    wind_diff = abs(w_dir - site.get("fav_wind", {}).get(season, 180))
    if wind_diff > 180:
        wind_diff = 360 - wind_diff
    warnings = []
    if wind_diff > 20:
        warnings.append(f"侧风偏航({wind_diff}°)")
    
    # === 最终评分 ===
    score = base_score
    score += wind_lift_score * ridge_cosine * altitude_factor
    score += thermal_compensation
    score += sea_breeze_score
    score += south_wind_boost
    score -= inversion_penalty
    score -= cloud_penalty
    score -= precip_penalty
    
    # 硬约束
    if precip > 0.1:
        score = 0
    
    score = max(0, min(100, score))
    
    return {
        "score": int(score),
        "wind_lift": round(wind_lift_score, 1),
        "thermal_compensation": round(thermal_compensation, 1),
        "sea_breeze": round(sea_breeze_score, 1),
        "south_wind_boost": round(south_wind_boost, 1),
        "ridge_cosine": round(ridge_cosine, 2),
        "altitude_factor": altitude_factor,
        "inversion_penalty": inversion_penalty,
        "cloud_penalty": cloud_penalty,
        "precip_penalty": precip_penalty,
        "warnings": warnings,
        "site_type": site_type
    }

def get_peak_weight_v5(site, date_obj, season):
    """V5 峰值系数"""
    month = date_obj.month
    day = date_obj.day
    
    peak_matrix = site.get("peak_matrix", {}).get(season, {})
    
    if month not in peak_matrix:
        return 0.5
    
    matrix = peak_matrix[month]
    if day <= 10:
        return matrix[0]
    elif day <= 20:
        return matrix[1]
    else:
        return matrix[2]

# ============== 站点配置 ==============

HOTSPOTS_V5 = [
    {
        "name": "都统岩",
        "lat": 30.76,
        "lon": 103.42,
        "type": "内陆山脊",
        "ridge_orient": 30,
        "fav_wind": {"春": 180, "秋": 0},
        "baseline": {"春": 0.85, "秋": 0.80},
        "peak_matrix": {
            "春": {3: [0.6, 0.8, 1.0], 4: [1.2, 1.5, 1.3], 5: [1.1, 0.9, 0.6]},
            "秋": {9: [0.7, 1.0, 1.3], 10: [1.4, 1.2, 0.8], 11: [0.6, 0.5, 0.3]}
        }
    },
    {
        "name": "龙泉山",
        "lat": 30.556,
        "lon": 104.307,
        "type": "内陆山脊",
        "ridge_orient": 20,
        "fav_wind": {"春": 180, "秋": 0},
        "baseline": {"春": 0.85, "秋": 0.80},
        "peak_matrix": {
            "春": {3: [0.7, 0.9, 1.1], 4: [1.3, 1.4, 1.2], 5: [1.0, 0.8, 0.5]},
            "秋": {9: [0.8, 1.1, 1.4], 10: [1.5, 1.3, 0.9], 11: [0.7, 0.5, 0.4]}
        }
    },
    {
        "name": "尧山电视台",
        "lat": 25.30,
        "lon": 110.38,
        "type": "喀斯特山脊",
        "ridge_orient": 135,
        "fav_wind": {"春": 165, "秋": 345},
        "baseline": {"春": 0.90, "秋": 0.85},
        "peak_matrix": {
            "春": {3: [0.8, 1.0, 1.3], 4: [1.4, 1.6, 1.5], 5: [1.2, 0.9, 0.6]},
            "秋": {9: [0.6, 0.8, 1.1], 10: [1.3, 1.5, 1.4], 11: [1.1, 0.8, 0.5]}
        }
    },
    {
        "name": "冠头岭",
        "lat": 21.45,
        "lon": 109.05,
        "type": "滨海廊道",
        "ridge_orient": 90,
        "fav_wind": {"春": 190, "秋": 20},
        "baseline": {"春": 0.90, "秋": 0.60},
        "peak_matrix": {
            "春": {3: [0.8, 1.1, 1.4], 4: [1.6, 1.5, 1.2], 5: [0.9, 0.6, 0.4]},
            "秋": {9: [0.7, 0.9, 1.1], 10: [1.2, 1.0, 0.7], 11: [0.5, 0.4, 0.3]}
        }
    },
    {
        "name": "九龙山",
        "lat": 29.5,
        "lon": 121.5,
        "type": "内陆山脊",
        "ridge_orient": 45,
        "fav_wind": {"春": 135, "秋": 315},
        "baseline": {"春": 0.80, "秋": 0.80},
        "peak_matrix": {
            "春": {3: [0.6, 0.8, 1.0], 4: [1.2, 1.4, 1.2], 5: [1.0, 0.7, 0.5]},
            "秋": {9: [0.7, 1.0, 1.2], 10: [1.3, 1.2, 0.8], 11: [0.6, 0.4, 0.3]}
        }
    },
    {
        "name": "渔洋山",
        "lat": 31.2,
        "lon": 120.4,
        "type": "滨海廊道",
        "ridge_orient": 90,
        "fav_wind": {"春": 135, "秋": 315},
        "baseline": {"春": 0.80, "秋": 0.80},
        "peak_matrix": {
            "春": {3: [0.6, 0.8, 1.0], 4: [1.1, 1.3, 1.1], 5: [0.8, 0.6, 0.4]},
            "秋": {9: [0.6, 0.9, 1.1], 10: [1.2, 1.0, 0.7], 11: [0.5, 0.4, 0.3]}
        }
    },
    {
        "name": "南汇东滩",
        "lat": 30.9,
        "lon": 121.9,
        "type": "河口湿地",
        "ridge_orient": 0,
        "fav_wind": {"春": 90, "秋": 270},
        "baseline": {"春": 0.75, "秋": 0.75},
        "peak_matrix": {
            "春": {3: [0.5, 0.7, 0.9], 4: [1.0, 1.2, 1.0], 5: [0.7, 0.5, 0.3]},
            "秋": {9: [0.6, 0.8, 1.0], 10: [1.1, 0.9, 0.6], 11: [0.4, 0.3, 0.2]}
        }
    },
    {
        "name": "崇明东滩",
        "lat": 31.5,
        "lon": 121.9,
        "type": "河口湿地",
        "ridge_orient": 0,
        "fav_wind": {"春": 90, "秋": 270},
        "baseline": {"春": 0.75, "秋": 0.75},
        "peak_matrix": {
            "春": {3: [0.5, 0.7, 0.9], 4: [1.0, 1.2, 1.0], 5: [0.7, 0.5, 0.3]},
            "秋": {9: [0.6, 0.8, 1.0], 10: [1.1, 0.9, 0.6], 11: [0.4, 0.3, 0.2]}
        }
    }
]

def get_weather_v5(lat, lon, target_date):
    """获取天气数据"""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,pressure_msl",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "Asia/Shanghai",
        "forecast_days": 7
    }
    
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json()
    
    # 找到目标日期 12:00 的数据
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    
    target_str = target_date.strftime("%Y-%m-%d")
    
    for i, t in enumerate(times):
        if f"{target_str}T12:00" in t:
            # 转换风速: km/h -> kts
            w_spd_kmh = hourly["wind_speed_10m"][i]
            w_spd = w_spd_kmh / 1.852
            
            return {
                "temp_2m": hourly["temperature_2m"][i],
                "precip": hourly["precipitation"][i],
                "cloud": hourly["cloud_cover"][i],
                "w_spd": w_spd,
                "w_dir": hourly["wind_direction_10m"][i],
                "pressure": hourly["pressure_msl"][i],
            }
    
    return None

def get_rating(score):
    """获取评级"""
    if score >= 88:
        return "⭐⭐⭐⭐ 推荐"
    elif score >= 75:
        return "⭐⭐⭐ 值得"
    elif score >= 60:
        return "⭐⭐ 视情"
    elif score >= 40:
        return "⭐ 放弃"
    else:
        return "❌ 放弃"

# ============== 主程序 ==============

def main():
    print("\n" + "=" * 70)
    print("🦅 猛禽迁徙预测模型 V5.0 - 物理增强版")
    print("=" * 70)
    
    today = datetime.date(2026, 3, 24)
    season = "春"
    
    results = []
    
    print(f"\n📅 预测日期: {today} ({season}季)")
    print("\n正在计算各站点评分...\n")
    
    for site in HOTSPOTS_V5:
        print(f"→ {site['name']}...")
        
        weather = get_weather_v5(site["lat"], site["lon"], today)
        
        if weather:
            v5_result = calculate_v5_score(site, weather, today, season)
            
            print(f"   天气: {weather['temp_2m']:.1f}°C, 风速{weather['w_spd']:.1f}kts, 风向{weather['w_dir']}°")
            print(f"   V5得分: {v5_result['score']}分 {get_rating(v5_result['score'])}")
            print(f"   - 风速得分: {v5_result['wind_lift']}")
            print(f"   - 热力补偿: +{v5_result['thermal_compensation']}")
            print(f"   - 海陆风: +{v5_result['sea_breeze']}")
            print(f"   - 南风boost: +{v5_result['south_wind_boost']}")
            print(f"   - cos(θ)修正: {v5_result['ridge_cosine']}")
            print(f"   - 站点类型: {v5_result['site_type']}")
            print()
            
            results.append({
                "site": site["name"],
                "score": v5_result["score"],
                "weather": weather,
                "detail": v5_result
            })
        else:
            print(f"   ❌ 无法获取天气数据")
    
    # 汇总
    print("\n" + "=" * 70)
    print("📊 V5 模型预测结果汇总")
    print("=" * 70)
    
    print(f"\n{'站点':<12} {'V5得分':<8} {'V4得分':<8} {'差值':<8} {'评级'}")
    print("-" * 50)
    
    v4_scores = {
        "都统岩": 29,
        "龙泉山": 33,
        "尧山电视台": 64,
        "冠头岭": 66,
        "九龙山": 14,
        "渔洋山": 9,
        "南汇东滩": 13,
        "崇明东滩": 11
    }
    
    for r in results:
        v4 = v4_scores.get(r["site"], 0)
        diff = r["score"] - v4
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{r['site']:<12} {r['score']:<8} {v4:<8} {diff_str:<8} {get_rating(r['score'])}")
    
    print("\n" + "=" * 70)
    print("✅ V5 计算完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
