#!/usr/bin/env python3
"""
猛禽迁徙预测模型 V6 - 物理增强版 V2
改进：
1. Ridge_Ortho_Lift: 风向矢量在山脊法线方向的分量
2. 降水容忍度: 逻辑回归曲线，0.5mm半衰期
3. 海拔气压对齐: 高海拔站点使用925hPa数据
"""
import datetime
import math
import json
import requests
import numpy as np

# ============== V6 核心参数 ==============

SITE_TYPES = {
    "Ridge": ["都统岩", "龙泉山", "九龙山"],
    "Karst": ["尧山电视台"],
    "Coastal": ["冠头岭", "渔洋山"],
    "Wetland": ["南汇东滩", "崇明东滩"]
}

# 高海拔站点 (需要使用925hPa数据)
HIGH_ALTITUDE_SITES = ["都统岩", "龙泉山", "尧山电视台", "九龙山"]

V6_PARAMS = {
    "V_MIN": 8,
    "V_OPT_MIN": 15,
    "V_OPT_MAX": 30,
    "V_MAX": 45,
    "TAU": 5,
    "WSTAR_LOW_WIND_THRESHOLD": 6,
    "THERMAL_COMPENSATION": 0.8,
    "SST_DELTA_T_OPTIMAL": 3,
    # V6 新增
    "ORTHO_MIN_SPEED": 10,         # 正交分量有效最低风速
    "ORTHO_MIN_RATIO": 0.40,       # 最低保留动力得分比例
    "PRECIP_HALFLIFE": 0.5,        # 降水半衰期 (mm)
}

def get_site_type(site_name):
    for site_type, sites in SITE_TYPES.items():
        if site_name in sites:
            return site_type
    return "Ridge"

def is_high_altitude(site_name):
    """检查是否为高海拔站点"""
    return site_name in HIGH_ALTITUDE_SITES

def calculate_ridge_ortho_lift(w_spd, w_dir, ridge_orient):
    """
    V6 Ridge_Ortho_Lift 函数
    计算风向矢量在山脊法线方向的分量
    
    原理: 即使风向偏航，只要风有正交分量，就能产生地形升力
    条件: 风速 > 10 kts 时，保留至少 40% 动力得分
    """
    # 山脊法线方向 (与山脊走向垂直)
    normal_angle = (ridge_orient + 90) % 360
    
    # 风向与法线的夹角
    theta = abs(w_dir - normal_angle) % 360
    if theta > 180:
        theta = 360 - theta
    
    # 计算正交分量 (cos值)
    cos_theta = abs(math.cos(math.radians(theta)))
    
    # 只有当风速 > 阈值时，正交分量才有效
    if w_spd < V6_PARAMS["ORTHO_MIN_SPEED"]:
        return 0
    
    # 正交升力得分
    # 如果夹角接近90°(cos接近0)，升力最大
    # 如果夹角接近0°或180°(cos接近1)，升力最小(顺着山脊)
    # 但这是"穿过"山脊的情况
    
    # 修正: 使用sin分量表示垂直于风向的山脊分量
    sin_theta = math.sin(math.radians(theta))
    
    # 基础升力
    base_lift = sin_theta * 15
    
    # 强制保留最低得分
    if sin_theta > 0.1 and w_spd > V6_PARAMS["ORTHO_MIN_SPEED"]:
        min_lift = 15 * V6_PARAMS["ORTHO_MIN_RATIO"]
        base_lift = max(base_lift, min_lift)
    
    return base_lift

def calculate_precip_penalty_v6(precip):
    """
    V6 降水惩罚 - 逻辑回归曲线
    0.5mm 为半衰期阈值，而非全清零
    
    公式: penalty = 30 / (1 + exp(-k * (precip - threshold)))
    其中 k = ln(3) / halflife (使 threshold 处 penalty = 15)
    """
    if precip <= 0:
        return 0
    
    threshold = V6_PARAMS["PRECIP_HALFLIFE"]  # 0.5 mm
    k = math.log(3) / threshold  # 使 threshold 处为 15
    
    # 逻辑回归曲线
    penalty = 30 / (1 + math.exp(-k * (precip - threshold)))
    
    return min(30, penalty)

