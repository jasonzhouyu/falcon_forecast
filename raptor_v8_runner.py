#!/usr/bin/env python3
"""
猛禽迁徙预测模型 V8 - 山脊韧性模型与热力-动力互补
改进：
1. Ridge_Linear_Gain: 长度>50km山脊1.25x增益
2. 热力-动力互补: 风好时减免热力惩罚70%
3. Cloud_Base_Tolerance: 条件满足时降低云量惩罚
4. Mega-Raptor_Bonus: 3月下旬大雕爆发系数
"""
import datetime
import math
import json
import requests
import numpy as np

# ============== V8 核心参数 ==============

SITE_TYPES = {
    "Ridge": ["都统岩", "龙泉山", "九龙山"],
    "Karst": ["尧山电视台"],
    "Coastal": ["冠头岭", "渔洋山"],
    "Wetland": ["南汇东滩", "崇明东滩"]
}

HIGH_ALTITUDE_SITES = ["都统岩", "龙泉山", "尧山电视台", "九龙山"]

# V8 地理溢价
GEO_BONUS = {
    "冠头岭": {"春": 15, "秋": 5},
    "龙泉山": {"春": 10, "秋": 8},
    "都统岩": {"春": 10, "秋": 8},
}

# V8 山脊韧性 - 长度>50km的山脊有额外增益
RIDGE_RESILIENCE = {
    "都统岩": {"length_km": 80, "gain": 1.25},  # 龙泉山脉北段
    "龙泉山": {"length_km": 60, "gain": 1.25},  # 龙泉山
    "尧山电视台": {"length_km": 30, "gain": 1.0},  # 喀斯特孤峰
}

# V8 物候数据
PHENOLOGY_DATA = {
    "都统岩": {"春": {3: {"species": "赤腹鹰", "avg_count": 150, "peak_days": list(range(20, 31))}}},
    "龙泉山": {"春": {3: {"species": "灰脸鵟鹰", "avg_count": 180, "peak_days": list(range(20, 31))}}},
    "尧山电视台": {"春": {3: {"species": "赤腹鹰", "avg_count": 250, "peak_days": list(range(15, 27))}}},
    "冠头岭": {"春": {3: {"species": "黑冠鹃隼", "avg_count": 300, "peak_days": list(range(1, 16))}}},
    "九龙山": {"春": {3: {"species": "普通鵟", "avg_count": 60, "peak_days": list(range(20, 31))}}},
    "渔洋山": {"春": {3: {"species": "灰脸鵟鹰", "avg_count": 80, "peak_days": list(range(20, 31))}}},
    "南汇东滩": {"春": {3: {"species": "鹗", "avg_count": 40, "peak_days": list(range(15, 26))}}},
    "崇明东滩": {"春": {3: {"species": "鹗", "avg_count": 35, "peak_days": list(range(15, 26))}}},
}

# V8 Mega-Raptor 爆发日期 (3月下旬)
MEGA_RAPTOR_BONUS_SITES = ["龙泉山", "尧山电视台"]
MEGA_RAPTOR_BONUS_VALUE = 10

V8_PARAMS = {
    "V_MIN": 8,
    "V_OPT_MIN": 15,
    "V_OPT_MAX": 30,
    "V_MAX": 45,
    "TAU": 5,
    "ORTHO_MIN_SPEED": 10,
    "ORTHO_MIN_RATIO": 0.40,
    "PRECIP_HALFLIFE": 0.5,
    "MIN_CONSECUTIVE_HOURS": 3,
    "MIN_OPTIMUM_HOURS_SCORE": 40,
    "PHENOLOGY_MULTIPLIER": 1.2,
    # V8 新增
    "TEMP_COLD_THRESHOLD": 15,  # 温度低于此值认为冷
    "WIND_FOR_SLOPE_SOARING": 12,  # 风速大于此可做纯动力滑翔
    "WIND_ANGLE_FOR_SLOPE": 30,  # 风向夹角小于此可做纯动力滑翔
    "THERMAL_PENALTY_REDUCTION": 0.7,  # 热力惩罚减免比例
    "CLOUD_TOLERANCE_THRESHOLD": 70,  # 云量容忍阈值
    "CLOUD_PENALTY_REDUCTION": 0.6,  # 云量惩罚降低比例 (从-25降到-10)
}

