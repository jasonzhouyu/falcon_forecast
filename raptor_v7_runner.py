#!/usr/bin/env python3
"""
猛禽迁徙预测模型 V7 - 地理溢价与时间物候窗
改进：
1. 地理溢价: Gateway_Bonus, Inland_Funnel_Bonus
2. eBird物候修正: 物种爆发旬增益
3. 降水窗逻辑: 连续3小时无雨则得分不低于40
"""
import datetime
import math
import json
import requests
import numpy as np

# ============== V7 核心参数 ==============

SITE_TYPES = {
    "Ridge": ["都统岩", "龙泉山", "九龙山"],
    "Karst": ["尧山电视台"],
    "Coastal": ["冠头岭", "渔洋山"],
    "Wetland": ["南汇东滩", "崇明东滩"]
}

HIGH_ALTITUDE_SITES = ["都统岩", "龙泉山", "尧山电视台", "九龙山"]

# V7 地理溢价
GEO_BONUS = {
    "冠头岭": {"春": 15, "秋": 5},   # Gateway_Bonus: 跨海门户唯一性
    "龙泉山": {"春": 10, "秋": 8},   # Inland_Funnel_Bonus: 内陆收拢作用
    "都统岩": {"春": 10, "秋": 8},   # Inland_Funnel_Bonus
}

