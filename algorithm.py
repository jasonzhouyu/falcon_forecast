"""
猛禽迁徙预测系统 - 核心算法模块
包含所有预测逻辑和数据处理函数
"""
import os
import datetime
import urllib3
import ssl
import requests
import openmeteo_requests
import requests_cache
from retry_requests import retry
from dotenv import load_dotenv
import numpy as np
import json
from typing import List, Dict, Optional, Tuple

# --- SSL 配置 ---
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
ssl._create_default_https_context = ssl._create_unverified_context


class TLSAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = ctx
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 加载配置 (跳过不存在的 falcon_forecast/.env 文件)
# 直接使用默认值，因为即使没有 .env 文件也应该能正常运行

EBIRD_API_KEY = os.getenv("EBIRD_API_KEY", "")
EBIRD_RADIUS = int(os.getenv("EBIRD_SEARCH_RADIUS", 50))
EBIRD_BACK_DAYS = int(os.getenv("EBIRD_BACKLOOK_DAYS", 5))
EBIRD_CACHE_DIR = os.getenv("EBIRD_CACHE_DIR", "")


# --- EBirdClient 类 ---
class EBirdClient:
    def __init__(self, api_key: str, radius: int, back_days: int, cache_dir: str):
        self.api_key = api_key
        self.radius = radius
        self.back_days = back_days
        self.cache_dir = cache_dir
        self.base_url = "https://api.ebird.org/v2/data/obs/geo/recent"
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, lat: float, lon: float, date: datetime.date) -> str:
        lat_str = f"{lat:.2f}".replace('.', 'p')
        lon_str = f"{lon:.2f}".replace('.', 'p')
        date_str = date.strftime("%Y%m%d")
        return os.path.join(self.cache_dir, f"ebird_{lat_str}_{lon_str}_{date_str}.json")

    def get_recent_observations(self, lat: float, lon: float) -> List[Dict]:
        if not self.api_key:
            return []

        today = datetime.date.today()
        cache_path = self._get_cache_path(lat, lon, today)

        try:
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    print(f"🌍 从本地缓存加载eBird数据: {cache_path}")
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ 缓存读取失败: {e}")

        headers = {"X-eBirdApiToken": self.api_key}
        params = {
            "lat": lat, "lng": lon,
            "dist": self.radius, "back": self.back_days,
            "sppLocale": "zh"
        }

        try:
            response = requests.get(
                self.base_url,
                headers=headers,
                params=params,
                verify=False,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                try:
                    with open(cache_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"🌍 新数据已缓存至: {cache_path}")
                except IOError as e:
                    print(f"⚠️ 缓存写入失败: {e}")
                return data
            else:
                print(f"⚠️ eBird API 响应异常: HTTP {response.status_code}")
                return []
        except Exception as e:
            print(f"⚠️ eBird API 请求失败: {e}")
            return []


# --- eBird 数据处理模块 ---
def process_ebird_data(
        obs_list: List[Dict],
        target_birds_str: str,
        peak_months: List[int],
        current_month: int
) -> Tuple[float, Optional[Dict], List[str]]:
    if not obs_list:
        if current_month in peak_months:
            return 0.7, None, ["📉 eBird 空间惩罚: 周边近期无目击"]
        else:
            return 0.4, None, ["📉 严重惩罚: 非核心期且无记录"]

    keywords = []
    for bird in target_birds_str.split('、'):
        cleaned = bird.replace("(高峰)", "").replace("(爆发)", "").replace("(首阵)", "")
        if "类" in cleaned:
            keywords.append(cleaned.replace("类", ""))
        else:
            keywords.append(cleaned)

    total_obs_count = 0
    latest_evidence = None

    for obs in obs_list:
        c_name = obs.get("comName", "")
        if any(kw in c_name for kw in keywords):
            count = obs.get("howMany", 1)
            total_obs_count += count

            obs_date = datetime.datetime.strptime(obs["obsDt"], "%Y-%m-%d %H:%M") if "obsDt" in obs else None
            if obs_date and (not latest_evidence or obs_date > latest_evidence["date"]):
                latest_evidence = {
                    "species": c_name,
                    "count": count,
                    "date": obs_date,
                    "loc": obs.get("locName", "未知地点")
                }

    warnings = []
    if total_obs_count == 0:
        multiplier = 0.7 if current_month in peak_months else 0.4
        warnings.append("📉 eBird雷达静默: 目标猛禽未进入周边区域")
    else:
        bonus = min(0.2, total_obs_count * 0.005)
        multiplier = 1.0 + bonus
        if bonus > 0.05:
            warnings.append(f"📡 eBird 迁徙流验证: 侦测到周边 {total_obs_count} 只次记录")

    return multiplier, latest_evidence, warnings


# --- 监测站点数据 ---
HOTSPOTS = [
    {
        "name": "都统岩", "lat": 30.76, "lon": 103.42, "type": "内陆山脊",
        "ridge_orient": 30, "max_w_spd": 45,
        "fav_wind": {"春": 180, "秋": 0},
        "baseline": {"春": 0.85, "秋": 0.80},
        "peak_matrix": {
            "春": {3: [0.6, 0.8, 1.0], 4: [1.2, 1.5, 1.3], 5: [1.1, 0.9, 0.6]},
            "秋": {9: [0.7, 1.0, 1.3], 10: [1.4, 1.2, 0.8], 11: [0.6, 0.5, 0.3]}
        },
        "desc": "成都崇州。山脊呈北东-南西走向。",
        "phenology": {
            "春": {1: "大鵟、鹗、普通鵟", 2: "凤头蜂鹰、赤腹鹰、林雕", 3: "赤腹鹰(高峰)、燕隼"},
            "秋": {1: "凤头蜂鹰、赤腹鹰", 2: "灰脸鵟鹰(高峰)、普通鵟", 3: "普通鵟、大鵟、雕类"}
        }
    },
    {
        "name": "龙泉山", "lat": 30.556, "lon": 104.307, "type": "内陆山脊",
        "ridge_orient": 20, "max_w_spd": 45,
        "fav_wind": {"春": 180, "秋": 0},
        "baseline": {"春": 0.85, "秋": 0.80},
        "peak_matrix": {
            "春": {3: [0.7, 0.9, 1.1], 4: [1.3, 1.4, 1.2], 5: [1.0, 0.8, 0.5]},
            "秋": {9: [0.8, 1.1, 1.4], 10: [1.5, 1.3, 0.9], 11: [0.7, 0.5, 0.4]}
        },
        "desc": "成渝南北长脊。典型内陆山脊走廊。",
        "phenology": {
            "春": {1: "普通鵟、鹗", 2: "凤头蜂鹰、灰脸鵟鹰", 3: "赤腹鹰、日本松雀鹰"},
            "秋": {1: "凤头蜂鹰、赤腹鹰", 2: "灰脸鵟鹰(高峰)、普通鵟", 3: "普通鵟、大鵟、秃鹫"}
        }
    },
    {
        "name": "尧山电视台", "lat": 25.299919698768235, "lon": 110.38234770496055, "type": "喀斯特山脊",
        "ridge_orient": 135, "max_w_spd": 40,
        "fav_wind": {"春": 165, "秋": 345},
        "baseline": {"春": 0.90, "秋": 0.85},
        "peak_matrix": {
            "春": {3: [0.8, 1.0, 1.3], 4: [1.4, 1.6, 1.5], 5: [1.2, 0.9, 0.6]},
            "秋": {9: [0.6, 0.8, 1.1], 10: [1.3, 1.5, 1.4], 11: [1.1, 0.8, 0.5]}
        },
        "desc": "桂林市区最高峰(909.3m)。喀斯特地貌孤峰效应明显。",
        "phenology": {
            "春": {1: "普通鵟、鹗、蛇雕", 2: "凤头蜂鹰、赤腹鹰、林雕", 3: "赤腹鹰(高峰)、松雀鹰、燕隼"},
            "秋": {1: "赤腹鹰、蜂鹰、灰脸鵟鹰", 2: "灰脸鵟鹰(高峰)、普通鵟、鹗", 3: "普通鵟、大鵟、蛇雕、凤头鹰"}
        }
    },
    {
        "name": "冠头岭", "lat": 21.45, "lon": 109.05, "type": "海角瓶颈",
        "ridge_orient": 90, "max_w_spd": 40,
        "fav_wind": {"春": 190, "秋": 20},
        "baseline": {"春": 1.05, "秋": 0.60},
        "peak_matrix": {
            "春": {3: [0.8, 1.1, 1.4], 4: [1.6, 1.5, 1.2], 5: [0.9, 0.6, 0.4]},
            "秋": {9: [0.7, 0.9, 1.1], 10: [1.2, 1.0, 0.7], 11: [0.5, 0.4, 0.3]}
        },
        "desc": "北部湾起点。春季黑冠鹃隼第一站。",
        "phenology": {
            "春": {1: "黑冠鹃隼(首阵)、鹗", 2: "黑冠鹃隼(高峰)、赤腹鹰", 3: "赤腹鹰(爆发)、林雕"},
            "秋": {1: "赤腹鹰、隼类", 2: "灰脸鵟鹰、蜂鹰", 3: "普通鵟、鹞类"}
        }
    },
    {
        "name": "九龙山", "lat": 30.681, "lon": 121.021, "type": "沿海瓶颈",
        "ridge_orient": 60, "max_w_spd": 40,
        "fav_wind": {"春": 200, "秋": 20},
        "baseline": {"春": 0.90, "秋": 0.95},
        "peak_matrix": {
            "春": {3: [0.7, 0.8, 1.0], 4: [1.2, 1.3, 1.1], 5: [0.9, 0.7, 0.4]},
            "秋": {9: [0.8, 1.0, 1.3], 10: [1.4, 1.2, 0.8], 11: [0.6, 0.4, 0.3]}
        },
        "desc": "浙江平湖，杭州湾瓶颈。",
        "phenology": {
            "春": {1: "普通鵟、鹗", 2: "凤头蜂鹰、赤腹鹰", 3: "赤腹鹰(高峰)"},
            "秋": {1: "赤腹鹰、蜂鹰", 2: "灰脸鵟鹰(高峰)", 3: "普通鵟、阿穆尔隼"}
        }
    },
    {
        "name": "渔洋山", "lat": 31.20, "lon": 120.45, "type": "湖岸汇聚",
        "ridge_orient": 45, "max_w_spd": 35,
        "fav_wind": {"春": 180, "秋": 10},
        "baseline": {"春": 0.80, "秋": 0.90},
        "peak_matrix": {
            "春": {3: [0.7, 0.8, 1.0], 4: [1.2, 1.3, 1.1], 5: [0.9, 0.7, 0.4]},
            "秋": {9: [0.8, 1.0, 1.3], 10: [1.4, 1.2, 0.8], 11: [0.6, 0.4, 0.3]}
        },
        "desc": "太湖东岸。",
        "phenology": {
            "春": {1: "普通鵟、鹗", 2: "凤头蜂鹰、日本松雀鹰", 3: "赤腹鹰"},
            "秋": {1: "凤头蜂鹰", 2: "灰脸鵟鹰(高峰)、雀鹰", 3: "普通鵟、大鵟"}
        }
    },
    {
        "name": "南汇东滩", "lat": 30.87, "lon": 121.94, "type": "滨海廊道",
        "ridge_orient": 155, "max_w_spd": 55,
        "fav_wind": {"春": 135, "秋": 22.5},
        "baseline": {"春": 0.75, "秋": 1.10},
        "peak_matrix": {
            "春": {3: [0.6, 0.7, 0.9], 4: [1.1, 1.2, 1.0], 5: [0.8, 0.6, 0.3]},
            "秋": {9: [0.9, 1.2, 1.5], 10: [1.7, 1.4, 1.0], 11: [0.8, 0.5, 0.3]}
        },
        "desc": "上海陆地最东南角。",
        "phenology": {
            "春": {1: "普通鵟、鹗、白尾鹞", 2: "赤腹鹰、日本松雀鹰", 3: "燕隼、红隼"},
            "秋": {1: "赤腹鹰(爆发)、凤头蜂鹰", 2: "红脚隼(高峰)、游隼、灰脸鵟鹰", 3: "短耳鸮(迁徙)、普通鵟、大鵟"}
        }
    },
    {
        "name": "崇明东滩", "lat": 31.51, "lon": 121.96, "type": "河口湿地",
        "ridge_orient": 90, "max_w_spd": 50,
        "fav_wind": {"春": 150, "秋": 330},
        "baseline": {"春": 0.70, "秋": 1.05},
        "peak_matrix": {
            "春": {3: [0.5, 0.7, 0.9], 4: [1.2, 1.3, 1.1], 5: [0.8, 0.5, 0.3]},
            "秋": {9: [0.8, 1.1, 1.4], 10: [1.6, 1.3, 0.9], 11: [0.7, 0.4, 0.3]}
        },
        "desc": "长江入海口。",
        "phenology": {
            "春": {1: "白腹鹞、鹗、白尾鹞", 2: "赤腹鹰、灰脸鵟鹰", 3: "鹊鹞、燕隼"},
            "秋": {1: "赤腹鹰、鹊鹞(高峰)", 2: "白腹鹞、红脚隼、灰脸鵟鹰", 3: "普通鵟、白尾海雕(罕见记录)"}
        }
    }
]

# --- 物种配置 ---
SPECIES_CONFIG = {
    '凤头蜂鹰': {'thermal_req': 0.9, 'v_max': 30, 'behavior': "形成热力柱，高空滑翔"},
    '普通鵟': {'thermal_req': 0.5, 'v_max': 42, 'behavior': "低空穿梭，利用地形升力"},
    '黑冠鹃隼': {'thermal_req': 1.0, 'v_max': 25, 'behavior': "集群快速通过，不喜强风"},
    '赤腹鹰': {'thermal_req': 0.7, 'v_max': 35, 'behavior': "中等高度，松散集群"},
    '隼类': {'thermal_req': 0.3, 'v_max': 50, 'behavior': "高速直线飞行，少用热力"},
    '蛇雕': {'thermal_req': 0.6, 'v_max': 45, 'behavior': "利用山脊动力，巡航高度较高"},
    '凤头鹰': {'thermal_req': 0.8, 'v_max': 28, 'behavior': "偏好森林边缘，中等热力需求"},
    '松雀鹰': {'thermal_req': 0.7, 'v_max': 32, 'behavior': "快速穿插飞行，喜开阔地带"},
    '灰脸鵟鹰': {'thermal_req': 0.8, 'v_max': 40, 'behavior': "集群飞行，偏爱山脊线"},
    '林雕': {'thermal_req': 0.7, 'v_max': 38, 'behavior': "高山飞行，利用地形波升力"},
    '鹗': {'thermal_req': 0.4, 'v_max': 48, 'behavior': "沿水域飞行，热力需求低"},
    '大鵟': {'thermal_req': 0.5, 'v_max': 44, 'behavior': "开阔地巡航，中等热力需求"},
    '燕隼': {'thermal_req': 0.3, 'v_max': 55, 'behavior': "高速飞行，几乎不用热力"},
    '日本松雀鹰': {'thermal_req': 0.6, 'v_max': 38, 'behavior': "快速飞行，中等热力需求"},
    '秃鹫': {'thermal_req': 0.3, 'v_max': 50, 'behavior': "利用上升气流，长时间滑翔"},
    '雕类': {'thermal_req': 0.5, 'v_max': 45, 'behavior': "高空盘旋，利用热力柱"},
    '雀鹰': {'thermal_req': 0.6, 'v_max': 35, 'behavior': "快速穿插，灵活飞行"},
    '阿穆尔隼': {'thermal_req': 0.4, 'v_max': 52, 'behavior': "集群高速飞行"},
    '红脚隼': {'thermal_req': 0.3, 'v_max': 48, 'behavior': "集群高速飞行，沿海岸线迁徙"},
    '游隼': {'thermal_req': 0.2, 'v_max': 60, 'behavior': "高速俯冲捕食，沿海岸线飞行"},
    '白腹鹞': {'thermal_req': 0.5, 'v_max': 35, 'behavior': "低空盘旋，湿地生境搜索猎物"},
    '鹊鹞': {'thermal_req': 0.6, 'v_max': 38, 'behavior': "湿地生境，低空飞行觅食"},
    '白尾鹞': {'thermal_req': 0.5, 'v_max': 40, 'behavior': "开阔地低空飞行，偏好湿地"},
    '白尾海雕': {'thermal_req': 0.4, 'v_max': 50, 'behavior': "大型海雕，沿海岸线飞行"},
    '短耳鸮': {'thermal_req': 0.3, 'v_max': 30, 'behavior': "夜间迁徙，黄昏活动"}
}


# --- 辅助函数 ---
def get_peak_weight(site, date_obj, season):
    m, d = date_obj.month, date_obj.day
    p_idx = 0 if d <= 10 else (1 if d <= 20 else 2)
    return site['peak_matrix'].get(season, {}).get(m, [1.0, 1.0, 1.0])[p_idx]


def get_phenology_info(site, date_obj):
    m, d = date_obj.month, date_obj.day
    season = "春" if 2 <= m <= 6 else "秋" if 8 <= m <= 12 else "非迁徙期"
    p_idx = 1 if d <= 10 else (2 if d <= 20 else 3)
    if season == "非迁徙期":
        return season, "本地种", "非迁徙主窗口期"
    birds = site['phenology'].get(season, {}).get(p_idx, "数据更新中")
    period_desc = f"{m}月{'上旬' if p_idx == 1 else '中旬' if p_idx == 2 else '下旬'}"
    return season, birds, period_desc


def get_recommend_index_detailed(score):
    if score >= 88:
        return "⭐⭐⭐⭐⭐", "【不可错过】爆发预警"
    elif score >= 75:
        return "⭐⭐⭐⭐", "【非常推荐】动力条件优秀"
    elif score >= 60:
        return "⭐⭐⭐", "【值得一去】符合迁徙背景"
    elif score >= 40:
        return "⭐⭐", "【视情前往】动力较弱"
    else:
        return "⭐", "【建议放弃】迁徙流极其微弱"


def get_kettle_description(prob):
    if prob >= 80:
        return "🔥 极易成柱", "热力对流极强"
    if prob >= 50:
        return "⛅ 可能成柱", "热力中等"
    return "🍃 难以成柱", "气层稳定"


def get_behavior_prediction(target_birds, score, kettle_prob, wind_speed):
    behaviors = []
    for bird in target_birds.split('、'):
        if bird in SPECIES_CONFIG:
            config = SPECIES_CONFIG[bird]
            if wind_speed > config['v_max'] * 0.8:
                behaviors.append(f"{bird}: 强风抑制")
            elif score > 75 and kettle_prob > 60:
                behaviors.append(f"{bird}: {config['behavior']} (热力增强)")
            else:
                behaviors.append(f"{bird}: {config['behavior']}")
    return " | ".join(behaviors) if behaviors else "无特定行为预测"


# --- 核心评分算法 ---
def calculate_expert_score_v32(w, site, season, conf_val, peak_weight, target_birds, ebird_multiplier, ebird_warnings):
    score = 65 * site['baseline'].get(season, 1.0) * peak_weight
    kettle_prob = 0
    warnings = list(ebird_warnings)
    uncertainty = int(30 * (1 - conf_val))
    front_multiplier = 1.0
    season_annealing = 1.0
    inversion_penalty = 0
    drift_side = None
    behavior_pred = ""
    thermal_efficiency = 0
    ridge_lift_efficiency = 0

    def safe_float(value):
        return float(value) if isinstance(value, (np.floating, np.integer)) else value

    w = {k: safe_float(v) for k, v in w.items()}

    # 逆温层检测
    delta_T = 0
    if 'temp_850hPa' in w and 'temp_925hPa' in w:
        delta_T = w['temp_850hPa'] - w['temp_925hPa']
        if delta_T > 0:
            inversion_penalty = min(15, delta_T * 5)
            warnings.append(f"🌡️ 逆温阻尼(ΔT={delta_T:.1f}℃)")

    # 侧风偏航计算
    if 'ridge_orient' in site:
        ridge_angle = site['ridge_orient']
        normal_angle = (ridge_angle + 90) % 360
        wind_diff = abs(w['w_dir'] - normal_angle)
        if wind_diff > 180:
            wind_diff = 360 - wind_diff
        if wind_diff > 20:
            cross_product = np.sin(np.radians(w['w_dir'] - ridge_angle))
            drift_side = "迎风面侧斜面" if cross_product > 0 else "背风面侧斜面"
            warnings.append(f"🌬 侧风偏航({wind_diff:.0f}°)")

    # 物种敏感度
    heavy_species = ['林雕', '大鵟', '雕类', '秃鹫', '白尾海雕']
    active_species = [s for s in SPECIES_CONFIG if s in target_birds]
    heavy_species_present = any(s in heavy_species for s in active_species)

    # 季节性退火
    current_month = datetime.datetime.now().month
    peak_months = list(site['peak_matrix'][season].keys()) if season in site['peak_matrix'] else []
    if peak_months and (current_month < min(peak_months) or current_month > max(peak_months)):
        season_annealing = 0.6
        warnings.append("🍂 物候衰减: 非核心迁徙窗口期")

    # 冷锋触发
    if (w.get('precip', 0) < -0.5 and w.get('cloud', 0) < -20 and w.get('w_spd', 0) > 5 and 180 < w['w_dir'] < 270):
        front_multiplier = 1.5 if heavy_species_present else 1.3
        warnings.append("❄️ 冷锋触发" if heavy_species_present else "🌬 冷锋前沿")

    config = None
    thermal_req = 0.5
    ridge_lift_weight = 1.0

    if active_species:
        if heavy_species_present:
            thermal_req = 0.4
            ridge_lift_weight = 1.5
        else:
            max_thermal_req = 0
            for s in active_species:
                if s in SPECIES_CONFIG and SPECIES_CONFIG[s]['thermal_req'] > max_thermal_req:
                    max_thermal_req = SPECIES_CONFIG[s]['thermal_req']
                    config = SPECIES_CONFIG[s]
            if config:
                thermal_req = config['thermal_req']

        if config and w['w_spd'] > config['v_max'] * 0.9:
            score -= 20
            warnings.append(f"⚠️ 强风限制")
        elif not config and active_species and w['w_spd'] > 40:
            score -= 15

        if thermal_req > 0.6 and w['li'] > -1.0:
            score -= 15 * (thermal_req / 0.8)
            warnings.append(f"🌡️ 热力不足")

    # 气象硬约束
    if w.get('precip', 0) > 0.03:
        return 0, 0, ["🌧 严重降水"], uncertainty, delta_T, None, "", 0, 0
    if w.get('cloud', 0) > 85:
        score -= 25
        warnings.append("🌫 低能见度/厚云覆盖")

    # 地形动力学
    ridge_lift_effect = 0
    if site['type'] in ["内陆山脊", "喀斯特山脊"]:
        ridge_angle = site['ridge_orient']
        impact_angle = abs((w['w_dir'] - ridge_angle + 90) % 180 - 90)
        lift_eff = 1.0 if impact_angle < 30 else 0.3
        if 15 < w['w_spd'] < 40:
            ridge_lift_effect = (lift_eff * 15) * ridge_lift_weight
            score += ridge_lift_effect
        elif w['w_spd'] >= 40:
            score -= 15
            warnings.append("🚩 强风切变限制")
    elif site['type'] in ["滨海廊道", "河口湿地"]:
        if 8 < w['w_spd'] < 25 and w['w_dir'] in [site['fav_wind'][season] - 30, site['fav_wind'][season] + 30]:
            score += 20
            warnings.append("🌊 理想海陆风条件")
        elif w['w_spd'] > 40:
            score -= 20

    # 热力修正
    thermal_base = min(abs(w['li']) * 12, 30) if w['li'] < 0 else 0
    if 'temp_850hPa' in w and 'temp_925hPa' in w and (w['temp_850hPa'] - w['temp_925hPa']) < 3:
        thermal_base *= 0.8
        warnings.append("💧 高湿抑制")
    if w['w_spd'] > 28:
        thermal_base *= 0.4
    score += thermal_base

    # 鹰柱计算
    if w['li'] < -1.0:
        wind_penalty = max(0, 1 - (w['w_spd'] / 45))
        cloud_bonus = 15 if w['cloud'] < 30 else (-10 if w['cloud'] > 70 else 0)
        kettle_prob = (abs(w['li']) * 20 + (w['cape'] / 25)) * wind_penalty + cloud_bonus
        kettle_prob = min(kettle_prob, 98)

    if delta_T > 0:
        kettle_prob = max(0, kettle_prob * (1 - delta_T * 0.1))

    behavior_pred = get_behavior_prediction(target_birds, score, kettle_prob, w['w_spd'])
    thermal_efficiency = min(100, abs(w['li']) * 15) if w['li'] < 0 else 0
    if 'ridge_orient' in site:
        wind_diff = abs((w['w_dir'] - site['ridge_orient'] + 90) % 180 - 90)
        ridge_lift_efficiency = max(0, 100 - wind_diff * 2)

    final_s = min(100, score * front_multiplier * season_annealing * ebird_multiplier - inversion_penalty)
    return (int(max(0, min(100, final_s))), int(kettle_prob), warnings,
            uncertainty, delta_T, drift_side, behavior_pred, thermal_efficiency, ridge_lift_efficiency)


# --- 桂林特殊修正 ---
def calculate_guilin_modifier(w, season):
    modifiers = []
    if 120 < w['w_dir'] < 220:
        delta_T = w.get('temp_925hPa', 0) - w.get('temp_850hPa', 0)
        if delta_T > 3:
            modifiers.append(("低空压制", 0.85))
        else:
            modifiers.append(("河谷热通道", 1.25))

    karst_effect = 1.0
    if 10 < w['w_spd'] < 25:
        karst_effect = 1.2
        modifiers.append(("峰林动力增益", 1.2))
    elif w['w_spd'] > 35:
        karst_effect = 0.6
        modifiers.append(("严重紊流风险", 0.6))

    return karst_effect, modifiers


# --- 报告生成 ---
def generate_professional_report(site, results, ebird_evidence, ebird_multiplier, sel_date):
    if not results:
        return "❌ 无计算结果"

    window_size = 3
    best_window_score = 0
    best_window_start = 4
    best_window_end = 7

    for start_hour in range(4, 21 - window_size + 1):
        window_scores = []
        for h in range(start_hour, start_hour + window_size):
            hour_score = 0
            for r in results:
                if r[2] == h:
                    hour_score = r[0]
                    break
            window_scores.append(hour_score)
        avg_score = sum(window_scores) / window_size
        if avg_score > best_window_score:
            best_window_score = avg_score
            best_window_start = start_hour
            best_window_end = start_hour + window_size - 1

    best_hour = max(results, key=lambda x: x[0])
    season, _, _ = get_phenology_info(site, sel_date)

    report = [
        "=" * 80,
        f"🦅 猛禽迁徙研判报告 | {site['name']} | {datetime.date.today()}",
        "=" * 80,
        "",
        f"【核心综述】迁徙适宜度: {best_hour[0]}/100 {get_recommend_index_detailed(best_hour[0])[0]}",
        f"黄金观测窗口: {best_window_start:02d}:00-{best_window_end:02d}:00",
        ""
    ]

    if ebird_evidence:
        report.extend([
            "【实证数据】",
            f"最新记录: {ebird_evidence['date'].strftime('%m-%d %H:%M')} 在 {ebird_evidence['loc']}",
            f"观测到 {ebird_evidence['count']}只 {ebird_evidence['species']}",
            f"空间修正系数: {ebird_multiplier:.2f}x",
            ""
        ])

    report.extend([
        "【动态评分表】",
        "-" * 80,
        f"{'时刻':^6} | {'评分':^6} | {'鹰柱%':^6} | {'风速':^6} | {'风向':^6} | {'LI':^6}",
        "-" * 80
    ])

    all_hours_data = {r[2]: r for r in results}

    for h in range(4, 21):
        if h in all_hours_data:
            r = all_hours_data[h]
            report.append(f"{h:02d}:00 | {r[0]:^6} | {r[1]:^6}% | {r[6]:^6.1f}k | {r[4]:^6.0f}° | {r[3]:^6.1f}")

    report.extend([
        "",
        "=" * 80
    ])

    return "\n".join(report)