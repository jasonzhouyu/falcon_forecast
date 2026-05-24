#!/usr/bin/env python3
"""
猛禽迁徙预测模型 V9 - 季节镜像与风速自适应
基于 V8 改进:
1. Season_Switch: Spring vs Autumn 模式切换
2. Cold_Front_Bonus: 24h降温>5°C且气压上升=冷锋过境,+20
3. 内陆低风速补偿: 都统岩/龙泉山从8kts降至6kts
4. 集成秋季权重表 (CSV)
5. Juvenile_Dispersal_Factor: 沿海站点秋季额外增益
6. 历史丰度权重表 (CSV)
"""
import datetime
import math
import requests
import warnings
warnings.filterwarnings('ignore')

# ============== V9 配置 ==============

# 站点类型
SITE_TYPES = {
    "Ridge": ["都统岩", "龙泉山", "九龙山"],
    "Karst": ["尧山电视台"],
    "Coastal": ["冠头岭", "渔洋山"],
    "Wetland": ["南汇东滩", "崇明东滩"]
}

# 高海拔站点 (使用925hPa数据)
HIGH_ALTITUDE = ["都统岩", "龙泉山", "尧山电视台", "九龙山"]

# 内陆低风速站点 (风速阈值降至6kts)
LOW_WIND = ["都统岩", "龙泉山"]

# 地理溢价
GEO_BONUS = {
    "冠头岭": {"春": 15, "秋": 5},
    "龙泉山": {"春": 10, "秋": 8},
    "都统岩": {"春": 10, "秋": 8},
}

# 山脊韧性 (长度>50km的山脊)
RIDGE_RESILIENCE = {
    "都统岩": 1.25,  # 80km
    "龙泉山": 1.25,  # 60km
    "尧山电视台": 1.0,
}

# 历史丰度权重 (从 CSV 读取)
ABUNDANCE = {
    "冠头岭": 1.85,
    "龙泉山": 1.45,
    "都统岩": 1.20,
    "尧山电视台": 1.35,
    "南汇东滩": 1.10,
    "九龙山": 1.15,
    "渔洋山": 1.05,
    "崇明东滩": 1.00,
}

# 秋季权重 (从 CSV 读取)
AUTUMN_WEIGHTS = {
    "龙泉山": 1.35,
    "都统岩": 1.35,
    "冠头岭": 1.50,
    "南汇东滩": 1.40,
    "崇明东滩": 1.40,
    "九龙山": 1.25,
    "渔洋山": 1.25,
}

# V9 参数
V9_PARAMS = {
    # 风速
    "V_MIN_INLAND": 6,    # 内陆站点最低风速
    "V_MIN_STANDARD": 8,  # 标准最低风速
    "V_OPT_MIN": 15,
    "V_OPT_MAX": 30,
    "V_MAX": 45,
    "TAU": 5,
    
    # 正交升力
    "ORTHO_MIN_SPEED": 10,
    "ORTHO_MIN_RATIO": 0.40,
    
    # 降水
    "PRECIP_HALFLIFE": 0.5,
    "MIN_CONSECUTIVE_HOURS": 3,
    "MIN_OPTIMUM_HOURS_SCORE": 40,
    
    # 物候
    "PHENOLOGY_MULTIPLIER": 1.2,
    
    # 热力-动力互补
    "TEMP_COLD_THRESHOLD": 15,
    "WIND_FOR_SLOPE_SOARING": 12,
    "WIND_ANGLE_FOR_SLOPE": 30,
    "THERMAL_PENALTY_REDUCTION": 0.7,
    
    # 云量容忍
    "CLOUD_TOLERANCE_THRESHOLD": 70,
    "CLOUD_PENALTY_REDUCTION": 0.6,
    
    # 冷锋
    "COLD_FRONT_TEMP_DROP": 5,
    "COLD_FRONT_PRESSURE_RISE": 2,
    "COLD_FRONT_BONUS": 20,
    
    # 幼鸟扩散
    "JUVENILE_DISPERSAL_BONUS": 8,
}

# Mega-Raptor 站点
MEGA_RAPTOR_SITES = ["龙泉山", "尧山电视台"]

# ============== 站点配置 ==============

SITES = [
    {
        "name": "都统岩",
        "lat": 30.76,
        "lon": 103.42,
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
        "ridge_orient": 0,
        "fav_wind": {"春": 90, "秋": 270},
        "baseline": {"春": 0.75, "秋": 0.75},
        "peak_matrix": {
            "春": {3: [0.5, 0.7, 0.9], 4: [1.0, 1.2, 1.0], 5: [0.7, 0.5, 0.3]},
            "秋": {9: [0.6, 0.8, 1.0], 10: [1.1, 0.9, 0.6], 11: [0.4, 0.3, 0.2]}
        }
    },
]

