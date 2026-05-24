#!/usr/bin/env python3
"""
猛禽预测 V9 HTML 完整版
- 当日播报: 4-20点每小时预测 + 最佳时段
- 7天趋势: 折线图 (matplotlib 生成静态图片)
"""
import os
import sys
import datetime
import json
import math
import base64
import requests
import warnings
warnings.filterwarnings('ignore')

# 导入 matplotlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 设置中文字体
plt.rcParams['axes.unicode_minus'] = False
font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
chart_font = fm.FontProperties(fname=font_path)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 导入 BirdReport 客户端
sys.path.insert(0, os.path.join(SCRIPT_DIR, '..'))
try:
    from birdreport_client import get_raptor_birdreport_data, RAPTOR_SITE_MAP
except ImportError:
    get_raptor_birdreport_data = None
    RAPTOR_SITE_MAP = {}

# ============== 站点配置 ==============

SITE_TYPES = {
    "Ridge": ["都统岩", "龙泉山", "九龙山"],
    "Karst": ["尧山电视台"],
    "Coastal": ["冠头岭", "渔洋山"],
    "Wetland": ["南汇东滩", "崇明东滩"]
}

HIGH_ALTITUDE = ["都统岩", "龙泉山", "尧山电视台", "九龙山"]
LOW_WIND = ["都统岩", "龙泉山"]

SITES = [
    {"name": "都统岩", "lat": 30.76, "lon": 103.42, "ridge_orient": 30, "fav_wind": {"春": 180, "秋": 0}, "baseline": {"春": 0.85, "秋": 0.80}, "peak_matrix": {"春": {3: [0.6, 0.8, 1.0], 4: [1.2, 1.5, 1.3], 5: [1.1, 0.9, 0.6]}, "秋": {9: [0.7, 1.0, 1.3], 10: [1.4, 1.2, 0.8], 11: [0.6, 0.5, 0.3]}}},
    {"name": "龙泉山", "lat": 30.556, "lon": 104.307, "ridge_orient": 20, "fav_wind": {"春": 180, "秋": 0}, "baseline": {"春": 0.85, "秋": 0.80}, "peak_matrix": {"春": {3: [0.7, 0.9, 1.1], 4: [1.3, 1.4, 1.2], 5: [1.0, 0.8, 0.5]}, "秋": {9: [0.8, 1.1, 1.4], 10: [1.5, 1.3, 0.9], 11: [0.7, 0.5, 0.4]}}},
    {"name": "尧山电视台", "lat": 25.30, "lon": 110.38, "ridge_orient": 135, "fav_wind": {"春": 165, "秋": 345}, "baseline": {"春": 0.90, "秋": 0.85}, "peak_matrix": {"春": {3: [0.8, 1.0, 1.3], 4: [1.4, 1.6, 1.5], 5: [1.2, 0.9, 0.6]}, "秋": {9: [0.6, 0.8, 1.1], 10: [1.3, 1.5, 1.4], 11: [1.1, 0.8, 0.5]}}},
    {"name": "冠头岭", "lat": 21.45, "lon": 109.05, "ridge_orient": 90, "fav_wind": {"春": 190, "秋": 20}, "baseline": {"春": 0.90, "秋": 0.60}, "peak_matrix": {"春": {3: [0.8, 1.1, 1.4], 4: [1.6, 1.5, 1.2], 5: [0.9, 0.6, 0.4]}, "秋": {9: [0.7, 0.9, 1.1], 10: [1.2, 1.0, 0.7], 11: [0.5, 0.4, 0.3]}}},
    {"name": "九龙山", "lat": 29.5, "lon": 121.5, "ridge_orient": 45, "fav_wind": {"春": 135, "秋": 315}, "baseline": {"春": 0.80, "秋": 0.80}, "peak_matrix": {"春": {3: [0.6, 0.8, 1.0], 4: [1.2, 1.4, 1.2], 5: [1.0, 0.7, 0.5]}, "秋": {9: [0.7, 1.0, 1.2], 10: [1.3, 1.2, 0.8], 11: [0.6, 0.4, 0.3]}}},
    {"name": "渔洋山", "lat": 31.2, "lon": 120.4, "ridge_orient": 90, "fav_wind": {"春": 135, "秋": 315}, "baseline": {"春": 0.80, "秋": 0.80}, "peak_matrix": {"春": {3: [0.6, 0.8, 1.0], 4: [1.1, 1.3, 1.1], 5: [0.8, 0.6, 0.4]}, "秋": {9: [0.6, 0.9, 1.1], 10: [1.2, 1.0, 0.7], 11: [0.5, 0.4, 0.3]}}},
    {"name": "南汇东滩", "lat": 30.9, "lon": 121.9, "ridge_orient": 0, "fav_wind": {"春": 90, "秋": 270}, "baseline": {"春": 0.75, "秋": 0.75}, "peak_matrix": {"春": {3: [0.5, 0.7, 0.9], 4: [1.0, 1.2, 1.0], 5: [0.7, 0.5, 0.3]}, "秋": {9: [0.6, 0.8, 1.0], 10: [1.1, 0.9, 0.6], 11: [0.4, 0.3, 0.2]}}},
    {"name": "崇明东滩", "lat": 31.5, "lon": 121.9, "ridge_orient": 0, "fav_wind": {"春": 90, "秋": 270}, "baseline": {"春": 0.75, "秋": 0.75}, "peak_matrix": {"春": {3: [0.5, 0.7, 0.9], 4: [1.0, 1.2, 1.0], 5: [0.7, 0.5, 0.3]}, "秋": {9: [0.6, 0.8, 1.0], 10: [1.1, 0.9, 0.6], 11: [0.4, 0.3, 0.2]}}},
]

