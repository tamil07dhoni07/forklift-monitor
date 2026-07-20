#!/usr/bin/env python3
"""
BonBloc Technology - 3D Dashboard Splash Screen (GTK3 + Cairo)
Forklift Monitoring System
Fixed version - no black screen issue
"""

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, GLib, Gdk, GObject
import cairo
import math
import random
import os
from datetime import datetime

# ============================================================
# PARTICLE SYSTEM
# ============================================================
class Particle:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.reset()

    def reset(self):
        self.x = random.uniform(0, self.width)
        self.y = random.uniform(0, self.height)
        self.z = random.uniform(0.5, 3.0)
        self.size = random.uniform(1.5, 4.0)
        self.speed = random.uniform(0.3, 1.2)
        self.opacity = random.uniform(0.1, 0.6)
        self.color = random.choice([
            (0, 200, 255),
            (0, 150, 255),
            (100, 200, 255),
            (0, 255, 200),
        ])

    def update(self):
        self.y -= self.speed * self.z
        if self.y < -10:
            self.y = self.height + 10
            self.x = random.uniform(0, self.width)

    def draw(self, ctx):
        glow_size = self.size * 3 * self.z
        ctx.set_source_rgba(
            self.color[0]/255, self.color[1]/255, self.color[2]/255,
            self.opacity * 0.15
        )
        ctx.arc(self.x, self.y, glow_size, 0, 2 * math.pi)
        ctx.fill()

        ctx.set_source_rgba(
            self.color[0]/255, self.color[1]/255, self.color[2]/255,
            self.opacity
        )
        ctx.arc(self.x, self.y, self.size * self.z, 0, 2 * math.pi)
        ctx.fill()


# ============================================================
# CIRCULAR GAUGE (Cairo DrawingArea)
# ============================================================
class CircularGauge(Gtk.DrawingArea):
    def __init__(self, title="GAUGE", max_value=100):
        super().__init__()
        self.title = title
        self.max_value = max_value
        self.current_value = 0.0
        self.target_value = 0.0
        self.set_size_request(150, 150)
        self.connect("draw", self.on_draw)
        self.anim_id = None

    def set_value(self, value):
        self.target_value = min(value, self.max_value)
        if self.anim_id is None:
            self.anim_id = GLib.timeout_add(16, self.animate)

    def animate(self):
        diff = self.target_value - self.current_value
        if abs(diff) < 0.5:
            self.current_value = self.target_value
            self.anim_id = None
            self.queue_draw()
            return False
        self.current_value += diff * 0.1
        self.queue_draw()
        return True

    def on_draw(self, widget, ctx):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        cx, cy = width / 2, height / 2
        radius = 60

        # Clear with transparent background
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        # Outer glow
        shadow = cairo.RadialGradient(cx, cy, radius * 0.8, cx, cy, radius + 10)
        shadow.add_color_stop_rgba(0, 0, 0.4, 0.8, 0.3)
        shadow.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(shadow)
        ctx.arc(cx, cy, radius + 10, 0, 2 * math.pi)
        ctx.fill()

        # Inner background
        bg = cairo.RadialGradient(cx, cy, 0, cx, cy, radius)
        bg.add_color_stop_rgba(0, 0.04, 0.08, 0.14, 0.9)
        bg.add_color_stop_rgba(0.7, 0.02, 0.05, 0.09, 0.9)
        bg.add_color_stop_rgba(1, 0.01, 0.02, 0.05, 0.9)
        ctx.set_source(bg)
        ctx.arc(cx, cy, radius, 0, 2 * math.pi)
        ctx.fill()

        # Background arc
        ctx.set_line_width(5)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgba(0.12, 0.2, 0.28, 0.8)
        ctx.arc(cx, cy, radius - 10, math.radians(135), math.radians(405))
        ctx.stroke()

        # Value arc
        if self.current_value > 0:
            span = (self.current_value / self.max_value) * 270
            ratio = self.current_value / self.max_value

            ctx.set_line_width(6)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)

            # Gradient color
            r = 0.0
            g = 0.8 - ratio * 0.3
            b = 1.0 - ratio * 0.4

            ctx.set_source_rgba(r, g, b, 0.9)
            ctx.arc(cx, cy, radius - 10, math.radians(135), math.radians(135 + span))
            ctx.stroke()

            # Glow
            ctx.set_line_width(10)
            ctx.set_source_rgba(r, g, b, 0.15)
            ctx.arc(cx, cy, radius - 10, math.radians(135), math.radians(135 + span))
            ctx.stroke()

        # Value text
        ctx.set_source_rgb(1, 1, 1)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(20)
        text = f"{int(self.current_value)}"
        ext = ctx.text_extents(text)
        ctx.move_to(cx - ext.width/2, cy + 6)
        ctx.show_text(text)

        # Title
        ctx.set_source_rgba(0.4, 0.7, 1, 0.9)
        ctx.set_font_size(8)
        ext = ctx.text_extents(self.title)
        ctx.move_to(cx - ext.width/2, cy + 24)
        ctx.show_text(self.title)

        return False