def calculate_wind_lift_score_v6(w_spd, site_type):
    """V6 风速升力得分"""
    V = w_spd
    
    if V < V6_PARAMS["V_MIN"]:
        score = 15 * math.exp(-(V6_PARAMS["V_MIN"] - V) / V6_PARAMS["TAU"])
    elif V6_PARAMS["V_OPT_MIN"] <= V <= V6_PARAMS["V_OPT_MAX"]:
        score = 15
    elif V > V6_PARAMS["V_MAX"]:
        score = max(0, 15 - (V - V6_PARAMS["V_MAX"]) * 1.5)
    else:
        if V < V6_PARAMS["V_OPT_MIN"]:
            score = 15 * (V - V6_PARAMS["V_MIN"]) / (V6_PARAMS["V_OPT_MIN"] - V6_PARAMS["V_MIN"])
        else:
            score = 15 * (1 - (V - V6_PARAMS["V_OPT_MAX"]) / (V6_PARAMS["V_MAX"] - V6_PARAMS["V_OPT_MAX"]))
    
    return max(0, min(15, score))

def calculate_thermal_convection_v6(temp_2m, temp_850hPa, w_spd):
    """V6 热力对流参数"""
    delta_theta = temp_2m - temp_850hPa
    
    if delta_theta < 0:
        W_star = abs(delta_theta) * 0.5
    else:
        W_star = 0
    
    if w_spd < V6_PARAMS["WSTAR_LOW_WIND_THRESHOLD"] and W_star > 2:
        compensation = min(5, (W_star - 2) * V6_PARAMS["THERMAL_COMPENSATION"])
    else:
        compensation = 0
    
    return W_star, compensation

def calculate_sea_breeze_index_v6(site_type, temp_2m, sst=None):
    """V6 海陆风指数"""
    if site_type != "Coastal":
        return 0
    
    if sst is None:
        sst = temp_2m - 2.5
    
    delta_t = temp_2m - sst
    
    if 2 <= delta_t <= 5:
        return 15
    elif delta_t > 5:
        return 10
    elif delta_t > 0:
        return 5 * delta_t / 2
    else:
        return 0

def calculate_spring_south_wind_boost(w_dir, site_type, season):
    """V6 春季南风增强"""
    if season != "春":
        return 0
    
    if site_type not in ["Ridge", "Karst"]:
        return 0
    
    if 135 <= w_dir <= 225:
        southness = 1 - abs(w_dir - 180) / 45
        return southness * 10
    return 0

