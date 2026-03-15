import os
import sys
import json
import datetime
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import webbrowser

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

class TestFalconForecastApp:
    def __init__(self, root):
        self.root = root
        self.root.title("猛禽迁徙预测系统 - 测试版")
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
        site_combobox['values'] = ["都统岩", "龙泉山", "尧山电视台", "冠头岭", "九龙山", "渔洋山", "南汇东滩", "崇明东滩"]
        if site_combobox['values']:
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
            
            # 获取选中的日期
            date_str = self.date_var.get().split(' ')[0]
            sel_date = datetime.date.fromisoformat(date_str)
            
            # 生成模拟报告
            report = f"=" * 120 + "\n"
            report += f"🦅 猛禽迁徙学术研判报告 v35.0 | {site_name} | {sel_date}\n"
            report += f"=" * 120 + "\n\n"
            report += "【核心综述】\n"
            report += "* 迁徙适宜度总分: 85/100 (⭐⭐⭐⭐)\n"
            report += "* 黄金观测窗口: 10:00-12:00 (连续3小时平均分:82.7)\n"
            report += "* 窗口特征: 优秀观测窗口 | 中等热力 | 理想风速 | 中等集群概率 | 春季迁徙高峰\n"
            report += "* 预测强度: 集中(Heavy)\n\n"
            report += "【实证数据】\n"
            report += "- 最新记录: 03-12 14:30 在 桂林尧山\n"
            report += "  观测到 5只 凤头蜂鹰\n"
            report += "- 空间修正系数: 1.05x (+5%)\n\n"
            report += "【动态评分表 (04:00-20:00)】\n"
            report += "-" * 120 + "\n"
            report += f"{'时刻':^8} | {'评分':^8} | {'推荐':^10} | {'鹰柱%':^8} | {'风速':^6} | {'风向':^6} | {'LI':^6} | {'ΔT':^6} | {'行为预测':^30}\n"
            report += "-" * 120 + "\n"
            
            # 模拟小时数据
            for h in range(4, 21):
                score = 40 + (h - 4) * 3 if h < 12 else 76 - (h - 12) * 3
                kettle_prob = 20 + (h - 4) * 3 if h < 12 else 44 - (h - 12) * 2
                wind_speed = 12 - (h - 4) * 0.5 if h < 12 else 8 + (h - 12) * 0.3
                wind_dir = 180 - (h - 4) * 5 if h < 12 else 140 + (h - 12) * 3
                li = -0.5 - (h - 4) * 0.1 if h < 12 else -1.3 + (h - 12) * 0.05
                delta_T = -0.2 + (h - 4) * 0.05 if h < 12 else 0.4 - (h - 12) * 0.04
                
                stars = "⭐⭐" if score < 60 else "⭐⭐⭐" if score < 75 else "⭐⭐⭐⭐"
                kettle_desc = "难以成柱" if kettle_prob < 40 else "可能成柱" if kettle_prob < 70 else "极易成柱"
                is_golden = "🌅" if 10 <= h <= 12 else ""
                
                report += f"{h:02d}:00{is_golden} | {score:^8} | {stars:^10} | {kettle_prob:^3}% ({kettle_desc[:5]}) | "
                report += f"{wind_speed:^6.1f}k | {wind_dir:^6.0f}° | {li:^6.1f} | {delta_T:^6.1f} | 凤头蜂鹰: 形成热力柱，高空滑翔\n"
            
            report += "\n【天气专项分析】\n"
            report += "1. 逆温层风险: ΔT=0.4℃ → 轻微影响热力发展\n"
            report += "2. 地形升力效率: 95% (风向与山脊夹角5°)\n"
            report += "3. 热力转化率: 30% (LI=-2.2, CAPE=70%J/kg)\n"
            report += "4. 风速适宜度: 7.0kts → 理想地形升力\n\n"
            report += "【黄金观测窗口分析】\n"
            report += "* 窗口时段: 10:00-12:00 (气象算法自动计算)\n"
            report += "* 窗口平均分: 82.7/100\n"
            report += "* 窗口特征: 优秀观测窗口 | 中等热力 | 理想风速 | 中等集群概率 | 春季迁徙高峰\n"
            report += "* 选取依据: 连续3小时平均迁徙适宜度最高\n\n"
            report += "【专业观测策略】\n"
            report += "1. 黄金窗口配置:\n"
            report += "   - 10:00-12:00: 使用20倍镜\n"
            report += "   - 搜索高度: 500-800m 山脊线\n"
            report += "2. 重点识别特征:\n"
            report += "   - 注意凤头蜂鹰的振翅频率\n"
            report += "3. 数据记录建议:\n"
            report += "   - 每小时记录集群大小和飞行方向\n"
            report += "   - 标记热力柱出现时间和持续时间\n\n"
            report += f"【{site_name}特别提示】\n"
            report += "=" * 60 + "\n"
            report += f"* 地形特征: 测试站点，模拟数据\n\n"
            report += "最佳观测点:\n"
            report += "  1. 测试观测点1: 测试描述\n"
            report += "  2. 测试观测点2: 测试描述\n\n"
            report += "时间策略:\n"
            report += "  • 春季: 3月下旬至4月中旬，雨后转晴的第一个大晴天\n"
            report += "  • 秋季: 10月中下旬，10:00-16:00\n\n"
            report += "设备建议:\n"
            report += "  • 必备: 8×42双筒，20-60×单筒\n"
            report += "  • 三脚架: 山顶风大，需重型脚架\n"
            report += "  • 记录: GPS记录迁徙路径\n\n"
            report += "=" * 120
            
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
    app = TestFalconForecastApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
