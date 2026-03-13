from flask import Flask, render_template, request, jsonify
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from raptorcast_v4_guilin import raptor_expert_v32, HOTSPOTS, generate_professional_report, calculate_expert_score_v32, get_phenology_info, get_peak_weight, process_ebird_data, EBirdClient, EBIRD_API_KEY, EBIRD_RADIUS, EBIRD_BACK_DAYS, EBIRD_CACHE_DIR
import datetime
import numpy as np

app = Flask(__name__)

@app.route('/')
def index():
    # 生成未来7天的日期列表
    date_list = []
    week_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for i in range(7):
        date = datetime.date.today() + datetime.timedelta(days=i)
        label = "今天" if i == 0 else "明天" if i == 1 else week_map[date.weekday()]
        date_list.append({
            'date': date.isoformat(),
            'label': label,
            'display': f"{date} ({label})"
        })
    
    # 准备站点数据
    sites = []
    for i, site in enumerate(HOTSPOTS, 1):
        sites.append({
            'id': i,
            'name': site['name'],
            'type': site['type'],
            'desc': site['desc']
        })
    
    return render_template('index.html', sites=sites, date_list=date_list)

@app.route('/predict', methods=['POST'])
def predict():
    try:
        # 获取请求参数
        site_id = int(request.form['site'])
        date_str = request.form['date']
        
        # 解析日期
        sel_date = datetime.date.fromisoformat(date_str)
        
        # 获取站点信息
        site = HOTSPOTS[site_id - 1]
        
        # 基础参数提取
        d_idx = (sel_date - datetime.date.today()).days
        conf_val = 1.0 if d_idx == 0 else 0.9 if d_idx == 1 else 0.8 if d_idx <= 3 else 0.5
        season, target_birds, pheno_desc = get_phenology_info(site, sel_date)
        peak_w = get_peak_weight(site, sel_date, season)
        current_month = sel_date.month
        peak_months = list(site['peak_matrix'][season].keys()) if season in site['peak_matrix'] else []
        
        # 获取eBird数据
        ebird = EBirdClient(EBIRD_API_KEY, EBIRD_RADIUS, EBIRD_BACK_DAYS, EBIRD_CACHE_DIR)
        obs_data = ebird.get_recent_observations(site['lat'], site['lon'])
        ebird_multiplier, ebird_evidence, ebird_warnings = process_ebird_data(
            obs_data, target_birds, peak_months, current_month
        )
        
        # 气象数据获取
        import requests
        from retry_requests import retry
        import requests_cache
        from openmeteo_requests import Client
        from raptorcast_v4_guilin import TLSAdapter
        
        session = requests.Session()
        session.mount("https://", TLSAdapter())
        session.verify = False
        cache_session = requests_cache.CachedSession('.cache', backend='sqlite', expire_after=3600, session=session)
        openmeteo = Client(session=retry(cache_session))
        
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": site['lat'], "longitude": site['lon'],
            "hourly": ["precipitation", "cape", "lifted_index", "wind_speed_850hPa",
                       "wind_direction_850hPa", "cloud_cover", "temperature_850hPa", "temperature_925hPa"],
            "timezone": "Asia/Shanghai",
            "start_date": sel_date.isoformat(),
            "end_date": sel_date.isoformat()
        }
        
        responses = openmeteo.weather_api(url, params=params, verify=False)
        response = responses[0]
        hourly = response.Hourly()
        
        hourly_data = {
            "precip": hourly.Variables(0).ValuesAsNumpy(),
            "cape": hourly.Variables(1).ValuesAsNumpy(),
            "li": hourly.Variables(2).ValuesAsNumpy(),
            "w_spd": hourly.Variables(3).ValuesAsNumpy(),
            "w_dir": hourly.Variables(4).ValuesAsNumpy(),
            "cloud": hourly.Variables(5).ValuesAsNumpy(),
            "temp_850hPa": hourly.Variables(6).ValuesAsNumpy(),
            "temp_925hPa": hourly.Variables(7).ValuesAsNumpy()
        }
        
        # 核心计算循环 (04:00-20:00)
        results = []
        for h in range(4, 21):  # 覆盖 04:00 - 20:00
            w_h = {}
            for k, v in hourly_data.items():
                if h < len(v):
                    w_h[k] = float(v[h])
                else:
                    w_h[k] = 0.0  # 默认值
            
            # 动态选择评分算法 (尧山特殊逻辑)
            if site["name"] == "尧山电视台":
                from raptorcast_v4_guilin import calculate_guilin_modifier
                (score, kettle_prob, warnings, uncertainty, delta_T,
                 drift_side, behavior_pred, thermal_eff, ridge_eff) = calculate_expert_score_v32(
                    w_h, site, season, conf_val, peak_w, target_birds, ebird_multiplier, ebird_warnings
                )
                # 应用尧山特殊修正
                guilin_mod, guilin_mods = calculate_guilin_modifier(w_h, season)
                score = int(score * guilin_mod)
                for mod_name, _ in guilin_mods:
                    warnings.append(f"🏔️ 尧山增益: {mod_name}")
            else:
                (score, kettle_prob, warnings, uncertainty, delta_T,
                 drift_side, behavior_pred, thermal_eff, ridge_eff) = calculate_expert_score_v32(
                    w_h, site, season, conf_val, peak_w, target_birds, ebird_multiplier, ebird_warnings
                )
            
            # 存储结果 (评分, 鹰柱概率, 小时, LI, 风向, ΔT, 风速, 行为预测, 热力效率, 地形效率)
            results.append((score, kettle_prob, h, w_h['li'], w_h['w_dir'], delta_T, w_h['w_spd'],
                            behavior_pred, thermal_eff, ridge_eff))
        
        # 生成报告
        report = generate_professional_report(site, results, ebird_evidence, ebird_multiplier, sel_date)
        
        # 准备结果数据
        result_data = {
            'site': site['name'],
            'date': sel_date.isoformat(),
            'report': report,
            'results': []
        }
        
        # 处理小时数据
        for r in results:
            result_data['results'].append({
                'hour': r[2],
                'score': r[0],
                'kettle_prob': r[1],
                'li': r[3],
                'wind_dir': r[4],
                'delta_T': r[5],
                'wind_speed': r[6],
                'behavior_pred': r[7],
                'thermal_eff': r[8],
                'ridge_eff': r[9]
            })
        
        return render_template('result.html', result=result_data)
        
    except Exception as e:
        import traceback
        error_message = f"错误: {str(e)}\n{traceback.format_exc()}"
        return render_template('error.html', error=error_message)

def main():
    app.run(debug=True, host='0.0.0.0', port=5001)

if __name__ == '__main__':
    main()