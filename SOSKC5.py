import sys
import requests
import yaml
import re
import pandas as pd
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QPushButton, QLineEdit,
                             QLabel, QComboBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt


# ====================== 核心逻辑类 ======================
class ProxyProcessor:
    @staticmethod
    def get_region_weight(name, order_list):
        lower_name = name.lower()
        for index, keyword_group in enumerate(order_list):
            sub_keywords = re.findall(r'[a-zA-Z]+|[\u4e00-\u9fa5]+', keyword_group)
            for kw in sub_keywords:
                if kw.lower() in lower_name:
                    return index
        return 999

    @classmethod
    def process(cls, urls, s_port, sort_order_raw, sort_mode):
        sort_order = [x.strip() for x in sort_order_raw.replace('，', ',').split(',') if x.strip()]
        all_proxies = []
        seen_names = set()
        headers = {'User-Agent': 'Clash-verge/1.4.4 (Mihomo)'}

        for group_idx, url in enumerate(urls):
            url = url.strip()
            if not url: continue
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                data = yaml.safe_load(resp.text)
                if data and isinstance(data, dict) and 'proxies' in data:
                    for p_idx, p in enumerate(data['proxies']):
                        if re.search(r'流量|到期|官网|地址|重置|群组|订阅', p['name']): continue
                        p['origin'] = f"机场_{group_idx + 1}"
                        p['group_idx'] = group_idx
                        p['original_index'] = p_idx

                        clean_name = p['name'].strip()
                        if clean_name in seen_names:
                            clean_name = f"{clean_name}_{len(seen_names)}"
                        p['name'] = clean_name
                        seen_names.add(clean_name)
                        all_proxies.append(p)
            except:
                continue

        if not all_proxies: return None, None

        # 排序
        if sort_mode == "🌍 地区优先级":
            all_proxies.sort(
                key=lambda x: (cls.get_region_weight(x['name'], sort_order), x['group_idx'], x['original_index']))
        else:
            all_proxies.sort(key=lambda x: (x['group_idx'], x['original_index']))

        # 生成配置
        config_out = {
            "allow-lan": True, "mode": "rule",
            "dns": {"enable": True, "enhanced-mode": "fake-ip", "nameserver": ["114.114.114.114"]},
            "proxies": all_proxies,
            "listeners": [
                {"name": f"mixed_{i}", "type": "mixed", "port": s_port + i, "proxy": p['name']}
                for i, p in enumerate(all_proxies)
            ]
        }

        # 生成表格数据
        table_data = []
        for i, p in enumerate(all_proxies):
            table_data.append([i + 1, p['origin'], p['name'], s_port + i])

        return yaml.dump(config_out, allow_unicode=True, sort_keys=False), table_data


# ====================== UI 界面类 ======================
class AdsPowerHelper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("节点助手 - 桌面版")
        self.resize(1100, 700)
        self.yaml_data = ""
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # --- 左侧面板 ---
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel(" 输入订阅链接 (一行一个):"))
        self.url_input = QTextEdit()
        left_panel.addWidget(self.url_input)

        config_layout = QVBoxLayout()
        config_layout.addWidget(QLabel("起始端口:"))
        self.port_input = QLineEdit("42010")
        config_layout.addWidget(self.port_input)

        config_layout.addWidget(QLabel("排序模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["🌍 地区优先级", "📋 订阅原始顺序"])
        config_layout.addWidget(self.mode_combo)

        config_layout.addWidget(QLabel("排序关键词:"))
        self.order_input = QLineEdit("JP日本, SG新加坡, HK香港, KR韩国, US美国, TW台湾")
        config_layout.addWidget(self.order_input)

        self.gen_btn = QPushButton("🔄 开始生成")
        self.gen_btn.setFixedHeight(40)
        self.gen_btn.setStyleSheet("background-color: #0078D4; color: white; font-weight: bold;")
        self.gen_btn.clicked.connect(self.handle_generate)
        left_panel.addLayout(config_layout)
        left_panel.addWidget(self.gen_btn)

        # --- 右侧面板 ---
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("2. 端口分配预览:"))
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["序号", "来源", "节点名称", " 端口"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right_panel.addWidget(self.table)

        self.save_btn = QPushButton("💾 保存 YAML 文件")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.handle_save)
        right_panel.addWidget(self.save_btn)

        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 2)

    def handle_generate(self):
        urls = self.url_input.toPlainText().split('\n')
        try:
            port = int(self.port_input.text())
        except:
            QMessageBox.warning(self, "错误", "起始端口必须是数字")
            return

        yaml_str, table_data = ProxyProcessor.process(
            urls, port, self.order_input.text(), self.mode_combo.currentText()
        )

        if yaml_str:
            self.yaml_data = yaml_str
            self.table.setRowCount(len(table_data))
            for r_idx, row in enumerate(table_data):
                for c_idx, col in enumerate(row):
                    self.table.setItem(r_idx, c_idx, QTableWidgetItem(str(col)))
            self.save_btn.setEnabled(True)
            QMessageBox.information(self, "成功", "节点已完成排序并生成预览！")
        else:
            QMessageBox.warning(self, "提示", "未获取到有效节点，请检查链接。")

    def handle_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "保存文件", "SOCKS5.yaml", "YAML Files (*.yaml)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.yaml_data)
            QMessageBox.information(self, "保存成功", f"文件已保存至:\n{path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AdsPowerHelper()
    window.show()
    sys.exit(app.exec())