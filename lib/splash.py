#!/usr/bin/env python3
"""
BonBloc Technology - 3D Dashboard Splash Screen
Forklift Monitoring System
"""

import sys
import os
import math
import random
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QProgressBar, QGraphicsDropShadowEffect, QFrame,
    QGraphicsOpacityEffect
)
from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize,
    pyqtSignal, QThread
)
from PyQt5.QtGui import (
    QPainter, QColor, QLinearGradient, QRadialGradient, QFont,
    QPen, QBrush, QFontDatabase, QPixmap, QIcon, QPolygonF, QPointF,
    QConicalGradient, QFontMetrics
)

# ============================================================
# 3D GLOWING PARTICLE SYSTEM (Background Animation)
# ============================================================
class Particle:
    def __init__(self, width, height):
        self.x = random.uniform(0, width)
        self.y = random.uniform(0, height)
        self.z = random.uniform(0.5, 3.0)  # depth for 3D effect
        self.size = random.uniform(1.5, 4.0)
        self.speed = random.uniform(0.2, 1.0)
        self.opacity = random.uniform(0.1, 0.6)
        self.color = random.choice([
            QColor(0, 200, 255),   # Cyan
            QColor(0, 150, 255),   # Blue
            QColor(100, 200, 255), # Light Blue
            QColor(0, 255, 200),   # Teal
        ])
        self.width = width
        self.height = height

    def update(self):
        self.y -= self.speed * self.z
        if self.y < -10:
            self.y = self.height + 10
            self.x = random.uniform(0, self.width)

    def draw(self, painter):
        painter.setOpacity(self.opacity)
        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.NoPen)
        # Draw with glow effect by drawing larger semi-transparent circle first
        glow_size = self.size * 3 * self.z
        painter.setOpacity(self.opacity * 0.15)
        painter.drawEllipse(
            QPointF(self.x - glow_size/2, self.y - glow_size/2),
            glow_size, glow_size
        )
        painter.setOpacity(self.opacity)
        painter.drawEllipse(
            QPointF(self.x - self.size*self.z/2, self.y - self.size*self.z/2),
            self.size * self.z, self.size * self.z
        )


# ============================================================
# 3D CIRCULAR GAUGE WIDGET
# ============================================================
class CircularGauge(QFrame):
    def __init__(self, title="GAUGE", max_value=100, parent=None):
        super().__init__(parent)
        self.title = title
        self.max_value = max_value
        self.current_value = 0
        self.target_value = 0
        self.setFixedSize(160, 160)
        self.setFrameShape(QFrame.NoFrame)

        # Animation timer
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.animate_value)

    def set_value(self, value):
        self.target_value = min(value, self.max_value)
        self.anim_timer.start(16)  # ~60fps

    def animate_value(self):
        diff = self.target_value - self.current_value
        if abs(diff) < 0.5:
            self.current_value = self.target_value
            self.anim_timer.stop()
        else:
            self.current_value += diff * 0.1
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        center_x = self.width() / 2
        center_y = self.height() / 2
        radius = 65

        # Background dark circle with 3D depth
        painter.setPen(Qt.NoPen)

        # Outer shadow ring
        shadow_gradient = QRadialGradient(center_x, center_y, radius + 8)
        shadow_gradient.setColorAt(0, QColor(0, 100, 200, 60))
        shadow_gradient.setColorAt(1, QColor(0, 50, 100, 0))
        painter.setBrush(QBrush(shadow_gradient))
        painter.drawEllipse(center_x - radius - 8, center_y - radius - 8,
                           (radius + 8) * 2, (radius + 8) * 2)

        # Inner dark background
        bg_gradient = QRadialGradient(center_x, center_y, radius)
        bg_gradient.setColorAt(0, QColor(10, 20, 35))
        bg_gradient.setColorAt(0.7, QColor(5, 12, 22))
        bg_gradient.setColorAt(1, QColor(2, 6, 12))
        painter.setBrush(QBrush(bg_gradient))
        painter.drawEllipse(center_x - radius, center_y - radius,
                           radius * 2, radius * 2)

        # Progress arc
        pen = QPen()
        pen.setWidth(6)
        pen.setCapStyle(Qt.RoundCap)

        # Background arc
        pen.setColor(QColor(30, 50, 70))
        painter.setPen(pen)
        painter.drawArc(center_x - radius + 12, center_y - radius + 12,
                       (radius - 12) * 2, (radius - 12) * 2,
                       225 * 16, -270 * 16)

        # Value arc with gradient
        value_gradient = QConicalGradient(center_x, center_y, 225)
        value_gradient.setColorAt(0, QColor(0, 255, 200))
        value_gradient.setColorAt(0.5, QColor(0, 150, 255))
        value_gradient.setColorAt(1, QColor(0, 255, 200))
        pen.setBrush(QBrush(value_gradient))
        pen.setWidth(8)
        painter.setPen(pen)

        span = int((self.current_value / self.max_value) * 270 * 16)
        painter.drawArc(center_x - radius + 12, center_y - radius + 12,
                       (radius - 12) * 2, (radius - 12) * 2,
                       225 * 16, -span)

        # Value text
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Segoe UI", 18, QFont.Bold)
        painter.setFont(font)
        value_text = f"{int(self.current_value)}"
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(value_text)
        painter.drawText(int(center_x - text_width/2), int(center_y + 5), value_text)

        # Title
        painter.setPen(QColor(100, 180, 255))
        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        fm = painter.fontMetrics()
        title_width = fm.horizontalAdvance(self.title)
        painter.drawText(int(center_x - title_width/2), int(center_y + 28), self.title)

        painter.end()