def get_site_type(site_name):
    for site_type, sites in SITE_TYPES.items():
        if site_name in sites:
            return site_type
    return "Ridge"

def is_high_altitude(site_name):
    return site_name in HIGH_ALTITUDE_SITES

def calculate_geographic_bonus(site_name, season):
    if site_name in GEO_BONUS:
        return GEO_BONUS[site_name].get(season, 0)
    return 0

def calculate_ridge_resilience(site_name):
    """V8 山脊韧性模型 - 长度>50km的山脊有1.25x增益"""
    if site_name in RIDGE_RESILIENCE:
        return RIDGE_RESILIENCE[site_name]["gain"]
    return 1.0

def calculate_mega_raptor_bonus(site_name, date_obj):
    """V8 Mega-Raptor Bonus - 3月下旬大雕爆发"""
    month = date_obj.month
    day = date_obj.day
    
    if site_name in MEGA_RAPTOR_BONUS_SITES:
        if month == 3 and day >= 20:
            return MEGA_RAPTOR_BONUS_VALUE
    
    return 0

def calculate_thermal_dynamic_compensation(temp_2m, w_spd, w_dir, ridge_orient, base_thermal_penalty):
    """
    V8 热力-动力互补逻辑
    若温度<15℃但风速>12kts且风向夹角<30°，则减免热力惩罚70%
    """
    # 温度是否够热
    is_cold = temp_2m < V8_PARAMS["TEMP_COLD_THRESHOLD"]
    
    # 风力是否足够做纯动力滑翔
    is_windy_enough = w_spd > V8_PARAMS["WIND_FOR_SLOPE_SOARING"]
    
    # 风向是否正向山脊
    wind_diff = abs(w_dir - ridge_orient) % 180
    if wind_diff > 90:
        wind_diff = 180 - wind_diff
    is_favorable_direction = wind_diff < V8_PARAMS["WIND_ANGLE_FOR_SLOPE"]
    
    # 如果满足所有条件，可以减免热力惩罚
    if is_cold and is_windy_enough and is_favorable_direction:
        reduced_penalty = base_thermal_penalty * (1 - V8_PARAMS["THERMAL_PENALTY_REDUCTION"])
        return reduced_penalty, True
    
    return base_thermal_penalty, False

def calculate_cloud_tolerance(cloud, precip, w_dir, season):
    """
    V8 云底高度容忍度
    若云量>70%但降水=0且风向为顺风(南风分量)，则降低云量惩罚
    """
    # 是否无降水
    if precip > 0:
        return 0, False
    
    # 是否有南风分量 (对于春季迁徙有利)
    if 135 <= w_dir <= 225:
        has_south_component = True
    else:
        has_south_component = False
    
    # 是否满足容忍条件
    if cloud > V8_PARAMS["CLOUD_TOLERANCE_THRESHOLD"] and has_south_component:
        # 原始惩罚 -25，降低到 -10
        original_penalty = 25
        reduced_penalty = original_penalty * (1 - V8_PARAMS["CLOUD_PENALTY_REDUCTION"])
        return reduced_penalty, True
    
    # 默认云量惩罚
    if cloud > 85:
        return 25, False
    elif cloud > 70:
        return 10, False
    
    return 0, False

def calculate_phenology_multiplier(site_name, date_obj, base_score):
    month = date_obj.month
    day = date_obj.day
    
    if site_name in PHENOLOGY_DATA:
        season_data = PHENOLOGY_DATA[site_name].get("春", {})
        if month in season_data:
            month_data = season_data[month]
            peak_days = month_data.get("peak_days", [])
            avg_count = month_data.get("avg_count", 0)
            
            phenology_score = math.log(avg_count + 1)
            
            if day in peak_days:
                if base_score < 40:
                    return V8_PARAMS["PHENOLOGY_MULTIPLIER"]
    
    return 1.0