V9_PARAMS = {
    "V_MIN_INLAND": 6, "V_MIN_STANDARD": 8, "V_OPT_MIN": 15, "V_OPT_MAX": 30, "V_MAX": 45, "TAU": 5,
    "ORTHO_MIN_SPEED": 10, "ORTHO_MIN_RATIO": 0.40,
    "PRECIP_HALFLIFE": 0.5,
    "TEMP_COLD_THRESHOLD": 15, "WIND_FOR_SLOPE_SOARING": 12, "WIND_ANGLE_FOR_SLOPE": 30, "THERMAL_PENALTY_REDUCTION": 0.7,
    "CLOUD_TOLERANCE_THRESHOLD": 70, "CLOUD_PENALTY_REDUCTION": 0.6,
    "COLD_FRONT_TEMP_DROP": 5, "COLD_FRONT_PRESSURE_RISE": 2, "COLD_FRONT_BONUS": 20,
    "JUVENILE_DISPERSAL_BONUS": 8,
}

RIDGE_RESILIENCE = {"都统岩": 1.25, "龙泉山": 1.25, "尧山电视台": 1.0}
ABUNDANCE = {"都统岩": 1.20, "龙泉山": 1.45, "尧山电视台": 1.35, "冠头岭": 1.85, "九龙山": 1.15, "渔洋山": 1.05, "南汇东滩": 1.10, "崇明东滩": 1.00}
AUTUMN_WEIGHTS = {"龙泉山": 1.35, "都统岩": 1.35, "冠头岭": 1.50, "南汇东滩": 1.40, "崇明东滩": 1.40, "九龙山": 1.25, "渔洋山": 1.25}
GEO_BONUS = {"冠头岭": {"春": 15, "秋": 5}, "龙泉山": {"春": 10, "秋": 8}, "都统岩": {"春": 10, "秋": 8}}
MEGA_RAPTOR_SITES = ["龙泉山", "尧山电视台"]

# ============== V9 函数 ==============

def get_season(date_obj):
    if date_obj.month in [3, 4, 5]: return "春"
    elif date_obj.month in [9, 10, 11]: return "秋"
    return "春"

def get_site_type(name):
    for st, sites in SITE_TYPES.items():
        if name in sites: return st
    return "Ridge"

def calculate_abundance_weight(name, season):
    base = ABUNDANCE.get(name, 1.0)
    if season == "秋" and name in AUTUMN_WEIGHTS:
        return base * AUTUMN_WEIGHTS[name]
    return base