# ============================================================
# BAR INDICATOR
# ============================================================
class BarIndicator(Gtk.DrawingArea):
    def __init__(self, label="SENSOR", color=(0, 200, 255)):
        super().__init__()
        self.label_text = label
        self.bar_color = color
        self.value = 0.0
        self.target_value = 0.0
        self.set_size_request(180, 30)
        self.connect("draw", self.on_draw)
        self.anim_id = None

    def set_value(self, value):
        self.target_value = min(value, 100)
        if self.anim_id is None:
            self.anim_id = GLib.timeout_add(16, self.animate)

    def animate(self):
        diff = self.target_value - self.value
        if abs(diff) < 0.5:
            self.value = self.target_value
            self.anim_id = None
            self.queue_draw()
            return False
        self.value += diff * 0.08
        self.queue_draw()
        return True

    def on_draw(self, widget, ctx):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()

        # Clear
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        # Background track
        ctx.set_source_rgba(0.08, 0.14, 0.22, 0.8)
        self.rounded_rect(ctx, 70, 8, 100, 14, 7)
        ctx.fill()

        # Value bar
        bar_width = (self.value / 100) * 96
        if bar_width > 0:
            gradient = cairo.LinearGradient(72, 0, 72 + bar_width, 0)
            gradient.add_color_stop_rgba(0, 
                self.bar_color[0]/255 * 0.7, 
                self.bar_color[1]/255 * 0.7, 
                self.bar_color[2]/255 * 0.7, 0.9)
            gradient.add_color_stop_rgba(0.5,
                self.bar_color[0]/255,
                self.bar_color[1]/255,
                self.bar_color[2]/255, 0.9)
            gradient.add_color_stop_rgba(1,
                self.bar_color[0]/255 * 1.3,
                self.bar_color[1]/255 * 1.3,
                self.bar_color[2]/255 * 1.3, 0.9)
            ctx.set_source(gradient)
            self.rounded_rect(ctx, 72, 10, bar_width, 10, 5)
            ctx.fill()

        # Label
        ctx.set_source_rgba(0.6, 0.7, 0.85, 0.9)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(9)
        ctx.move_to(2, 20)
        ctx.show_text(self.label_text)

        # Value text
        ctx.set_source_rgb(1, 1, 1)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(9)
        text = f"{int(self.value)}"
        ctx.move_to(175, 20)
        ctx.show_text(text)

        return False

    def rounded_rect(self, ctx, x, y, w, h, r):
        ctx.move_to(x + r, y)
        ctx.line_to(x + w - r, y)
        ctx.arc(x + w - r, y + r, r, -math.pi/2, 0)
        ctx.line_to(x + w, y + h - r)
        ctx.arc(x + w - r, y + h - r, r, 0, math.pi/2)
        ctx.line_to(x + r, y + h)
        ctx.arc(x + r, y + h - r, r, math.pi/2, math.pi)
        ctx.line_to(x, y + r)
        ctx.arc(x + r, y + r, r, math.pi, math.pi * 1.5)
        ctx.close_path()


