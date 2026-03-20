"""
猛禽迁徙预测系统 - PyQt6 现代桌面 GUI
"""
import os
import sys
import json
import datetime
import threading
import traceback

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTextEdit, QTabWidget,
    QLineEdit, QSpinBox, QGroupBox, QFormLayout, QMessageBox,
    QProgressBar, QFrame, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from raptorcast_v4_guilin import (
    HOTSPOTS, EBIRD_CACHE_DIR, EBIRD_API_KEY, EBIRD_RADIUS, EBIRD_BACK_DAYS,
    get_phenology_info, get_peak_weight, process_ebird_data,
    EBirdClient, calculate_expert_score_v32, calculate_guilin_modifier,
    generate_professional_report, TLSAdapter
)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

# ── 样式表 ──────────────────────────────────────────────────────────
STYLESHEET = """
QMainWindow {
    background-color: #1e1e2e;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #1e1e2e;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #313244;
    color: #cdd6f4;
    padding: 10px 24px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-size: 14px;
    font-weight: bold;
}
QTabBar::tab:selected {
    background-color: #45475a;
    color: #f5c2e7;
}
QTabBar::tab:hover {
    background-color: #585b70;
}
QLabel {
    color: #cdd6f4;
    font-size: 13px;
}
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    min-height: 20px;
}
QComboBox::drop-down {
    border: none;
    width: 30px;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #585b70;
    border: 1px solid #45475a;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 8px;
    padding: 12px 32px;
    font-size: 15px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #74c7ec;
}
QPushButton:pressed {
    background-color: #89dceb;
}
QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}
QTextEdit {
    background-color: #181825;
    color: #a6e3a1;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 12px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 13px;
    selection-background-color: #45475a;
}
QLineEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}
QSpinBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
}
QGroupBox {
    color: #f5c2e7;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 20px;
    font-size: 14px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
}
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 4px;
    height: 6px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}
QTableWidget {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
    gridline-color: #313244;
    font-size: 12px;
}
QTableWidget::item {
    padding: 6px;
}
QHeaderView::section {
    background-color: #313244;
    color: #f5c2e7;
    padding: 8px;
    border: none;
    font-weight: bold;
    font-size: 12px;
}
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


# ── 后台预测线程 ────────────────────────────────────────────────────
class PredictionWorker(QThread):
    finished = pyqtSignal(str, list)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, site, sel_date, d_idx, config):
        super().__init__()
        self.site = site
        self.sel_date = sel_date
        self.d_idx = d_idx
        self.config = config

    def run(self):
        try:
            site = self.site
            sel_date = self.sel_date
            d_idx = self.d_idx

            conf_val = 1.0 if d_idx == 0 else 0.9 if d_idx == 1 else 0.8 if d_idx <= 3 else 0.5
            season, target_birds, pheno_desc = get_phenology_info(site, sel_date)
            peak_w = get_peak_weight(site, sel_date, season)
            current_month = sel_date.month
            peak_months = list(site['peak_matrix'][season].keys()) if season in site['peak_matrix'] else []

            # eBird
            self.progress.emit("正在获取 eBird 观测数据...")
            api_key = self.config.get("ebird_api_key", EBIRD_API_KEY)
            radius = self.config.get("ebird_search_radius", EBIRD_RADIUS)
            back_days = self.config.get("ebird_backlook_days", EBIRD_BACK_DAYS)
            ebird = EBirdClient(api_key, radius, back_days, EBIRD_CACHE_DIR)
            obs_data = ebird.get_recent_observations(site['lat'], site['lon'])
            ebird_multiplier, ebird_evidence, ebird_warnings = process_ebird_data(
                obs_data, target_birds, peak_months, current_month
            )

            # 气象
            self.progress.emit("正在获取气象预报数据...")
            import requests
            from retry_requests import retry
            import requests_cache
            from openmeteo_requests import Client

            session = requests.Session()
            session.mount("https://", TLSAdapter())
            session.verify = False
            cache_session = requests_cache.CachedSession(
                '.cache', backend='sqlite', expire_after=3600, session=session
            )
            openmeteo = Client(session=retry(cache_session))

            params = {
                "latitude": site['lat'], "longitude": site['lon'],
                "hourly": [
                    "precipitation", "cape", "lifted_index",
                    "wind_speed_850hPa", "wind_direction_850hPa",
                    "cloud_cover", "temperature_850hPa", "temperature_925hPa"
                ],
                "timezone": "Asia/Shanghai",
                "start_date": sel_date.isoformat(),
                "end_date": sel_date.isoformat()
            }
            responses = openmeteo.weather_api(
                "https://api.open-meteo.com/v1/forecast", params=params, verify=False
            )
            hourly = responses[0].Hourly()
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

            # 计算
            self.progress.emit("正在运行迁徙预测模型...")
            results = []
            for h in range(4, 21):
                w_h = {}
                for k, v in hourly_data.items():
                    w_h[k] = float(v[h]) if h < len(v) else 0.0

                if site["name"] == "尧山电视台":
                    (score, kettle_prob, warnings, uncertainty, delta_T,
                     drift_side, behavior_pred, thermal_eff, ridge_eff) = calculate_expert_score_v32(
                        w_h, site, season, conf_val, peak_w, target_birds,
                        ebird_multiplier, ebird_warnings
                    )
                    guilin_mod, guilin_mods = calculate_guilin_modifier(w_h, season)
                    score = int(score * guilin_mod)
                    for mod_name, _ in guilin_mods:
                        warnings.append(f"尧山增益: {mod_name}")
                else:
                    (score, kettle_prob, warnings, uncertainty, delta_T,
                     drift_side, behavior_pred, thermal_eff, ridge_eff) = calculate_expert_score_v32(
                        w_h, site, season, conf_val, peak_w, target_birds,
                        ebird_multiplier, ebird_warnings
                    )

                results.append((
                    score, kettle_prob, h, w_h['li'], w_h['w_dir'],
                    delta_T, w_h['w_spd'], behavior_pred, thermal_eff, ridge_eff
                ))

            self.progress.emit("正在生成报告...")
            report = generate_professional_report(
                site, results, ebird_evidence, ebird_multiplier, sel_date
            )
            self.finished.emit(report, results)

        except Exception as e:
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")


# ── 主窗口 ──────────────────────────────────────────────────────────
class FalconForecastGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = self._load_config()
        self.worker = None
        self._init_ui()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "ebird_api_key": "",
            "china_birding_token": "",
            "ebird_search_radius": 50,
            "ebird_backlook_days": 5
        }

    def _save_config(self):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def _init_ui(self):
        self.setWindowTitle("Falcon Forecast - 猛禽迁徙预测系统 v1.0")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)

        # 设置全局字体（优先使用 Noto Sans CJK 以支持中文）
        app_font = QFont("Noto Sans CJK SC", 13)
        app_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        QApplication.instance().setFont(app_font)

        # 顶部标题
        header = QLabel("Falcon Forecast  猛禽迁徙预测系统")
        header.setFont(QFont("Noto Sans CJK SC", 22, QFont.Weight.Bold))
        header.setStyleSheet("color: #f5c2e7; padding: 8px 0;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Tab 页
        tabs = QTabWidget()
        tabs.addTab(self._create_predict_tab(), "预测分析")
        tabs.addTab(self._create_config_tab(), "配置管理")
        tabs.addTab(self._create_about_tab(), "关于")
        layout.addWidget(tabs)

    # ── 预测分析 Tab ────────────────────────────────────────────────
    def _create_predict_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)

        # 参数选择区
        params_group = QGroupBox("参数选择")
        params_layout = QHBoxLayout(params_group)
        params_layout.setSpacing(20)

        # 站点
        site_layout = QVBoxLayout()
        site_label = QLabel("监测站点")
        site_label.setStyleSheet("font-weight: bold; color: #89b4fa;")
        self.site_combo = QComboBox()
        for s in HOTSPOTS:
            self.site_combo.addItem(f"{s['name']}  ({s['type']})")
        self.site_combo.currentIndexChanged.connect(self._on_site_changed)
        site_layout.addWidget(site_label)
        site_layout.addWidget(self.site_combo)
        params_layout.addLayout(site_layout, 2)

        # 日期
        date_layout = QVBoxLayout()
        date_label = QLabel("预测日期")
        date_label.setStyleSheet("font-weight: bold; color: #89b4fa;")
        self.date_combo = QComboBox()
        week_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for i in range(7):
            d = datetime.date.today() + datetime.timedelta(days=i)
            tag = "今天" if i == 0 else "明天" if i == 1 else week_map[d.weekday()]
            self.date_combo.addItem(f"{d}  ({tag})", d)
        date_layout.addWidget(date_label)
        date_layout.addWidget(self.date_combo)
        params_layout.addLayout(date_layout, 2)

        # 按钮
        btn_layout = QVBoxLayout()
        btn_layout.addStretch()
        self.run_btn = QPushButton("执行预测")
        self.run_btn.setMinimumHeight(44)
        self.run_btn.clicked.connect(self._run_prediction)
        btn_layout.addWidget(self.run_btn)
        params_layout.addLayout(btn_layout, 1)

        layout.addWidget(params_group)

        # 站点描述
        self.site_desc = QLabel()
        self.site_desc.setStyleSheet(
            "color: #a6adc8; background-color: #313244; "
            "border-radius: 6px; padding: 10px; font-size: 12px;"
        )
        self.site_desc.setWordWrap(True)
        self._on_site_changed(0)
        layout.addWidget(self.site_desc)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(6)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(self.status_label)

        # 结果区 — 分为表格和报告
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 小时评分表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(8)
        self.result_table.setHorizontalHeaderLabels([
            "时刻", "评分", "推荐", "鹰柱%", "风速(kts)", "风向", "LI", "ΔT(℃)"
        ])
        self.result_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setStyleSheet(
            self.result_table.styleSheet() +
            "QTableWidget { alternate-background-color: #1e1e2e; }"
        )
        self.result_table.verticalHeader().setVisible(False)
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self.result_table)

        # 报告文本
        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setPlaceholderText("点击「执行预测」查看结果...")
        splitter.addWidget(self.report_text)

        splitter.setSizes([300, 400])
        layout.addWidget(splitter, 1)

        return widget

    def _on_site_changed(self, idx):
        if 0 <= idx < len(HOTSPOTS):
            s = HOTSPOTS[idx]
            self.site_desc.setText(
                f"{s['name']}  |  {s['type']}  |  "
                f"({s['lat']:.2f}, {s['lon']:.2f})  |  {s['desc']}"
            )

    def _run_prediction(self):
        idx = self.site_combo.currentIndex()
        site = HOTSPOTS[idx]
        sel_date = self.date_combo.currentData()
        d_idx = self.date_combo.currentIndex()

        self.run_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("正在初始化...")
        self.report_text.clear()
        self.result_table.setRowCount(0)

        self.worker = PredictionWorker(site, sel_date, d_idx, self.config)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, msg):
        self.status_label.setText(msg)

    def _on_finished(self, report, results):
        self.progress_bar.setVisible(False)
        self.run_btn.setEnabled(True)
        self.status_label.setText("预测完成")
        self.report_text.setText(report)
        self._fill_table(results)

    def _on_error(self, msg):
        self.progress_bar.setVisible(False)
        self.run_btn.setEnabled(True)
        self.status_label.setText("预测失败")
        self.report_text.setText(f"错误:\n{msg}")

    def _fill_table(self, results):
        self.result_table.setRowCount(len(results))
        for row, r in enumerate(results):
            score, kettle, hour, li, w_dir, dT, w_spd = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
            stars = "★★★★★" if score >= 88 else "★★★★" if score >= 75 else "★★★" if score >= 60 else "★★" if score >= 40 else "★"

            items = [
                f"{hour:02d}:00", str(score), stars,
                f"{kettle}%", f"{w_spd:.1f}", f"{w_dir:.0f}°",
                f"{li:.1f}", f"{dT:+.1f}" if dT != 0 else "-"
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                # 评分列着色
                if col == 1:
                    if score >= 75:
                        item.setForeground(QColor("#a6e3a1"))
                    elif score >= 50:
                        item.setForeground(QColor("#f9e2af"))
                    else:
                        item.setForeground(QColor("#f38ba8"))
                self.result_table.setItem(row, col, item)

    # ── 配置 Tab ────────────────────────────────────────────────────
    def _create_config_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)

        api_group = QGroupBox("API 配置")
        form = QFormLayout(api_group)
        form.setSpacing(12)

        self.ebird_key_input = QLineEdit(self.config.get("ebird_api_key", ""))
        self.ebird_key_input.setPlaceholderText("从 ebird.org/api/keygen 获取")
        self.ebird_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("eBird API Key:", self.ebird_key_input)

        self.china_token_input = QLineEdit(self.config.get("china_birding_token", ""))
        self.china_token_input.setPlaceholderText("中国观鸟记录中心 Token")
        self.china_token_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("观鸟中心 Token:", self.china_token_input)

        layout.addWidget(api_group)

        search_group = QGroupBox("搜索参数")
        form2 = QFormLayout(search_group)
        form2.setSpacing(12)

        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(1, 200)
        self.radius_spin.setValue(self.config.get("ebird_search_radius", 50))
        self.radius_spin.setSuffix(" km")
        form2.addRow("eBird 搜索半径:", self.radius_spin)

        self.backdays_spin = QSpinBox()
        self.backdays_spin.setRange(1, 30)
        self.backdays_spin.setValue(self.config.get("ebird_backlook_days", 5))
        self.backdays_spin.setSuffix(" 天")
        form2.addRow("eBird 回溯天数:", self.backdays_spin)

        layout.addWidget(search_group)

        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self._save_config_clicked)
        layout.addWidget(save_btn)
        layout.addStretch()

        return widget

    def _save_config_clicked(self):
        self.config["ebird_api_key"] = self.ebird_key_input.text()
        self.config["china_birding_token"] = self.china_token_input.text()
        self.config["ebird_search_radius"] = self.radius_spin.value()
        self.config["ebird_backlook_days"] = self.backdays_spin.value()
        try:
            self._save_config()
            QMessageBox.information(self, "成功", "配置已保存")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    # ── 关于 Tab ────────────────────────────────────────────────────
    def _create_about_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Falcon Forecast")
        title.setFont(QFont("Noto Sans CJK SC", 28, QFont.Weight.Bold))
        title.setStyleSheet("color: #f5c2e7;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("猛禽迁徙预测系统")
        subtitle.setFont(QFont("Noto Sans CJK SC", 16))
        subtitle.setStyleSheet("color: #cdd6f4;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        info_lines = [
            "版本: v1.0.0",
            "融合地形动力学、热力学与物种特异性生物阈值",
            "支持 8 个监测站点的迁徙预测",
            "气象数据来源: Open-Meteo API",
            "观测数据来源: eBird API",
        ]
        for line in info_lines:
            lbl = QLabel(line)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #a6adc8; font-size: 13px;")
            layout.addWidget(lbl)

        layout.addStretch()
        return widget


# ── 入口 ────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = FalconForecastGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