def wind_lift_score(w_spd, name):
    v_min = V9_PARAMS["V_MIN_INLAND"] if name in LOW_WIND else V9_PARAMS["V_MIN_STANDARD"]
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
    normal_angle = (ridge_orient + 90) % 360
    theta = abs(w_dir - normal_angle) % 360
    if theta > 180: theta = 360 - theta
    if w_spd < V9_PARAMS["ORTHO_MIN_SPEED"]: return 0
    sin_theta = math.sin(math.radians(theta))
    base_lift = sin_theta * 15
    if sin_theta > 0.1 and w_spd > V9_PARAMS["ORTHO_MIN_SPEED"]:
        min_lift = 15 * V9_PARAMS["ORTHO_MIN_RATIO"]
        base_lift = max(base_lift, min_lift)
    return base_lift

def calculate_sea_breeze_index(site_type, temp_2m):
    if site_type != "Coastal": return 0
    delta_t = temp_2m - (temp_2m - 2.5)
    if 2 <= delta_t <= 5: return 15
    elif delta_t > 5: return 10
    elif delta_t > 0: return 5 * delta_t / 2
    return 0

def calculate_south_wind_boost(w_dir, site_type, season):
    if season != "春": return 0
    if site_type not in ["Ridge", "Karst"]: return 0
    if 135 <= w_dir <= 225: return (1 - abs(w_dir - 180) / 45) * 10
    return 0

def calculate_geographic_bonus(name, season):
    return GEO_BONUS.get(name, {}).get(season, 0)

def calculate_mega_raptor_bonus(name, date_obj, season):
    if season == "春" and name in MEGA_RAPTOR_SITES:
        if date_obj.month == 3 and date_obj.day >= 20: return 10
    return 0

def calculate_juvenile_dispersal_bonus(name, season):
    if season == "秋" and name in ["南汇东滩", "崇明东滩", "冠头岭"]:
        return V9_PARAMS["JUVENILE_DISPERSAL_BONUS"]
    return 0

def calculate_precip_penalty(precip):
    if precip <= 0: return 0
    k = math.log(3) / V9_PARAMS["PRECIP_HALFLIFE"]
    penalty = 30 / (1 + math.exp(-k * (precip - V9_PARAMS["PRECIP_HALFLIFE"])))
    return min(30, penalty)

def calculate_thermal_dynamic_compensation(temp_2m, w_spd, w_dir, ridge_orient, season):
    if season != "春": return 0, False
    if temp_2m >= V9_PARAMS["TEMP_COLD_THRESHOLD"]: return 0, False
    if w_spd < V9_PARAMS["WIND_FOR_SLOPE_SOARING"]: return 15, False
    wind_diff = abs(w_dir - ridge_orient) % 180
    if wind_diff > 90: wind_diff = 180 - wind_diff
    if wind_diff >= V9_PARAMS["WIND_ANGLE_FOR_SLOPE"]: return 15, False
    return 15 * (1 - V9_PARAMS["THERMAL_PENALTY_REDUCTION"]), True

def calculate_cloud_tolerance(cloud, precip, w_dir, season):
    if precip > 0 or season != "春": return 25 if cloud > 85 else 10 if cloud > 70 else 0, False
    if cloud > V9_PARAMS["CLOUD_TOLERANCE_THRESHOLD"] and 135 <= w_dir <= 225: return 10, True
    return 25 if cloud > 85 else 10 if cloud > 70 else 0, False

def get_hourly_weather(lat, lon, start_date, days=1, is_high_alt=False):
    """获取指定日期范围的小时天气"""
    try:
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,precipitation,cloud_cover,wind_speed_10m,wind_direction_10m,surface_pressure",
            "timezone": "Asia/Shanghai",
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": (start_date + datetime.timedelta(days=days-1)).strftime("%Y-%m-%d")
        }
        if is_high_alt:
            params["hourly"] += ",wind_speed_925hPa,temperature_850hPa"
        
        resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15, verify=False)
        data = resp.json()
        return data.get("hourly", {})
    except Exception as e:
        print(f"   ⚠️ 天气获取失败: {e}")
        return {}

