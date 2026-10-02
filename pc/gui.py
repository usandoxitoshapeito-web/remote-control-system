#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import sqlite3
import qrcode
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from io import BytesIO

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QListWidget,
    QListWidgetItem, QDialog, QMessageBox, QInputDialog, QTextEdit,
    QTabWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QSize
from PyQt6.QtGui import QPixmap, QIcon, QImage, QFont
from PyQt6.QtGui import QColor

def get_db():
    conn = sqlite3.connect("devices.db")
    conn.row_factory = sqlite3.Row
    return conn

class RemoteControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🖥️ Remote Control - PC Central")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet(self.get_dark_style())
        
        # Menu principal
        self.init_ui()
        self.selected_device = None
        self.refresh_devices()
        
        # Timer para atualizar
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_devices)
        self.timer.start(2000)  # a cada 2 segundos
    
    def get_dark_style(self):
        return """
            QMainWindow {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QWidget {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #084394;
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: white;
                border: 2px solid #0078d4;
                padding: 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QListWidget {
                background-color: #2d2d2d;
                color: white;
                border: 2px solid #0078d4;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
            }
            QLabel {
                color: #ffffff;
            }
            QTextEdit {
                background-color: #2d2d2d;
                color: #00ff00;
                border: 2px solid #0078d4;
                border-radius: 4px;
                font-family: Courier New;
                font-size: 10px;
            }
            QTabWidget::pane {
                border: 2px solid #0078d4;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px 20px;
                border: none;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
            }
        """
    
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        
        # PAINEL ESQUERDO - Lista de dispositivos
        left_panel = QVBoxLayout()
        
        left_title = QLabel("📱 Seus Dispositivos")
        left_title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        left_panel.addWidget(left_title)
        
        self.device_list = QListWidget()
        self.device_list.itemClicked.connect(self.on_device_selected)
        left_panel.addWidget(self.device_list)
        
        btn_add = QPushButton("➕ Adicionar Dispositivo")
        btn_add.clicked.connect(self.add_device_dialog)
        left_panel.addWidget(btn_add)
        
        btn_refresh = QPushButton("🔄 Atualizar")
        btn_refresh.clicked.connect(self.refresh_devices)
        left_panel.addWidget(btn_refresh)
        
        # PAINEL DIREITO - Abas
        right_tabs = QTabWidget()
        
        # Aba 1: Informações
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        
        info_title = QLabel("ℹ️ Detalhes do Dispositivo")
        info_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        info_layout.addWidget(info_title)
        
        self.device_info = QTextEdit()
        self.device_info.setReadOnly(True)
        self.device_info.setText("Selecione um dispositivo para ver os detalhes")
        info_layout.addWidget(self.device_info)
        
        right_tabs.addTab(info_widget, "📋 Informações")
        
        # Aba 2: QR Code
        qr_widget = QWidget()
        qr_layout = QVBoxLayout(qr_widget)
        
        qr_title = QLabel("🔐 QR Code de Emparelhamento")
        qr_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        qr_layout.addWidget(qr_title)
        
        self.qr_label = QLabel("Selecione um dispositivo")
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr_layout.addWidget(self.qr_label)
        
        btn_copy_token = QPushButton("📋 Copiar Token")
        btn_copy_token.clicked.connect(self.copy_token)
        qr_layout.addWidget(btn_copy_token)
        
        right_tabs.addTab(qr_widget, "🔐 Emparelhamento")
        
        # Aba 3: Controle
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        
        control_title = QLabel("🎮 Controle")
        control_title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        control_layout.addWidget(control_title)
        
        btn_connect = QPushButton("🔗 Conectar Dispositivo")
        btn_connect.clicked.connect(self.connect_device)
        control_layout.addWidget(btn_connect)
        
        btn_disconnect = QPushButton("🔌 Desconectar")
        btn_disconnect.clicked.connect(self.disconnect_device)
        control_layout.addWidget(btn_disconnect)
        
        btn_view_screen = QPushButton("📺 Visualizar Tela (Em breve)")
        btn_view_screen.setEnabled(False)
        control_layout.addWidget(btn_view_screen)
        
        btn_send_input = QPushButton("⌨️ Enviar Comando (Em breve)")
        btn_send_input.setEnabled(False)
        control_layout.addWidget(btn_send_input)
        
        control_layout.addStretch()
        
        btn_remove = QPushButton("🗑️ Remover Dispositivo")
        btn_remove.clicked.connect(self.remove_device)
        control_layout.addWidget(btn_remove)
        
        right_tabs.addTab(control_widget, "🎮 Controle")
        
        # Monta layout final
        left_container = QWidget()
        left_container.setLayout(left_panel)
        
        main_layout.addWidget(left_container, 1)
        main_layout.addWidget(right_tabs, 1)
        
        central.setLayout(main_layout)
    
    def refresh_devices(self):
        """Atualiza lista de dispositivos"""
        self.device_list.clear()
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT device_id, device_name, nickname, status, last_seen FROM devices ORDER BY created_at DESC"
        )
        devices = cursor.fetchall()
        conn.close()
        
        for device in devices:
            device_id, device_name, nickname, status, last_seen = device
            status_icon = "🟢" if status == "online" else "🔴"
            item_text = f"{status_icon} {nickname} ({device_name})"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, device_id)
            
            if status == "online":
                item.setForeground(QColor("#00ff00"))
            else:
                item.setForeground(QColor("#ff6b6b"))
            
            self.device_list.addItem(item)
    
    def on_device_selected(self, item):
        """Quando um dispositivo é selecionado"""
        self.selected_device = item.data(Qt.ItemDataRole.UserRole)
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT device_id, device_name, nickname, status, token, photo_path, created_at, last_seen FROM devices WHERE device_id = ?",
            (self.selected_device,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            device_id, device_name, nickname, status, token, photo_path, created_at, last_seen = row
            
            info_text = f"""╔════════════════════════════════════════╗
║        INFORMAÇÕES DO DISPOSITIVO      ║
╚════════════════════════════════════════╝

Nome: {device_name}
Apelido: {nickname}
ID: {device_id}

Status: {'🟢 Online' if status == 'online' else '🔴 Offline'}
Telecnectado em: {last_seen or 'Nunca'}
Registrado em: {created_at}

Token: {token}

╔════════════════════════════════════════╗
║  INSTRUÇÕES DE EMPARELHAMENTO         ║
╚════════════════════════════════════════╝

1. Instale o app Android no seu celular
2. Abra o app e clique em "Conectar"
3. Escaneie o QR code ou digite o token
4. Confirme a conexão no celular
5. Pronto! Agora você pode controlar

Nota: Todas as ações requerem consentimento
do dono do celular.
            """
            self.device_info.setText(info_text)
            
            # Gera QR code
            self.generate_qr_code(token)
    
    def generate_qr_code(self, token):
        """Gera QR code para emparelhamento"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(token)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="white", back_color="#1a1a1a")
            
            # Converte para QPixmap
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.read())
            
            self.qr_label.setPixmap(pixmap.scaledToWidth(300))
        except Exception as e:
            self.qr_label.setText(f"Erro ao gerar QR: {e}")
    
    def copy_token(self):
        """Copia token para clipboard"""
        if not self.selected_device:
            QMessageBox.warning(self, "Erro", "Selecione um dispositivo")
            return
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT token FROM devices WHERE device_id = ?", (self.selected_device,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            token = row[0]
            clipboard = QApplication.clipboard()
            clipboard.setText(token)
            QMessageBox.information(self, "Sucesso", f"Token copiado: {token}")
    
    def add_device_dialog(self):
        """Dialog para adicionar novo dispositivo"""
        device_name, ok = QInputDialog.getText(
            self,
            "Novo Dispositivo",
            "Nome do dispositivo (ex: Celular João):",
            text="Meu Celular"
        )
        if not ok or not device_name:
            return
        
        nickname, ok = QInputDialog.getText(
            self,
            "Novo Dispositivo",
            "Apelido (ex: João):",
            text=device_name
        )
        if not ok:
            return
        
        device_id = str(uuid4())
        token = str(uuid4())
        now = datetime.utcnow().isoformat()
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO devices (device_id, device_name, nickname, photo_path, status, token, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (device_id, device_name, nickname, "", "offline", token, now)
        )
        conn.commit()
        conn.close()
        
        QMessageBox.information(
            self,
            "✓ Sucesso",
            f"Dispositivo '{device_name}' adicionado!\n\nToken: {token}\n\nUse este token no app Android para emparelhar."
        )
        
        self.refresh_devices()
    
    def connect_device(self):
        """Conecta ao dispositivo"""
        if not self.selected_device:
            QMessageBox.warning(self, "Erro", "Selecione um dispositivo")
            return
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT status, device_name FROM devices WHERE device_id = ?", (self.selected_device,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            status, device_name = row
            if status == "online":
                QMessageBox.information(
                    self,
                    "✓ Conectado",
                    f"Dispositivo '{device_name}' está online e pronto!\n\nA visualização da tela e controle remoto serão implementados em breve."
                )
            else:
                QMessageBox.warning(
                    self,
                    "⚠️ Desconectado",
                    f"Dispositivo '{device_name}' está offline.\n\nCertifique-se de que o app Android está rodando e conectado."
                )
    
    def disconnect_device(self):
        """Desconecta do dispositivo"""
        if not self.selected_device:
            QMessageBox.warning(self, "Erro", "Selecione um dispositivo")
            return
        
        QMessageBox.information(self, "Info", "Desconexão será implementada em breve")
    
    def remove_device(self):
        """Remove um dispositivo"""
        if not self.selected_device:
            QMessageBox.warning(self, "Erro", "Selecione um dispositivo")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            "Tem certeza que deseja remover este dispositivo?"
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM devices WHERE device_id = ?", (self.selected_device,))
            conn.commit()
            conn.close()
            
            self.selected_device = None
            self.device_info.setText("Selecione um dispositivo para ver os detalhes")
            self.qr_label.setText("Selecione um dispositivo")
            self.refresh_devices()
            
            QMessageBox.information(self, "✓ Removido", "Dispositivo removido com sucesso")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RemoteControlGUI()
    window.show()
    sys.exit(app.exec())
