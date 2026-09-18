import sys
import ctypes
import subprocess
import os
import json
import winreg as reg
import psutil
from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtWidgets import (QApplication, QLabel, QVBoxLayout, QWidget, 
                               QFrame, QHBoxLayout, QProgressBar, QPushButton, 
                               QDialog, QCheckBox, QSlider, QColorDialog)
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush

def run_as_admin():
    try:
        if ctypes.windll.shell32.IsUserAnAdmin():
            return True
    except:
        pass
    
    script = sys.argv[0]
    params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
    return False

def setup_auto_start():
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, key_path, 0, reg.KEY_SET_VALUE)
        script_path = os.path.abspath(sys.argv[0])
        
        python_path = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(python_path):
            python_path = sys.executable
            
        command = f'"{python_path}" "{script_path}"'
        reg.SetValueEx(key, "ModernTempMonitorPySide", 0, reg.REG_SZ, command)
        reg.CloseKey(key)
    except Exception as e:
        print(f"No se pudo configurar el inicio automático: {e}")

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración del Monitor")
        self.setFixedSize(340, 620)
        self.setWindowFlags(Qt.Dialog | Qt.WindowStaysOnTopHint | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QLabel {
                color: #f8fafc;
                font-size: 13px;
                font-weight: 500;
            }
            QCheckBox {
                color: #f8fafc;
                font-size: 13px;
                spacing: 8px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #334155;
                height: 6px;
                background: #1e293b;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #38bdf8;
                border: none;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)
        
        lbl_title = QLabel("<b>Panel de Control</b>")
        lbl_title.setStyleSheet("font-size: 15px; color: #38bdf8; margin-bottom: 2px;")
        layout.addWidget(lbl_title)
        
        self.chk_ram = QCheckBox("Mostrar RAM")
        self.chk_disk = QCheckBox("Mostrar DISCO")
        self.chk_cpu = QCheckBox("Mostrar CPU (Cierra todo si se apaga)")
        
        layout.addWidget(self.chk_ram)
        layout.addWidget(self.chk_disk)
        layout.addWidget(self.chk_cpu)

        self.chk_neon = QCheckBox("Activar Brillo Neón Luminoso 💡")
        layout.addWidget(self.chk_neon)
        
        layout.addWidget(QLabel("Ancho de las Tarjetas (Desde 80px):"))
        self.slider_card_width = QSlider(Qt.Horizontal)
        self.slider_card_width.setRange(80, 260)  # Rango extendido hacia abajo para hacerlas muy chicas
        layout.addWidget(self.slider_card_width)

        layout.addWidget(QLabel("Alto de las Tarjetas (Desde 70px):"))
        self.slider_card_height = QSlider(Qt.Horizontal)
        self.slider_card_height.setRange(70, 240)  # Rango extendido hacia abajo
        layout.addWidget(self.slider_card_height)

        layout.addWidget(QLabel("Tamaño de Texto / Números:"))
        self.slider_font_size = QSlider(Qt.Horizontal)
        self.slider_font_size.setRange(14, 60)  # Permite textos más pequeños para tarjetas chicas
        layout.addWidget(self.slider_font_size)

        layout.addWidget(QLabel("Difuminado de Neón:"))
        self.slider_neon_blur = QSlider(Qt.Horizontal)
        self.slider_neon_blur.setRange(1, 8)
        layout.addWidget(self.slider_neon_blur)
        
        layout.addWidget(QLabel("Transparencia Fondo (%):"))
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(0, 100) 
        layout.addWidget(self.slider_opacity)

        layout.addWidget(QLabel("Color de Fondo:"))
        self.btn_color_palette = QPushButton("Abrir Paleta de Colores 🎨")
        self.btn_color_palette.setCursor(Qt.PointingHandCursor)
        self.btn_color_palette.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #38bdf8;
                border: none;
                font-size: 13px;
                font-weight: bold;
                padding: 7px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        layout.addWidget(self.btn_color_palette)
        
        self.parent_widget = parent

class DesktopOverlayWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.config_dir = os.path.join(app_dir, "ModernTempMonitor")
        try:
            os.makedirs(self.config_dir, exist_ok=True)
        except Exception:
            pass
        self.config_file = os.path.join(self.config_dir, "config.json")
        
        self.current_opacity = 0.90
        self.current_color = QColor(15, 23, 42)
        self.card_width = 185
        self.card_height = 135
        self.font_size = 42
        self.neon_enabled = True
        self.neon_blur = 3
        self.saved_x = None
        self.saved_y = None
        self.cards_visibility = {"ram": True, "disk": True, "cpu": True}
        
        self.last_ram = 0
        self.last_disk = 0
        self.last_cpu = 0

        self.load_config()

        self.dragging = False
        self.offset = QPoint()

        self.update_dynamic_stylesheet()
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        # --- TARJETA RAM ---
        self.ram_card = QFrame()
        self.ram_card.setObjectName("Card")
        ram_layout = QVBoxLayout(self.ram_card)
        ram_layout.setContentsMargins(8, 6, 8, 6)
        ram_layout.setSpacing(4)
        
        ram_top = QHBoxLayout()
        lbl_ram_icon = QLabel("🧠")
        lbl_ram_icon.setFont(QFont("Segoe UI", 10))
        lbl_ram_name = QLabel("RAM")
        lbl_ram_name.setObjectName("TitleLabel")
        
        self.ram_close_btn = QPushButton("✕")
        self.ram_close_btn.setObjectName("CloseButton")
        self.ram_close_btn.setFixedSize(16, 16)
        self.ram_close_btn.setCursor(Qt.PointingHandCursor)
        self.ram_close_btn.clicked.connect(lambda: self.toggle_card("ram", False))
        
        ram_top.addWidget(lbl_ram_icon)
        ram_top.addWidget(lbl_ram_name)
        ram_top.addStretch()
        ram_top.addWidget(self.ram_close_btn)
        
        self.ram_label = QLabel("---")
        self.ram_label.setAlignment(Qt.AlignCenter)
        
        self.ram_progress = QProgressBar()
        self.ram_progress.setRange(0, 100)
        self.ram_progress.setValue(0)
        self.ram_progress.setTextVisible(False)
        self.ram_progress.setFixedHeight(4)
        
        ram_layout.addLayout(ram_top)
        ram_layout.addWidget(self.ram_label)
        ram_layout.addWidget(self.ram_progress)

        # --- TARJETA DISCO ---
        self.disk_card = QFrame()
        self.disk_card.setObjectName("Card")
        disk_layout = QVBoxLayout(self.disk_card)
        disk_layout.setContentsMargins(8, 6, 8, 6)
        disk_layout.setSpacing(4)
        
        disk_top = QHBoxLayout()
        lbl_disk_icon = QLabel("💾")
        lbl_disk_icon.setFont(QFont("Segoe UI", 10))
        lbl_disk_name = QLabel("DISCO")
        lbl_disk_name.setObjectName("TitleLabel")
        
        self.disk_close_btn = QPushButton("✕")
        self.disk_close_btn.setObjectName("CloseButton")
        self.disk_close_btn.setFixedSize(16, 16)
        self.disk_close_btn.setCursor(Qt.PointingHandCursor)
        self.disk_close_btn.clicked.connect(lambda: self.toggle_card("disk", False))
        
        disk_top.addWidget(lbl_disk_icon)
        disk_top.addWidget(lbl_disk_name)
        disk_top.addStretch()
        disk_top.addWidget(self.disk_close_btn)
        
        self.disk_label = QLabel("---")
        self.disk_label.setAlignment(Qt.AlignCenter)

        disk_layout.addLayout(disk_top)
        disk_layout.addWidget(self.disk_label)

        # --- TARJETA CPU ---
        self.cpu_card = QFrame()
        self.cpu_card.setObjectName("Card")
        cpu_layout = QVBoxLayout(self.cpu_card)
        cpu_layout.setContentsMargins(8, 6, 8, 6)
        cpu_layout.setSpacing(4)
        
        cpu_top = QHBoxLayout()
        lbl_cpu_icon = QLabel("💻")
        lbl_cpu_icon.setFont(QFont("Segoe UI", 10))
        lbl_cpu_name = QLabel("CPU")
        lbl_cpu_name.setObjectName("TitleLabel")
        
        self.config_btn = QPushButton("⚙")
        self.config_btn.setObjectName("ConfigButton")
        self.config_btn.setFixedSize(16, 16)
        self.config_btn.setCursor(Qt.PointingHandCursor)
        self.config_btn.clicked.connect(self.open_settings)
        
        self.cpu_close_btn = QPushButton("✕")
        self.cpu_close_btn.setObjectName("CloseButton")
        self.cpu_close_btn.setFixedSize(16, 16)
        self.cpu_close_btn.setCursor(Qt.PointingHandCursor)
        self.cpu_close_btn.clicked.connect(lambda: self.toggle_card("cpu", False))
        
        cpu_top.addWidget(lbl_cpu_icon)
        cpu_top.addWidget(lbl_cpu_name)
        cpu_top.addStretch()
        cpu_top.addWidget(self.config_btn)
        cpu_top.addWidget(self.cpu_close_btn)
        
        self.cpu_label = QLabel("---")
        self.cpu_label.setAlignment(Qt.AlignCenter)

        cpu_layout.addLayout(cpu_top)
        cpu_layout.addWidget(self.cpu_label)

        main_layout.addWidget(self.ram_card)
        main_layout.addWidget(self.disk_card)
        main_layout.addWidget(self.cpu_card)
        
        self.setLayout(main_layout)
        
        self.ram_card.setVisible(self.cards_visibility.get("ram", True))
        self.disk_card.setVisible(self.cards_visibility.get("disk", True))
        self.cpu_card.setVisible(True)

        self.update_widget_size_by_visible_cards()
        self.restore_window_position()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.safe_update_hardware_stats)
        self.timer.start(3000)
        self.safe_update_hardware_stats()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.current_opacity = data.get("opacity", 0.90)
                    c = data.get("color", [15, 23, 42])
                    self.current_color = QColor(c[0], c[1], c[2])
                    self.card_width = data.get("card_width", 185)
                    self.card_height = data.get("card_height", 135)
                    self.font_size = data.get("font_size", 42)
                    self.neon_enabled = data.get("neon_enabled", True)
                    self.neon_blur = data.get("neon_blur", 3)
                    self.saved_x = data.get("x", None)
                    self.saved_y = data.get("y", None)
                    self.cards_visibility = data.get("cards", {"ram": True, "disk": True, "cpu": True})
            except Exception as e:
                print(f"Error al leer configuración JSON: {e}")

    def save_config(self):
        try:
            data = {
                "opacity": self.current_opacity,
                "color": [self.current_color.red(), self.current_color.green(), self.current_color.blue()],
                "card_width": self.card_width,
                "card_height": self.card_height,
                "font_size": self.font_size,
                "neon_enabled": self.neon_enabled,
                "neon_blur": self.neon_blur,
                "x": self.x(),
                "y": self.y(),
                "cards": {
                    "ram": self.ram_card.isVisible(),
                    "disk": self.disk_card.isVisible(),
                    "cpu": True
                }
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error al guardar configuración JSON: {e}")

    def update_widget_size_by_visible_cards(self):
        visible_cards = [card for card in [self.ram_card, self.disk_card, self.cpu_card] if card.isVisible()]
        count = len(visible_cards)
        if count == 0:
            return
            
        spacing = 8
        new_content_width = (count * self.card_width) + ((count - 1) * spacing)
        
        for card in visible_cards:
            card.setFixedWidth(self.card_width)
            card.setFixedHeight(self.card_height)
            
        self.setFixedSize(new_content_width + 32, self.card_height + 40)
        self.update()

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            box_rect = self.rect().adjusted(8, 8, -8, -8)
            
            if self.neon_enabled and self.neon_blur > 0:
                glow_color = QColor(56, 189, 248)
                for i in range(self.neon_blur, 0, -1):
                    alpha = max(5, int(35 / self.neon_blur * (self.neon_blur - i + 1)))
                    glow_color.setAlpha(alpha)
                    painter.setPen(QPen(glow_color, i * 2))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRoundedRect(box_rect.adjusted(-i, -i, i, i), 16, 16)
            
            bg_c = QColor(self.current_color)
            bg_c.setAlphaF(self.current_opacity)
            painter.setBrush(QBrush(bg_c))
            
            if self.neon_enabled:
                painter.setPen(QPen(QColor(125, 211, 252), 2))
            else:
                painter.setPen(QPen(QColor(51, 65, 85), 1))
                
            painter.drawRoundedRect(box_rect, 14, 14)
        except Exception:
            pass

    def update_dynamic_stylesheet(self):
        r, g, b = self.current_color.red(), self.current_color.green(), self.current_color.blue()
        card_r = min(255, r + 20)
        card_g = min(255, g + 20)
        card_b = min(255, b + 20)

        card_rgba = f"rgba({card_r}, {card_g}, {card_b}, {min(self.current_opacity + 0.15, 1.0)})"

        self.setStyleSheet(f"""
            QFrame#Card {{
                background-color: {card_rgba};
                border: 1px solid rgba(51, 65, 85, 1.0);
                border-radius: 10px;
            }}
            QLabel {{
                color: #f8fafc;
            }}
            QLabel#TitleLabel {{
                font-size: 10px;
                color: #94a3b8;
                font-weight: 600;
            }}
            QPushButton#CloseButton {{
                background-color: #ef4444;
                color: #ffffff;
                border: none;
                font-size: 9px;
                font-weight: bold;
                border-radius: 3px;
            }}
            QPushButton#CloseButton:hover {{
                background-color: #dc2626;
            }}
            QPushButton#ConfigButton {{
                background-color: #334155;
                color: #38bdf8;
                border: none;
                font-size: 9px;
                border-radius: 3px;
            }}
            QPushButton#ConfigButton:hover {{
                background-color: #475569;
            }}
            QProgressBar {{
                background-color: #334155;
                border: none;
                border-radius: 2px;
                height: 4px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: #38bdf8;
                border-radius: 2px;
            }}
        """)
        self.update_stat_labels_style()
        self.update()

    def update_stat_labels_style(self):
        try:
            ram_color = "#ef4444" if self.last_ram >= 90 else "#38bdf8"
            disk_color = "#ef4444" if self.last_disk >= 70 else "#38bdf8"
            cpu_color = "#ef4444" if self.last_cpu >= 70 else "#38bdf8"

            style = f"font-size: {self.font_size}px; font-weight: bold; color: "
            self.ram_label.setStyleSheet(style + ram_color + ";")
            self.disk_label.setStyleSheet(style + disk_color + ";")
            self.cpu_label.setStyleSheet(style + cpu_color + ";")
        except Exception:
            pass

    def open_settings(self):
        self.timer.stop()
        
        dialog = SettingsDialog(self)
        dialog.chk_ram.setChecked(self.ram_card.isVisible())
        dialog.chk_disk.setChecked(self.disk_card.isVisible())
        dialog.chk_cpu.setChecked(True)
        dialog.chk_cpu.setEnabled(False)
        dialog.chk_neon.setChecked(self.neon_enabled)
        dialog.slider_card_width.setValue(self.card_width)
        dialog.slider_card_height.setValue(self.card_height)
        dialog.slider_font_size.setValue(self.font_size)
        dialog.slider_neon_blur.setValue(self.neon_blur)
        dialog.slider_opacity.setValue(int(self.current_opacity * 100))
        
        dialog.chk_ram.toggled.connect(lambda state: self.toggle_card("ram", state))
        dialog.chk_disk.toggled.connect(lambda state: self.toggle_card("disk", state))
        dialog.chk_cpu.toggled.connect(lambda state: self.toggle_card("cpu", state))
        dialog.chk_neon.toggled.connect(self.toggle_neon)
        
        dialog.slider_card_width.valueChanged.connect(self.change_card_width)
        dialog.slider_card_height.valueChanged.connect(self.change_card_height)
        dialog.slider_font_size.valueChanged.connect(self.change_font_size)
        dialog.slider_neon_blur.valueChanged.connect(self.change_neon_blur)
        dialog.slider_opacity.sliderReleased.connect(lambda: self.change_widget_opacity(dialog.slider_opacity.value()))
        
        dialog.btn_color_palette.clicked.connect(self.open_color_picker)
        
        dialog.exec()
        self.save_config()
        self.timer.start(3000)

    def toggle_neon(self, state):
        self.neon_enabled = state
        self.update()
        self.save_config()

    def change_card_width(self, width_val):
        self.card_width = width_val
        self.update_widget_size_by_visible_cards()
        self.save_config()

    def change_card_height(self, height_val):
        self.card_height = height_val
        self.update_widget_size_by_visible_cards()
        self.save_config()

    def change_font_size(self, size_val):
        self.font_size = size_val
        self.update_stat_labels_style()
        self.save_config()

    def change_neon_blur(self, blur_val):
        self.neon_blur = blur_val
        self.update()
        self.save_config()

    def change_widget_opacity(self, opacity_val):
        self.current_opacity = opacity_val / 100.0
        self.update_dynamic_stylesheet()
        self.save_config()

    def open_color_picker(self):
        color = QColorDialog.getColor(self.current_color, self, "Seleccionar Color de Fondo del Widget")
        if color.isValid():
            self.current_color = color
            self.update_dynamic_stylesheet()
            self.save_config()

    def toggle_card(self, card_name, show):
        if card_name == "cpu" and not show:
            self.close()
            return

        if card_name == "ram":
            self.ram_card.setVisible(show)
        elif card_name == "disk":
            self.disk_card.setVisible(show)
        
        self.update_widget_size_by_visible_cards()
        self.save_config()

    def center_at_top(self):
        try:
            screen = QApplication.primaryScreen().geometry()
            x = ((screen.width() - self.width()) // 2) + 40
            y = 0  
            self.move(x, y)
        except Exception:
            self.move(100, 0)

    def restore_window_position(self):
        if self.saved_x is not None and self.saved_y is not None:
            self.move(self.saved_x, self.saved_y)
        else:
            self.center_at_top()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.save_config()
        event.accept()

    def closeEvent(self, event):
        self.save_config()
        event.accept()

    def safe_update_hardware_stats(self):
        try:
            self.update_hardware_stats()
        except Exception as e:
            print(f"Excepción controlada en actualización de hardware: {e}")

    def update_hardware_stats(self):
        if self.ram_card.isVisible():
            try:
                ram_usage = psutil.virtual_memory().percent
                self.last_ram = ram_usage
                self.ram_label.setText(f"{ram_usage}%")
                self.ram_progress.setValue(int(ram_usage))
            except Exception:
                self.ram_label.setText("N/D")

        if self.disk_card.isVisible():
            disk_temp_str = "N/D"
            disk_celsius = 0
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                cmd_disk = "powershell -Command \"(Get-PhysicalDisk | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue).Temperature\""
                output_disk = subprocess.check_output(cmd_disk, shell=True, timeout=1.5, startupinfo=startupinfo).decode().strip()
                if output_disk:
                    disk_celsius = float(output_disk.split()[0])
                    if disk_celsius > 200:
                        disk_celsius = disk_celsius - 273.15
                    if 0 < disk_celsius < 100:
                        disk_temp_str = f"{disk_celsius:.1f}°C"
            except Exception:
                pass
            
            if disk_temp_str == "N/D":
                try:
                    disk_usage = psutil.disk_usage('C:').percent
                    disk_temp_str = f"{disk_usage}%"
                    disk_celsius = disk_usage
                except Exception:
                    pass
                
            self.last_disk = disk_celsius
            self.disk_label.setText(disk_temp_str)

        if self.cpu_card.isVisible():
            cpu_temp_str = "N/D"
            cpu_celsius = 0
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                cmd_cpu = "powershell -Command \"Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace 'root/wmi' | Select-Object -ExpandProperty CurrentTemperature\""
                output_cpu = subprocess.check_output(cmd_cpu, shell=True, timeout=1.5, startupinfo=startupinfo).decode().strip()
                if output_cpu:
                    temp_kelvin = float(output_cpu.split()[0])
                    cpu_celsius = (temp_kelvin / 10.0) - 273.15
                    if 0 < cpu_celsius < 120:
                        cpu_temp_str = f"{cpu_celsius:.1f}°C"
            except Exception:
                pass
            
            self.last_cpu = cpu_celsius
            self.cpu_label.setText(cpu_temp_str)

        self.update_stat_labels_style()

if __name__ == "__main__":
    if run_as_admin():
        setup_auto_start()
        
        app = QApplication(sys.argv)
        window = DesktopOverlayWidget()
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit()