def calculate_v9_score_hourly(site, hourly_weather, target_hour, date_obj, season):
    """计算单小时评分"""
    name = site["name"]
    site_type = get_site_type(name)
    
    is_high_alt = name in HIGH_ALTITUDE
    
    # 容错处理：确保数据存在
    temp_2m_list = hourly_weather.get("temperature_2m", [])
    w_spd_list = hourly_weather.get("wind_speed_10m", [])
    w_dir_list = hourly_weather.get("wind_direction_10m", [])
    cloud_list = hourly_weather.get("cloud_cover", [])
    precip_list = hourly_weather.get("precipitation", [])
    
    # 如果数据为空，使用默认值
    temp_2m = temp_2m_list[target_hour] if len(temp_2m_list) > target_hour else 15
    w_spd_kmh = w_spd_list[target_hour] if len(w_spd_list) > target_hour else 10
    w_spd = w_spd_kmh / 1.852
    w_dir = w_dir_list[target_hour] if len(w_dir_list) > target_hour else 180
    cloud = cloud_list[target_hour] if len(cloud_list) > target_hour else 50
    precip = precip_list[target_hour] if len(precip_list) > target_hour else 0
    
    if is_high_alt and "wind_speed_925hPa" in hourly_weather:
        w_spd_925_list = hourly_weather.get("wind_speed_925hPa", [])
        if len(w_spd_925_list) > target_hour:
            w_spd_925 = w_spd_925_list[target_hour]
            if w_spd_925 and w_spd_925 > 0:
                w_spd = w_spd_925 / 1.852
    
    # 基础分
    peak_matrix = site["peak_matrix"][season]
    month, day = date_obj.month, date_obj.day
    if month in peak_matrix:
        matrix = peak_matrix[month]
        peak_weight = matrix[2] if day > 20 else matrix[1] if day > 10 else matrix[0]
    else:
        peak_weight = 0.5
    baseline = site["baseline"][season]
    base_score = 65 * baseline * peak_weight
    
    base_score *= RIDGE_RESILIENCE.get(name, 1.0)
    base_score *= calculate_abundance_weight(name, season)
    
    wind_lift = wind_lift_score(w_spd, name)
    ortho_lift = calculate_ridge_ortho_lift(w_spd, w_dir, site["ridge_orient"])
    total_wind = max(wind_lift, ortho_lift) * 0.6 + min(wind_lift, ortho_lift) * 0.4 if ortho_lift > 0 else wind_lift
    
    sea_breeze = calculate_sea_breeze_index(site_type, temp_2m)
    south_wind = calculate_south_wind_boost(w_dir, site_type, season)
    geo_bonus = calculate_geographic_bonus(name, season)
    mega_bonus = calculate_mega_raptor_bonus(name, date_obj, season)
    juvenile_bonus = calculate_juvenile_dispersal_bonus(name, season)
    
    thermal_penalty, _ = calculate_thermal_dynamic_compensation(temp_2m, w_spd, w_dir, site["ridge_orient"], season)
    cloud_penalty, _ = calculate_cloud_tolerance(cloud, precip, w_dir, season)
    precip_penalty = calculate_precip_penalty(precip)
    
    score = base_score + total_wind + sea_breeze + south_wind + geo_bonus + mega_bonus + juvenile_bonus - thermal_penalty - cloud_penalty - precip_penalty
    
    if precip > 1.0: score = 0
    score = max(0, min(100, int(score)))
    
    return {
        "score": score,
        "temp": temp_2m,
        "wind": w_spd,
        "dir": w_dir,
        "cloud": cloud,
        "precip": precip
    }

def get_rating(score):
    if score >= 88: return "⭐⭐⭐⭐⭐ 推荐"
    elif score >= 75: return "⭐⭐⭐ 值得"
    elif score >= 60: return "⭐⭐ 视情"
    elif score >= 40: return "⭐ 放弃"
    return "❌ 放弃"

