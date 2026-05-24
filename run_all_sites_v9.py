#!/usr/bin/env python3
"""
猛禽预测 V9 完整版 - 7天报告生成与发送
整合 raptor_v9_runner.py 完整算法
"""
import os
import sys
import datetime
import json
import smtplib
import math
import requests
import warnings
warnings.filterwarnings('ignore')

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# SMTP 配置
SMTP_CONFIG = {
    "host": "smtp.163.com",
    "port": 465,
    "user": "jasonzhouyu@163.com",
    "password": "REDACTED_SEE_DOTENV",
    "from_name": "猛禽预测"
}

# ============== V9 完整配置 ==============

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

# V9 参数
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

def get_weather(lat, lon, date, is_high_alt):
    try:
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,precipitation,cloud_cover,wind_speed_10m,wind_direction_10m,surface_pressure",
            "daily": "temperature_2m_max", "timezone": "Asia/Shanghai", "forecast_days": 7
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
                    "pressure": hourly.get("surface_pressure", [1013])[i]
                }
                if is_high_alt and "wind_speed_925hPa" in hourly:
                    w_spd_925 = hourly.get("wind_speed_925hPa", [0])[i]
                    if w_spd_925 and w_spd_925 > 0:
                        weather["w_spd"] = w_spd_925 / 1.852
                        weather["temp_850hPa"] = hourly.get("temperature_850hPa", [weather["temp_2m"]-6.5])[i]
                if "temp_850hPa" not in weather:
                    weather["temp_850hPa"] = weather["temp_2m"] - 6.5
                return weather
    except Exception as e:
        print(f"   ⚠️ 天气获取失败: {e}")
    return None

def calculate_v9_score(site, weather_data, date_obj, season):
    name = site["name"]
    site_type = get_site_type(name)
    temp_2m = weather_data.get("temp_2m", 15)
    w_spd = weather_data.get("w_spd", 10)
    w_dir = weather_data.get("w_dir", 180)
    cloud = weather_data.get("cloud", 50)
    precip = weather_data.get("precip", 0)
    
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
    
    # 乘数
    base_score *= RIDGE_RESILIENCE.get(name, 1.0)
    base_score *= calculate_abundance_weight(name, season)
    
    # 加分项
    wind_lift = wind_lift_score(w_spd, name)
    ortho_lift = calculate_ridge_ortho_lift(w_spd, w_dir, site["ridge_orient"])
    total_wind = max(wind_lift, ortho_lift) * 0.6 + min(wind_lift, ortho_lift) * 0.4 if ortho_lift > 0 else wind_lift
    
    sea_breeze = calculate_sea_breeze_index(site_type, temp_2m)
    south_wind = calculate_south_wind_boost(w_dir, site_type, season)
    geo_bonus = calculate_geographic_bonus(name, season)
    mega_bonus = calculate_mega_raptor_bonus(name, date_obj, season)
    juvenile_bonus = calculate_juvenile_dispersal_bonus(name, season)
    
    # 惩罚项
    thermal_penalty, _ = calculate_thermal_dynamic_compensation(temp_2m, w_spd, w_dir, site["ridge_orient"], season)
    cloud_penalty, _ = calculate_cloud_tolerance(cloud, precip, w_dir, season)
    precip_penalty = calculate_precip_penalty(precip)
    
    # 最终计算
    score = base_score + total_wind + sea_breeze + south_wind + geo_bonus + mega_bonus + juvenile_bonus - thermal_penalty - cloud_penalty - precip_penalty
    
    if precip > 1.0: score = 0
    score = max(0, min(100, int(score)))
    return score

def get_rating(score):
    if score >= 88: return "⭐⭐⭐⭐⭐ 推荐"
    elif score >= 75: return "⭐⭐⭐ 值得"
    elif score >= 60: return "⭐⭐ 视情"
    elif score >= 40: return "⭐ 放弃"
    return "❌ 放弃"

# ============== 报告生成 ==============

def load_subscribers():
    f = os.path.join(SCRIPT_DIR, "subscribers.json")
    if os.path.exists(f):
        with open(f) as fp:
            return json.load(fp)
    return []

def send_email(to_email, subject, html_content):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SMTP_CONFIG["user"]
        msg['To'] = to_email
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))
        server = smtplib.SMTP_SSL(SMTP_CONFIG["host"], SMTP_CONFIG["port"])
        server.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])
        server.sendmail(SMTP_CONFIG["user"], to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"   ❌ 邮件失败: {e}")
        return False