# ============================================================
# 3D BAR CHART INDICATOR
# ============================================================
class BarIndicator(QFrame):
    def __init__(self, label="SENSOR", color=QColor(0, 200, 255), parent=None):
        super().__init__(parent)
        self.label_text = label
        self.bar_color = color
        self.value = 0
        self.target_value = 0
        self.setFixedSize(200, 35)
        self.setFrameShape(QFrame.NoFrame)

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.animate)

    def set_value(self, value):
        self.target_value = min(value, 100)
        self.anim_timer.start(16)

    def animate(self):
        diff = self.target_value - self.value
        if abs(diff) < 0.5:
            self.value = self.target_value
            self.anim_timer.stop()
        else:
            self.value += diff * 0.08
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background track
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(20, 35, 55))
        painter.drawRoundedRect(80, 10, 110, 14, 7, 7)

        # Value bar with gradient
        bar_width = int((self.value / 100) * 106)
        if bar_width > 0:
            gradient = QLinearGradient(80, 0, 80 + bar_width, 0)
            gradient.setColorAt(0, self.bar_color.darker(120))
            gradient.setColorAt(0.5, self.bar_color)
            gradient.setColorAt(1, self.bar_color.lighter(130))
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(82, 12, bar_width, 10, 5, 5)

        # Label
        painter.setPen(QColor(150, 180, 210))
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.drawText(5, 23, self.label_text)

        # Value text
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font)
        painter.drawText(195, 23, f"{int(self.value)}")

        painter.end()


