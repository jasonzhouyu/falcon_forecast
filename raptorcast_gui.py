# -*- coding: utf-8 -*-
"""
猛禽迁徙预测系统 - GUI 版本 (简洁美观UI)
"""
import os
import sys
import io
import traceback

# 添加日志文件
def setup_logging():
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_log.txt")
    if getattr(sys, 'frozen', False):
        log_file = os.path.join(os.path.dirname(sys.executable), "debug_log.txt")
    
    # 重定向 stdout 和 stderr 到日志文件
    class Logger:
        def __init__(self, log_file):
            self.log_file = log_file
            self.console = sys.stdout
        def write(self, message):
            self.console.write(message)
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(message)
            except:
                pass
        def flush(self):
            self.console.flush()
    
    sys.stdout = Logger(log_file)
    sys.stderr = Logger(log_file)

# 设置日志
setup_logging()

print("=== 猛禽迁徙预测系统启动 ===")
print(f"当前目录: {os.getcwd()}")
print(f"Python 版本: {sys.version}")
print(f"可执行文件路径: {sys.executable}")
print(f"是否打包: {getattr(sys, 'frozen', False)}")

# 在某些环境（如 PyInstaller 打包、无控制台模式）中，sys.stdout/stderr 可能为 None
# 必须先检查是否为 None，再检查 buffer 属性
if sys.stdout is None:
    sys.stdout = io.StringIO()
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

if sys.stderr is None:
    sys.stderr = io.StringIO()
elif hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import datetime
import urllib3
import ssl
import requests
import openmeteo_requests
import requests_cache
from retry_requests import retry
from pathlib import Path
import json
import threading

# 获取正确的工作目录
def get_app_path():
    """获取应用正确的路径，处理 PyInstaller 打包情况"""
    if getattr(sys, 'frozen', False):
        # 打包后的情况
        base_path = os.path.dirname(sys.executable)
        # 检查 algorithm.py 是否在 exe 同目录下
        alt_path = os.path.join(base_path, 'algorithm.py')
        if os.path.exists(alt_path):
            return base_path
        # 检查是否在 _MEIPASS 临时目录中
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        return base_path
    else:
        # 开发模式
        return os.path.dirname(os.path.abspath(__file__))

app_path = get_app_path()
sys.path.insert(0, app_path)

# 导入算法模块
try:
    from algorithm import (
        HOTSPOTS, get_phenology_info, get_peak_weight,
        calculate_expert_score_v32, calculate_guilin_modifier,
        generate_professional_report
    )
except ImportError as e:
    # 如果导入失败，显示错误
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    tk.Message(None, text=f"无法加载算法模块: {e}", icon='error').grid()
    root.destroy()
    sys.exit(1)

# SSL
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


urllib3.disable_warnings()

# 配置路径 - 支持打包后的路径
def get_config_dir():
    """获取配置目录"""
    if getattr(sys, 'frozen', False):
        # 打包后：放在 exe 同目录下的 config 文件夹
        return Path(sys.executable).parent / "config"
    else:
        # 开发模式
        return Path(__file__).parent / "config"

CONFIG_FILE = get_config_dir() / "settings.json"

def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"ebird_api_key": "", "search_radius": 50, "backlook_days": 5}