def generate_7day_report(target_date):
    season = get_season(target_date)
    all_data = {}
    results = []
    
    print(f"\n{'='*60}")
    print(f"🦅 猛禽迁徙预测 V9 完整版 - {target_date} ({season}季)")
    print(f"{'='*60}\n")
    
    for site in SITES:
        print(f"→ {site['name']}...")
        weather = get_weather(site["lat"], site["lon"], target_date, site["name"] in HIGH_ALTITUDE)
        
        if weather:
            score = calculate_v9_score(site, weather, target_date, season)
            rating = get_rating(score)
            
            print(f"   天气: {weather['temp_2m']:.1f}°C, 风速{weather['w_spd']:.1f}kts, 风向{weather['w_dir']}°")
            print(f"   V9得分: {score}分 {rating}")
            
            all_data[site["name"]] = {
                "score": score,
                "rating": rating,
                "temp": weather["temp_2m"],
                "wind": weather["w_spd"],
                "dir": weather["w_dir"],
                "cloud": weather.get("cloud", 0),
                "precip": weather.get("precip", 0)
            }
            results.append({"site": site["name"], "score": score})
    
    # 排序
    results.sort(key=lambda x: -x["score"])
    return all_data, results

def format_dingtalk(date_str, all_data, sorted_results):
    lines = [f"## 🦅 猛禽迁徙预测 V9 ({date_str})", ""]
    lines.append("### 各站点评分")
    lines.append("")
    lines.append("| 站点 | 评分 | 评级 | 温度 | 风速 |")
    lines.append("| --- | --- | --- | --- | --- |")
    
    for r in sorted_results:
        name = r["site"]
        d = all_data[name]
        lines.append(f"| **{name}** | {d['score']} | {d['rating']} | {d['temp']:.0f}°C | {d['wind']:.0f}kts |")
    
    lines.append("")
    if sorted_results:
        best = sorted_results[0]
        lines.append(f"### 🏆 最佳: {best['site']} ({best['score']}分)")
    
    return "\n".join(lines)

def format_email_html(date_str, all_data, sorted_results):
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        h2 {{ color: #2E7D32; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: center; }}
        th {{ background-color: #4CAF50; color: white; }}
        .score-high {{ color: #d32f2f; font-weight: bold; }}
        .score-mid {{ color: #f57c00; }}
        .score-low {{ color: #757575; }}
        .best {{ background-color: #fff3cd; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>🦅 猛禽迁徙预测 V9 完整版</h2>
        <p><strong>日期:</strong> {date_str}</p>
        
        <table>
            <tr><th>站点</th><th>评分</th><th>评级</th><th>温度</th><th>风速</th><th>风向</th></tr>
"""
    
    for r in sorted_results:
        name = r["site"]
        d = all_data[name]
        score = d["score"]
        score_cls = "score-high" if score >= 75 else "score-mid" if score >= 60 else "score-low"
        is_best = r == sorted_results[0]
        best_cls = ' class="best"' if is_best else ''
        
        html += f"""            <tr{best_cls}>
                <td><strong>{name}</strong></td>
                <td class="{score_cls}">{score}</td>
                <td>{d['rating']}</td>
                <td>{d['temp']:.0f}°C</td>
                <td>{d['wind']:.0f} kts</td>
                <td>{d['dir']}°</td>
            </tr>
"""
    
    html += """        </table>
        
        <h3>📊 评分说明</h3>
        <ul>
            <li>⭐⭐⭐⭐⭐ 推荐 (≥88分) - 不可错过的迁徙高峰</li>
            <li>⭐⭐⭐ 值得 (≥75分) - 动力条件优秀</li>
            <li>⭐⭐ 视情 (≥60分) - 适合常规观测</li>
            <li>⭐ 放弃 (≥40分) - 效率可能较低</li>
            <li>❌ 放弃 (&lt;40分) - 建议不前往</li>
        </ul>
        
        <p><em>数据来源: Open-Meteo 气象预报 | V9 算法: 季节镜像+风速自适应+历史丰度权重+冷锋检测+幼鸟扩散</em></p>
    </div>
</body>
</html>
"""
    return html

# ============== 主程序 ==============

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dingtalk", choices=["dingtalk", "console"])
    parser.add_argument("--no-email", action="store_true")
    args = parser.parse_args()
    
    today = datetime.date.today()
    date_str = today.strftime("%Y-%m-%d")
    
    all_data, sorted_results = generate_7day_report(today)
    
    # 输出钉钉消息
    if args.output == "dingtalk":
        dingtalk_msg = format_dingtalk(date_str, all_data, sorted_results)
        print("\n---DINGTALK_START---\n")
        print(dingtalk_msg)
        print("\n---DINGTALK_END---\n")
    
    # 保存 HTML
    html = format_email_html(date_str, all_data, sorted_results)
    html_file = os.path.join(SCRIPT_DIR, f"raptor_v9_report_{date_str}.html")
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ HTML 已保存: {html_file}")
    
    # 发送邮件
    if not args.no_email:
        subscribers = load_subscribers()
        if subscribers:
            subject = f"🦅 猛禽迁徙预测 V9 - {date_str}"
            for email in subscribers:
                print(f"📧 发送到: {email}...")
                if send_email(email, subject, html):
                    print(f"   ✅ 发送成功")
        else:
            print("⚠️ 无订阅者")
    
    print("\n✅ V9 完整版预测完成")

if __name__ == "__main__":
    main()
