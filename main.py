import sys
import ctypes
import subprocess
import os
import winreg as reg
import psutil
from PySide6.QtCore import QTimer, Qt, QPoint
from PySide6.QtWidgets import (QApplication, QLabel, QVBoxLayout, QWidget, 
                               QFrame, QHBoxLayout, QProgressBar)
from PySide6.QtGui import QFont

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
    """Configura la aplicación para que se ejecute automáticamente al iniciar Windows."""
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = reg.OpenKey(reg.HKEY_CURRENT_USER, key_path, 0, reg.KEY_SET_VALUE)
        script_path = os.path.abspath(sys.argv[0])
        
        # Intentar usar pythonw.exe para que corra en segundo plano sin consola negra
        python_path = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(python_path):
            python_path = sys.executable
            
        command = f'"{python_path}" "{script_path}"'
        reg.SetValueEx(key, "ModernTempMonitorPySide", 0, reg.REG_SZ, command)
        reg.CloseKey(key)
    except Exception as e:
        print(f"No se pudo configurar el inicio automático: {e}")

class DesktopOverlayWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        # Ventana flotante, sin bordes, siempre visible arriba
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(440, 130)
        
        self.dragging = False
        self.offset = QPoint()

        # Estilos base de la interfaz
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 23, 42, 0.88);
                color: #f8fafc;
                font-family: 'Segoe UI', Arial, sans-serif;
                border-radius: 14px;
            }
            QFrame#Card {
                background-color: rgba(30, 41, 59, 0.9);
                border: 1px solid rgba(51, 65, 85, 0.8);
                border-radius: 10px;
            }
            QLabel#TitleLabel {
                font-size: 11px;
                color: #94a3b8;
                font-weight: 600;
            }
            QProgressBar {
                background-color: #334155;
                border: none;
                border-radius: 3px;
                height: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 3px;
            }
        """)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)
        
        def create_metric_card(icon_str, name_str):
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(4)
            
            top_row = QHBoxLayout()
            lbl_icon = QLabel(icon_str)
            lbl_icon.setFont(QFont("Segoe UI", 12))
            lbl_name = QLabel(name_str)
            lbl_name.setObjectName("TitleLabel")
            top_row.addWidget(lbl_icon)
            top_row.addWidget(lbl_name)
            top_row.addStretch()
            
            lbl_val = QLabel("---")
            # Estilo inicial normal (Azul claro)
            lbl_val.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
            lbl_val.setAlignment(Qt.AlignCenter)
            
            card_layout.addLayout(top_row)
            card_layout.addWidget(lbl_val)
            
            return card, lbl_val

        cpu_card, self.cpu_label = create_metric_card("💻", "CPU")
        disk_card, self.disk_label = create_metric_card("💾", "DISCO")
        
        # Tarjeta RAM
        ram_card = QFrame()
        ram_card.setObjectName("Card")
        ram_layout = QVBoxLayout(ram_card)
        ram_layout.setContentsMargins(10, 8, 10, 8)
        ram_layout.setSpacing(4)
        
        ram_top = QHBoxLayout()
        lbl_ram_icon = QLabel("🧠")
        lbl_ram_icon.setFont(QFont("Segoe UI", 12))
        lbl_ram_name = QLabel("RAM")
        lbl_ram_name.setObjectName("TitleLabel")
        ram_top.addWidget(lbl_ram_icon)
        ram_top.addWidget(lbl_ram_name)
        ram_top.addStretch()
        
        self.ram_label = QLabel("---")
        self.ram_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
        self.ram_label.setAlignment(Qt.AlignCenter)
        
        self.ram_progress = QProgressBar()
        self.ram_progress.setRange(0, 100)
        self.ram_progress.setValue(0)
        self.ram_progress.setTextVisible(False)
        
        ram_layout.addLayout(ram_top)
        ram_layout.addWidget(self.ram_label)
        ram_layout.addWidget(self.ram_progress)

        main_layout.addWidget(cpu_card)
        main_layout.addWidget(disk_card)
        main_layout.addWidget(ram_card)
        
        self.setLayout(main_layout)
        
        # Centrar en la parte superior de la pantalla
        self.center_at_top()

        # Timer de actualización cada 3 segundos
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_hardware_stats)
        self.timer.start(3000)
        self.update_hardware_stats()

    def center_at_top(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = 10 
        self.move(x, y)

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
        event.accept()

    def update_hardware_stats(self):
        # 1. CPU Temp y Alerta de 70°C
        cpu_temp_str = "N/D"
        cpu_celsius = 0
        try:
            cmd_cpu = "powershell -Command \"Get-WmiObject MSAcpi_ThermalZoneTemperature -Namespace 'root/wmi' | Select-Object -ExpandProperty CurrentTemperature\""
            output_cpu = subprocess.check_output(cmd_cpu, shell=True).decode().strip()
            if output_cpu:
                temp_kelvin = float(output_cpu.split()[0])
                cpu_celsius = (temp_kelvin / 10.0) - 273.15
                if 0 < cpu_celsius < 120:
                    cpu_temp_str = f"{cpu_celsius:.1f}°C"
        except Exception:
            pass
        
        self.cpu_label.setText(cpu_temp_str)
        # Condición de Alerta CPU >= 70°C
        if cpu_celsius >= 70:
            self.cpu_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #ef4444;") # Rojo Alerta
        else:
            self.cpu_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;") # Azul Normal

        # 2. Disco Duro Temp y Alerta de 70°C
        disk_temp_str = "N/D"
        disk_celsius = 0
        try:
            cmd_disk = "powershell -Command \"(Get-PhysicalDisk | Get-StorageReliabilityCounter -ErrorAction SilentlyContinue).Temperature\""
            output_disk = subprocess.check_output(cmd_disk, shell=True).decode().strip()
            if output_disk:
                disk_celsius = float(output_disk.split()[0])
                if disk_celsius > 200:
                    disk_celsius = disk_celsius - 273.15
                if 0 < disk_celsius < 100:
                    disk_temp_str = f"{disk_celsius:.1f}°C"
        except Exception:
            pass
            
        self.disk_label.setText(disk_temp_str)
        # Condición de Alerta Disco >= 70°C
        if disk_celsius >= 70:
            self.disk_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #ef4444;")
        else:
            self.disk_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")

        # 3. RAM Uso
        try:
            ram_usage = psutil.virtual_memory().percent
            self.ram_label.setText(f"{ram_usage}%")
            self.ram_progress.setValue(int(ram_usage))
            
            # Opcional: Alerta si la RAM pasa del 90% de uso
            if ram_usage >= 90:
                self.ram_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #ef4444;")
            else:
                self.ram_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #38bdf8;")
        except Exception:
            self.ram_label.setText("N/D")

if __name__ == "__main__":
    if run_as_admin():
        # Configurar inicio automático con Windows al arrancar
        setup_auto_start()
        
        app = QApplication(sys.argv)
        window = DesktopOverlayWidget()
        window.show()
        sys.exit(app.exec())
    else:
        sys.exit()