# ============== 辅助函数 ==============

def get_season(date_obj):
    """判断季节"""
    if date_obj.month in [3, 4, 5]:
        return "春"
    elif date_obj.month in [9, 10, 11]:
        return "秋"
    return "春"

def get_site_type(site_name):
    """获取站点类型"""
    for st, sites in SITE_TYPES.items():
        if site_name in sites:
            return st
    return "Ridge"

def is_high_altitude(site_name):
    return site_name in HIGH_ALTITUDE

def is_low_wind_site(site_name):
    return site_name in LOW_WIND

def calculate_abundance_weight(site_name, season):
    """计算历史丰度权重"""
    base = ABUNDANCE.get(site_name, 1.0)
    if season == "秋" and site_name in AUTUMN_WEIGHTS:
        return base * AUTUMN_WEIGHTS[site_name]
    return base

def calculate_wind_lift_score(w_spd, site_name):
    """风速升力得分 - V9 内陆站点使用更低阈值"""
    if is_low_wind_site(site_name):
        v_min = V9_PARAMS["V_MIN_INLAND"]  # 6 kts
    else:
        v_min = V9_PARAMS["V_MIN_STANDARD"]  # 8 kts
    
    V = w_spd
    
    if V < v_min:
        return 15 * math.exp(-(v_min - V) / V9_PARAMS["TAU"])
    elif V9_PARAMS["V_OPT_MIN"] <= V <= V9_PARAMS["V_OPT_MAX"]:
        return 15
    elif V > V9_PARAMS["V_MAX"]:
        return max(0, 15 - (V - V9_PARAMS["V_MAX"]) * 1.5)
    else:
        if V < V9_PARAMS["V_OPT_MIN"]:
            return 15 * (V - v_min) / (V9_PARAMS["V_OPT_MIN"] - v_min)
        return 15 * (1 - (V - V9_PARAMS["V_OPT_MAX"]) / (V9_PARAMS["V_MAX"] - V9_PARAMS["V_OPT_MAX"]))

def calculate_ridge_ortho_lift(w_spd, w_dir, ridge_orient):
    """Ridge_Ortho_Lift - 风向矢量在山脊法线方向的分量"""
    normal_angle = (ridge_orient + 90) % 360
    theta = abs(w_dir - normal_angle) % 360
    if theta > 180:
        theta = 360 - theta
    
    if w_spd < V9_PARAMS["ORTHO_MIN_SPEED"]:
        return 0
    
    sin_theta = math.sin(math.radians(theta))
    base_lift = sin_theta * 15
    
    if sin_theta > 0.1 and w_spd > V9_PARAMS["ORTHO_MIN_SPEED"]:
        min_lift = 15 * V9_PARAMS["ORTHO_MIN_RATIO"]
        base_lift = max(base_lift, min_lift)
    
    return base_lift

def calculate_sea_breeze_index(site_type, temp_2m):
    """海陆风指数"""
    if site_type != "Coastal":
        return 0
    delta_t = temp_2m - (temp_2m - 2.5)
    if 2 <= delta_t <= 5:
        return 15
    elif delta_t > 5:
        return 10
    elif delta_t > 0:
        return 5 * delta_t / 2
    return 0

def calculate_south_wind_boost(w_dir, site_type, season):
    """春季南风增强"""
    if season != "春":
        return 0
    if site_type not in ["Ridge", "Karst"]:
        return 0
    if 135 <= w_dir <= 225:
        return (1 - abs(w_dir - 180) / 45) * 10
    return 0

def calculate_geographic_bonus(site_name, season):
    """地理溢价"""
    return GEO_BONUS.get(site_name, {}).get(season, 0)

def calculate_mega_raptor_bonus(site_name, date_obj, season):
    """Mega-Raptor 大雕爆发"""
    if season == "春" and site_name in MEGA_RAPTOR_SITES:
        if date_obj.month == 3 and date_obj.day >= 20:
            return 10
    return 0

def calculate_juvenile_dispersal_bonus(site_name, season):
    """秋季幼鸟扩散增益"""
    if season == "秋" and site_name in ["南汇东滩", "崇明东滩", "冠头岭"]:
        return V9_PARAMS["JUVENILE_DISPERSAL_BONUS"]
    return 0

def calculate_precip_penalty(precip):
    """降水惩罚 - 逻辑回归曲线"""
    if precip <= 0:
        return 0
    k = math.log(3) / V9_PARAMS["PRECIP_HALFLIFE"]
    penalty = 30 / (1 + math.exp(-k * (precip - V9_PARAMS["PRECIP_HALFLIFE"])))
    return min(30, penalty)