def calculate_v6_score(site, weather_data, date_obj, season):
    """V6 评分计算"""
    name = site["name"]
    site_type = get_site_type(name)
    
    # 提取气象数据
    temp_2m = weather_data.get("temp_2m", 15)
    w_spd = weather_data.get("w_spd", 10)
    w_dir = weather_data.get("w_dir", 180)
    cloud = weather_data.get("cloud", 50)
    precip = weather_data.get("precip", 0)
    pressure = weather_data.get("pressure", 1013)
    temp_850hPa = weather_data.get("temp_850hPa", 10)
    
    # === V6 核心计算 ===
    
    # 1. 基础分数
    baseline = site.get("baseline", {}).get(season, 0.85)
    peak_weight = get_peak_weight_v6(site, date_obj, season)
    base_score = 65 * baseline * peak_weight
    
    # 2. V6 风速升力得分
    wind_lift_score = calculate_wind_lift_score_v6(w_spd, site_type)
    
    # 3. V6 Ridge_Ortho_Lift (关键改进!)
    if site_type in ["Ridge", "Karst"]:
        ortho_lift = calculate_ridge_ortho_lift(w_spd, w_dir, site.get("ridge_orient", 90))
    else:
        ortho_lift = 0
    
    # 4. V6 热力对流补偿
    W_star, thermal_compensation = calculate_thermal_convection_v6(
        temp_2m, temp_850hPa, w_spd
    )
    
    # 5. V6 海陆风指数
    sea_breeze_score = calculate_sea_breeze_index_v6(
        site_type, temp_2m, weather_data.get("sst")
    )
    
    # 6. V6 春季南风增强
    south_wind_boost = calculate_spring_south_wind_boost(w_dir, site_type, season)
    
    # === 传统因子 (V6改进) ===
    
    # 逆温层检测
    delta_T = temp_850hPa - (temp_2m - 6.5 * 2.5)
    inversion_penalty = 0
    if delta_T > 0:
        inversion_penalty = min(15, delta_T * 5)
    
    # 云量惩罚
    cloud_penalty = 0
    if cloud > 85:
        cloud_penalty = 25
    elif cloud > 70:
        cloud_penalty = 10
    
    # V6 降水惩罚 (改进!)
    precip_penalty = calculate_precip_penalty_v6(precip)
    
    # 侧风警告 (V6 改进 - 不再作为主要扣分项)
    wind_diff = abs(w_dir - site.get("fav_wind", {}).get(season, 180))
    if wind_diff > 180:
        wind_diff = 360 - wind_diff
    warnings = []
    if wind_diff > 45:
        warnings.append(f"侧风偏航({wind_diff}°)")
    
    # === 最终评分 ===
    score = base_score
    
    # 组合升力得分: 基础风速 + 正交分量
    total_wind_score = wind_lift_score
    if ortho_lift > 0:
        total_wind_score = max(wind_lift_score, ortho_lift) * 0.6 + min(wind_lift_score, ortho_lift) * 0.4
    
    score += total_wind_score
    score += thermal_compensation
    score += sea_breeze_score
    score += south_wind_boost
    score -= inversion_penalty
    score -= cloud_penalty
    score -= precip_penalty
    
    # 硬约束 (V6 放宽: 从 0.1mm 改为 1mm)
    if precip > 1.0:
        score = 0
    
    score = max(0, min(100, score))
    
    return {
        "score": int(score),
        "wind_lift": round(wind_lift_score, 1),
        "ortho_lift": round(ortho_lift, 1),
        "total_wind": round(total_wind_score, 1),
        "thermal_compensation": round(thermal_compensation, 1),
        "sea_breeze": round(sea_breeze_score, 1),
        "south_wind_boost": round(south_wind_boost, 1),
        "inversion_penalty": inversion_penalty,
        "cloud_penalty": cloud_penalty,
        "precip_penalty": round(precip_penalty, 1),
        "warnings": warnings,
        "site_type": site_type
    }

def get_peak_weight_v6(site, date_obj, season):
    """V6 峰值系数"""
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

HOTSPOTS_V6 = [
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

def get_weather_v6(lat, lon, target_date, is_high_alt=False):
    """
    V6 天气获取 - 支持高海拔站点使用925hPa数据
    """
    # 高海拔站点需要额外获取925hPa数据
    params_base = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,pressure_msl,surface_pressure",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "Asia/Shanghai",
        "forecast_days": 7
    }
    
    # 如果是高海拔站点，添加925hPa数据
    if is_high_alt:
        params_base["hourly"] += ",wind_speed_925hPa,wind_direction_925hPa,temperature_850hPa"
    
    resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params_base, timeout=10)
    data = resp.json()
    
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    target_str = target_date.strftime("%Y-%m-%d")
    
    for i, t in enumerate(times):
        if f"{target_str}T12:00" in t:
            w_spd_kmh = hourly["wind_speed_10m"][i]
            w_spd = w_spd_kmh / 1.852
            
            weather = {
                "temp_2m": hourly["temperature_2m"][i],
                "precip": hourly["precipitation"][i],
                "cloud": hourly["cloud_cover"][i],
                "w_spd": w_spd,
                "w_dir": hourly["wind_direction_10m"][i],
                "pressure": hourly["surface_pressure"][i] if "surface_pressure" in hourly else hourly["pressure_msl"][i],
            }
            
            # 高海拔站点使用925hPa数据覆盖
            if is_high_alt and "wind_speed_925hPa" in hourly:
                w_spd_925 = hourly["wind_speed_925hPa"][i]
                if w_spd_925 and w_spd_925 > 0:
                    weather["w_spd"] = w_spd_925 / 1.852
                    weather["w_dir_925"] = hourly["wind_direction_925hPa"][i]
                    weather["temp_850hPa"] = hourly["temperature_850hPa"][i]
            
            # 确保有 temp_850hPa
            if "temp_850hPa" not in weather:
                weather["temp_850hPa"] = weather["temp_2m"] - 6.5
            
            return weather
    
    return None

