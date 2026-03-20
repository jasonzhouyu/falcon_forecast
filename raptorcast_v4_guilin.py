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

# --- 1. 终极 SSL 强制绕过配置 ---
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

# 加载配置
_project_root = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(_project_root, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

# 获取配置
EBIRD_API_KEY = os.getenv("EBIRD_API_KEY", "")
EBIRD_RADIUS = int(os.getenv("EBIRD_SEARCH_RADIUS", 50))
EBIRD_BACK_DAYS = int(os.getenv("EBIRD_BACKLOOK_DAYS", 5))
EBIRD_CACHE_DIR = os.path.join(_project_root, 'ebird_daily_cache')


# --- 2. 重构后的 EBirdClient 类 ---
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

        # 尝试从缓存加载
        try:
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    print(f"🌍 从本地缓存加载eBird数据: {cache_path}")
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ 缓存读取失败: {e}")

        # 调用API获取数据
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
                # 保存到缓存
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


# --- 3. eBird 数据处理模块 ---
def process_ebird_data(
        obs_list: List[Dict],
        target_birds_str: str,
        peak_months: List[int],
        current_month: int
) -> Tuple[float, Optional[Dict], List[str]]:
    """处理eBird数据并计算空间异质性修正"""
    if not obs_list:
        if current_month in peak_months:
            return 0.7, None, ["📉 eBird 空间惩罚: 周边近期无目击"]
        else:
            return 0.4, None, ["📉 严重惩罚: 非核心期且无记录"]

    # 解析目标鸟类关键词
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

    # 计算修正乘数
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


# --- 4. 全量学术数据库：8大监测站地形与历史物候 ---
HOTSPOTS = [
    {
        "name": "都统岩",
        "lat": 30.76,
        "lon": 103.42,
        "type": "内陆山脊",
        "ridge_orient": 30,
        "max_w_spd": 45,
        "fav_wind": {
            "春": 180,
            "秋": 0
        },
        "baseline": {
            "春": 0.85,
            "秋": 0.80
        },
        "peak_matrix": {
            "春": {
                3: [0.6, 0.8, 1.0],
                4: [1.2, 1.5, 1.3],
                5: [1.1, 0.9, 0.6]
            },
            "秋": {
                9: [0.7, 1.0, 1.3],
                10: [1.4, 1.2, 0.8],
                11: [0.6, 0.5, 0.3]
            }
        },
        "desc": "成都崇州。利用坡面动力升力场。山脊呈北东-南西走向。",
        "phenology": {
            "春": {
                1: "大鵟、鹗、普通鵟",
                2: "凤头蜂鹰、赤腹鹰、林雕",
                3: "赤腹鹰(高峰)、燕隼"
            },
            "秋": {
                1: "凤头蜂鹰、赤腹鹰",
                2: "灰脸鵟鹰(高峰)、普通鵟",
                3: "普通鵟、大鵟、雕类"
            }
        }
    },
    {
        "name": "龙泉山",
        "lat": 30.556,
        "lon": 104.307,
        "type": "内陆山脊",
        "ridge_orient": 20,
        "max_w_spd": 45,
        "fav_wind": {
            "春": 180,
            "秋": 0
        },
        "baseline": {
            "春": 0.85,
            "秋": 0.80
        },
        "peak_matrix": {
            "春": {
                3: [0.7, 0.9, 1.1],
                4: [1.3, 1.4, 1.2],
                5: [1.0, 0.8, 0.5]
            },
            "秋": {
                9: [0.8, 1.1, 1.4],
                10: [1.5, 1.3, 0.9],
                11: [0.7, 0.5, 0.4]
            }
        },
        "desc": "成渝南北长脊。典型内陆山脊走廊，地形动力升力场强大。",
        "phenology": {
            "春": {
                1: "普通鵟、鹗",
                2: "凤头蜂鹰、灰脸鵟鹰",
                3: "赤腹鹰、日本松雀鹰"
            },
            "秋": {
                1: "凤头蜂鹰、赤腹鹰",
                2: "灰脸鵟鹰(高峰)、普通鵟",
                3: "普通鵟、大鵟、秃鹫"
            }
        }
    },
    {
        "name": "尧山电视台",
        "lat": 25.299919698768235,
        "lon": 110.38234770496055,
        "type": "喀斯特山脊",
        "ridge_orient": 135,
        "max_w_spd": 40,
        "fav_wind": {
            "春": 165,
            "秋": 345
        },
        "baseline": {
            "春": 0.90,
            "秋": 0.85
        },
        "peak_matrix": {
            "春": {
                3: [0.8, 1.0, 1.3],
                4: [1.4, 1.6, 1.5],
                5: [1.2, 0.9, 0.6]
            },
            "秋": {
                9: [0.6, 0.8, 1.1],
                10: [1.3, 1.5, 1.4],
                11: [1.1, 0.8, 0.5]
            }
        },
        "desc": "桂林市区最高峰(909.3m)。喀斯特地貌孤峰效应明显，漓江河谷热力通道，春季东南风水汽输送，秋季过境猛禽重要落脚点。",
        "phenology": {
            "春": {
                1: "普通鵟、鹗、蛇雕",
                2: "凤头蜂鹰、赤腹鹰、林雕",
                3: "赤腹鹰(高峰)、松雀鹰、燕隼"
            },
            "秋": {
                1: "赤腹鹰、蜂鹰、灰脸鵟鹰",
                2: "灰脸鵟鹰(高峰)、普通鵟、鹗",
                3: "普通鵟、大鵟、蛇雕、凤头鹰"
            }
        }
    },
    {
        "name": "冠头岭",
        "lat": 21.45,
        "lon": 109.05,
        "type": "海角瓶颈",
        "ridge_orient": 90,
        "max_w_spd": 40,
        "fav_wind": {
            "春": 190,
            "秋": 20
        },
        "baseline": {
            "春": 1.05,
            "秋": 0.60
        },
        "peak_matrix": {
            "春": {
                3: [0.8, 1.1, 1.4],
                4: [1.6, 1.5, 1.2],
                5: [0.9, 0.6, 0.4]
            },
            "秋": {
                9: [0.7, 0.9, 1.1],
                10: [1.2, 1.0, 0.7],
                11: [0.5, 0.4, 0.3]
            }
        },
        "desc": "北部湾起点。春季黑冠鹃隼第一站。南风引导暖湿气流对流显著。",
        "phenology": {
            "春": {
                1: "黑冠鹃隼(首阵)、鹗",
                2: "黑冠鹃隼(高峰)、赤腹鹰",
                3: "赤腹鹰(爆发)、林雕"
            },
            "秋": {
                1: "赤腹鹰、隼类",
                2: "灰脸鵟鹰、蜂鹰",
                3: "普通鵟、鹞类"
            }
        }
    },
    {
        "name": "九龙山",
        "lat": 30.681,
        "lon": 121.021,
        "type": "沿海瓶颈",
        "ridge_orient": 60,
        "max_w_spd": 40,
        "fav_wind": {
            "春": 200,
            "秋": 20
        },
        "baseline": {
            "春": 0.90,
            "秋": 0.95
        },
        "peak_matrix": {
            "春": {
                3: [0.7, 0.8, 1.0],
                4: [1.2, 1.3, 1.1],
                5: [0.9, 0.7, 0.4]
            },
            "秋": {
                9: [0.8, 1.0, 1.3],
                10: [1.4, 1.2, 0.8],
                11: [0.6, 0.4, 0.3]
            }
        },
        "desc": "浙江平湖，杭州湾瓶颈。鹰群在此汇聚绕行水域。滩涂升温快，对流强烈。",
        "phenology": {
            "春": {
                1: "普通鵟、鹗",
                2: "凤头蜂鹰、赤腹鹰",
                3: "赤腹鹰(高峰)"
            },
            "秋": {
                1: "赤腹鹰、蜂鹰",
                2: "灰脸鵟鹰(高峰)",
                3: "普通鵟、阿穆尔隼"
            }
        }
    },
    {
        "name": "渔洋山",
        "lat": 31.20,
        "lon": 120.45,
        "type": "湖岸汇聚",
        "ridge_orient": 45,
        "max_w_spd": 35,
        "fav_wind": {
            "春": 180,
            "秋": 10
        },
        "baseline": {
            "春": 0.80,
            "秋": 0.90
        },
        "peak_matrix": {
            "春": {
                3: [0.7, 0.8, 1.0],
                4: [1.2, 1.3, 1.1],
                5: [0.9, 0.7, 0.4]
            },
            "秋": {
                9: [0.8, 1.0, 1.3],
                10: [1.4, 1.2, 0.8],
                11: [0.6, 0.4, 0.3]
            }
        },
        "desc": "太湖东岸。利用湖陆风效应及湖岸线热力气旋，对流窗口期明显。",
        "phenology": {
            "春": {
                1: "普通鵟、鹗",
                2: "凤头蜂鹰、日本松雀鹰",
                3: "赤腹鹰"
            },
            "秋": {
                1: "凤头蜂鹰",
                2: "灰脸鵟鹰(高峰)、雀鹰",
                3: "普通鵟、大鵟"
            }
        }
    },
    # ============== 新增站点：上海南汇（南汇嘴/南汇东滩） ==============
    {
        "name": "南汇东滩",
        "lat": 30.87,  # 接近南汇嘴及滴水湖外围滩涂
        "lon": 121.94,
        "type": "滨海廊道",
        "ridge_orient": 155,  # 沿海岸线走向，西北-东南
        "max_w_spd": 55,  # 海边无遮挡，阵风极强
        "fav_wind": {
            "春": 135,  # 东南风引导
            "秋": 22.5  # 偏北风/东北风利于压向岸边
        },
        "baseline": {
            "春": 0.75,
            "秋": 1.10  # 秋季是南汇的绝对高峰
        },
        "peak_matrix": {
            "春": {
                3: [0.6, 0.7, 0.9],
                4: [1.1, 1.2, 1.0],
                5: [0.8, 0.6, 0.3]
            },
            "秋": {
                9: [0.9, 1.2, 1.5],  # 9月下旬赤腹鹰、红脚隼开始爆发
                10: [1.7, 1.4, 1.0],  # 10月上旬是隼类高峰
                11: [0.8, 0.5, 0.3]
            }
        },
        "desc": "上海陆地最东南角。典型的海岸线引导效应，秋季是小型隼类（红脚隼、燕隼、阿穆尔隼）跨海前的集结地，受海陆风环流影响明显。",
        "phenology": {
            "春": {
                1: "普通鵟、鹗、白尾鹞",
                2: "赤腹鹰、日本松雀鹰",
                3: "燕隼、红隼"
            },
            "秋": {
                1: "赤腹鹰(爆发)、凤头蜂鹰",
                2: "红脚隼(高峰)、游隼、灰脸鵟鹰",
                3: "短耳鸮(迁徙)、普通鵟、大鵟"
            }
        }
    },
    # ============== 新增站点：上海崇明东滩 ==============
    {
        "name": "崇明东滩",
        "lat": 31.51,  # 崇明东滩鸟类国家级自然保护区核心带
        "lon": 121.96,
        "type": "河口湿地",
        "ridge_orient": 90,  # 沿长江口东西向分布
        "max_w_spd": 50,
        "fav_wind": {
            "春": 150,
            "秋": 330  # 西北风有利于猛禽在长江口岛链间移动
        },
        "baseline": {
            "春": 0.70,
            "秋": 1.05
        },
        "peak_matrix": {
            "春": {
                3: [0.5, 0.7, 0.9],
                4: [1.2, 1.3, 1.1],
                5: [0.8, 0.5, 0.3]
            },
            "秋": {
                9: [0.8, 1.1, 1.4],
                10: [1.6, 1.3, 0.9],
                11: [0.7, 0.4, 0.3]
            }
        },
        "desc": "长江入海口。猛禽迁徙的重要'跳岛'点，对湿地生境依赖性强的鹞类（白腹鹞、鹊鹞）比例极高，也是海雕类罕见的记录点。",
        "phenology": {
            "春": {
                1: "白腹鹞、鹗、白尾鹞",
                2: "赤腹鹰、灰脸鵟鹰",
                3: "鹊鹞、燕隼"
            },
            "秋": {
                1: "赤腹鹰、鹊鹞(高峰)",
                2: "白腹鹞、红脚隼、灰脸鵟鹰",
                3: "普通鵟、白尾海雕(罕见记录)"
            }
        }
    }
]

# --- 5. 物种配置字典（扩展版）---
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


# --- 6. 辅助计算逻辑增强版 ---
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
        return "⭐⭐⭐⭐⭐", "【不可错过】爆发预警：历史极值结合完美气象动力"
    elif score >= 75:
        return "⭐⭐⭐⭐", "【非常推荐】动力条件优秀，迁徙流显著"
    elif score >= 60:
        return "⭐⭐⭐", "【值得一去】符合迁徙背景，适合常规守候"
    elif score >= 40:
        return "⭐⭐", "【视情前往】动力较弱，效率可能较低"
    else:
        return "⭐", "【建议放弃】学术预测显示迁徙流极其微弱或离散严重"


def get_kettle_description(prob):
    if prob >= 80:
        return "🔥 极易成柱", "热力对流极强，易见密集鹰柱"
    if prob >= 50:
        return "⛅ 可能成柱", "热力中等，或受阵风扰动"
    return "🍃 难以成柱", "气层稳定，对流动力不足"


def get_behavior_prediction(target_birds, score, kettle_prob, wind_speed):
    behaviors = []
    for bird in target_birds.split('、'):
        if bird in SPECIES_CONFIG:
            config = SPECIES_CONFIG[bird]
            if wind_speed > config['v_max'] * 0.8:
                behaviors.append(f"{bird}: 强风抑制({wind_speed:.1f}kts > {config['v_max']}kts阈值)")
            elif score > 75 and kettle_prob > 60:
                behaviors.append(f"{bird}: {config['behavior']} (热力增强)")
            else:
                behaviors.append(f"{bird}: {config['behavior']} (常规模式)")
    return " | ".join(behaviors) if behaviors else "无特定行为预测"


# --- 7. 核心学术模型增强版（修复版）---
def calculate_expert_score_v32(w, site, season, conf_val, peak_weight, target_birds, ebird_multiplier, ebird_warnings):
    # 初始化基础分数
    score = 65 * site['baseline'].get(season, 1.0) * peak_weight
    kettle_prob = 0
    warnings = list(ebird_warnings)
    uncertainty = int(30 * (1 - conf_val))
    front_multiplier = 1.0
    backlog_bonus = 0
    season_annealing = 1.0
    inversion_penalty = 0
    drift_side = None
    behavior_pred = ""
    thermal_efficiency = 0
    ridge_lift_efficiency = 0

    # 处理numpy.float32数据
    def safe_float(value):
        return float(value) if isinstance(value, (np.floating, np.integer)) else value

    # 转换所有气象数据为Python原生float类型
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
            if cross_product > 0:
                drift_side = "迎风面侧斜面"
            else:
                drift_side = "背风面侧斜面"
            warnings.append(f"🌬 侧风偏航({wind_diff:.0f}°)")

    # 物种敏感度分析
    heavy_species = ['林雕', '大鵟', '雕类', '秃鹫', '白尾海雕']
    small_species = ['隼类', '赤腹鹰', '黑冠鹃隼', '红脚隼']
    active_species = [s for s in SPECIES_CONFIG if s in target_birds]
    heavy_species_present = any(s in heavy_species for s in active_species)
    small_species_present = any(s in small_species for s in active_species)

    # 季节性退火检测
    current_month = datetime.datetime.now().month
    peak_months = list(site['peak_matrix'][season].keys()) if season in site['peak_matrix'] else []
    if peak_months and (current_month < min(peak_months) or current_month > max(peak_months)):
        season_annealing = 0.6
        warnings.append("🍂 物候衰减: 非核心迁徙窗口期")

    # 冷锋触发检测
    if (w.get('precip', 0) < -0.5 and
            w.get('cloud', 0) < -20 and
            w.get('w_spd', 0) > 5 and
            180 < w['w_dir'] < 270):
        front_multiplier = 1.5 if heavy_species_present else 1.3
        warnings.append("❄️ 冷锋触发: 大型雕类迁徙窗口开启" if heavy_species_present else "🌬 冷锋前沿: 迁徙流增强预期")

    # 修复点1: 初始化config变量，避免访问未定义的变量
    config = None
    thermal_req = 0.5
    ridge_lift_weight = 1.0

    if active_species:
        if heavy_species_present:
            thermal_req = 0.4
            ridge_lift_weight = 1.5
        else:
            # 找出活跃物种中热力需求最高的配置
            max_thermal_req = 0
            for s in active_species:
                if s in SPECIES_CONFIG and SPECIES_CONFIG[s]['thermal_req'] > max_thermal_req:
                    max_thermal_req = SPECIES_CONFIG[s]['thermal_req']
                    config = SPECIES_CONFIG[s]

            if config:
                thermal_req = config['thermal_req']
                ridge_lift_weight = 1.0
            else:
                thermal_req = 0.5
                ridge_lift_weight = 1.0

        # 修复点2: 只有在config存在时才检查风速限制
        if config and w['w_spd'] > config['v_max'] * 0.9:
            score -= 20
            wind_msg = f"⚠️ 强风限制{active_species}迁徙"
            if conf_val < 0.7 and w['w_spd'] > config['v_max'] * 0.8:
                uncertainty += 15
                wind_msg += " (模型波动大)"
            warnings.append(wind_msg)
        # 修复点3: 如果没有配置，但仍然有活跃物种，使用默认的风速限制检查
        elif not config and active_species and w['w_spd'] > 40:  # 默认风速限制
            score -= 15
            warnings.append(f"⚠️ 强风限制{active_species}迁徙(默认风速检查)")

        if thermal_req > 0.6 and w['li'] > -1.0:
            score -= 15 * (thermal_req / 0.8)
            warnings.append(f"🌡️ 热力不足，{active_species}不耐飞(LI={w['li']:.1f})")

    # 气象硬约束
    if w.get('precip', 0) > 0.03:
        return 0, 0, ["🌧 严重降水"], uncertainty, delta_T, None, "", 0, 0
    if w.get('cloud', 0) > 85:
        score -= 25
        if conf_val < 0.7:
            uncertainty += 10
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
        # 沿海站点特殊逻辑：海陆风效应
        if 8 < w['w_spd'] < 25 and w['w_dir'] in [site['fav_wind'][season] - 30, site['fav_wind'][season] + 30]:
            score += 20
            warnings.append("🌊 理想海陆风条件")
        elif w['w_spd'] > 40:
            score -= 20
            warnings.append("🌪 沿海强风限制")

    # 热力湿度修正
    thermal_base = min(abs(w['li']) * 12, 30) if w['li'] < 0 else 0
    if 'temp_850hPa' in w and 'temp_925hPa' in w and (w['temp_850hPa'] - w['temp_925hPa']) < 3:
        thermal_base *= 0.8
        warnings.append("💧 高湿抑制: 热气流抬升能力减弱")
    if w['w_spd'] > 28:
        thermal_base *= 0.4
    score += thermal_base

    # 鹰柱可能性计算
    if w['li'] < -1.0:
        wind_penalty = max(0, 1 - (w['w_spd'] / 45))
        cloud_bonus = 15 if w['cloud'] < 30 else (-10 if w['cloud'] > 70 else 0)
        kettle_prob = (abs(w['li']) * 20 + (w['cape'] / 25)) * wind_penalty + cloud_bonus
        kettle_prob = min(kettle_prob, 98)

    if delta_T > 0:
        kettle_prob = max(0, kettle_prob * (1 - delta_T * 0.1))

    # 行为预测和效率计算
    behavior_pred = get_behavior_prediction(target_birds, score, kettle_prob, w['w_spd'])
    thermal_efficiency = min(100, abs(w['li']) * 15) if w['li'] < 0 else 0
    if 'ridge_orient' in site:
        wind_diff = abs((w['w_dir'] - site['ridge_orient'] + 90) % 180 - 90)
        ridge_lift_efficiency = max(0, 100 - wind_diff * 2)

    # 最终评分
    final_s = min(100,
                  score * front_multiplier * season_annealing * ebird_multiplier + backlog_bonus - inversion_penalty)
    return (int(max(0, min(100, final_s))), int(kettle_prob), warnings,
            uncertainty, delta_T, drift_side, behavior_pred,
            thermal_efficiency, ridge_lift_efficiency)


# --- 8. 各监测点特殊计算函数和观测策略（专业增强版）---
def calculate_guilin_modifier(w, season):
    """
    基于广西喀斯特地貌及漓江水汽输送的修正模型
    参考：广西大学及中科院关于华南猛禽迁徙路径的气象关联研究
    """
    modifiers = []

    # 1. 漓江河谷-平原热力差异效应
    # 东南风引导低层暖湿空气沿河谷北上，受尧山地形阻挡形成动力抬升
    if 120 < w['w_dir'] < 220:
        delta_T = w.get('temp_925hPa', 0) - w.get('temp_850hPa', 0)
        if delta_T > 3:  # 强逆温层压制，猛禽被迫低飞
            modifiers.append(("低空压制（利于拍摄）", 0.85))
        else:
            modifiers.append(("河谷热通道", 1.25))

    # 2. 喀斯特孤峰剪切力效应
    # 尧山作为孤立高地，在中等风速下产生显著的背风坡涡旋
    karst_effect = 1.0
    if 10 < w['w_spd'] < 25:
        karst_effect = 1.2
        modifiers.append(("峰林动力增益", 1.2))
    elif w['w_spd'] > 35:
        # 强风导致严重紊流，猛禽避开山脊
        karst_effect = 0.6
        modifiers.append(("严重紊流风险", 0.6))

    # 3. 亚热带季风水汽修正
    humidity_effect = 1.0
    # 春季（3-5月）高湿度有利于形成碎积云，指示热气流位置
    if season == "春":
        if w.get('rh_surface', 0) > 75:
            humidity_effect = 1.15
            modifiers.append(("云标热气流", 1.15))
    return karst_effect * humidity_effect, modifiers


# 为每个监测点定义观测策略（基于权威观察经验）
SITE_OBSERVATION_STRATEGIES = {
    "都统岩": {
        "最佳观测点": [
            "1. 顶峰平台: 利用山脊线北东-南西走向产生的动力升力",
            "2. 东坡峭壁缘: 春季（3-5月）四川盆地水汽抬升，此处易形成热力支柱",
            "3. 西侧缓坡: 秋季（9-11月）冷空气翻越山脊后的下沉区，常有大型雕类（如林雕）利用动力翼装滑翔"
        ],
        "时间策略": [
            "• 春季: 10:00-14:00。重点观测凤头蜂鹰爆发，受四川盆地逆温层消散时间影响",
            "• 秋季: 09:30-16:00。冷锋过境后北风2-3级时，普通鵟、雀鹰规模极大",
            "• 特殊: 冷锋过境后1-2天，北风增强时观察大型雕类"
        ],
        "设备建议": [
            "• 必备: 8×42双筒，20-60×单筒（高倍单筒观察极高空猛禽）",
            "• 记录设备: 标记热力柱出现时间和集群大小",
            "• 防风装备: 山顶风大，需冲锋衣、手套"
        ],
        "地形特征": "龙泉山脉北段，典型的单斜山脊。迁徙路径受龙泉山褶断束导引"
    },
    "龙泉山": {
        "最佳观测点": [
            "1. 凉风顶/垭口: 典型的'瓶颈'地形，强制引导鹰群通过",
            "2. 南向开阔山脊: 春季观察北返的灰脸鵟鹰",
            "3. 林缘观测点: 重点搜索日本松雀鹰等低空突击型猛禽"
        ],
        "时间策略": [
            "• 春季: 清晨08:30即有低空过境，中午前后利用热气流高度攀升",
            "• 秋季: 11:00-15:00为高峰。根据《四川鸟类名录》记载，秋季猛禽多样性略高于春季",
            "• 特殊注意: 成都平原多雾，需关注能见度 > 5km 的窗口"
        ],
        "设备建议": [
            "• 必备: 10×42双筒，25-50×单筒",
            "• 移动设备: 长山脊需移动观察，建议使用对讲机协调多点观察",
            "• 记录: 标记不同观测点的过境数量对比"
        ],
        "地形特征": "南北走向的狭长山脊走廊，是横断山脉以东最重要的迁徙通道"
    },
    "尧山电视台": {
        "最佳观测点": [
            "1. 电视塔顶层: 360度覆盖，可观察到从中越边境及南岭北上的路径",
            "2. 缆车沿线开阔地: 观察林间起飞的赤腹鹰",
            "3. 东坡步道: 春季东南风迎风面，热力最佳"
        ],
        "时间策略": [
            "• 春季: 3月下旬至4月中旬，雨后转晴的第一个大晴天，09:30-15:00",
            "• 秋季: 10月中下旬，10:00-16:00",
            "• 特殊: 注意'河谷效应'，猛禽常沿漓江水系导航"
        ],
        "设备建议": [
            "• 必备: 8×42双筒，20-60×单筒",
            "• 三脚架: 山顶风大，需重型脚架",
            "• 记录: GPS记录迁徙路径，标记河谷通道"
        ],
        "地形特征": "漓江东岸最高峰，喀斯特孤峰与背斜山脊结合部"
    },
    "冠头岭": {
        "最佳观测点": [
            "1. 北平点（主要）: 秋季（10-11月）黑冠鹃隼集群的必经之地",
            "2. 海角灯塔: 观察猛禽在海上寻找热气流失败后的折返行为",
            "3. 东坡悬崖: 春季南风迎风面，观察低空过境"
        ],
        "时间策略": [
            "• 春季: 08:00-11:00。南风引导下，低空过境频繁",
            "• 秋季: 13:00-17:00。黑冠鹃隼通常在午后至傍晚形成巨大的'鹰柱'",
            "• 特殊: 南风增强时，注意黑冠鹃隼前锋"
        ],
        "设备建议": [
            "• 必备: 8×32双筒（海边湿度大），15-45×单筒",
            "• 防潮: 相机、望远镜防潮措施，海边湿度大",
            "• 广角双筒: 应对近距离、大群爆发的黑冠鹃隼"
        ],
        "地形特征": "海角（Cape）地形。猛禽跨海前的最后集结点，或沿海线绕行的转折点"
    },
    "九龙山": {
        "最佳观测点": [
            "1. 山顶观海平台: 秋季（9月）观察赤腹鹰'过海'前的盘旋",
            "2. 西侧谷地: 春季避风处，猛禽在此修整",
            "3. 东侧滩涂: 观察绕行水域的猛禽集群"
        ],
        "时间策略": [
            "• 春季: 规模较小，主要为散兵，09:00-15:00",
            "• 秋季（核心）: 9月中旬。受冷高压控制，北风吹向海洋，赤腹鹰爆发期单日可达数千只，10:00-16:00",
            "• 特殊: 午后热力升力减弱，鹰群高度会迅速下降，注意低空观察"
        ],
        "设备建议": [
            "• 必备: 8×42双筒，20-60×单筒",
            "• 长焦: 400mm以上镜头拍摄滩涂猛禽",
            "• 记录: 潮汐时间对观察影响大，需记录潮汐与过境时间关系"
        ],
        "地形特征": "杭州湾北岸孤山。海陆风热力环流显著，典型的内陆迁徙向沿海迁徙转换点"
    },
    "渔洋山": {
        "最佳观测点": [
            "1. 三连岛视野: 观察猛禽试图'切半径'跨越水面的行为",
            "2. 南麓坡顶: 春季东南风时，承接从浙江北上的凤头蜂鹰",
            "3. 湖岸观景台: 太湖东岸全景，观察绕湖飞行"
        ],
        "时间策略": [
            "• 春季: 5月上旬。凤头蜂鹰的主战场，08:30-14:30",
            "• 秋季: 10月。普通鵟、隼类较多，10:00-16:00",
            "• 特殊: 晴天午后，湖岸线热力气旋明显，注意观察绕湖飞行"
        ],
        "设备建议": [
            "• 必备: 8×42双筒，15-45×单筒",
            "• 偏振镜: 减少湖面反光，便于发现低空背景下的猛禽",
            "• 轻便装备: 多观测点移动观察，标记湖岸线飞行路径"
        ],
        "地形特征": "太湖滨湖丘陵。猛禽在跨越大型水体（太湖）时的'心理屏障'导致其沿湖岸绕行"
    },
    "南汇东滩": {
        "最佳观测点": [
            "1. 南汇嘴观海平台: 上海陆地最东南角，观察鹗和隼类沿海岸线飞行",
            "2. 滴水湖外围滩涂: 秋季红脚隼集群过境前的集结地",
            "3. 东滩湿地栈道: 观察白尾鹞、鹗等湿地猛禽"
        ],
        "时间策略": [
            "• 春季: 3-5月，08:00-12:00。鹗和隼类沿海岸线北迁",
            "• 秋季: 9月中旬-10月下旬，13:00-17:00。红脚隼集群爆发期，受海陆风环流影响明显",
            "• 特殊: 东北风或偏北风天气，猛禽被'压'向海岸线，观察效果最佳"
        ],
        "设备建议": [
            "• 必备: 8×32双筒（海边湿度大），15-45×单筒",
            "• 长焦: 500mm以上镜头拍摄滩涂猛禽",
            "• 防风: 海边风大，需重型三脚架和防风装备"
        ],
        "地形特征": "上海陆地最东南角。典型的海岸线引导效应，秋季是小型隼类跨海前的集结地"
    },
    "崇明东滩": {
        "最佳观测点": [
            "1. 东滩鸟类保护区观鸟台: 长江入海口全景，观察猛禽'跳岛'迁徙",
            "2. 湿地栈道沿线: 鹞类（白腹鹞、鹊鹞）在湿地生境的出现率极高",
            "3. 堤坝外侧滩涂: 观察鹗捕鱼及海雕类罕见记录"
        ],
        "时间策略": [
            "• 春季: 3-5月，09:00-15:00。鹞类北迁高峰",
            "• 秋季: 9-11月，10:00-16:00。鹞类南迁及红脚隼过境",
            "• 特殊: 西北风天气有利于猛禽在长江口岛链间移动，观察效果最佳"
        ],
        "设备建议": [
            "• 必备: 8×42双筒，20-60×单筒",
            "• 望远镜: 高倍单筒观察远距离猛禽",
            "• 记录设备: GPS记录迁徙路径，特别关注鹞类行为"
        ],
        "地形特征": "长江入海口。猛禽迁徙的重要'跳岛'点，鹞类在湿地生境的出现率显著高于其他山地站点"
    }
}


# --- 9. 专业报告生成模块（专业增强版）---
def generate_professional_report(site, results, ebird_evidence, ebird_multiplier, sel_date, weather_summary=None):
    """生成专业级分析报告"""
    # 找出最佳时段
    if not results:
        return "❌ 无计算结果"

    # 根据评分找出最佳观测窗口（黄金观测窗口）
    # 黄金观测窗口定义：连续3小时平均分最高的时段
    window_size = 3
    best_window_score = 0
    best_window_start = 4
    best_window_end = 4 + window_size - 1

    # 遍历所有可能的3小时窗口
    for start_hour in range(4, 21 - window_size + 1):
        window_scores = []
        for h in range(start_hour, start_hour + window_size):
            # 查找对应小时的评分
            hour_score = 0
            for r in results:
                if r[2] == h:  # r[2]是小时
                    hour_score = r[0]
                    break
            window_scores.append(hour_score)

        avg_score = sum(window_scores) / window_size
        if avg_score > best_window_score:
            best_window_score = avg_score
            best_window_start = start_hour
            best_window_end = start_hour + window_size - 1

    # 获取最佳窗口的最高分小时
    best_window_data = []
    for h in range(best_window_start, best_window_end + 1):
        for r in results:
            if r[2] == h:
                best_window_data.append(r)
                break

    if not best_window_data:
        best_hour = max(results, key=lambda x: x[0])
    else:
        best_hour = max(best_window_data, key=lambda x: x[0])

    avg_score = sum(r[0] for r in results) / len(results) if results else 0

    # 获取季节信息
    season, _, _ = get_phenology_info(site, sel_date)

    # 获取站点观测策略
    site_strategy = SITE_OBSERVATION_STRATEGIES.get(site['name'], {})

    # 黄金观测窗口的详细描述
    def get_golden_window_description(golden_window_data, season):
        """根据黄金观测窗口的气象数据生成详细描述"""
        descriptions = []

        if not golden_window_data:
            return "无黄金窗口数据"

        avg_score = sum(r[0] for r in golden_window_data) / len(golden_window_data)
        avg_li = sum(r[3] for r in golden_window_data) / len(golden_window_data)
        avg_wind = sum(r[6] for r in golden_window_data) / len(golden_window_data)
        avg_kettle = sum(r[1] for r in golden_window_data) / len(golden_window_data)

        # 基于评分
        if avg_score >= 85:
            descriptions.append("爆发级观测窗口")
        elif avg_score >= 70:
            descriptions.append("优秀观测窗口")
        elif avg_score >= 55:
            descriptions.append("良好观测窗口")
        else:
            descriptions.append("一般观测窗口")

        # 基于热力条件
        if avg_li < -2.0:
            descriptions.append("强热力发展")
        elif avg_li < -1.0:
            descriptions.append("中等热力")
        else:
            descriptions.append("弱热力条件")

        # 基于风速
        if 10 < avg_wind < 25:
            descriptions.append("理想风速")
        elif avg_wind <= 10:
            descriptions.append("低风速")
        else:
            descriptions.append("较高风速")

        # 基于鹰柱概率
        if avg_kettle > 70:
            descriptions.append("高集群概率")
        elif avg_kettle > 40:
            descriptions.append("中等集群概率")

        # 基于季节
        if season == "春":
            descriptions.append("春季迁徙高峰")
        elif season == "秋":
            descriptions.append("秋季迁徙高峰")

        return " | ".join(descriptions)

    golden_window_desc = get_golden_window_description(best_window_data, season)

    # 核心综述
    report = [
        "=" * 120,
        f"🦅 猛禽迁徙学术研判报告 v35.0 | {site['name']} | {datetime.date.today()}",
        "=" * 120,
        "",
        "【核心综述】",
        f"* 迁徙适宜度总分: {best_hour[0]}/100 ({get_recommend_index_detailed(best_hour[0])[0]})",
        f"* 黄金观测窗口: {best_window_start:02d}:00-{best_window_end:02d}:00 (连续{window_size}小时平均分:{best_window_score:.1f})",
        f"* 窗口特征: {golden_window_desc}",
        f"* 预测强度: {'离散(Low)' if avg_score < 50 else '稳定(Moderate)' if avg_score < 70 else '集中(Heavy)' if avg_score < 85 else '爆发(Massive)'}",
        ""
    ]

    # eBird实证数据
    if ebird_evidence:
        report.extend([
            "【实证数据】",
            f"- 最新记录: {ebird_evidence['date'].strftime('%m-%d %H:%M')} 在 {ebird_evidence['loc']}",
            f"  观测到 {ebird_evidence['count']}只 {ebird_evidence['species']}",
            f"- 空间修正系数: {ebird_multiplier:.2f}x ({'+' + str(int((ebird_multiplier - 1) * 100)) + '%' if ebird_multiplier > 1 else str(int(ebird_multiplier * 100)) + '%'})",
            ""
        ])

    # 动态评分表 (04:00-20:00)
    report.extend([
        "【动态评分表 (04:00-20:00)】",
        "-" * 120,
        f"{'时刻':^8} | {'评分':^8} | {'推荐':^10} | {'鹰柱%':^8} | {'风速':^6} | {'风向':^6} | {'LI':^6} | {'ΔT':^6} | {'行为预测':^30}",
        "-" * 120
    ])

    # 获取所有小时的评分
    all_hours_data = {}
    for r in results:
        all_hours_data[r[2]] = r

    # 输出04:00-20:00
    for h in range(4, 21):
        if h in all_hours_data:
            r = all_hours_data[h]
            stars, _ = get_recommend_index_detailed(r[0])
            k_title, _ = get_kettle_description(r[1])
            delta_T_display = f"{r[5]:+.1f}" if r[5] != 0 else "-"
            is_golden = "🌅" if best_window_start <= h <= best_window_end else ""

            report.append(
                f"{h:02d}:00{is_golden} | {r[0]:^8} | {stars:^10} | {r[1]:^3}% ({k_title[:5]}) | "
                f"{r[6]:^6.1f}k | {r[4]:^6.0f}° | {r[3]:^6.1f} | {delta_T_display:^6} | {r[7][:30]}"
            )
        else:
            # 没有数据的时段
            report.append(
                f"{h:02d}:00 | {'N/A':^8} | {'':^10} | {'':^8} | {'':^6} | {'':^6} | {'':^6} | {'':^6} | {'无数据':^30}")

    # 天气专项分析
    report.extend([
        "",
        "【天气专项分析】",
        f"1. 逆温层风险: ΔT={best_hour[5]:.1f}℃ → {'轻微影响' if best_hour[5] < 0.5 else '中度抑制' if best_hour[5] < 1.0 else '严重阻碍'}热力发展",
        f"2. 地形升力效率: {best_hour[9]:.0f}% (风向与山脊夹角{abs((best_hour[4] - site['ridge_orient'] + 90) % 180 - 90):.0f}°)",
        f"3. 热力转化率: {best_hour[8]:.0f}% (LI={best_hour[3]:.1f}, CAPE={best_hour[1]:.0f}J/kg)",
        f"4. 风速适宜度: {best_hour[6]:.1f}kts → {'理想地形升力' if 15 < best_hour[6] < 30 else '偏低' if best_hour[6] <= 15 else '可能抑制热力'}",
        ""
    ])

    # 黄金观测窗口详细分析
    report.extend([
        "【黄金观测窗口分析】",
        f"* 窗口时段: {best_window_start:02d}:00-{best_window_end:02d}:00 (气象算法自动计算)",
        f"* 窗口平均分: {best_window_score:.1f}/100",
        f"* 窗口特征: {golden_window_desc}",
        f"* 选取依据: 连续{window_size}小时平均迁徙适宜度最高",
        ""
    ])

    # 观测策略
    report.extend([
        "【专业观测策略】",
        f"1. 黄金窗口配置:",
        f"   - {best_window_start:02d}:00-{best_window_end:02d}:00: 使用{20 if best_window_score > 75 else 40}倍镜",
        f"   - 搜索高度: {300 if best_hour[5] > 0 else 500}-800m {'迎风坡' if best_hour[6] > 15 else '山脊线'}",
        "2. 重点识别特征:",
    ])

    if '|' in best_hour[7]:
        first_bird = best_hour[7].split('|')[0].split(':')[0]
    elif ':' in best_hour[7]:
        first_bird = best_hour[7].split(':')[0]
    else:
        first_bird = "猛禽"

    report.append(f"   - 注意{first_bird}的振翅频率")
    report.extend([
        "3. 数据记录建议:",
        "   - 每小时记录集群大小和飞行方向",
        "   - 标记热力柱出现时间和持续时间",
    ])

    # 站点特别提示
    if site_strategy:
        report.extend([
            "",
            f"【{site['name']}特别提示】",
            "=" * 60,
            f"* 地形特征: {site_strategy.get('地形特征', site['desc'][:50])}",
            "",
            "最佳观测点:"
        ])

        for point in site_strategy.get("最佳观测点", []):
            report.append(f"  {point}")

        report.extend([
            "",
            "时间策略:"
        ])

        for strategy in site_strategy.get("时间策略", []):
            report.append(f"  {strategy}")

        report.extend([
            "",
            "设备建议:"
        ])

        for equipment in site_strategy.get("设备建议", []):
            report.append(f"  {equipment}")

    report.append("")
    report.append("=" * 120)

    return "\n".join(report)


# --- 10. 主程序增强版（修复版）---
def raptor_expert_v32():
    print("\n" + "█" * 85)
    print("      🦅 猛禽迁徙专家系统 v35.0 (8站点专业增强版)")
    print("█" * 85)

    # 显示监测站列表
    for i, h in enumerate(HOTSPOTS, 1):
        print(f"{i}. {h['name']} ({h['type']})\n    └─ {h['desc']}")

    try:
        site_choice = int(input("\n请选择站点序号 (1-8): ")) - 1
        site = HOTSPOTS[site_choice]
    except (ValueError, IndexError):
        print("❌ 站点选择无效")
        return

    # 日期选择
    week_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    date_list = [datetime.date.today() + datetime.timedelta(days=i) for i in range(7)]
    for i, d in enumerate(date_list):
        label = "今天" if i == 0 else "明天" if i == 1 else week_map[d.weekday()]
        print(f"{i}. {d} ({label})")

    try:
        d_idx = int(input("请选择日期序号 (0-6): "))
        sel_date = date_list[d_idx]
    except (ValueError, IndexError):
        print("❌ 日期选择无效")
        return

    # 基础参数提取
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
    session = requests.Session()
    session.mount("https://", TLSAdapter())
    session.verify = False
    cache_session = requests_cache.CachedSession('.cache', backend='sqlite', expire_after=3600, session=session)
    openmeteo = openmeteo_requests.Client(session=retry(cache_session))

    try:
        url = "https://api.open-meteo.com/v1/forecast"
        # 获取04:00-20:00的气象数据
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

        # --- 核心计算循环 (04:00-20:00) ---
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

        # --- 生成并打印报告 ---
        report = generate_professional_report(site, results, ebird_evidence, ebird_multiplier, sel_date)
        print(report)

    except Exception as e:
        print(f"❌ 程序运行出错: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    raptor_expert_v32()