def generate_chart_image(labels, scores, site_name, chart_color):
    """生成静态折线图并返回 base64 编码"""
    font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
    chart_font = fm.FontProperties(fname=font_path)
    
    fig, ax = plt.subplots(figsize=(6, 2.5))
    ax.plot(labels, scores, marker='o', color=chart_color, linewidth=2, markersize=5)
    ax.fill_between(labels, scores, alpha=0.2, color=chart_color)
    ax.set_ylim(0, 100)
    ax.set_ylabel('评分', fontsize=9, fontproperties=chart_font)
    ax.set_title(site_name, fontsize=10, fontweight='bold', fontproperties=chart_font)
    ax.grid(True, alpha=0.3)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8, rotation=45)
    
    # 保存到内存
    from io import BytesIO
    buf = BytesIO()
    plt.savefig(buf, dpi=100, bbox_inches='tight', facecolor='white', format='png')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

# ============== BirdReport 实况验证 ==============

def generate_birdreport_html(target_date):
    """生成 BirdReport 实况验证 HTML 片段"""
    if not get_raptor_birdreport_data:
        return ""
    
    try:
        from datetime import timedelta
        date_to = target_date.strftime('%Y-%m-%d')
        date_from = (target_date - timedelta(days=3)).strftime('%Y-%m-%d')
        data = get_raptor_birdreport_data(date_from, date_to)
    except Exception as e:
        return f"<!-- BirdReport fetch failed: {e} -->"
    
    # 只显示有猛禽记录或报告数>0的站点
    active_sites = [(name, d) for name, d in data.items() if d['report_count'] > 0]
    
    if not active_sites:
        return ""
    
    html_parts = ["""
        <div class="section">
            <div class="section-title">📋 近期实况验证 (BirdReport · 近3天)</div>
"""]
    
    for site_name, d in active_sites:
        raptors = d['target_species']
        all_count = d['species_count']
        
        # 站点活跃度标签
        if d['report_count'] >= 10:
            activity_badge = '<span style="background:#4caf50;color:white;padding:2px 8px;border-radius:8px;font-size:10px;">活跃</span>'
        elif d['report_count'] >= 3:
            activity_badge = '<span style="background:#ff9800;color:white;padding:2px 8px;border-radius:8px;font-size:10px;">一般</span>'
        else:
            activity_badge = '<span style="background:#9e9e9e;color:white;padding:2px 8px;border-radius:8px;font-size:10px;">稀少</span>'
        
        html_parts.append(f"""
            <div class="site-card">
                <div class="site-header">
                    <div class="site-name">📍 {site_name} {activity_badge}</div>
                    <span style="font-size:11px;color:#999;">{d['report_count']}份报告 · {all_count}种鸟</span>
                </div>
""")
        
        if raptors:
            raptor_list = ' · '.join(
                f"<b>{sp['taxonname']}</b><span style='color:#999;font-size:10px;'>({sp['recordcount']}次)</span>"
                for sp in raptors[:8]
            )
            if len(raptors) > 8:
                raptor_list += f" <span style='color:#999;'>等{len(raptors)}种</span>"
            
            # 判断一致性标签
            raptor_count = len(raptors)
            if raptor_count >= 4:
                match_badge = '<span style="color:#4caf50;font-weight:bold;">✅ 猛禽活跃</span>'
            elif raptor_count >= 1:
                match_badge = '<span style="color:#ff9800;">🟡 有个体记录</span>'
            else:
                match_badge = '<span style="color:#f44336;">⬜ 无猛禽记录</span>'
            
            html_parts.append(f"""                <div style="font-size:12px;margin-top:4px;">
                    {match_badge}<br>
                    🦅 {raptor_list}
                </div>
""")
        else:
            # 有报告但无猛禽
            if d['report_count'] >= 3 and all_count > 10:
                note = '<span style="color:#999;font-size:11px;">⚠️ 鸟友上报中未见猛禽（可能观察者未专注猛禽）</span>'
            else:
                note = '<span style="color:#999;font-size:11px;">暂无猛禽记录</span>'
            html_parts.append(f"""                <div style="font-size:12px;margin-top:4px;">
                    {note}
                </div>
""")
        
        html_parts.append("            </div>\n")
    
    html_parts.append("""        </div>
""")
    
    return "\n".join(html_parts)


# ============== HTML 生成 ==============