def get_rating(score):
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
    print("🦅 猛禽迁徙预测模型 V6.0 - 物理增强版 V2")
    print("=" * 70)
    
    today = datetime.date(2026, 3, 24)
    season = "春"
    
    results = []
    
    print(f"\n📅 预测日期: {today} ({season}季)")
    print("\n正在计算各站点评分 (V6算法)...\n")
    
    for site in HOTSPOTS_V6:
        print(f"→ {site['name']}...")
        
        high_alt = is_high_altitude(site["name"])
        weather = get_weather_v6(site["lat"], site["lon"], today, high_alt)
        
        if weather:
            v6_result = calculate_v6_score(site, weather, today, season)
            
            print(f"   天气: {weather['temp_2m']:.1f}°C, 风速{weather['w_spd']:.1f}kts, 风向{weather['w_dir']}°")
            print(f"   V6得分: {v6_result['score']}分 {get_rating(v6_result['score'])}")
            print(f"   - 风速得分: {v6_result['wind_lift']}")
            print(f"   - 正交升力: {v6_result['ortho_lift']}")
            print(f"   - 综合风力: {v6_result['total_wind']}")
            print(f"   - 热力补偿: +{v6_result['thermal_compensation']}")
            print(f"   - 海陆风: +{v6_result['sea_breeze']}")
            print(f"   - 南风boost: +{v6_result['south_wind_boost']}")
            print(f"   - 降水惩罚: -{v6_result['precip_penalty']}")
            print(f"   - 站点类型: {v6_result['site_type']}")
            print(f"   - 高海拔修正: {'是' if high_alt else '否'}")
            print()
            
            results.append({
                "site": site["name"],
                "score": v6_result["score"],
                "weather": weather,
                "detail": v6_result,
                "high_alt": high_alt
            })
        else:
            print(f"   ❌ 无法获取天气数据")
    
    # 汇总
    print("\n" + "=" * 70)
    print("📊 V6 模型预测结果汇总")
    print("=" * 70)
    
    print(f"\n{'站点':<12} {'V6得分':<8} {'V5得分':<8} {'V4得分':<8} {'评级'}")
    print("-" * 55)
    
    v5_scores = {
        "都统岩": 31,
        "龙泉山": 47,
        "尧山电视台": 37,
        "冠头岭": 87,
        "九龙山": 0,
        "渔洋山": 0,
        "南汇东滩": 6,
        "崇明东滩": 0
    }
    
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
        v5 = v5_scores.get(r["site"], 0)
        v4 = v4_scores.get(r["site"], 0)
        diff_v5 = r["score"] - v5
        diff_v5_str = f"+{diff_v5}" if diff_v5 > 0 else str(diff_v5)
        print(f"{r['site']:<12} {r['score']:<8} {v5:<8} {diff_v5_str:<8} {get_rating(r['score'])}")
    
    print("\n" + "=" * 70)
    print("✅ V6 计算完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