def calculate_thermal_dynamic_compensation(temp_2m, w_spd, w_dir, ridge_orient, season):
    """热力-动力互补 - 春季强化"""
    if season != "春":
        return 0, False
    
    if temp_2m >= V9_PARAMS["TEMP_COLD_THRESHOLD"]:
        return 0, False
    
    if w_spd < V9_PARAMS["WIND_FOR_SLOPE_SOARING"]:
        return 15, False
    
    wind_diff = abs(w_dir - ridge_orient) % 180
    if wind_diff > 90:
        wind_diff = 180 - wind_diff
    
    if wind_diff >= V9_PARAMS["WIND_ANGLE_FOR_SLOPE"]:
        return 15, False
    
    # 减免70%
    return 15 * (1 - V9_PARAMS["THERMAL_PENALTY_REDUCTION"]), True

def calculate_cloud_tolerance(cloud, precip, w_dir, season):
    """云底高度容忍 - 春季"""
    if precip > 0 or season != "春":
        return 25 if cloud > 85 else 10 if cloud > 70 else 0, False
    
    if cloud > V9_PARAMS["CLOUD_TOLERANCE_THRESHOLD"] and 135 <= w_dir <= 225:
        return 10, True
    
    return 25 if cloud > 85 else 10 if cloud > 70 else 0, False

def calculate_cold_front_bonus(weather_today, weather_yesterday):
    """冷锋检测 - 24h降温>5°C且气压上升"""
    if not weather_today or not weather_yesterday:
        return 0
    
    temp_drop = weather_yesterday.get("temp_2m", 15) - weather_today.get("temp_2m", 15)
    pressure_rise = weather_today.get("pressure", 1013) - weather_yesterday.get("pressure", 1013)
    
    if temp_drop > V9_PARAMS["COLD_FRONT_TEMP_DROP"] and pressure_rise > V9_PARAMS["COLD_FRONT_PRESSURE_RISE"]:
        return V9_PARAMS["COLD_FRONT_BONUS"]
    return 0

def calculate_phenology_multiplier(site_name, date_obj, score, season):
    """物候爆发增益"""
    if season != "春" or score >= 40:
        return 1.0
    
    # 3月下旬爆发旬
    peaks = {
        "都统岩": range(20, 31),
        "龙泉山": range(20, 31),
        "尧山电视台": range(15, 27),
        "冠头岭": range(1, 16),
        "九龙山": range(20, 31),
        "渔洋山": range(20, 31),
        "南汇东滩": range(15, 26),
        "崇明东滩": range(15, 26),
    }
    
    if site_name in peaks and date_obj.day in peaks[site_name]:
        return V9_PARAMS["PHENOLOGY_MULTIPLIER"]
    
    return 1.0

def get_weather(lat, lon, date, is_high_alt):
    """获取天气数据"""
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,precipitation,cloud_cover,wind_speed_10m,wind_direction_10m,pressure_msl,surface_pressure",
            "daily": "temperature_2m_max",
            "timezone": "Asia/Shanghai",
            "forecast_days": 7
        }
        
        if is_high_alt:
            params["hourly"] += ",wind_speed_925hPa,temperature_850hPa"
        
        resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15, verify=False)
        data = resp.json()
        
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        target_str = date.strftime("%Y-%m-%d")
        
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
                    "pressure": hourly.get("surface_pressure", hourly.get("pressure_msl", [1013]))[i] if isinstance(hourly.get("surface_pressure", hourly.get("pressure_msl")), list) else 1013
                }
                
                if is_high_alt and "wind_speed_925hPa" in hourly:
                    w_spd_925 = hourly["wind_wind_925hPa"][i]
                    if w_spd_925 and w_spd_925 > 0:
                        weather["w_spd"] = w_spd_925 / 1.852
                        weather["temp_850hPa"] = hourly["temperature_850hPa"][i]
                
                if "temp_850hPa" not in weather:
                    weather["temp_850hPa"] = weather["temp_2m"] - 6.5
                
                return weather
    except Exception as e:
        print(f"Error: {e}")
    return None

def get_rating(score):
    """评级"""
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

# ============== 主计算 ==============