# V7 物候配置 (模拟 eBird 历史数据)
PHENOLOGY_DATA = {
    "都统岩": {
        "春": {
            3: {"species": "赤腹鹰", "avg_count": 150, "peak_days": [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]},
            4: {"species": "凤头蜂鹰", "avg_count": 200, "peak_days": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
        }
    },
    "龙泉山": {
        "春": {
            3: {"species": "灰脸鵟鹰", "avg_count": 180, "peak_days": [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]},
            4: {"species": "赤腹鹰", "avg_count": 120, "peak_days": [5, 6, 7, 8, 9, 10]},
        }
    },
    "尧山电视台": {
        "春": {
            3: {"species": "赤腹鹰", "avg_count": 250, "peak_days": [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26]},
            4: {"species": "林雕", "avg_count": 80, "peak_days": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
        }
    },
    "冠头岭": {
        "春": {
            3: {"species": "黑冠鹃隼", "avg_count": 300, "peak_days": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]},
            4: {"species": "赤腹鹰", "avg_count": 200, "peak_days": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]},
        }
    },
    "九龙山": {
        "春": {
            3: {"species": "普通鵟", "avg_count": 60, "peak_days": [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]},
            4: {"species": "雀鹰", "avg_count": 50, "peak_days": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
        }
    },
    "渔洋山": {
        "春": {
            3: {"species": "灰脸鵟鹰", "avg_count": 80, "peak_days": [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]},
            4: {"species": "赤腹鹰", "avg_count": 70, "peak_days": [5, 6, 7, 8, 9, 10, 11, 12, 13]},
        }
    },
    "南汇东滩": {
        "春": {
            3: {"species": "鹗", "avg_count": 40, "peak_days": [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]},
            4: {"species": "白尾鹞", "avg_count": 30, "peak_days": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
        }
    },
    "崇明东滩": {
        "春": {
            3: {"species": "鹗", "avg_count": 35, "peak_days": [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]},
            4: {"species": "白尾鹞", "avg_count": 25, "peak_days": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
        }
    },
}

V7_PARAMS = {
    "V_MIN": 8,
    "V_OPT_MIN": 15,
    "V_OPT_MAX": 30,
    "V_MAX": 45,
    "TAU": 5,
    "WSTAR_LOW_WIND_THRESHOLD": 6,
    "THERMAL_COMPENSATION": 0.8,
    "SST_DELTA_T_OPTIMAL": 3,
    "ORTHO_MIN_SPEED": 10,
    "ORTHO_MIN_RATIO": 0.40,
    "PRECIP_HALFLIFE": 0.5,
    # V7 新增
    "MIN_CONSECUTIVE_HOURS": 3,  # 连续无雨小时数阈值
    "MIN_OPTIMUM_HOURS_SCORE": 40,  # 满足条件后的最低得分
    "PHENOLOGY_MULTIPLIER": 1.2,   # 物候爆发增益
}

def get_site_type(site_name):
    for site_type, sites in SITE_TYPES.items():
        if site_name in sites:
            return site_type
    return "Ridge"

def is_high_altitude(site_name):
    return site_name in HIGH_ALTITUDE_SITES

def calculate_geographic_bonus(site_name, season):
    """V7 地理溢价"""
    if site_name in GEO_BONUS:
        return GEO_BONUS[site_name].get(season, 0)
    return 0

def calculate_phenology_multiplier(site_name, date_obj, base_score):
    """
    V7 eBird 物候修正
    若处于物种爆发旬，获得1.2倍增益
    """
    month = date_obj.month
    day = date_obj.day
    
    # 获取该站点该月份的物候数据
    if site_name in PHENOLOGY_DATA:
        season_data = PHENOLOGY_DATA[site_name].get("春", {})
        if month in season_data:
            month_data = season_data[month]
            peak_days = month_data.get("peak_days", [])
            avg_count = month_data.get("avg_count", 0)
            
            # 计算物候得分
            phenology_score = math.log(avg_count + 1)
            
            # 如果在爆发旬
            if day in peak_days:
                # 基础分低于40时，触发增益
                if base_score < 40:
                    return V7_PARAMS["PHENOLOGY_MULTIPLIER"]
    
    return 1.0

def calculate_optimum_hours(weather_hourly, target_date):
    """
    V7 降水窗逻辑
    统计"可用观测小时数": 连续3小时无雨且风力达标
    """
    hourly = weather_hourly
    times = hourly.get("time", [])
    
    target_str = target_date.strftime("%Y-%m-%d")
    
    # 找出白天时段 (8:00 - 18:00)
    daylight_hours = []
    for i, t in enumerate(times):
        if target_str in t:
            hour = int(t.split("T")[1].split(":")[0])
            if 8 <= hour <= 18:
                precip = hourly.get("precipitation", [0])[i] if i < len(hourly.get("precipitation", [])) else 0
                w_spd_kmh = hourly.get("wind_speed_10m", [0])[i] if i < len(hourly.get("wind_speed_10m", [])) else 0
                w_spd = w_spd_kmh / 1.852
                
                daylight_hours.append({
                    "hour": hour,
                    "precip": precip,
                    "w_spd": w_spd,
                    "good": precip == 0 and w_spd >= 8  # 无雨且风速>=8kts
                })
    
    # 统计连续无雨且风力达标的小时
    max_consecutive = 0
    current_consecutive = 0
    for h in daylight_hours:
        if h["good"]:
            current_consecutive += 1
            max_consecutive = max(max_consecutive, current_consecutive)
        else:
            current_consecutive = 0
    
    return max_consecutive

def calculate_ridge_ortho_lift(w_spd, w_dir, ridge_orient):
    normal_angle = (ridge_orient + 90) % 360
    theta = abs(w_dir - normal_angle) % 360
    if theta > 180:
        theta = 360 - theta
    
    if w_spd < V7_PARAMS["ORTHO_MIN_SPEED"]:
        return 0
    
    sin_theta = math.sin(math.radians(theta))
    base_lift = sin_theta * 15
    
    if sin_theta > 0.1 and w_spd > V7_PARAMS["ORTHO_MIN_SPEED"]:
        min_lift = 15 * V7_PARAMS["ORTHO_MIN_RATIO"]
        base_lift = max(base_lift, min_lift)
    
    return base_lift

def calculate_precip_penalty_v7(precip):
    if precip <= 0:
        return 0
    
    threshold = V7_PARAMS["PRECIP_HALFLIFE"]
    k = math.log(3) / threshold
    penalty = 30 / (1 + math.exp(-k * (precip - threshold)))
    
    return min(30, penalty)

def calculate_wind_lift_score_v7(w_spd, site_type):
    V = w_spd
    
    if V < V7_PARAMS["V_MIN"]:
        score = 15 * math.exp(-(V7_PARAMS["V_MIN"] - V) / V7_PARAMS["TAU"])
    elif V7_PARAMS["V_OPT_MIN"] <= V <= V7_PARAMS["V_OPT_MAX"]:
        score = 15
    elif V > V7_PARAMS["V_MAX"]:
        score = max(0, 15 - (V - V7_PARAMS["V_MAX"]) * 1.5)
    else:
        if V < V7_PARAMS["V_OPT_MIN"]:
            score = 15 * (V - V7_PARAMS["V_MIN"]) / (V7_PARAMS["V_OPT_MIN"] - V7_PARAMS["V_MIN"])
        else:
            score = 15 * (1 - (V - V7_PARAMS["V_OPT_MAX"]) / (V7_PARAMS["V_MAX"] - V7_PARAMS["V_OPT_MAX"]))
    
    return max(0, min(15, score))

def calculate_thermal_convection_v7(temp_2m, temp_850hPa, w_spd):
    delta_theta = temp_2m - temp_850hPa
    
    if delta_theta < 0:
        W_star = abs(delta_theta) * 0.5
    else:
        W_star = 0
    
    if w_spd < V7_PARAMS["WSTAR_LOW_WIND_THRESHOLD"] and W_star > 2:
        compensation = min(5, (W_star - 2) * V7_PARAMS["THERMAL_COMPENSATION"])
    else:
        compensation = 0
    
    return W_star, compensation

def calculate_sea_breeze_index_v7(site_type, temp_2m, sst=None):
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
    if season != "春":
        return 0
    
    if site_type not in ["Ridge", "Karst"]:
        return 0
    
    if 135 <= w_dir <= 225:
        southness = 1 - abs(w_dir - 180) / 45
        return southness * 10
    return 0

def calculate_v7_score(site, weather_data, date_obj, season, optimum_hours=0):
    """V7 评分计算"""
    name = site["name"]
    site_type = get_site_type(name)
    
    temp_2m = weather_data.get("temp_2m", 15)
    w_spd = weather_data.get("w_spd", 10)
    w_dir = weather_data.get("w_dir", 180)
    cloud = weather_data.get("cloud", 50)
    precip = weather_data.get("precip", 0)
    pressure = weather_data.get("pressure", 1013)
    temp_850hPa = weather_data.get("temp_850hPa", 10)
    
    # === V7 核心计算 ===
    
    # 1. 基础分数
    baseline = site.get("baseline", {}).get(season, 0.85)
    peak_weight = get_peak_weight_v7(site, date_obj, season)
    base_score = 65 * baseline * peak_weight
    
    # 2. 风速升力得分
    wind_lift_score = calculate_wind_lift_score_v7(w_spd, site_type)
    
    # 3. Ridge_Ortho_Lift
    if site_type in ["Ridge", "Karst"]:
        ortho_lift = calculate_ridge_ortho_lift(w_spd, w_dir, site.get("ridge_orient", 90))
    else:
        ortho_lift = 0
    
    # 4. 热力对流补偿
    W_star, thermal_compensation = calculate_thermal_convection_v7(
        temp_2m, temp_850hPa, w_spd
    )
    
    # 5. 海陆风指数
    sea_breeze_score = calculate_sea_breeze_index_v7(
        site_type, temp_2m, weather_data.get("sst")
    )
    
    # 6. 春季南风增强
    south_wind_boost = calculate_spring_south_wind_boost(w_dir, site_type, season)
    
    # 7. V7 地理溢价 (新增!)
    geo_bonus = calculate_geographic_bonus(name, season)
    
    # === 传统因子 ===
    
    # 逆温层
    delta_T = temp_850hPa - (temp_2m - 6.5 * 2.5)
    inversion_penalty = 0
    if delta_T > 0:
        inversion_penalty = min(15, delta_T * 5)
    
    # 云量
    cloud_penalty = 0
    if cloud > 85:
        cloud_penalty = 25
    elif cloud > 70:
        cloud_penalty = 10
    
    # 降水
    precip_penalty = calculate_precip_penalty_v7(precip)
    
    # 侧风警告
    wind_diff = abs(w_dir - site.get("fav_wind", {}).get(season, 180))
    if wind_diff > 180:
        wind_diff = 360 - wind_diff
    warnings = []
    if wind_diff > 45:
        warnings.append(f"侧风偏航({wind_diff}°)")
    
    # === 最终评分计算 ===
    score = base_score
    
    # 组合升力得分
    total_wind_score = wind_lift_score
    if ortho_lift > 0:
        total_wind_score = max(wind_lift_score, ortho_lift) * 0.6 + min(wind_lift_score, ortho_lift) * 0.4
    
    score += total_wind_score
    score += thermal_compensation
    score += sea_breeze_score
    score += south_wind_boost
    score += geo_bonus  # V7 地理溢价
    score -= inversion_penalty
    score -= cloud_penalty
    score -= precip_penalty
    
    # === V7 降水窗逻辑 (关键改进!) ===
    if optimum_hours >= V7_PARAMS["MIN_CONSECUTIVE_HOURS"]:
        # 有连续3小时以上无雨且风力达标，不应低于40分
        score = max(score, V7_PARAMS["MIN_OPTIMUM_HOURS_SCORE"])
        warnings.append(f"降水窗开启({optimum_hours}小时)")
    
    # === V7 物候修正 (关键改进!) ===
    phenology_mult = calculate_phenology_multiplier(name, date_obj, score)
    if phenology_mult > 1.0:
        score *= phenology_mult
        warnings.append("物候爆发增益(1.2x)")
    
    # 硬约束
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
        "geo_bonus": round(geo_bonus, 1),
        "inversion_penalty": inversion_penalty,
        "cloud_penalty": cloud_penalty,
        "precip_penalty": round(precip_penalty, 1),
        "optimum_hours": optimum_hours,
        "phenology_mult": phenology_mult,
        "warnings": warnings,
        "site_type": site_type
    }

def get_peak_weight_v7(site, date_obj, season):
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

HOTSPOTS_V7 = [
    {"name": "都统岩", "lat": 30.76, "lon": 103.42, "type": "内陆山脊", "ridge_orient": 30,
     "fav_wind": {"春": 180, "秋": 0}, "baseline": {"春": 0.85, "秋": 0.80},
     "peak_matrix": {"春": {3: [0.6, 0.8, 1.0], 4: [1.2, 1.5, 1.3], 5: [1.1, 0.9, 0.6]}}},
    {"name": "龙泉山", "lat": 30.556, "lon": 104.307, "type": "内陆山脊", "ridge_orient": 20,
     "fav_wind": {"春": 180, "秋": 0}, "baseline": {"春": 0.85, "秋": 0.80},
     "peak_matrix": {"春": {3: [0.7, 0.9, 1.1], 4: [1.3, 1.4, 1.2], 5: [1.0, 0.8, 0.5]}}},
    {"name": "尧山电视台", "lat": 25.30, "lon": 110.38, "type": "喀斯特山脊", "ridge_orient": 135,
     "fav_wind": {"春": 165, "秋": 345}, "baseline": {"春": 0.90, "秋": 0.85},
     "peak_matrix": {"春": {3: [0.8, 1.0, 1.3], 4: [1.4, 1.6, 1.5], 5: [1.2, 0.9, 0.6]}}},
    {"name": "冠头岭", "lat": 21.45, "lon": 109.05, "type": "滨海廊道", "ridge_orient": 90,
     "fav_wind": {"春": 190, "秋": 20}, "baseline": {"春": 0.90, "秋": 0.60},
     "peak_matrix": {"春": {3: [0.8, 1.1, 1.4], 4: [1.6, 1.5, 1.2], 5: [0.9, 0.6, 0.4]}}},
    {"name": "九龙山", "lat": 29.5, "lon": 121.5, "type": "内陆山脊", "ridge_orient": 45,
     "fav_wind": {"春": 135, "秋": 315}, "baseline": {"春": 0.80, "秋": 0.80},
     "peak_matrix": {"春": {3: [0.6, 0.8, 1.0], 4: [1.2, 1.4, 1.2], 5: [1.0, 0.7, 0.5]}}},
    {"name": "渔洋山", "lat": 31.2, "lon": 120.4, "type": "滨海廊道", "ridge_orient": 90,
     "fav_wind": {"春": 135, "秋": 315}, "baseline": {"春": 0.80, "秋": 0.80},
     "peak_matrix": {"春": {3: [0.6, 0.8, 1.0], 4: [1.1, 1.3, 1.1], 5: [0.8, 0.6, 0.4]}}},
    {"name": "南汇东滩", "lat": 30.9, "lon": 121.9, "type": "河口湿地", "ridge_orient": 0,
     "fav_wind": {"春": 90, "秋": 270}, "baseline": {"春": 0.75, "秋": 0.75},
     "peak_matrix": {"春": {3: [0.5, 0.7, 0.9], 4: [1.0, 1.2, 1.0], 5: [0.7, 0.5, 0.3]}}},
    {"name": "崇明东滩", "lat": 31.5, "lon": 121.9, "type": "河口湿地", "ridge_orient": 0,
     "fav_wind": {"春": 90, "秋": 270}, "baseline": {"春": 0.75, "秋": 0.75},
     "peak_matrix": {"春": {3: [0.5, 0.7, 0.9], 4: [1.0, 1.2, 1.0], 5: [0.7, 0.5, 0.3]}}},
]

def get_weather_v7(lat, lon, target_date, is_high_alt=False):
    """V7 天气获取"""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,precipitation,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,pressure_msl,surface_pressure",
        "daily": "temperature_2m_max,temperature_2m_min",
        "timezone": "Asia/Shanghai",
        "forecast_days": 7
    }
    
    if is_high_alt:
        params["hourly"] += ",wind_speed_925hPa,wind_direction_925hPa,temperature_850hPa"
    
    resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
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
                "pressure": hourly.get("surface_pressure", hourly.get("pressure_msl", 1013))[i] if isinstance(hourly.get("surface_pressure", hourly.get("pressure_msl")), list) else (hourly.get("surface_pressure") or hourly.get("pressure_msl") or 1013),
            }
            
            # 确保 pressure 是数值
            if isinstance(weather["pressure"], list):
                weather["pressure"] = weather["pressure"][i]
            
            if is_high_alt and "wind_speed_925hPa" in hourly:
                w_spd_925 = hourly["wind_speed_925hPa"][i]
                if w_spd_925 and w_spd_925 > 0:
                    weather["w_spd"] = w_spd_925 / 1.852
                    weather["w_dir_925"] = hourly["wind_direction_925hPa"][i]
                    weather["temp_850hPa"] = hourly["temperature_850hPa"][i]
            
            if "temp_850hPa" not in weather:
                weather["temp_850hPa"] = weather["temp_2m"] - 6.5
            
            return weather, hourly  # 返回天气数据和小时数据
    
    return None, None

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
    print("🦅 猛禽迁徙预测模型 V7.0 - 地理溢价与时间物候窗")
    print("=" * 70)
    
    today = datetime.date(2026, 3, 24)
    season = "春"
    
    results = []
    
    print(f"\n📅 预测日期: {today} ({season}季)")
    print("\n正在计算各站点评分 (V7算法)...\n")
    
    for site in HOTSPOTS_V7:
        print(f"→ {site['name']}...")
        
        high_alt = is_high_altitude(site["name"])
        weather, hourly_data = get_weather_v7(site["lat"], site["lon"], today, high_alt)
        
        if weather:
            # V7 降水窗逻辑
            optimum_hours = 0
            if hourly_data:
                optimum_hours = calculate_optimum_hours(hourly_data, today)
            
            v7_result = calculate_v7_score(site, weather, today, season, optimum_hours)
            
            print(f"   天气: {weather['temp_2m']:.1f}°C, 风速{weather['w_spd']:.1f}kts, 风向{weather['w_dir']}°")
            print(f"   V7得分: {v7_result['score']}分 {get_rating(v7_result['score'])}")
            print(f"   - 综合风力: {v7_result['total_wind']}")
            print(f"   - 地理溢价: +{v7_result['geo_bonus']}")
            print(f"   - 物候增益: {v7_result['phenology_mult']}x")
            print(f"   - 降水窗: {optimum_hours}小时")
            print(f"   - 降水惩罚: -{v7_result['precip_penalty']}")
            print(f"   - 警告: {v7_result['warnings']}")
            print()
            
            results.append({
                "site": site["name"],
                "score": v7_result["score"],
                "weather": weather,
                "detail": v7_result,
                "optimum_hours": optimum_hours
            })
        else:
            print(f"   ❌ 无法获取天气数据")
    
    # 汇总
    print("\n" + "=" * 70)
    print("📊 V7 模型预测结果汇总")
    print("=" * 70)
    
    print(f"\n{'站点':<12} {'V7':<6} {'V6':<6} {'V5':<6} {'V4':<6} {'评级'}")
    print("-" * 50)
    
    v6_scores = {"都统岩": 36, "龙泉山": 51, "尧山电视台": 46, "冠头岭": 81, "九龙山": 0, "渔洋山": 0, "南汇东滩": 12, "崇明东滩": 1}
    v5_scores = {"都统岩": 31, "龙泉山": 47, "尧山电视台": 37, "冠头岭": 87, "九龙山": 0, "渔洋山": 0, "南汇东滩": 6, "崇明东滩": 0}
    v4_scores = {"都统岩": 29, "龙泉山": 33, "尧山电视台": 64, "冠头岭": 66, "九龙山": 14, "渔洋山": 9, "南汇东滩": 13, "崇明东滩": 11}
    
    for r in results:
        v6 = v6_scores.get(r["site"], 0)
        diff = r["score"] - v6
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{r['site']:<12} {r['score']:<6} {v6:<6} {diff_str:<6} {get_rating(r['score'])}")
    
    print("\n" + "=" * 70)
    print("✅ V7 计算完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