# ============================================================
# HEXAGON STATUS CARD (3D Style)
# ============================================================
class HexStatusCard(QFrame):
    def __init__(self, title, icon_text, parent=None):
        super().__init__(parent)
        self.title = title
        self.icon_text = icon_text
        self.status = "ONLINE"
        self.status_color = QColor(0, 255, 150)
        self.setFixedSize(140, 100)
        self.setFrameShape(QFrame.NoFrame)

    def set_status(self, status, color):
        self.status = status
        self.status_color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 3D card background
        painter.setPen(Qt.NoPen)

        # Shadow
        shadow = QGraphicsDropShadowEffect()

        # Card gradient
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(15, 30, 50))
        gradient.setColorAt(1, QColor(8, 18, 32))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(2, 2, self.width()-4, self.height()-4, 10, 10)

        # Top border glow
        pen = QPen(QColor(0, 150, 255, 100))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(2, 2, self.width()-4, self.height()-4, 10, 10)

        # Icon area (hexagon-ish circle)
        painter.setPen(Qt.NoPen)
        icon_gradient = QRadialGradient(35, 35, 20)
        icon_gradient.setColorAt(0, QColor(0, 150, 255, 80))
        icon_gradient.setColorAt(1, QColor(0, 80, 160, 30))
        painter.setBrush(QBrush(icon_gradient))
        painter.drawEllipse(15, 15, 40, 40)

        # Icon text
        painter.setPen(QColor(0, 200, 255))
        font = QFont("Segoe UI", 16, QFont.Bold)
        painter.setFont(font)
        painter.drawText(15, 15, 40, 40, Qt.AlignCenter, self.icon_text)

        # Title
        painter.setPen(QColor(180, 200, 220))
        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.drawText(65, 20, 70, 20, Qt.AlignLeft | Qt.AlignVCenter, self.title)

        # Status dot
        painter.setPen(Qt.NoNoPen)
        painter.setBrush(QBrush(self.status_color))
        painter.drawEllipse(65, 48, 8, 8)

        # Status text
        painter.setPen(self.status_color)
        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        painter.drawText(78, 48, 55, 15, Qt.AlignLeft | Qt.AlignVCenter, self.status)

        painter.end()