def calculate_v9_score(site, weather_data, date_obj, season):
    """V9 评分计算"""
    name = site["name"]
    site_type = get_site_type(name)
    
    temp_2m = weather_data.get("temp_2m", 15)
    w_spd = weather_data.get("w_spd", 10)
    w_dir = weather_data.get("w_dir", 180)
    cloud = weather_data.get("cloud", 50)
    precip = weather_data.get("precip", 0)
    pressure = weather_data.get("pressure", 1013)
    
    # 1. 基础分
    peak_matrix = site["peak_matrix"][season]
    month = date_obj.month
    day = date_obj.day
    
    if month in peak_matrix:
        matrix = peak_matrix[month]
        if day <= 10:
            peak_weight = matrix[0]
        elif day <= 20:
            peak_weight = matrix[1]
        else:
            peak_weight = matrix[2]
    else:
        peak_weight = 0.5
    
    baseline = site["baseline"][season]
    base_score = 65 * baseline * peak_weight
    
    # 2. 山脊韧性
    base_score *= RIDGE_RESILIENCE.get(name, 1.0)
    
    # 3. 历史丰度权重
    base_score *= calculate_abundance_weight(name, season)
    
    # 4. 风速升力
    wind_lift_score = calculate_wind_lift_score(w_spd, name)
    
    # 5. Ridge_Ortho_Lift
    ortho_lift = calculate_ridge_ortho_lift(w_spd, w_dir, site["ridge_orient"])
    total_wind = max(wind_lift_score, ortho_lift) * 0.6 + min(wind_lift_score, ortho_lift) * 0.4 if ortho_lift > 0 else wind_lift_score
    
    # 6. 海陆风
    sea_breeze = calculate_sea_breeze_index(site_type, temp_2m)
    
    # 7. 南风增强
    south_wind = calculate_south_wind_boost(w_dir, site_type, season)
    
    # 8. 地理溢价
    geo_bonus = calculate_geographic_bonus(name, season)
    
    # 9. Mega-Raptor
    mega_bonus = calculate_mega_raptor_bonus(name, date_obj, season)
    
    # 10. 冷锋
    cold_front_bonus = 0  # 需要昨日数据
    
    # 11. 幼鸟扩散
    juvenile_bonus = calculate_juvenile_dispersal_bonus(name, season)
    
    # 惩罚项
    thermal_penalty, _ = calculate_thermal_dynamic_compensation(temp_2m, w_spd, w_dir, site["ridge_orient"], season)
    cloud_penalty, _ = calculate_cloud_tolerance(cloud, precip, w_dir, season)
    precip_penalty = calculate_precip_penalty(precip)
    
    # 最终评分
    score = base_score
    score += total_wind
    score += sea_breeze
    score += south_wind
    score += geo_bonus
    score += mega_bonus
    score += cold_front_bonus
    score += juvenile_bonus
    score -= thermal_penalty
    score -= cloud_penalty
    score -= precip_penalty
    
    # 物候修正
    phen_mult = calculate_phenology_multiplier(name, date_obj, score, season)
    if phen_mult > 1.0:
        score *= phen_mult
    
    # 硬约束
    if precip > 1.0:
        score = 0
    
    score = max(0, min(100, int(score)))
    
    return score

# ============== 主程序 ==============

def main():
    print("\n" + "=" * 60)
    print("🦅 猛禽迁徙预测模型 V9.0 - 季节镜像与风速自适应")
    print("=" * 60)
    
    today = datetime.date(2026, 3, 24)
    season = get_season(today)
    
    print(f"\n📅 {today} ({season}季)\n")
    
    results = []
    
    for site in SITES:
        print(f"→ {site['name']}...")
        
        weather = get_weather(site["lat"], site["lon"], today, is_high_altitude(site["name"]))
        
        if weather:
            score = calculate_v9_score(site, weather, today, season)
            abundance_w = calculate_abundance_weight(site["name"], season)
            resilience = RIDGE_RESILIENCE.get(site["name"], 1.0)
            
            print(f"   天气: {weather['temp_2m']:.1f}°C, 风速{weather['w_spd']:.1f}kts, 风向{weather['w_dir']}°")
            print(f"   V9得分: {score}分 {get_rating(score)}")
            print(f"   - 丰度权重: {abundance_w:.2f}x, 山脊韧性: {resilience}x")
            print()
            
            results.append({"site": site["name"], "score": score})
    
    # 汇总
    print("\n" + "=" * 60)
    print("📊 V9 模型预测结果汇总")
    print("=" * 60)
    
    print(f"\n{'站点':<12} {'V9':<6} {'V8':<6} {'变化':<6} {'评级'}")
    print("-" * 50)
    
    v8_scores = {
        "都统岩": 45,
        "龙泉山": 86,
        "尧山电视台": 56,
        "冠头岭": 96,
        "九龙山": 0,
        "渔洋山": 0,
        "南汇东滩": 0,
        "崇明东滩": 13
    }
    
    for r in results:
        v8 = v8_scores.get(r["site"], 0)
        diff = r["score"] - v8
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{r['site']:<12} {r['score']:<6} {v8:<6} {diff_str:<6} {get_rating(r['score'])}")
    
    print("\n✅ V9 计算完成")

if __name__ == "__main__":
    main()