def calculate_optimum_hours(weather_hourly, target_date):
    hourly = weather_hourly
    times = hourly.get("time", [])
    target_str = target_date.strftime("%Y-%m-%d")
    
    daylight_hours = []
    for i, t in enumerate(times):
        if target_str in t:
            hour = int(t.split("T")[1].split(":")[0])
            if 8 <= hour <= 18:
                precip_list = hourly.get("precipitation", [])
                w_spd_list = hourly.get("wind_speed_10m", [])
                precip = precip_list[i] if i < len(precip_list) else 0
                w_spd = (w_spd_list[i] / 1.852) if i < len(w_spd_list) else 0
                
                daylight_hours.append({
                    "hour": hour,
                    "precip": precip,
                    "w_spd": w_spd,
                    "good": precip == 0 and w_spd >= 8
                })
    
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
    
    if w_spd < V8_PARAMS["ORTHO_MIN_SPEED"]:
        return 0
    
    sin_theta = math.sin(math.radians(theta))
    base_lift = sin_theta * 15
    
    if sin_theta > 0.1 and w_spd > V8_PARAMS["ORTHO_MIN_SPEED"]:
        min_lift = 15 * V8_PARAMS["ORTHO_MIN_RATIO"]
        base_lift = max(base_lift, min_lift)
    
    return base_lift

def calculate_precip_penalty(precip):
    if precip <= 0:
        return 0
    
    threshold = V8_PARAMS["PRECIP_HALFLIFE"]
    k = math.log(3) / threshold
    penalty = 30 / (1 + math.exp(-k * (precip - threshold)))
    
    return min(30, penalty)

def calculate_wind_lift_score(w_spd, site_type):
    V = w_spd
    
    if V < V8_PARAMS["V_MIN"]:
        score = 15 * math.exp(-(V8_PARAMS["V_MIN"] - V) / V8_PARAMS["TAU"])
    elif V8_PARAMS["V_OPT_MIN"] <= V <= V8_PARAMS["V_OPT_MAX"]:
        score = 15
    elif V > V8_PARAMS["V_MAX"]:
        score = max(0, 15 - (V - V8_PARAMS["V_MAX"]) * 1.5)
    else:
        if V < V8_PARAMS["V_OPT_MIN"]:
            score = 15 * (V - V8_PARAMS["V_MIN"]) / (V8_PARAMS["V_OPT_MIN"] - V8_PARAMS["V_MIN"])
        else:
            score = 15 * (1 - (V - V8_PARAMS["V_OPT_MAX"]) / (V8_PARAMS["V_MAX"] - V8_PARAMS["V_OPT_MAX"]))
    
    return max(0, min(15, score))

def calculate_spring_south_wind_boost(w_dir, site_type, season):
    if season != "春":
        return 0
    if site_type not in ["Ridge", "Karst"]:
        return 0
    if 135 <= w_dir <= 225:
        southness = 1 - abs(w_dir - 180) / 45
        return southness * 10
    return 0

def calculate_sea_breeze_index(site_type, temp_2m, sst=None):
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
    return 0