# ============================================================
# STATUS CARD
# ============================================================
class StatusCard(Gtk.DrawingArea):
    def __init__(self, title, icon_text):
        super().__init__()
        self.title = title
        self.icon_text = icon_text
        self.status = "ONLINE"
        self.status_color = (0, 255, 150)
        self.set_size_request(130, 90)
        self.connect("draw", self.on_draw)

    def set_status(self, status, color):
        self.status = status
        self.status_color = color
        self.queue_draw()

    def on_draw(self, widget, ctx):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()

        # Clear
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.set_operator(cairo.OPERATOR_SOURCE)
        ctx.paint()
        ctx.set_operator(cairo.OPERATOR_OVER)

        # Card background
        gradient = cairo.LinearGradient(0, 0, 0, height)
        gradient.add_color_stop_rgba(0, 0.06, 0.12, 0.2, 0.85)
        gradient.add_color_stop_rgba(1, 0.03, 0.07, 0.13, 0.85)
        ctx.set_source(gradient)
        self.rounded_rect(ctx, 0, 0, width, height, 8)
        ctx.fill()

        # Border
        ctx.set_line_width(1)
        ctx.set_source_rgba(0, 0.5, 1, 0.3)
        self.rounded_rect(ctx, 0, 0, width, height, 8)
        ctx.stroke()

        # Top glow line
        ctx.set_line_width(2)
        ctx.set_source_rgba(0, 0.6, 1, 0.4)
        ctx.move_to(8, 1)
        ctx.line_to(width - 8, 1)
        ctx.stroke()

        # Icon
        ctx.set_source_rgba(0, 0.7, 1, 0.8)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(18)
        ext = ctx.text_extents(self.icon_text)
        ctx.move_to(15, 28)
        ctx.show_text(self.icon_text)

        # Title
        ctx.set_source_rgba(0.7, 0.8, 0.9, 0.9)
        ctx.set_font_size(9)
        ctx.move_to(45, 20)
        ctx.show_text(self.title)

        # Status dot
        ctx.set_source_rgba(
            self.status_color[0]/255,
            self.status_color[1]/255,
            self.status_color[2]/255, 1
        )
        ctx.arc(48, 38, 3, 0, 2 * math.pi)
        ctx.fill()

        # Status text
        ctx.set_source_rgba(
            self.status_color[0]/255,
            self.status_color[1]/255,
            self.status_color[2]/255, 1
        )
        ctx.set_font_size(8)
        ctx.move_to(55, 41)
        ctx.show_text(self.status)

        return False

    def rounded_rect(self, ctx, x, y, w, h, r):
        ctx.move_to(x + r, y)
        ctx.line_to(x + w - r, y)
        ctx.arc(x + w - r, y + r, r, -math.pi/2, 0)
        ctx.line_to(x + w, y + h - r)
        ctx.arc(x + w - r, y + h - r, r, 0, math.pi/2)
        ctx.line_to(x + r, y + h)
        ctx.arc(x + r, y + h - r, r, math.pi/2, math.pi)
        ctx.line_to(x, y + r)
        ctx.arc(x + r, y + r, r, math.pi, math.pi * 1.5)
        ctx.close_path()