def save_config(config):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class RaptorCastApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🦅 猛禽迁徙预测系统 v35.0")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)
        
        # 样式配置
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # 自定义颜色
        self.colors = {
            'bg': '#f5f7fa',
            'header': '#2c3e50',
            'accent': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'text': '#2c3e50',
            'light_text': '#7f8c8d'
        }
        
        self.config = load_config()
        self.setup_styles()
        self.create_ui()
        
    def setup_styles(self):
        self.style.configure('Title.TLabel', font=('Microsoft YaHei', 22, 'bold'), background=self.colors['header'], foreground='white')
        self.style.configure('Subtitle.TLabel', font=('Segoe UI', 10), background=self.colors['header'], foreground='#a0a0a0')
        self.style.configure('Header.TLabel', font=('Microsoft YaHei', 12, 'bold'), foreground=self.colors['text'])
        self.style.configure('Info.TLabel', font=('Microsoft YaHei', 9), foreground=self.colors['light_text'])
        self.style.configure('Accent.TButton', font=('Microsoft YaHei', 11, 'bold'))
        
    def create_ui(self):
        # 顶部深色标题栏
        header = tk.Frame(self.root, bg=self.colors['header'], height=80)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        title = ttk.Label(header, text="🦅 猛禽迁徙预测系统", style='Title.TLabel')
        title.pack(pady=(15, 5))
        
        subtitle = ttk.Label(header, text="Raptor Migration Forecasting System v35.0", style='Subtitle.TLabel')
        subtitle.pack(pady=(0, 10))
        
        # 主容器
        main = tk.Frame(self.root, bg=self.colors['bg'])
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 左侧控制面板
        left = tk.Frame(main, bg='white', relief=tk.RAISED, bd=1)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        
        # 左侧标题
        left_title = tk.Frame(left, bg=self.colors['accent'], height=40)
        left_title.pack(fill=tk.X)
        left_title.pack_propagate(False)
        tk.Label(left_title, text="⚙️ 控制面板", bg=self.colors['accent'], fg='white', 
                font=('Microsoft YaHei', 12, 'bold')).pack(pady=8)
        
        # 左侧内容
        left_content = tk.Frame(left, bg='white', padx=15, pady=15)
        left_content.pack(fill=tk.BOTH, expand=True)
        
        # 站点选择
        ttk.Label(left_content, text="📍 监测站点", style='Header.TLabel').pack(anchor=tk.W, pady=(10, 5))
        
        self.site_var = tk.StringVar(value=HOTSPOTS[2]['name'])
        site_names = [h['name'] for h in HOTSPOTS]
        self.site_combo = ttk.Combobox(left_content, textvariable=self.site_var, values=site_names, 
                                        state='readonly', font=('Microsoft YaHei', 10))
        self.site_combo.pack(fill=tk.X, pady=(0, 15))
        
        # 日期选择
        ttk.Label(left_content, text="📅 预测日期", style='Header.TLabel').pack(anchor=tk.W, pady=(10, 5))
        
        today = datetime.date.today()
        self.date_options = [(f"{today + datetime.timedelta(days=i)}", i) for i in range(7)]
        self.date_var = tk.StringVar(value=self.date_options[0][0])
        
        date_display = [f"今天 ({self.date_options[0][0]})", 
                       f"明天 ({self.date_options[1][0]})",
                       f"后天 ({self.date_options[2][0]})"] + [d[0] for d in self.date_options[3:]]
        
        self.date_combo = ttk.Combobox(left_content, textvariable=self.date_var, values=date_display,
                                        state='readonly', font=('Microsoft YaHei', 10))
        self.date_combo.pack(fill=tk.X, pady=(0, 20))
        
        # 按钮
        self.run_btn = tk.Button(left_content, text="🚀 开始预测", 
                                 bg=self.colors['success'], fg='white',
                                 font=('Microsoft YaHei', 12, 'bold'),
                                 relief=tk.FLAT, padx=20, pady=10,
                                 cursor='hand2', command=self.run_prediction)
        self.run_btn.pack(pady=10, fill=tk.X)
        
        config_btn = tk.Button(left_content, text="⚙️ API 配置",
                              bg=self.colors['accent'], fg='white',
                              font=('Microsoft YaHei', 10),
                              relief=tk.FLAT, padx=20, pady=8,
                              cursor='hand2', command=self.open_config)
        config_btn.pack(pady=5, fill=tk.X)
        
        # API 状态
        self.api_status = tk.Label(left_content, text="", font=('Microsoft YaHei', 9),
                                   bg='white', fg=self.colors['warning'])
        self.api_status.pack(pady=15)
        self.update_api_status()
        
        # 站点信息
        info_frame = tk.Frame(left_content, bg='#ecf0f1', relief=tk.FLAT, padx=10, pady=10)
        info_frame.pack(pady=10, fill=tk.X)
        
        self.site_info = tk.Label(info_frame, text="", font=('Microsoft YaHei', 9),
                                  bg='#ecf0f1', fg=self.colors['light_text'], justify=tk.LEFT)
        self.site_info.pack()
        
        self.site_combo.bind('<<ComboboxSelected>>', self.on_site_change)
        self.on_site_change()
        
        # 右侧结果面板
        right = tk.Frame(main, bg='white', relief=tk.RAISED, bd=1)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        right_title = tk.Frame(right, bg=self.colors['accent'], height=40)
        right_title.pack(fill=tk.X)
        right_title.pack_propagate(False)
        tk.Label(right_title, text="📊 预测结果", bg=self.colors['accent'], fg='white',
                font=('Microsoft YaHei', 12, 'bold')).pack(pady=8)
        
        self.result_text = scrolledtext.ScrolledText(right, wrap=tk.WORD, font=('Consolas', 10),
                                                    bg='#fafafa', relief=tk.FLAT, bd=0)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 初始提示
        self.result_text.insert(1.0, "👋 欢迎使用猛禽迁徙预测系统！\n\n请在左侧选择：\n  1. 监测站点\n  2. 预测日期\n\n然后点击「🚀 开始预测」按钮获取迁徙报告。")
        
        # 底部状态栏
        status = tk.Frame(self.root, bg='#ecf0f1', height=30)
        status.pack(fill=tk.X, side=tk.BOTTOM)
        status.pack_propagate(False)
        
        self.status_bar = tk.Label(status, text="✅ 就绪", bg='#ecf0f1', 
                                    fg=self.colors['light_text'], font=('Microsoft YaHei', 9), anchor=tk.W)
        self.status_bar.pack(side=tk.LEFT, padx=15)
        
    def on_site_change(self, event=None):
        name = self.site_var.get()
        for h in HOTSPOTS:
            if h['name'] == name:
                self.site_info.config(text=f"类型: {h['type']}\n{h['desc'][:40]}...")
                break
                
    def update_api_status(self):
        if self.config.get("ebird_api_key"):
            self.api_status.config(text="✅ eBird API 已配置", fg=self.colors['success'])
        else:
            self.api_status.config(text="⚠️ eBird API 未配置\n(可跳过，不影响基本功能)", fg=self.colors['warning'])
    
    def open_config(self):
        win = tk.Toplevel(self.root)
        win.title("⚙️ API 配置")
        win.geometry("420x380")
        win.transient(self.root)
        win.resizable(False, False)
        
        # 内容
        content = tk.Frame(win, padx=25, pady=20)
        content.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(content, text="🔑 eBird API Key", font=('Microsoft YaHei', 11, 'bold')).pack(anchor=tk.W, pady=(0, 8))
        
        api_key_var = tk.StringVar(value=self.config.get("ebird_api_key", ""))
        api_entry = tk.Entry(content, textvariable=api_key_var, font=('Microsoft YaHei', 10), width=35)
        api_entry.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(content, text="申请地址: https://ebird.org/api/keygen", 
                font=('Segoe UI', 8), fg='#7f8c8d').pack(anchor=tk.W, pady=(0, 15))
        
        tk.Frame(content, height=1, bg='#ecf0f1').pack(fill=tk.X, pady=10)
        
        tk.Label(content, text="📍 搜索参数", font=('Microsoft YaHei', 11, 'bold')).pack(anchor=tk.W, pady=10)
        
        param_frame = tk.Frame(content)
        param_frame.pack(fill=tk.X)
        
        tk.Label(param_frame, text="搜索半径 (km):").pack(side=tk.LEFT)
        radius_var = tk.StringVar(value=str(self.config.get("search_radius", 50)))
        tk.Entry(param_frame, textvariable=radius_var, width=10).pack(side=tk.LEFT, padx=(10, 20))
        
        tk.Label(param_frame, text="回溯天数:").pack(side=tk.LEFT)
        days_var = tk.StringVar(value=str(self.config.get("backlook_days", 5)))
        tk.Entry(param_frame, textvariable=days_var, width=10).pack(side=tk.LEFT, padx=(10, 0))
        
        def save():
            self.config["ebird_api_key"] = api_key_var.get()
            self.config["search_radius"] = int(radius_var.get() or 50)
            self.config["backlook_days"] = int(days_var.get() or 5)
            save_config(self.config)
            self.update_api_status()
            messagebox.showinfo("✅ 保存成功", "配置已保存！", parent=win)
            win.destroy()
        
        btn_frame = tk.Frame(content)
        btn_frame.pack(pady=20)
        
        tk.Button(btn_frame, text="💾 保存配置", bg=self.colors['success'], fg='white',
                  font=('Microsoft YaHei', 10), relief=tk.FLAT, padx=15, pady=5,
                  command=save).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="取消", bg='#95a5a6', fg='white',
                  font=('Microsoft YaHei', 10), relief=tk.FLAT, padx=15, pady=5,
                  command=win.destroy).pack(side=tk.LEFT, padx=5)
        
    def run_prediction(self):
        site_name = self.site_var.get()
        
        for i, h in enumerate(HOTSPOTS):
            if h['name'] == site_name:
                site_idx = i
                break
        
        try:
            date_str = self.date_combo.get()
            if "今天" in date_str:
                date_idx = 0
            elif "明天" in date_str:
                date_idx = 1
            elif "后天" in date_str:
                date_idx = 2
            else:
                date_idx = int(date_str.split('-')[-1]) - datetime.date.today().day
                if date_idx < 0:
                    date_idx = 0
        except:
            date_idx = 0
            
        sel_date = datetime.date.today() + datetime.timedelta(days=date_idx)
        site = HOTSPOTS[site_idx]
        
        self.run_btn.config(state='disabled', bg='#bdc3c7', text="⏳ 预测中...")
        self.status_bar.config(text=f"🌐 正在获取 {site['name']} {sel_date} 的气象数据...", fg=self.colors['accent'])
        
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, f"站点: {site['name']}\n日期: {sel_date}\n\n")
        self.result_text.insert(tk.END, "🌐 正在获取气象数据，请稍候...\n")
        self.root.update()
        
        threading.Thread(target=self.prediction_thread, args=(site, sel_date), daemon=True).start()
    
    def prediction_thread(self, site, sel_date):
        try:
            session = requests.Session()
            session.mount("https://", TLSAdapter())
            session.verify = False
            cache_session = requests_cache.CachedSession('.cache', backend='sqlite', expire_after=3600)
            cache_session.mount("https://", TLSAdapter())
            openmeteo = openmeteo_requests.Client(session=retry(cache_session))
            
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": site['lat'],
                "longitude": site['lon'],
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
            
            # 检查数据长度是否足够
            data_len = len(hourly_data["precip"])
            if data_len < 21:
                raise ValueError(f"气象数据不足: 仅获取到 {data_len} 小时数据，需要至少21小时")
            
            self.root.after(0, lambda: self.result_text.insert(tk.END, "📊 正在计算迁徙适宜度...\n\n"))
            
            conf_val = 1.0
            season, target_birds, _ = get_phenology_info(site, sel_date)
            peak_w = get_peak_weight(site, sel_date, season)
            current_month = sel_date.month
            peak_months = list(site['peak_matrix'][season].keys())
            
            results = []
            ebird_multiplier = 1.0
            ebird_warnings = []
            
            for h in range(4, 21):
                w_h = {}
                for k, v in hourly_data.items():
                    w_h[k] = float(v[h]) if h < len(v) else 0.0
                
                if site.get("name") == "尧山电视台":
                    score, kettle_prob, warnings, _, delta_T, _, behavior_pred, thermal_eff, ridge_eff = calculate_expert_score_v32(
                        w_h, site, season, conf_val, peak_w, target_birds, ebird_multiplier, ebird_warnings
                    )
                    guilin_mod, _ = calculate_guilin_modifier(w_h, season)
                    score = int(score * guilin_mod)
                else:
                    score, kettle_prob, warnings, _, delta_T, _, behavior_pred, thermal_eff, ridge_eff = calculate_expert_score_v32(
                        w_h, site, season, conf_val, peak_w, target_birds, ebird_multiplier, ebird_warnings
                    )
                
                results.append((score, kettle_prob, h, w_h['li'], w_h['w_dir'], delta_T, w_h['w_spd'], behavior_pred, thermal_eff, ridge_eff))
            
            report = generate_professional_report(site, results, None, ebird_multiplier, sel_date)
            
            self.root.after(0, lambda: self.display_report(report))
            
        except Exception as e:
            import traceback
            error_msg = f"❌ 错误: {str(e)}\n\n{traceback.format_exc()}"
            self.root.after(0, lambda: self.result_text.insert(tk.END, error_msg))
            self.root.after(0, lambda: self.status_bar.config(text="❌ 预测失败", fg='red'))
            self.root.after(0, lambda: self.run_btn.config(state='normal', bg=self.colors['success'], text="🚀 开始预测"))
    
    def display_report(self, report):
        self.result_text.delete(1.0, tk.END)
        self.result_text.insert(tk.END, report)
        
        lines = report.split('\n')
        score_text = ""
        for line in lines:
            if '迁徙适宜度:' in line:
                score_text = line.strip()
                break
        
        self.status_bar.config(text=f"✅ {score_text}", fg=self.colors['success'])
        self.run_btn.config(state='normal', bg=self.colors['success'], text="🚀 开始预测")


def main():
    print("开始创建 RaptorCastApp 实例...")
    try:
        app = RaptorCastApp()
        print("RaptorCastApp 实例创建成功")
        print("开始进入主循环...")
        app.root.mainloop()
        print("主循环结束")
    except Exception as e:
        print(f"错误: {str(e)}")
        print(f"堆栈跟踪: {traceback.format_exc()}")


if __name__ == "__main__":
    print("调用 main() 函数...")
    main()
    print("main() 函数执行完毕")