def calculate_v8_score(site, weather_data, date_obj, season, optimum_hours=0):
    """V8 评分计算"""
    name = site["name"]
    site_type = get_site_type(name)
    
    temp_2m = weather_data.get("temp_2m", 15)
    w_spd = weather_data.get("w_spd", 10)
    w_dir = weather_data.get("w_dir", 180)
    cloud = weather_data.get("cloud", 50)
    precip = weather_data.get("precip", 0)
    pressure = weather_data.get("pressure", 1013)
    temp_850hPa = weather_data.get("temp_850hPa", 10)
    
    # === V8 核心计算 ===
    
    # 1. 基础分数
    baseline = site.get("baseline", {}).get(season, 0.85)
    peak_weight = get_peak_weight(site, date_obj, season)
    base_score = 65 * baseline * peak_weight
    
    # 2. V8 山脊韧性 (新增!)
    ridge_resilience = calculate_ridge_resilience(name)
    base_score *= ridge_resilience
    
    # 3. 风速升力得分
    wind_lift_score = calculate_wind_lift_score(w_spd, site_type)
    
    # 4. Ridge_Ortho_Lift
    if site_type in ["Ridge", "Karst"]:
        ortho_lift = calculate_ridge_ortho_lift(w_spd, w_dir, site.get("ridge_orient", 90))
    else:
        ortho_lift = 0
    
    # 5. 海陆风指数
    sea_breeze_score = calculate_sea_breeze_index(site_type, temp_2m, weather_data.get("sst"))
    
    # 6. 春季南风增强
    south_wind_boost = calculate_spring_south_wind_boost(w_dir, site_type, season)
    
    # 7. 地理溢价
    geo_bonus = calculate_geographic_bonus(name, season)
    
    # 8. V8 Mega-Raptor Bonus (新增!)
    mega_raptor_bonus = calculate_mega_raptor_bonus(name, date_obj)
    
    # === 惩罚项计算 ===
    
    # 逆温层
    delta_T = temp_850hPa - (temp_2m - 6.5 * 2.5)
    inversion_penalty = 0
    if delta_T > 0:
        inversion_penalty = min(15, delta_T * 5)
    
    # 热力不足惩罚 + V8 热力-动力互补 (新增!)
    thermal_penalty = 0
    if temp_2m < V8_PARAMS["TEMP_COLD_THRESHOLD"]:
        thermal_penalty = 15  # 基础热力不足惩罚
        thermal_penalty, was_compensated = calculate_thermal_dynamic_compensation(
            temp_2m, w_spd, w_dir, site.get("ridge_orient", 90), thermal_penalty
        )
    thermal_penalty_applied = was_compensated if 'was_compensated' in locals() else False
    
    # 云量惩罚 + V8 云底高度容忍度 (新增!)
    cloud_penalty, cloud_tolerated = calculate_cloud_tolerance(cloud, precip, w_dir, season)
    
    # 降水惩罚
    precip_penalty = calculate_precip_penalty(precip)
    
    # 侧风警告
    wind_diff = abs(w_dir - site.get("fav_wind", {}).get(season, 180))
    if wind_diff > 180:
        wind_diff = 360 - wind_diff
    warnings = []
    if wind_diff > 45:
        warnings.append(f"侧风偏航({wind_diff}°)")
    if thermal_penalty_applied:
        warnings.append("热力-动力互补(减免70%)")
    if cloud_tolerated:
        warnings.append("云底高度容忍")
    
    # === 最终评分计算 ===
    score = base_score
    
    total_wind_score = wind_lift_score
    if ortho_lift > 0:
        total_wind_score = max(wind_lift_score, ortho_lift) * 0.6 + min(wind_lift_score, ortho_lift) * 0.4
    
    score += total_wind_score
    score += sea_breeze_score
    score += south_wind_boost
    score += geo_bonus
    score += mega_raptor_bonus  # V8 Mega-Raptor
    score -= inversion_penalty
    score -= thermal_penalty
    score -= cloud_penalty
    score -= precip_penalty
    
    # 降水窗逻辑
    if optimum_hours >= V8_PARAMS["MIN_CONSECUTIVE_HOURS"]:
        score = max(score, V8_PARAMS["MIN_OPTIMUM_HOURS_SCORE"])
        warnings.append(f"降水窗开启({optimum_hours}小时)")
    
    # 物候修正
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
        "ridge_resilience": ridge_resilience,
        "total_wind": round(total_wind_score, 1),
        "sea_breeze": round(sea_breeze_score, 1),
        "south_wind_boost": round(south_wind_boost, 1),
        "geo_bonus": round(geo_bonus, 1),
        "mega_raptor_bonus": mega_raptor_bonus,
        "inversion_penalty": inversion_penalty,
        "thermal_penalty": round(thermal_penalty, 1),
        "cloud_penalty": round(cloud_penalty, 1),
        "precip_penalty": round(precip_penalty, 1),
        "optimum_hours": optimum_hours,
        "phenology_mult": phenology_mult,
        "warnings": warnings,
        "site_type": site_type
    }