# ============================================================
# MAIN 3D DASHBOARD SPLASH SCREEN
# ============================================================
class DashboardSplash(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("BonBloc Technology - Forklift Monitoring System")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.showFullScreen()

        # Color scheme
        self.bg_dark = QColor(5, 10, 18)
        self.accent_cyan = QColor(0, 200, 255)
        self.accent_blue = QColor(0, 100, 200)

        # Particles
        self.particles = [Particle(self.width(), self.height()) for _ in range(80)]

        # Setup central widget
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.central.setStyleSheet("background-color: #050a12;")

        # Main layout
        main_layout = QVBoxLayout(self.central)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(20)

        # ========== TOP BAR ==========
        top_bar = QHBoxLayout()

        # Company branding
        brand_layout = QVBoxLayout()
        brand_label = QLabel("BONBLOC")
        brand_label.setStyleSheet("""
            color: #00c8ff;
            font-size: 28px;
            font-weight: bold;
            font-family: 'Segoe UI', Arial;
            letter-spacing: 4px;
        """)

        tagline = QLabel("TECHNOLOGY")
        tagline.setStyleSheet("""
            color: #4a90c8;
            font-size: 12px;
            font-family: 'Segoe UI', Arial;
            letter-spacing: 8px;
            margin-top: -5px;
        """)

        brand_layout.addWidget(brand_label)
        brand_layout.addWidget(tagline)
        top_bar.addLayout(brand_layout)

        top_bar.addStretch()

        # System status indicator
        self.sys_status = QLabel("● SYSTEM ACTIVE")
        self.sys_status.setStyleSheet("""
            color: #00ff96;
            font-size: 11px;
            font-family: 'Segoe UI', Arial;
            letter-spacing: 2px;
            padding: 5px 15px;
            background-color: rgba(0, 255, 150, 0.1);
            border: 1px solid rgba(0, 255, 150, 0.3);
            border-radius: 15px;
        """)
        top_bar.addWidget(self.sys_status)

        main_layout.addLayout(top_bar)

        # ========== MAIN DASHBOARD AREA ==========
        dashboard = QHBoxLayout()
        dashboard.setSpacing(25)

        # ---- Left Panel: Gauges ----
        left_panel = QVBoxLayout()
        left_panel.setSpacing(20)

        # Section title
        gauges_title = QLabel("◆ REAL-TIME METRICS")
        gauges_title.setStyleSheet("""
            color: #6ab4ff;
            font-size: 11px;
            font-family: 'Segoe UI', Arial;
            letter-spacing: 3px;
            padding-bottom: 5px;
            border-bottom: 1px solid rgba(0, 150, 255, 0.3);
        """)
        left_panel.addWidget(gauges_title)

        # Gauges container
        gauges_row = QHBoxLayout()
        self.gauge_cpu = CircularGauge("CPU LOAD", 100)
        self.gauge_mem = CircularGauge("MEMORY", 100)
        self.gauge_net = CircularGauge("NETWORK", 100)
        gauges_row.addWidget(self.gauge_cpu)
        gauges_row.addWidget(self.gauge_mem)
        gauges_row.addWidget(self.gauge_net)
        left_panel.addLayout(gauges_row)

        # Bar indicators
        bars_title = QLabel("◆ SENSOR DATA")
        bars_title.setStyleSheet("""
            color: #6ab4ff;
            font-size: 11px;
            font-family: 'Segoe UI', Arial;
            letter-spacing: 3px;
            padding-bottom: 5px;
            border-bottom: 1px solid rgba(0, 150, 255, 0.3);
            margin-top: 10px;
        """)
        left_panel.addWidget(bars_title)

        self.bar_temp = BarIndicator("TEMPERATURE", QColor(255, 100, 50))
        self.bar_vib = BarIndicator("VIBRATION", QColor(255, 200, 50))
        self.bar_load = BarIndicator("FORK LOAD", QColor(0, 200, 255))
        self.bar_bat = BarIndicator("BATTERY", QColor(0, 255, 150))

        left_panel.addWidget(self.bar_temp)
        left_panel.addWidget(self.bar_vib)
        left_panel.addWidget(self.bar_load)
        left_panel.addWidget(self.bar_bat)
        left_panel.addStretch()

        dashboard.addLayout(left_panel, 3)

        # ---- Center Panel: 3D Visualization ----
        center_panel = QVBoxLayout()

        viz_title = QLabel("◆ FORKLIFT MONITORING DASHBOARD")
        viz_title.setStyleSheet("""
            color: #6ab4ff;
            font-size: 11px;
            font-family: 'Segoe UI', Arial;
            letter-spacing: 3px;
            padding-bottom: 5px;
            border-bottom: 1px solid rgba(0, 150, 255, 0.3);
        """)
        center_panel.addWidget(viz_title)

        # 3D Visualization Area
        self.viz_widget = QWidget()
        self.viz_widget.setMinimumSize(400, 300)
        self.viz_widget.setStyleSheet("""
            background-color: rgba(8, 18, 35, 0.8);
            border: 1px solid rgba(0, 150, 255, 0.2);
            border-radius: 10px;
        """)

        # Add forklift visualization label inside
        viz_layout = QVBoxLayout(self.viz_widget)
        viz_layout.setAlignment(Qt.AlignCenter)

        self.forklift_icon = QLabel("🚜")
        self.forklift_icon.setStyleSheet("font-size: 80px;")
        self.forklift_icon.setAlignment(Qt.AlignCenter)
        viz_layout.addWidget(self.forklift_icon)

        self.viz_status = QLabel("INITIALIZING FORKLIFT SYSTEM...")
        self.viz_status.setStyleSheet("""
            color: #00c8ff;
            font-size: 14px;
            font-family: 'Segoe UI', Arial;
            letter-spacing: 2px;
        """)
        self.viz_status.setAlignment(Qt.AlignCenter)
        viz_layout.addWidget(self.viz_status)

        center_panel.addWidget(self.viz_widget)

        # Status cards row
        cards_row = QHBoxLayout()
        self.card_engine = HexStatusCard("ENGINE", "⚙")
        self.card_gps = HexStatusCard("GPS", "📡")
        self.card_cam = HexStatusCard("CAMERA", "📷")
        self.card_alert = HexStatusCard("ALERTS", "⚠")

        cards_row.addWidget(self.card_engine)
        cards_row.addWidget(self.card_gps)
        cards_row.addWidget(self.card_cam)
        cards_row.addWidget(self.card_alert)
        center_panel.addLayout(cards_row)

        dashboard.addLayout(center_panel, 4)

        # ---- Right Panel: Log & Info ----
        right_panel = QVBoxLayout()

        log_title = QLabel("◆ SYSTEM LOG")
        log_title.setStyleSheet("""
            color: #6ab4ff;
            font-size: 11px;
            font-family: 'Segoe UI', Arial;
            letter-spacing: 3px;
            padding-bottom: 5px;
            border-bottom: 1px solid rgba(0, 150, 255, 0.3);
        """)
        right_panel.addWidget(log_title)

        # Log display
        self.log_display = QLabel()
        self.log_display.setStyleSheet("""
            background-color: rgba(5, 12, 22, 0.9);
            color: #8ec8ff;
            font-family: 'Consolas', monospace;
            font-size: 10px;
            padding: 10px;
            border: 1px solid rgba(0, 150, 255, 0.2);
            border-radius: 8px;
        """)
        self.log_display.setMinimumSize(250, 200)
        self.log_display.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.log_display.setWordWrap(True)
        right_panel.addWidget(self.log_display)

        # Time display
        self.time_label = QLabel()
        self.time_label.setStyleSheet("""
            color: #4a90c8;
            font-size: 20px;
            font-family: 'Segoe UI', Arial;
            letter-spacing: 2px;
            padding: 10px;
        """)
        self.time_label.setAlignment(Qt.AlignCenter)
        right_panel.addWidget(self.time_label)

        right_panel.addStretch()
        dashboard.addLayout(right_panel, 2)

        main_layout.addLayout(dashboard, 1)

        # ========== BOTTOM PROGRESS BAR ==========
        bottom_layout = QVBoxLayout()
        bottom_layout.setSpacing(10)

        # Progress info
        progress_info = QHBoxLayout()
        self.step_label = QLabel("INITIALIZING...")
        self.step_label.setStyleSheet("""
            color: #ffffff;
            font-size: 13px;
            font-family: 'Segoe UI', Arial;
            letter-spacing: 1px;
        """)
        progress_info.addWidget(self.step_label)

        progress_info.addStretch()

        self.percent_label = QLabel("0%")
        self.percent_label.setStyleSheet("""
            color: #00c8ff;
            font-size: 16px;
            font-family: 'Segoe UI', Arial;
            font-weight: bold;
        """)
        progress_info.addWidget(self.percent_label)

        bottom_layout.addLayout(progress_info)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: rgba(20, 40, 70, 0.8);
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0066cc, stop:0.5 #00c8ff, stop:1 #00ff96);
                border-radius: 4px;
            }
        """)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        bottom_layout.addWidget(self.progress)

        main_layout.addLayout(bottom_layout)

        # ========== TIMERS & ANIMATIONS ==========

        # Particle animation timer
        self.particle_timer = QTimer(self)
        self.particle_timer.timeout.connect(self.update_particles)
        self.particle_timer.start(33)  # ~30fps for particles

        # Time update timer
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)
        self.update_time()

        # Loading steps
        self.steps = [
            ("Loading Database Modules...", self.step_database),
            ("Initializing Sensor Arrays...", self.step_sensors),
            ("Calibrating Forklift Systems...", self.step_calibration),
            ("Starting API Gateway...", self.step_api),
            ("Loading Dashboard Interface...", self.step_dashboard),
            ("System Ready - Launching...", self.step_ready)
        ]
        self.current_step = 0
        self.progress_value = 0

        # Start loading sequence
        self.load_timer = QTimer(self)
        self.load_timer.timeout.connect(self.advance_loading)
        self.load_timer.start(800)

        # Initial log
        self.log_messages = []
        self.add_log("System boot sequence initiated...")
        self.add_log("BonBloc Technology v2.0")
        self.add_log("Forklift Monitoring System")

        # Fade in animation
        self.setWindowOpacity(0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(1000)
        self.fade_in.setStartValue(0)
        self.fade_in.setEndValue(1)
        self.fade_in.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_in.start()

    def update_particles(self):
        for p in self.particles:
            p.update()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Dark background
        painter.fillRect(self.rect(), self.bg_dark)

        # Draw grid lines (3D perspective effect)
        painter.setPen(QPen(QColor(0, 100, 200, 15), 1))
        grid_spacing = 60
        for x in range(0, self.width(), grid_spacing):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid_spacing):
            painter.drawLine(0, y, self.width(), y)

        # Draw diagonal accent lines
        painter.setPen(QPen(QColor(0, 150, 255, 20), 1))
        for i in range(-self.height(), self.width(), 120):
            painter.drawLine(i, self.height(), i + self.height(), 0)

        # Draw particles
        for p in self.particles:
            p.draw(painter)

        # Draw ambient glow at corners
        corner_glow = QRadialGradient(0, 0, 300)
        corner_glow.setColorAt(0, QColor(0, 100, 200, 40))
        corner_glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(corner_glow))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, 300, 300)

        corner_glow2 = QRadialGradient(self.width(), self.height(), 300)
        corner_glow2.setColorAt(0, QColor(0, 200, 255, 30))
        corner_glow2.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(corner_glow2))
        painter.drawRect(self.width()-300, self.height()-300, 300, 300)

        painter.end()

    def update_time(self):
        now = datetime.now()
        self.time_label.setText(now.strftime("%H:%M:%S"))

    def add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_messages.append(f"[{timestamp}] {message}")
        if len(self.log_messages) > 12:
            self.log_messages.pop(0)
        self.log_display.setText("\n".join(self.log_messages))

    def advance_loading(self):
        if self.current_step < len(self.steps):
            text, callback = self.steps[self.current_step]
            self.step_label.setText(text)
            self.add_log(text)
            if callback:
                callback()
            self.current_step += 1
        else:
            self.load_timer.stop()
            self.fade_out_and_exit()

    def step_database(self):
        self.progress_value = 15
        self.progress.setValue(self.progress_value)
        self.percent_label.setText("15%")
        self.gauge_cpu.set_value(35)
        self.bar_temp.set_value(42)

    def step_sensors(self):
        self.progress_value = 32
        self.progress.setValue(self.progress_value)
        self.percent_label.setText("32%")
        self.gauge_mem.set_value(28)
        self.bar_vib.set_value(15)
        self.card_engine.set_status("WARMING", QColor(255, 200, 50))
        self.add_log("Sensor array online: 12/12")

    def step_calibration(self):
        self.progress_value = 48
        self.progress.setValue(self.progress_value)
        self.percent_label.setText("48%")
        self.gauge_net.set_value(55)
        self.bar_load.set_value(0)
        self.card_gps.set_status("LOCKING", QColor(255, 200, 50))
        self.viz_status.setText("CALIBRATING SENSORS...")
        self.add_log("GPS signal acquired: 8 satellites")

    def step_api(self):
        self.progress_value = 65
        self.progress.setValue(self.progress_value)
        self.percent_label.setText("65%")
        self.gauge_cpu.set_value(62)
        self.bar_bat.set_value(87)
        self.card_cam.set_status("ACTIVE", QColor(0, 255, 150))
        self.viz_status.setText("API GATEWAY ONLINE")
        self.add_log("REST API listening on port 8080")

    def step_dashboard(self):
        self.progress_value = 82
        self.progress.setValue(self.progress_value)
        self.percent_label.setText("82%")
        self.gauge_mem.set_value(45)
        self.bar_temp.set_value(38)
        self.card_engine.set_status("ONLINE", QColor(0, 255, 150))
        self.card_gps.set_status("LOCKED", QColor(0, 255, 150))
        self.viz_status.setText("DASHBOARD LOADING...")
        self.add_log("WebSocket connection established")

    def step_ready(self):
        self.progress_value = 100
        self.progress.setValue(self.progress_value)
        self.percent_label.setText("100%")
        self.gauge_cpu.set_value(12)
        self.gauge_mem.set_value(18)
        self.gauge_net.set_value(25)
        self.bar_vib.set_value(5)
        self.card_alert.set_status("CLEAR", QColor(0, 255, 150))
        self.viz_status.setText("SYSTEM READY")
        self.sys_status.setText("● ALL SYSTEMS NOMINAL")
        self.add_log("All systems operational. Launching dashboard...")

    def fade_out_and_exit(self):
        self.fade_out = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out.setDuration(1500)
        self.fade_out.setStartValue(1)
        self.fade_out.setEndValue(0)
        self.fade_out.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_out.finished.connect(self.close)
        self.fade_out.start()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

    def mousePressEvent(self, event):
        # Allow click to skip
        if self.current_step < len(self.steps):
            self.current_step = len(self.steps) - 1
            self.advance_loading()


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Set application font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Create and show splash
    splash = DashboardSplash()
    splash.show()

    sys.exit(app.exec_())