# ============================================================
# FIXED MAIN DASHBOARD SPLASH SCREEN
# ============================================================
class DashboardSplash(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)

        self.set_title("BonBloc Technology - Forklift Monitoring System")
        self.set_decorated(False)
        self.fullscreen()

        # CRITICAL FIX: Set RGBA visual for transparency support
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        # Dark background
        self.override_background_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(0.02, 0.04, 0.07, 1)
        )

        # Particles
        self.particles = []
        self.screen_w = 1920
        self.screen_h = 1080

        # ========== MAIN CONTAINER ==========
        # FIX: Use Gtk.Box instead of Gtk.Overlay to avoid black screen
        # Draw background on window's draw signal instead
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_margin_top(30)
        main_box.set_margin_bottom(30)
        main_box.set_margin_start(40)
        main_box.set_margin_end(40)
        main_box.set_spacing(15)
        self.add(main_box)

        # Connect window draw for background animation
        self.connect("draw", self.on_window_draw)

        # ========== TOP BAR ==========
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        top_bar.set_spacing(20)

        brand_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        brand_label = Gtk.Label()
        brand_label.set_markup(
            "<span font='26' weight='bold' foreground='#00c8ff' letter_spacing='4000'>"
            "BONBLOC"
            "</span>"
        )
        tagline = Gtk.Label()
        tagline.set_markup(
            "<span font='11' foreground='#4a90c8' letter_spacing='8000'>"
            "TECHNOLOGY"
            "</span>"
        )
        brand_box.pack_start(brand_label, False, False, 0)
        brand_box.pack_start(tagline, False, False, 0)
        top_bar.pack_start(brand_box, False, False, 0)

        top_bar.pack_end(Gtk.Label(), True, True, 0)

        self.sys_status = Gtk.Label()
        self.sys_status.set_markup(
            "<span font='10' foreground='#00ff96' letter_spacing='2000'>"
            "● SYSTEM ACTIVE"
            "</span>"
        )
        top_bar.pack_end(self.sys_status, False, False, 0)

        main_box.pack_start(top_bar, False, False, 0)

        # ========== DASHBOARD CONTENT ==========
        dashboard = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        dashboard.set_spacing(20)

        # ---- Left Panel ----
        left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_panel.set_spacing(12)

        gauges_title = Gtk.Label()
        gauges_title.set_markup(
            "<span font='10' foreground='#6ab4ff' letter_spacing='3000'>"
            "◆ REAL-TIME METRICS"
            "</span>"
        )
        gauges_title.set_halign(Gtk.Align.START)
        left_panel.pack_start(gauges_title, False, False, 0)

        gauges_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        gauges_row.set_spacing(12)
        gauges_row.set_halign(Gtk.Align.CENTER)

        self.gauge_cpu = CircularGauge("CPU LOAD", 100)
        self.gauge_mem = CircularGauge("MEMORY", 100)
        self.gauge_net = CircularGauge("NETWORK", 100)

        gauges_row.pack_start(self.gauge_cpu, False, False, 0)
        gauges_row.pack_start(self.gauge_mem, False, False, 0)
        gauges_row.pack_start(self.gauge_net, False, False, 0)
        left_panel.pack_start(gauges_row, False, False, 8)

        bars_title = Gtk.Label()
        bars_title.set_markup(
            "<span font='10' foreground='#6ab4ff' letter_spacing='3000'>"
            "◆ SENSOR DATA"
            "</span>"
        )
        bars_title.set_halign(Gtk.Align.START)
        left_panel.pack_start(bars_title, False, False, 0)

        self.bar_temp = BarIndicator("TEMPERATURE", (255, 100, 50))
        self.bar_vib = BarIndicator("VIBRATION", (255, 200, 50))
        self.bar_load = BarIndicator("FORK LOAD", (0, 200, 255))
        self.bar_bat = BarIndicator("BATTERY", (0, 255, 150))

        left_panel.pack_start(self.bar_temp, False, False, 3)
        left_panel.pack_start(self.bar_vib, False, False, 3)
        left_panel.pack_start(self.bar_load, False, False, 3)
        left_panel.pack_start(self.bar_bat, False, False, 3)

        dashboard.pack_start(left_panel, False, False, 0)

        # ---- Center Panel ----
        center_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        center_panel.set_spacing(12)

        viz_title = Gtk.Label()
        viz_title.set_markup(
            "<span font='10' foreground='#6ab4ff' letter_spacing='3000'>"
            "◆ FORKLIFT MONITORING DASHBOARD"
            "</span>"
        )
        viz_title.set_halign(Gtk.Align.START)
        center_panel.pack_start(viz_title, False, False, 0)

        # Visualization area - using EventBox for background styling
        viz_event = Gtk.EventBox()
        viz_event.set_size_request(380, 250)

        # Style the event box background
        viz_style = Gtk.CssProvider()
        viz_style.load_from_data(b"""
            eventbox {
                background-color: rgba(8, 18, 35, 0.85);
                border: 1px solid rgba(0, 150, 255, 0.25);
                border-radius: 10px;
            }
        """)
        viz_event.get_style_context().add_provider(
            viz_style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        viz_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        viz_box.set_spacing(10)
        viz_box.set_halign(Gtk.Align.CENTER)
        viz_box.set_valign(Gtk.Align.CENTER)

        self.forklift_icon = Gtk.Label()
        self.forklift_icon.set_markup(
            "<span font='55' foreground='#00c8ff'>🚜</span>"
        )
        viz_box.pack_start(self.forklift_icon, False, False, 0)

        self.viz_status = Gtk.Label()
        self.viz_status.set_markup(
            "<span font='13' foreground='#00c8ff' letter_spacing='2000'>"
            "INITIALIZING FORKLIFT SYSTEM..."
            "</span>"
        )
        viz_box.pack_start(self.viz_status, False, False, 0)

        viz_event.add(viz_box)
        center_panel.pack_start(viz_event, False, False, 0)

        # Status cards
        cards_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        cards_row.set_spacing(12)
        cards_row.set_halign(Gtk.Align.CENTER)

        self.card_engine = StatusCard("ENGINE", "⚙")
        self.card_gps = StatusCard("GPS", "📡")
        self.card_cam = StatusCard("CAMERA", "📷")
        self.card_alert = StatusCard("ALERTS", "⚠")

        cards_row.pack_start(self.card_engine, False, False, 0)
        cards_row.pack_start(self.card_gps, False, False, 0)
        cards_row.pack_start(self.card_cam, False, False, 0)
        cards_row.pack_start(self.card_alert, False, False, 0)
        center_panel.pack_start(cards_row, False, False, 8)

        dashboard.pack_start(center_panel, True, True, 0)

        # ---- Right Panel ----
        right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_panel.set_spacing(12)

        log_title = Gtk.Label()
        log_title.set_markup(
            "<span font='10' foreground='#6ab4ff' letter_spacing='3000'>"
            "◆ SYSTEM LOG"
            "</span>"
        )
        log_title.set_halign(Gtk.Align.START)
        right_panel.pack_start(log_title, False, False, 0)

        # Log display in styled frame
        log_event = Gtk.EventBox()
        log_event.set_size_request(230, 180)

        log_style = Gtk.CssProvider()
        log_style.load_from_data(b"""
            eventbox {
                background-color: rgba(5, 12, 22, 0.9);
                border: 1px solid rgba(0, 150, 255, 0.2);
                border-radius: 8px;
            }
        """)
        log_event.get_style_context().add_provider(
            log_style, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        self.log_display = Gtk.Label()
        self.log_display.set_markup(
            "<span font='9' foreground='#8ec8ff' font_family='monospace'>"
            "System boot sequence initiated...\n"
            "BonBloc Technology v2.0\n"
            "Forklift Monitoring System"
            "</span>"
        )
        self.log_display.set_line_wrap(True)
        self.log_display.set_halign(Gtk.Align.START)
        self.log_display.set_valign(Gtk.Align.START)
        self.log_display.set_margin_top(8)
        self.log_display.set_margin_start(8)
        self.log_display.set_margin_end(8)
        self.log_display.set_margin_bottom(8)

        log_event.add(self.log_display)
        right_panel.pack_start(log_event, False, False, 0)

        # Time display
        self.time_label = Gtk.Label()
        self.time_label.set_markup(
            "<span font='18' foreground='#4a90c8' letter_spacing='2000'>"
            "00:00:00"
            "</span>"
        )
        self.time_label.set_halign(Gtk.Align.CENTER)
        right_panel.pack_start(self.time_label, False, False, 8)

        dashboard.pack_end(right_panel, False, False, 0)

        main_box.pack_start(dashboard, True, True, 0)

        # ========== BOTTOM PROGRESS ==========
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bottom_box.set_spacing(8)

        progress_info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.step_label = Gtk.Label()
        self.step_label.set_markup(
            "<span font='12' foreground='#ffffff' letter_spacing='1000'>"
            "INITIALIZING..."
            "</span>"
        )
        progress_info.pack_start(self.step_label, False, False, 0)

        progress_info.pack_start(Gtk.Label(), True, True, 0)

        self.percent_label = Gtk.Label()
        self.percent_label.set_markup(
            "<span font='15' weight='bold' foreground='#00c8ff'>"
            "0%"
            "</span>"
        )
        progress_info.pack_end(self.percent_label, False, False, 0)

        bottom_box.pack_start(progress_info, False, False, 0)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(False)
        self.progress.set_size_request(-1, 6)

        # Style progress bar
        css_progress = Gtk.CssProvider()
        css_progress.load_from_data(b"""
            progressbar {
                min-height: 6px;
            }
            progressbar trough {
                background-color: rgba(20, 40, 70, 0.8);
                border: none;
                border-radius: 3px;
                min-height: 6px;
            }
            progressbar progress {
                background-image: linear-gradient(to right, #0066cc, #00c8ff, #00ff96);
                border-radius: 3px;
                min-height: 6px;
            }
        """)
        self.progress.get_style_context().add_provider(
            css_progress, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        bottom_box.pack_start(self.progress, False, False, 0)

        main_box.pack_end(bottom_box, False, False, 0)

        # ========== TIMERS ==========
        self.particle_timer = GLib.timeout_add(33, self.update_particles)
        self.time_timer = GLib.timeout_add(1000, self.update_time)

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
        self.log_messages = [
            "System boot sequence initiated...",
            "BonBloc Technology v2.0",
            "Forklift Monitoring System"
        ]

        self.load_timer = GLib.timeout_add(800, self.advance_loading)

        # Fade in
        self.opacity = 0.0
        GLib.timeout_add(30, self.fade_in)

    def fade_in(self):
        self.opacity += 0.05
        if self.opacity >= 1.0:
            self.opacity = 1.0
            return False
        # Use window opacity if composited, otherwise just proceed
        screen = self.get_screen()
        if screen.is_composited():
            self.set_opacity(self.opacity)
        return True

    def on_window_draw(self, widget, ctx):
        """Draw animated background behind all widgets"""
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()

        # Dark base
        ctx.set_source_rgb(0.02, 0.04, 0.07)
        ctx.paint()

        # Grid lines
        ctx.set_line_width(0.5)
        ctx.set_source_rgba(0, 0.4, 0.8, 0.06)
        grid_spacing = 60
        for x in range(0, width, grid_spacing):
            ctx.move_to(x, 0)
            ctx.line_to(x, height)
            ctx.stroke()
        for y in range(0, height, grid_spacing):
            ctx.move_to(0, y)
            ctx.line_to(width, y)
            ctx.stroke()

        # Diagonal lines
        ctx.set_source_rgba(0, 0.6, 1, 0.04)
        for i in range(-height, width, 120):
            ctx.move_to(i, height)
            ctx.line_to(i + height, 0)
            ctx.stroke()

        # Draw particles
        for p in self.particles:
            p.draw(ctx)

        # Corner glows
        corner_glow = cairo.RadialGradient(0, 0, 0, 0, 0, 250)
        corner_glow.add_color_stop_rgba(0, 0, 0.4, 0.8, 0.12)
        corner_glow.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(corner_glow)
        ctx.rectangle(0, 0, 250, 250)
        ctx.fill()

        corner_glow2 = cairo.RadialGradient(width, height, 0, width, height, 250)
        corner_glow2.add_color_stop_rgba(0, 0, 0.8, 1, 0.08)
        corner_glow2.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(corner_glow2)
        ctx.rectangle(width - 250, height - 250, 250, 250)
        ctx.fill()

        return False

    def update_particles(self):
        if not self.particles:
            w = self.get_allocated_width()
            h = self.get_allocated_height()
            self.particles = [Particle(w, h) for _ in range(60)]

        for p in self.particles:
            p.update()
        self.queue_draw()
        return True

    def update_time(self):
        now = datetime.now()
        self.time_label.set_markup(
            f"<span font='18' foreground='#4a90c8' letter_spacing='2000'>"
            f"{now.strftime('%H:%M:%S')}"
            f"</span>"
        )
        return True

    def add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_messages.append(f"[{timestamp}] {message}")
        if len(self.log_messages) > 10:
            self.log_messages.pop(0)
        log_text = "\n".join(self.log_messages)
        self.log_display.set_markup(
            f"<span font='9' foreground='#8ec8ff' font_family='monospace'>"
            f"{log_text}"
            f"</span>"
        )

    def advance_loading(self):
        if self.current_step < len(self.steps):
            text, callback = self.steps[self.current_step]
            self.step_label.set_markup(
                f"<span font='12' foreground='#ffffff' letter_spacing='1000'>"
                f"{text}"
                f"</span>"
            )
            self.add_log(text)
            if callback:
                callback()
            self.current_step += 1
            return True
        else:
            self.fade_out_and_exit()
            return False

    def step_database(self):
        self.progress.set_fraction(0.15)
        self.percent_label.set_markup(
            "<span font='15' weight='bold' foreground='#00c8ff'>15%</span>"
        )
        self.gauge_cpu.set_value(35)
        self.bar_temp.set_value(42)

    def step_sensors(self):
        self.progress.set_fraction(0.32)
        self.percent_label.set_markup(
            "<span font='15' weight='bold' foreground='#00c8ff'>32%</span>"
        )
        self.gauge_mem.set_value(28)
        self.bar_vib.set_value(15)
        self.card_engine.set_status("WARMING", (255, 200, 50))
        self.add_log("Sensor array online: 12/12")

    def step_calibration(self):
        self.progress.set_fraction(0.48)
        self.percent_label.set_markup(
            "<span font='15' weight='bold' foreground='#00c8ff'>48%</span>"
        )
        self.gauge_net.set_value(55)
        self.bar_load.set_value(0)
        self.card_gps.set_status("LOCKING", (255, 200, 50))
        self.viz_status.set_markup(
            "<span font='13' foreground='#00c8ff' letter_spacing='2000'>"
            "CALIBRATING SENSORS..."
            "</span>"
        )
        self.add_log("GPS signal acquired: 8 satellites")

    def step_api(self):
        self.progress.set_fraction(0.65)
        self.percent_label.set_markup(
            "<span font='15' weight='bold' foreground='#00c8ff'>65%</span>"
        )
        self.gauge_cpu.set_value(62)
        self.bar_bat.set_value(87)
        self.card_cam.set_status("ACTIVE", (0, 255, 150))
        self.viz_status.set_markup(
            "<span font='13' foreground='#00c8ff' letter_spacing='2000'>"
            "API GATEWAY ONLINE"
            "</span>"
        )
        self.add_log("REST API listening on port 8080")

    def step_dashboard(self):
        self.progress.set_fraction(0.82)
        self.percent_label.set_markup(
            "<span font='15' weight='bold' foreground='#00c8ff'>82%</span>"
        )
        self.gauge_mem.set_value(45)
        self.bar_temp.set_value(38)
        self.card_engine.set_status("ONLINE", (0, 255, 150))
        self.card_gps.set_status("LOCKED", (0, 255, 150))
        self.viz_status.set_markup(
            "<span font='13' foreground='#00c8ff' letter_spacing='2000'>"
            "DASHBOARD LOADING..."
            "</span>"
        )
        self.add_log("WebSocket connection established")

    def step_ready(self):
        self.progress.set_fraction(1.0)
        self.percent_label.set_markup(
            "<span font='15' weight='bold' foreground='#00c8ff'>100%</span>"
        )
        self.gauge_cpu.set_value(12)
        self.gauge_mem.set_value(18)
        self.gauge_net.set_value(25)
        self.bar_vib.set_value(5)
        self.card_alert.set_status("CLEAR", (0, 255, 150))
        self.viz_status.set_markup(
            "<span font='13' foreground='#00c8ff' letter_spacing='2000'>"
            "SYSTEM READY"
            "</span>"
        )
        self.sys_status.set_markup(
            "<span font='10' foreground='#00ff96' letter_spacing='2000'>"
            "● ALL SYSTEMS NOMINAL"
            "</span>"
        )
        self.add_log("All systems operational. Launching dashboard...")

    def fade_out_and_exit(self):
        self.fade_opacity = 1.0
        GLib.timeout_add(30, self.do_fade_out)

    def do_fade_out(self):
        self.fade_opacity -= 0.03
        if self.fade_opacity <= 0:
            self.fade_opacity = 0
            self.destroy()
            Gtk.main_quit()
            return False
        screen = self.get_screen()
        if screen.is_composited():
            self.set_opacity(self.fade_opacity)
        return True


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================
class SplashScreen(DashboardSplash):
    """Drop-in replacement for original SplashScreen"""
    pass


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    win = DashboardSplash()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()