def get_peak_weight(site, date_obj, season):
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

HOTSPOTS_V8 = [
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

def get_weather_v8(lat, lon, target_date, is_high_alt=False):
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
                "pressure": hourly.get("surface_pressure", hourly.get("pressure_msl", [1013]))[i] if isinstance(hourly.get("surface_pressure", hourly.get("pressure_msl")), list) else 1013,
            }
            
            if is_high_alt and "wind_speed_925hPa" in hourly:
                w_spd_925 = hourly["wind_speed_925hPa"][i]
                if w_spd_925 and w_spd_925 > 0:
                    weather["w_spd"] = w_spd_925 / 1.852
                    weather["temp_850hPa"] = hourly["temperature_850hPa"][i]
            
            if "temp_850hPa" not in weather:
                weather["temp_850hPa"] = weather["temp_2m"] - 6.5
            
            return weather, hourly
    
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
    print("🦅 猛禽迁徙预测模型 V8.0 - 山脊韧性模型与热力-动力互补")
    print("=" * 70)
    
    today = datetime.date(2026, 3, 24)
    season = "春"
    
    results = []
    
    print(f"\n📅 预测日期: {today} ({season}季)")
    print("\n正在计算各站点评分 (V8算法)...\n")
    
    for site in HOTSPOTS_V8:
        print(f"→ {site['name']}...")
        
        high_alt = is_high_altitude(site["name"])
        weather, hourly_data = get_weather_v8(site["lat"], site["lon"], today, high_alt)
        
        if weather:
            optimum_hours = 0
            if hourly_data:
                optimum_hours = calculate_optimum_hours(hourly_data, today)
            
            v8_result = calculate_v8_score(site, weather, today, season, optimum_hours)
            
            print(f"   天气: {weather['temp_2m']:.1f}°C, 风速{weather['w_spd']:.1f}kts, 风向{weather['w_dir']}°")
            print(f"   V8得分: {v8_result['score']}分 {get_rating(v8_result['score'])}")
            print(f"   - 山脊韧性: {v8_result['ridge_resilience']}x")
            print(f"   - Mega-Raptor: +{v8_result['mega_raptor_bonus']}")
            print(f"   - 综合风力: {v8_result['total_wind']}")
            print(f"   - 热力惩罚: -{v8_result['thermal_penalty']}")
            print(f"   - 云量惩罚: -{v8_result['cloud_penalty']}")
            print(f"   - 警告: {v8_result['warnings']}")
            print()
            
            results.append({
                "site": site["name"],
                "score": v8_result["score"],
                "detail": v8_result
            })
        else:
            print(f"   ❌ 无法获取天气数据")
    
    # 汇总
    print("\n" + "=" * 70)
    print("📊 V8 模型预测结果汇总")
    print("=" * 70)
    
    print(f"\n{'站点':<12} {'V8':<6} {'V7':<6} {'变化':<6} {'评级'}")
    print("-" * 45)
    
    v7_scores = {"都统岩": 46, "龙泉山": 61, "尧山电视台": 46, "冠头岭": 96, "九龙山": 0, "渔洋山": 0, "南汇东滩": 14, "崇明东滩": 1}
    
    for r in results:
        v7 = v7_scores.get(r["site"], 0)
        diff = r["score"] - v7
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{r['site']:<12} {r['score']:<6} {v7:<6} {diff_str:<6} {get_rating(r['score'])}")
    
    print("\n" + "=" * 70)
    print("✅ V8 计算完成")
    print("=" * 70)

if __name__ == "__main__":
    main()
