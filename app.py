import os
import sys
import json
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入核心算法模块
from raptorcast_v4_guilin import (
    raptor_expert_v32, HOTSPOTS, generate_professional_report, 
    calculate_expert_score_v32, get_phenology_info, get_peak_weight, 
    process_ebird_data, EBirdClient, EBIRD_API_KEY, EBIRD_RADIUS, 
    EBIRD_BACK_DAYS, EBIRD_CACHE_DIR
)

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

class FalconForecastApp:
    def __init__(self, root):
        self.root = root
        self.root.title("猛禽迁徙预测系统")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # 加载配置
        self.config = self.load_config()
        
        # 创建主框架
        self.main_frame = ttk.Notebook(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建算法执行选项卡
        self.create_algorithm_tab()
        
        # 创建配置选项卡
        self.create_config_tab()
        
        # 创建关于选项卡
        self.create_about_tab()
    
    def load_config(self):
        """加载配置文件"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                messagebox.showerror("错误", f"加载配置文件失败: {e}")
                return {}
        else:
            # 默认配置
            return {
                "ebird_api_key": "",
                "china_birding_token": "",
                "ebird_search_radius": 50,
                "ebird_backlook_days": 5
            }
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", "配置已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置文件失败: {e}")
    
    def create_algorithm_tab(self):
        """创建算法执行选项卡"""
        algorithm_tab = ttk.Frame(self.main_frame)
        self.main_frame.add(algorithm_tab, text="算法执行")
        
        # 站点选择
        ttk.Label(algorithm_tab, text="选择监测站点:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        
        self.site_var = tk.StringVar()
        site_combobox = ttk.Combobox(algorithm_tab, textvariable=self.site_var, width=30)
        site_combobox['values'] = [site['name'] for site in HOTSPOTS]
        if HOTSPOTS:
            site_combobox.current(0)
        site_combobox.grid(row=0, column=1, padx=10, pady=10, sticky=tk.W)
        
        # 日期选择
        ttk.Label(algorithm_tab, text="选择日期:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        
        self.date_var = tk.StringVar()
        date_combobox = ttk.Combobox(algorithm_tab, textvariable=self.date_var, width=30)
        
        # 生成未来7天的日期
        date_list = []
        week_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for i in range(7):
            date = datetime.date.today() + datetime.timedelta(days=i)
            label = "今天" if i == 0 else "明天" if i == 1 else week_map[date.weekday()]
            date_list.append(f"{date} ({label})")
        
        date_combobox['values'] = date_list
        if date_list:
            date_combobox.current(0)
        date_combobox.grid(row=1, column=1, padx=10, pady=10, sticky=tk.W)
        
        # 执行按钮
        execute_button = ttk.Button(algorithm_tab, text="执行预测", command=self.execute_algorithm)
        execute_button.grid(row=2, column=0, columnspan=2, padx=10, pady=20)
        
        # 结果显示
        ttk.Label(algorithm_tab, text="预测结果:").grid(row=3, column=0, padx=10, pady=10, sticky=tk.NW)
        
        self.result_text = tk.Text(algorithm_tab, height=20, width=90)
        self.result_text.grid(row=4, column=0, columnspan=2, padx=10, pady=10)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(algorithm_tab, orient=tk.VERTICAL, command=self.result_text.yview)
        scrollbar.grid(row=4, column=2, sticky=tk.NS)
        self.result_text.config(yscrollcommand=scrollbar.set)
    
    def create_config_tab(self):
        """创建配置选项卡"""
        config_tab = ttk.Frame(self.main_frame)
        self.main_frame.add(config_tab, text="配置管理")
        
        # eBird API Key
        ttk.Label(config_tab, text="eBird API Key:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        self.ebird_api_var = tk.StringVar(value=self.config.get("ebird_api_key", ""))
        ttk.Entry(config_tab, textvariable=self.ebird_api_var, width=50).grid(row=0, column=1, padx=10, pady=10, sticky=tk.W)
        
        # 中国观鸟记录中心Token
        ttk.Label(config_tab, text="中国观鸟记录中心Token:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        self.china_birding_var = tk.StringVar(value=self.config.get("china_birding_token", ""))
        ttk.Entry(config_tab, textvariable=self.china_birding_var, width=50).grid(row=1, column=1, padx=10, pady=10, sticky=tk.W)
        
        # eBird搜索半径
        ttk.Label(config_tab, text="eBird搜索半径 (公里):").grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)
        self.ebird_radius_var = tk.StringVar(value=str(self.config.get("ebird_search_radius", 50)))
        ttk.Entry(config_tab, textvariable=self.ebird_radius_var, width=10).grid(row=2, column=1, padx=10, pady=10, sticky=tk.W)
        
        # eBird回溯天数
        ttk.Label(config_tab, text="eBird回溯天数:").grid(row=3, column=0, padx=10, pady=10, sticky=tk.W)
        self.ebird_backdays_var = tk.StringVar(value=str(self.config.get("ebird_backlook_days", 5)))
        ttk.Entry(config_tab, textvariable=self.ebird_backdays_var, width=10).grid(row=3, column=1, padx=10, pady=10, sticky=tk.W)
        
        # 保存按钮
        save_button = ttk.Button(config_tab, text="保存配置", command=self.update_config)
        save_button.grid(row=4, column=0, columnspan=2, padx=10, pady=20)
        
        # 提示信息
        ttk.Label(config_tab, text="提示:", font=('Arial', 10, 'bold')).grid(row=5, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Label(config_tab, text="1. eBird API Key可从 https://ebird.org/api/keygen 获取", font=('Arial', 10)).grid(row=6, column=0, columnspan=2, padx=20, pady=2, sticky=tk.W)
        ttk.Label(config_tab, text="2. 中国观鸟记录中心Token可从相关平台获取", font=('Arial', 10)).grid(row=7, column=0, columnspan=2, padx=20, pady=2, sticky=tk.W)
    
    def create_about_tab(self):
        """创建关于选项卡"""
        about_tab = ttk.Frame(self.main_frame)
        self.main_frame.add(about_tab, text="关于")
        
        ttk.Label(about_tab, text="猛禽迁徙预测系统", font=('Arial', 16, 'bold')).pack(pady=20)
        ttk.Label(about_tab, text="版本: v1.0.0").pack(pady=5)
        ttk.Label(about_tab, text="基于AI的猛禽迁徙预测Web应用").pack(pady=5)
        ttk.Label(about_tab, text="融合地形动力学、热力热力学与物种特异性生物阈值").pack(pady=5)
        ttk.Label(about_tab, text="支持8个监测站点的迁徙预测").pack(pady=5)
        
        ttk.Button(about_tab, text="访问项目GitHub", command=lambda: webbrowser.open("https://github.com/jasonzhouyu/falcon_forecast")).pack(pady=20)
    
    def update_config(self):
        """更新配置"""
        try:
            self.config["ebird_api_key"] = self.ebird_api_var.get()
            self.config["china_birding_token"] = self.china_birding_var.get()
            self.config["ebird_search_radius"] = int(self.ebird_radius_var.get())
            self.config["ebird_backlook_days"] = int(self.ebird_backdays_var.get())
            self.save_config()
        except ValueError as e:
            messagebox.showerror("错误", f"配置值无效: {e}")
    
    def execute_algorithm(self):
        """执行预测算法"""
        # 清空结果
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, "正在执行预测，请稍候...\n")
        
        # 在新线程中执行算法
        threading.Thread(target=self.run_algorithm).start()
    
    def run_algorithm(self):
        """运行预测算法"""
        try:
            # 获取选中的站点
            site_name = self.site_var.get()
            site = None
            for s in HOTSPOTS:
                if s['name'] == site_name:
                    site = s
                    break
            
            if not site:
                self.result_text.insert(tk.END, "错误: 未找到选中的站点\n")
                return
            
            # 获取选中的日期
            date_str = self.date_var.get().split(' ')[0]
            sel_date = datetime.date.fromisoformat(date_str)
            
            # 基础参数提取
            d_idx = (sel_date - datetime.date.today()).days
            conf_val = 1.0 if d_idx == 0 else 0.9 if d_idx == 1 else 0.8 if d_idx <= 3 else 0.5
            season, target_birds, pheno_desc = get_phenology_info(site, sel_date)
            peak_w = get_peak_weight(site, sel_date, season)
            current_month = sel_date.month
            peak_months = list(site['peak_matrix'][season].keys()) if season in site['peak_matrix'] else []
            
            # 获取eBird数据
            ebird = EBirdClient(
                self.config.get("ebird_api_key", ""),
                self.config.get("ebird_search_radius", 50),
                self.config.get("ebird_backlook_days", 5),
                EBIRD_CACHE_DIR
            )
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
            
            # 显示结果
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, report)
            
        except Exception as e:
            import traceback
            error_message = f"错误: {str(e)}\n{traceback.format_exc()}"
            self.result_text.delete(1.0, tk.END)
            self.result_text.insert(tk.END, error_message)

def main():
    root = tk.Tk()
    app = FalconForecastApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