def generate_v9_html(target_date):
    season = get_season(target_date)
    date_str = target_date.strftime("%Y-%m-%d")
    
    all_hourly_data = {}  # 当日每小时数据
    all_7day_data = {}    # 7天数据
    
    print(f"\n{'='*60}")
    print(f"🦅 猛禽迁徙预测 V9 HTML - {date_str} ({season}季)")
    print(f"{'='*60}\n")
    
    # 获取每个站点的数据
    for site in SITES:
        name = site["name"]
        is_high_alt = name in HIGH_ALTITUDE
        
        print(f"→ {name}...")
        
        # 获取当日小时天气 (4-20点)
        hourly_weather = get_hourly_weather(site["lat"], site["lon"], target_date, days=1, is_high_alt=is_high_alt)
        
        hourly_scores = []
        for h in range(4, 21):  # 4点到20点
            result = calculate_v9_score_hourly(site, hourly_weather, h, target_date, season)
            result["hour"] = h
            result["rating"] = get_rating(result["score"])
            hourly_scores.append(result)
        
        all_hourly_data[name] = hourly_scores
        
        # 获取7天数据 (每天12点)
        day_weather = get_hourly_weather(site["lat"], site["lon"], target_date, days=7, is_high_alt=is_high_alt)
        
        day_scores = []
        for d in range(7):
            target_dt = target_date + datetime.timedelta(days=d)
            hour_idx = d * 24 + 12  # 每天12点
            if hour_idx < len(day_weather.get("temperature_2m", [])):
                result = calculate_v9_score_hourly(site, day_weather, hour_idx, target_dt, season)
                result["date"] = target_dt.strftime("%m-%d")
                result["weekday"] = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][target_dt.weekday()]
                result["rating"] = get_rating(result["score"])
                day_scores.append(result)
        
        all_7day_data[name] = day_scores
        
        # 找当日最佳
        best_hour = max(hourly_scores, key=lambda x: x["score"]) if hourly_scores else None
        print(f"   最佳: {best_hour['hour']}:00 ({best_hour['score']}分)" if best_hour else "   无数据")
    
    # 生成 HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; padding: 16px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        
        .header {{ background: linear-gradient(135deg, #2E7D32 0%, #43A047 100%); color: white; padding: 20px; border-radius: 12px 12px 0 0; }}
        .header h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .header .date {{ opacity: 0.9; font-size: 14px; }}
        
        .section {{ background: white; margin-bottom: 16px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden; }}
        .section-title {{ background: #f8f9fa; padding: 12px 16px; font-size: 16px; font-weight: 600; color: #333; border-bottom: 1px solid #eee; }}
        
        .site-card {{ padding: 12px 16px; border-bottom: 1px solid #f0f0f0; }}
        .site-card:last-child {{ border-bottom: none; }}
        .site-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
        .site-name {{ font-size: 15px; font-weight: 600; color: #333; }}
        .site-best {{ background: linear-gradient(135deg, #4caf50, #8bc34a); color: white; padding: 3px 10px; border-radius: 10px; font-size: 12px; }}
        
        .hourly-grid {{ display: grid; grid-template-columns: repeat(17, 1fr); gap: 2px; margin: 8px 0; }}
        .hour-cell {{ text-align: center; padding: 4px 2px; border-radius: 3px; font-size: 10px; }}
        .hour-cell.best {{ background: #4caf50; color: white; font-weight: bold; }}
        .hour-cell.good {{ background: #c8e6c9; }}
        .hour-cell.mid {{ background: #fff3e0; }}
        .hour-cell.poor {{ background: #ffcdd2; }}
        
        .best-time {{ background: #fff8e1; border: 1px solid #ffc107; border-radius: 6px; padding: 8px; margin-top: 8px; font-size: 12px; }}
        .best-time-title {{ font-weight: bold; color: #f57c00; }}
        
        .chart-container {{ padding: 16px; }}
        .chart-row {{ margin-bottom: 16px; }}
        .chart-row img {{ width: 100%; max-width: 500px; display: block; }}
        
        .legend {{ display: flex; gap: 16px; justify-content: center; padding: 12px; font-size: 11px; color: #666; flex-wrap: wrap; }}
        .legend-item {{ display: flex; align-items: center; gap: 4px; }}
        .legend-color {{ width: 12px; height: 12px; border-radius: 3px; }}
        
        .footer {{ text-align: center; color: #999; font-size: 11px; padding: 16px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🦅 猛禽迁徙预测 V9</h1>
            <div class="date">📅 {date_str} ({season}季) 更新</div>
        </div>
        
        <div class="legend">
            <div class="legend-item"><div class="legend-color" style="background:#4caf50"></div>推荐 (≥88)</div>
            <div class="legend-item"><div class="legend-color" style="background:#c8e6c9"></div>值得 (≥75)</div>
            <div class="legend-item"><div class="legend-color" style="background:#fff3e0"></div>视情 (≥60)</div>
            <div class="legend-item"><div class="legend-color" style="background:#ffcdd2"></div>放弃 (&lt;60)</div>
        </div>
        
        <div class="legend" style="margin-top: -8px;">
            <div class="legend-item"><span style="color:#666;">🕐 时间格式: 小时 | 评分</span></div>
        </div>
"""
    
    # ============== 第一部分：当日播报 ==============
    html += """
        <div class="section">
            <div class="section-title">📡 当日播报 (4-20时)</div>
"""
    
    # 按评分排序站点
    sorted_sites = sorted(all_hourly_data.items(), key=lambda x: -max(y["score"] for y in x[1]))
    
    for site_name, hourly_scores in sorted_sites:
        best = max(hourly_scores, key=lambda x: x["score"])
        
        html += f"""
            <div class="site-card">
                <div class="site-header">
                    <div class="site-name">📍 {site_name}</div>
                    <div class="site-best">★ 最佳 {best['hour']}:00 ({best['score']}分)</div>
                </div>
                <div class="hourly-grid">
"""
        
        for h in hourly_scores:
            score = h["score"]
            if score >= 88:
                cls = "best"
            elif score >= 75:
                cls = "good"
            elif score >= 60:
                cls = "mid"
            else:
                cls = "poor"
            html += f'<div class="hour-cell {cls}">{h["hour"]}<br>{score}</div>'
        
        html += """
                </div>
                <div class="best-time">
                    <div class="best-time-title">⏰ 推荐观测时段: """ + f"{best['hour']}:00 - {best['hour']+1}:00</div>\n"
        html += f"""                    <div>🌡️ {best['temp']:.0f}°C | 💨 {best['wind']:.1f}kt | ☁️ {best['cloud']:.0f}%</div>
                </div>
            </div>
"""
    
    html += """
        </div>
"""
    
    # ============== 第二部分：BirdReport 实况验证 ==============
    html += generate_birdreport_html(target_date)
    
    # ============== 第三部分：7天趋势 (matplotlib 图片) ==============
    html += """
        <div class="section">
            <div class="section-title">📈 7天趋势</div>
            <div class="chart-container">
"""
    
    # 图表颜色
    chart_colors = ['#2E7D32', '#1976D2', '#7B1FA2', '#C2185B', '#00796B', '#F57C00', '#5D4037', '#455A64']
    
    # 按7天数据排序站点
    sites_by_score = sorted(all_7day_data.items(), key=lambda x: -max((d["score"] for d in x[1]), default=0))
    
    for idx, (site_name, day_scores) in enumerate(sites_by_score):
        if not day_scores:
            continue
        
        labels = [d["date"] for d in day_scores]
        scores = [d["score"] for d in day_scores]
        
        # 生成 matplotlib 图表
        img_data = generate_chart_image(labels, scores, site_name, chart_colors[idx])
        
        html += f'''
            <div class="chart-row">
                <img src="data:image/png;base64,{img_data}">
            </div>
'''
    
    html += """
            </div>
        </div>
"""
    
    html += f"""
        <div class="footer">
            <p>🌍 由 OpenClaw 猛禽预测系统 V9 自动生成</p>
            <p>算法: 季节镜像+风速自适应+历史丰度权重+冷锋检测+幼鸟扩散</p>
        </div>
    </div>
</body>
</html>
"""
    
    # 保存文件
    output_file = os.path.join(SCRIPT_DIR, f"raptor_v9_full_{date_str}.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n✅ HTML saved: {output_file}")
    return output_file

if __name__ == "__main__":
    target_date = datetime.datetime.now().date()
    output_file = generate_v9_html(target_date)
    print(f"\n📁 File: {output_file}")
