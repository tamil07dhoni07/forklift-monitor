#!/usr/bin/env python3
"""
BonBloc Technology - 3D Dashboard Splash Screen (GTK3 + Cairo)
Forklift Monitoring System
Seamlessly integrates into existing GTK applications
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
# PARTICLE SYSTEM (3D Depth Effect)
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
            (0, 200, 255),    # Cyan
            (0, 150, 255),    # Blue
            (100, 200, 255),  # Light Blue
            (0, 255, 200),    # Teal
        ])

    def update(self):
        self.y -= self.speed * self.z
        if self.y < -10:
            self.y = self.height + 10
            self.x = random.uniform(0, self.width)

    def draw(self, ctx):
        # Glow effect
        glow_size = self.size * 3 * self.z
        ctx.set_source_rgba(
            self.color[0]/255, self.color[1]/255, self.color[2]/255,
            self.opacity * 0.15
        )
        ctx.arc(self.x, self.y, glow_size, 0, 2 * math.pi)
        ctx.fill()

        # Core particle
        ctx.set_source_rgba(
            self.color[0]/255, self.color[1]/255, self.color[2]/255,
            self.opacity
        )
        ctx.arc(self.x, self.y, self.size * self.z, 0, 2 * math.pi)
        ctx.fill()


# ============================================================
# CUSTOM 3D GAUGE WIDGET (GTK3 + Cairo)
# ============================================================
class CircularGauge(Gtk.DrawingArea):
    def __init__(self, title="GAUGE", max_value=100):
        super().__init__()
        self.title = title
        self.max_value = max_value
        self.current_value = 0.0
        self.target_value = 0.0
        self.set_size_request(160, 160)
        self.connect("draw", self.on_draw)

        # Animation
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
        radius = 65

        # Background dark circle with 3D depth
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()

        # Outer shadow ring
        shadow = cairo.RadialGradient(cx, cy, radius, cx, cy, radius + 15)
        shadow.add_color_stop_rgba(0, 0, 0.4, 0.8, 0.4)
        shadow.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(shadow)
        ctx.arc(cx, cy, radius + 15, 0, 2 * math.pi)
        ctx.fill()

        # Inner dark background
        bg = cairo.RadialGradient(cx, cy, 0, cx, cy, radius)
        bg.add_color_stop_rgba(0, 0.04, 0.08, 0.14, 1)
        bg.add_color_stop_rgba(0.7, 0.02, 0.05, 0.09, 1)
        bg.add_color_stop_rgba(1, 0.01, 0.02, 0.05, 1)
        ctx.set_source(bg)
        ctx.arc(cx, cy, radius, 0, 2 * math.pi)
        ctx.fill()

        # Background arc
        ctx.set_line_width(6)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_source_rgba(0.12, 0.2, 0.28, 1)
        ctx.arc(cx, cy, radius - 12, math.radians(135), math.radians(405))
        ctx.stroke()

        # Value arc with gradient
        if self.current_value > 0:
            span = (self.current_value / self.max_value) * 270

            # Create gradient along the arc
            ctx.set_line_width(8)
            ctx.set_line_cap(cairo.LINE_CAP_ROUND)

            # Draw arc with color based on value
            ratio = self.current_value / self.max_value
            r = 0 + ratio * 0
            g = 0.8 - ratio * 0.3
            b = 1.0 - ratio * 0.4
            ctx.set_source_rgba(r, g, b, 1)

            ctx.arc(cx, cy, radius - 12, math.radians(135), math.radians(135 + span))
            ctx.stroke()

            # Glow on the arc
            ctx.set_line_width(12)
            ctx.set_source_rgba(r, g, b, 0.2)
            ctx.arc(cx, cy, radius - 12, math.radians(135), math.radians(135 + span))
            ctx.stroke()

        # Value text
        ctx.set_source_rgb(1, 1, 1)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(22)
        text = f"{int(self.current_value)}"
        ext = ctx.text_extents(text)
        ctx.move_to(cx - ext.width/2, cy + 8)
        ctx.show_text(text)

        # Title
        ctx.set_source_rgba(0.4, 0.7, 1, 1)
        ctx.set_font_size(9)
        ext = ctx.text_extents(self.title)
        ctx.move_to(cx - ext.width/2, cy + 28)
        ctx.show_text(self.title)

        return False


# ============================================================
# BAR INDICATOR WIDGET
# ============================================================
class BarIndicator(Gtk.DrawingArea):
    def __init__(self, label="SENSOR", color=(0, 200, 255)):
        super().__init__()
        self.label_text = label
        self.bar_color = color
        self.value = 0.0
        self.target_value = 0.0
        self.set_size_request(200, 35)
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

        # Background track
        ctx.set_source_rgba(0.08, 0.14, 0.22, 1)
        ctx.rectangle(80, 10, 110, 14)
        ctx.fill()

        # Rounded corners for track
        ctx.set_source_rgba(0.08, 0.14, 0.22, 1)
        ctx.arc(80 + 7, 10 + 7, 7, math.pi, math.pi * 1.5)
        ctx.arc(80 + 110 - 7, 10 + 7, 7, math.pi * 1.5, 0)
        ctx.arc(80 + 110 - 7, 10 + 14 - 7, 7, 0, math.pi * 0.5)
        ctx.arc(80 + 7, 10 + 14 - 7, 7, math.pi * 0.5, math.pi)
        ctx.fill()

        # Value bar
        bar_width = (self.value / 100) * 106
        if bar_width > 0:
            gradient = cairo.LinearGradient(82, 0, 82 + bar_width, 0)
            gradient.add_color_stop_rgba(0, 
                self.bar_color[0]/255 * 0.7, 
                self.bar_color[1]/255 * 0.7, 
                self.bar_color[2]/255 * 0.7, 1)
            gradient.add_color_stop_rgba(0.5,
                self.bar_color[0]/255,
                self.bar_color[1]/255,
                self.bar_color[2]/255, 1)
            gradient.add_color_stop_rgba(1,
                self.bar_color[0]/255 * 1.3,
                self.bar_color[1]/255 * 1.3,
                self.bar_color[2]/255 * 1.3, 1)
            ctx.set_source(gradient)

            # Draw rounded bar
            ctx.rectangle(82, 12, bar_width, 10)
            ctx.fill()

            # Rounded ends
            ctx.arc(82 + 5, 12 + 5, 5, math.pi, math.pi * 1.5)
            ctx.arc(82 + bar_width - 5, 12 + 5, 5, math.pi * 1.5, 0)
            ctx.arc(82 + bar_width - 5, 12 + 10 - 5, 5, 0, math.pi * 0.5)
            ctx.arc(82 + 5, 12 + 10 - 5, 5, math.pi * 0.5, math.pi)
            ctx.fill()

        # Label
        ctx.set_source_rgba(0.6, 0.7, 0.85, 1)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(10)
        ctx.move_to(5, 23)
        ctx.show_text(self.label_text)

        # Value text
        ctx.set_source_rgb(1, 1, 1)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(10)
        text = f"{int(self.value)}"
        ctx.move_to(195, 23)
        ctx.show_text(text)

        return False


# ============================================================
# STATUS CARD WIDGET
# ============================================================
class StatusCard(Gtk.DrawingArea):
    def __init__(self, title, icon_text):
        super().__init__()
        self.title = title
        self.icon_text = icon_text
        self.status = "ONLINE"
        self.status_color = (0, 255, 150)
        self.set_size_request(140, 100)
        self.connect("draw", self.on_draw)

    def set_status(self, status, color):
        self.status = status
        self.status_color = color
        self.queue_draw()

    def on_draw(self, widget, ctx):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()

        # Card gradient background
        gradient = cairo.LinearGradient(0, 0, 0, height)
        gradient.add_color_stop_rgba(0, 0.06, 0.12, 0.2, 1)
        gradient.add_color_stop_rgba(1, 0.03, 0.07, 0.13, 1)
        ctx.set_source(gradient)

        # Rounded rectangle
        r = 10
        ctx.move_to(r, 0)
        ctx.line_to(width - r, 0)
        ctx.arc(width - r, r, r, -math.pi/2, 0)
        ctx.line_to(width, height - r)
        ctx.arc(width - r, height - r, r, 0, math.pi/2)
        ctx.line_to(r, height)
        ctx.arc(r, height - r, r, math.pi/2, math.pi)
        ctx.line_to(0, r)
        ctx.arc(r, r, r, math.pi, math.pi * 1.5)
        ctx.close_path()
        ctx.fill()

        # Top border glow
        ctx.set_line_width(1)
        ctx.set_source_rgba(0, 0.6, 1, 0.4)
        ctx.move_to(r, 0)
        ctx.line_to(width - r, 0)
        ctx.stroke()

        # Icon area glow
        icon_grad = cairo.RadialGradient(35, 35, 0, 35, 35, 22)
        icon_grad.add_color_stop_rgba(0, 0, 0.6, 1, 0.3)
        icon_grad.add_color_stop_rgba(1, 0, 0.3, 0.6, 0.1)
        ctx.set_source(icon_grad)
        ctx.arc(35, 35, 22, 0, 2 * math.pi)
        ctx.fill()

        # Icon text
        ctx.set_source_rgba(0, 0.8, 1, 1)
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(20)
        ext = ctx.text_extents(self.icon_text)
        ctx.move_to(35 - ext.width/2, 35 + ext.height/2)
        ctx.show_text(self.icon_text)

        # Title
        ctx.set_source_rgba(0.7, 0.8, 0.9, 1)
        ctx.set_font_size(10)
        ext = ctx.text_extents(self.title)
        ctx.move_to(65, 28)
        ctx.show_text(self.title)

        # Status dot
        ctx.set_source_rgba(
            self.status_color[0]/255,
            self.status_color[1]/255,
            self.status_color[2]/255, 1
        )
        ctx.arc(69, 52, 4, 0, 2 * math.pi)
        ctx.fill()

        # Status text
        ctx.set_source_rgba(
            self.status_color[0]/255,
            self.status_color[1]/255,
            self.status_color[2]/255, 1
        )
        ctx.set_font_size(9)
        ctx.move_to(78, 55)
        ctx.show_text(self.status)

        return False


# ============================================================
# MAIN 3D DASHBOARD SPLASH SCREEN (GTK3)
# ============================================================
class DashboardSplash(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)

        self.set_title("BonBloc Technology - Forklift Monitoring System")
        self.set_decorated(False)
        self.fullscreen()

        # Dark background color
        self.override_background_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(0.02, 0.04, 0.07, 1)
        )

        # Particles
        self.particles = []
        self.screen_w = 1920
        self.screen_h = 1080

        # Main container with custom draw for background
        self.overlay = Gtk.Overlay()
        self.add(self.overlay)

        # Background drawing area (particles + grid)
        self.bg_area = Gtk.DrawingArea()
        self.bg_area.set_size_request(self.screen_w, self.screen_h)
        self.bg_area.connect("draw", self.on_bg_draw)
        self.overlay.add(self.bg_area)

        # Content container
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.set_margin_top(30)
        self.content.set_margin_bottom(30)
        self.content.set_margin_start(40)
        self.content.set_margin_end(40)
        self.content.set_spacing(20)
        self.overlay.add_overlay(self.content)

        # ========== TOP BAR ==========
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        top_bar.set_spacing(20)

        # Branding
        brand_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        brand_label = Gtk.Label()
        brand_label.set_markup(
            "<span font='28' weight='bold' foreground='#00c8ff' letter_spacing='4000'>"
            "BONBLOC"
            "</span>"
        )
        tagline = Gtk.Label()
        tagline.set_markup(
            "<span font='12' foreground='#4a90c8' letter_spacing='8000'>"
            "TECHNOLOGY"
            "</span>"
        )
        brand_box.pack_start(brand_label, False, False, 0)
        brand_box.pack_start(tagline, False, False, 0)
        top_bar.pack_start(brand_box, False, False, 0)

        top_bar.pack_end(Gtk.Label(), True, True, 0)  # Spacer

        # System status
        self.sys_status = Gtk.Label()
        self.sys_status.set_markup(
            "<span font='11' foreground='#00ff96' letter_spacing='2000'>"
            "● SYSTEM ACTIVE"
            "</span>"
        )
        # Add styled frame for status
        status_frame = Gtk.Frame()
        status_frame.add(self.sys_status)
        status_frame.set_shadow_type(Gtk.ShadowType.NONE)
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            frame {
                background-color: rgba(0, 255, 150, 0.1);
                border: 1px solid rgba(0, 255, 150, 0.3);
                border-radius: 15px;
                padding: 5px 15px;
            }
        """)
        status_frame.get_style_context().add_provider(
            css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        top_bar.pack_end(status_frame, False, False, 0)

        self.content.pack_start(top_bar, False, False, 0)

        # ========== MAIN DASHBOARD AREA ==========
        dashboard = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        dashboard.set_spacing(25)

        # ---- Left Panel ----
        left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_panel.set_spacing(15)

        # Gauges title
        gauges_title = Gtk.Label()
        gauges_title.set_markup(
            "<span font='11' foreground='#6ab4ff' letter_spacing='3000'>"
            "◆ REAL-TIME METRICS"
            "</span>"
        )
        gauges_title.set_halign(Gtk.Align.START)
        left_panel.pack_start(gauges_title, False, False, 0)

        # Separator line
        sep1 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        css_sep = Gtk.CssProvider()
        css_sep.load_from_data(b"""
            separator {
                background-color: rgba(0, 150, 255, 0.3);
                min-height: 1px;
            }
        """)
        sep1.get_style_context().add_provider(
            css_sep, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        left_panel.pack_start(sep1, False, False, 5)

        # Gauges row
        gauges_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        gauges_row.set_spacing(15)
        gauges_row.set_halign(Gtk.Align.CENTER)

        self.gauge_cpu = CircularGauge("CPU LOAD", 100)
        self.gauge_mem = CircularGauge("MEMORY", 100)
        self.gauge_net = CircularGauge("NETWORK", 100)

        gauges_row.pack_start(self.gauge_cpu, False, False, 0)
        gauges_row.pack_start(self.gauge_mem, False, False, 0)
        gauges_row.pack_start(self.gauge_net, False, False, 0)
        left_panel.pack_start(gauges_row, False, False, 10)

        # Bars title
        bars_title = Gtk.Label()
        bars_title.set_markup(
            "<span font='11' foreground='#6ab4ff' letter_spacing='3000'>"
            "◆ SENSOR DATA"
            "</span>"
        )
        bars_title.set_halign(Gtk.Align.START)
        left_panel.pack_start(bars_title, False, False, 0)

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep2.get_style_context().add_provider(
            css_sep, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        left_panel.pack_start(sep2, False, False, 5)

        # Bar indicators
        self.bar_temp = BarIndicator("TEMPERATURE", (255, 100, 50))
        self.bar_vib = BarIndicator("VIBRATION", (255, 200, 50))
        self.bar_load = BarIndicator("FORK LOAD", (0, 200, 255))
        self.bar_bat = BarIndicator("BATTERY", (0, 255, 150))

        left_panel.pack_start(self.bar_temp, False, False, 5)
        left_panel.pack_start(self.bar_vib, False, False, 5)
        left_panel.pack_start(self.bar_load, False, False, 5)
        left_panel.pack_start(self.bar_bat, False, False, 5)

        dashboard.pack_start(left_panel, False, False, 0)

        # ---- Center Panel ----
        center_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        center_panel.set_spacing(15)

        viz_title = Gtk.Label()
        viz_title.set_markup(
            "<span font='11' foreground='#6ab4ff' letter_spacing='3000'>"
            "◆ FORKLIFT MONITORING DASHBOARD"
            "</span>"
        )
        viz_title.set_halign(Gtk.Align.START)
        center_panel.pack_start(viz_title, False, False, 0)

        sep3 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep3.get_style_context().add_provider(
            css_sep, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        center_panel.pack_start(sep3, False, False, 5)

        # Visualization area
        viz_frame = Gtk.Frame()
        viz_frame.set_size_request(400, 280)
        css_viz = Gtk.CssProvider()
        css_viz.load_from_data(b"""
            frame {
                background-color: rgba(8, 18, 35, 0.8);
                border: 1px solid rgba(0, 150, 255, 0.2);
                border-radius: 10px;
            }
        """)
        viz_frame.get_style_context().add_provider(
            css_viz, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        viz_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        viz_box.set_spacing(10)
        viz_box.set_halign(Gtk.Align.CENTER)
        viz_box.set_valign(Gtk.Align.CENTER)

        self.forklift_icon = Gtk.Label()
        self.forklift_icon.set_markup(
            "<span font='60' foreground='#00c8ff'>🚜</span>"
        )
        viz_box.pack_start(self.forklift_icon, False, False, 0)

        self.viz_status = Gtk.Label()
        self.viz_status.set_markup(
            "<span font='14' foreground='#00c8ff' letter_spacing='2000'>"
            "INITIALIZING FORKLIFT SYSTEM..."
            "</span>"
        )
        viz_box.pack_start(self.viz_status, False, False, 0)

        viz_frame.add(viz_box)
        center_panel.pack_start(viz_frame, False, False, 0)

        # Status cards
        cards_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        cards_row.set_spacing(15)
        cards_row.set_halign(Gtk.Align.CENTER)

        self.card_engine = StatusCard("ENGINE", "⚙")
        self.card_gps = StatusCard("GPS", "📡")
        self.card_cam = StatusCard("CAMERA", "📷")
        self.card_alert = StatusCard("ALERTS", "⚠")

        cards_row.pack_start(self.card_engine, False, False, 0)
        cards_row.pack_start(self.card_gps, False, False, 0)
        cards_row.pack_start(self.card_cam, False, False, 0)
        cards_row.pack_start(self.card_alert, False, False, 0)
        center_panel.pack_start(cards_row, False, False, 10)

        dashboard.pack_start(center_panel, True, True, 0)

        # ---- Right Panel ----
        right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_panel.set_spacing(15)

        log_title = Gtk.Label()
        log_title.set_markup(
            "<span font='11' foreground='#6ab4ff' letter_spacing='3000'>"
            "◆ SYSTEM LOG"
            "</span>"
        )
        log_title.set_halign(Gtk.Align.START)
        right_panel.pack_start(log_title, False, False, 0)

        sep4 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep4.get_style_context().add_provider(
            css_sep, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        right_panel.pack_start(sep4, False, False, 5)

        # Log display
        self.log_display = Gtk.Label()
        self.log_display.set_markup(
            "<span font='10' foreground='#8ec8ff' font_family='monospace'>"
            "System boot sequence initiated...\n"
            "BonBloc Technology v2.0\n"
            "Forklift Monitoring System"
            "</span>"
        )
        self.log_display.set_line_wrap(True)
        self.log_display.set_halign(Gtk.Align.START)
        self.log_display.set_valign(Gtk.Align.START)

        log_frame = Gtk.Frame()
        log_frame.add(self.log_display)
        log_frame.set_size_request(250, 200)
        css_log = Gtk.CssProvider()
        css_log.load_from_data(b"""
            frame {
                background-color: rgba(5, 12, 22, 0.9);
                border: 1px solid rgba(0, 150, 255, 0.2);
                border-radius: 8px;
                padding: 10px;
            }
            label {
                color: #8ec8ff;
                font-family: monospace;
            }
        """)
        log_frame.get_style_context().add_provider(
            css_log, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        right_panel.pack_start(log_frame, False, False, 0)

        # Time display
        self.time_label = Gtk.Label()
        self.time_label.set_markup(
            "<span font='20' foreground='#4a90c8' letter_spacing='2000'>"
            "00:00:00"
            "</span>"
        )
        self.time_label.set_halign(Gtk.Align.CENTER)
        right_panel.pack_start(self.time_label, False, False, 10)

        dashboard.pack_end(right_panel, False, False, 0)

        self.content.pack_start(dashboard, True, True, 0)

        # ========== BOTTOM PROGRESS ==========
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        bottom_box.set_spacing(10)

        progress_info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)

        self.step_label = Gtk.Label()
        self.step_label.set_markup(
            "<span font='13' foreground='#ffffff' letter_spacing='1000'>"
            "INITIALIZING..."
            "</span>"
        )
        progress_info.pack_start(self.step_label, False, False, 0)

        progress_info.pack_start(Gtk.Label(), True, True, 0)  # Spacer

        self.percent_label = Gtk.Label()
        self.percent_label.set_markup(
            "<span font='16' weight='bold' foreground='#00c8ff'>"
            "0%"
            "</span>"
        )
        progress_info.pack_end(self.percent_label, False, False, 0)

        bottom_box.pack_start(progress_info, False, False, 0)

        # Custom progress bar
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(False)
        self.progress.set_size_request(-1, 8)
        css_progress = Gtk.CssProvider()
        css_progress.load_from_data(b"""
            progressbar {
                min-height: 8px;
                border-radius: 4px;
            }
            progressbar trough {
                background-color: rgba(20, 40, 70, 0.8);
                border: none;
                border-radius: 4px;
                min-height: 8px;
            }
            progressbar progress {
                background-image: linear-gradient(to right, #0066cc, #00c8ff, #00ff96);
                border-radius: 4px;
                min-height: 8px;
            }
        """)
        self.progress.get_style_context().add_provider(
            css_progress, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        bottom_box.pack_start(self.progress, False, False, 0)

        self.content.pack_end(bottom_box, False, False, 0)

        # ========== TIMERS ==========
        # Particle animation
        self.particle_timer = GLib.timeout_add(33, self.update_particles)

        # Time update
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

        # Start loading
        self.load_timer = GLib.timeout_add(800, self.advance_loading)

        # Fade in effect
        self.opacity = 0.0
        self.fade_in()

    def fade_in(self):
        self.opacity += 0.05
        if self.opacity >= 1.0:
            self.opacity = 1.0
            self.set_opacity(self.opacity)
            return False
        self.set_opacity(self.opacity)
        GLib.timeout_add(30, self.fade_in)
        return False

    def set_opacity(self, opacity):
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.override_background_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(0.02, 0.04, 0.07, opacity)
        )

    def on_bg_draw(self, widget, ctx):
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()

        # Dark background
        ctx.set_source_rgb(0.02, 0.04, 0.07)
        ctx.paint()

        # Grid lines
        ctx.set_line_width(0.5)
        ctx.set_source_rgba(0, 0.4, 0.8, 0.08)
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
        ctx.set_source_rgba(0, 0.6, 1, 0.06)
        for i in range(-height, width, 120):
            ctx.move_to(i, height)
            ctx.line_to(i + height, 0)
            ctx.stroke()

        # Draw particles
        for p in self.particles:
            p.draw(ctx)

        # Corner glows
        corner_glow = cairo.RadialGradient(0, 0, 0, 0, 0, 300)
        corner_glow.add_color_stop_rgba(0, 0, 0.4, 0.8, 0.15)
        corner_glow.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(corner_glow)
        ctx.rectangle(0, 0, 300, 300)
        ctx.fill()

        corner_glow2 = cairo.RadialGradient(width, height, 0, width, height, 300)
        corner_glow2.add_color_stop_rgba(0, 0, 0.8, 1, 0.1)
        corner_glow2.add_color_stop_rgba(1, 0, 0, 0, 0)
        ctx.set_source(corner_glow2)
        ctx.rectangle(width - 300, height - 300, 300, 300)
        ctx.fill()

        return False

    def update_particles(self):
        # Initialize particles on first run
        if not self.particles:
            w = self.bg_area.get_allocated_width()
            h = self.bg_area.get_allocated_height()
            self.particles = [Particle(w, h) for _ in range(80)]

        for p in self.particles:
            p.update()
        self.bg_area.queue_draw()
        return True

    def update_time(self):
        now = datetime.now()
        self.time_label.set_markup(
            f"<span font='20' foreground='#4a90c8' letter_spacing='2000'>"
            f"{now.strftime('%H:%M:%S')}"
            f"</span>"
        )
        return True

    def add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_messages.append(f"[{timestamp}] {message}")
        if len(self.log_messages) > 12:
            self.log_messages.pop(0)
        log_text = "\n".join(self.log_messages)
        self.log_display.set_markup(
            f"<span font='10' foreground='#8ec8ff' font_family='monospace'>"
            f"{log_text}"
            f"</span>"
        )

    def advance_loading(self):
        if self.current_step < len(self.steps):
            text, callback = self.steps[self.current_step]
            self.step_label.set_markup(
                f"<span font='13' foreground='#ffffff' letter_spacing='1000'>"
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
            "<span font='16' weight='bold' foreground='#00c8ff'>15%</span>"
        )
        self.gauge_cpu.set_value(35)
        self.bar_temp.set_value(42)

    def step_sensors(self):
        self.progress.set_fraction(0.32)
        self.percent_label.set_markup(
            "<span font='16' weight='bold' foreground='#00c8ff'>32%</span>"
        )
        self.gauge_mem.set_value(28)
        self.bar_vib.set_value(15)
        self.card_engine.set_status("WARMING", (255, 200, 50))
        self.add_log("Sensor array online: 12/12")

    def step_calibration(self):
        self.progress.set_fraction(0.48)
        self.percent_label.set_markup(
            "<span font='16' weight='bold' foreground='#00c8ff'>48%</span>"
        )
        self.gauge_net.set_value(55)
        self.bar_load.set_value(0)
        self.card_gps.set_status("LOCKING", (255, 200, 50))
        self.viz_status.set_markup(
            "<span font='14' foreground='#00c8ff' letter_spacing='2000'>"
            "CALIBRATING SENSORS..."
            "</span>"
        )
        self.add_log("GPS signal acquired: 8 satellites")

    def step_api(self):
        self.progress.set_fraction(0.65)
        self.percent_label.set_markup(
            "<span font='16' weight='bold' foreground='#00c8ff'>65%</span>"
        )
        self.gauge_cpu.set_value(62)
        self.bar_bat.set_value(87)
        self.card_cam.set_status("ACTIVE", (0, 255, 150))
        self.viz_status.set_markup(
            "<span font='14' foreground='#00c8ff' letter_spacing='2000'>"
            "API GATEWAY ONLINE"
            "</span>"
        )
        self.add_log("REST API listening on port 8080")

    def step_dashboard(self):
        self.progress.set_fraction(0.82)
        self.percent_label.set_markup(
            "<span font='16' weight='bold' foreground='#00c8ff'>82%</span>"
        )
        self.gauge_mem.set_value(45)
        self.bar_temp.set_value(38)
        self.card_engine.set_status("ONLINE", (0, 255, 150))
        self.card_gps.set_status("LOCKED", (0, 255, 150))
        self.viz_status.set_markup(
            "<span font='14' foreground='#00c8ff' letter_spacing='2000'>"
            "DASHBOARD LOADING..."
            "</span>"
        )
        self.add_log("WebSocket connection established")

    def step_ready(self):
        self.progress.set_fraction(1.0)
        self.percent_label.set_markup(
            "<span font='16' weight='bold' foreground='#00c8ff'>100%</span>"
        )
        self.gauge_cpu.set_value(12)
        self.gauge_mem.set_value(18)
        self.gauge_net.set_value(25)
        self.bar_vib.set_value(5)
        self.card_alert.set_status("CLEAR", (0, 255, 150))
        self.viz_status.set_markup(
            "<span font='14' foreground='#00c8ff' letter_spacing='2000'>"
            "SYSTEM READY"
            "</span>"
        )
        self.sys_status.set_markup(
            "<span font='11' foreground='#00ff96' letter_spacing='2000'>"
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
        self.set_opacity(self.fade_opacity)
        return True

    def on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            Gtk.main_quit()

    def on_click(self, widget, event):
        if self.current_step < len(self.steps):
            self.current_step = len(self.steps) - 1
            self.advance_loading()


# ============================================================
# INTEGRATION HELPER - Drop-in replacement for your splash
# ============================================================
def show_dashboard_splash():
    """
    Show the 3D dashboard splash screen.
    Blocks until splash completes or is dismissed.
    Returns when splash finishes.
    """
    win = DashboardSplash()
    win.show_all()
    Gtk.main()


# ============================================================
# BACKWARD COMPATIBILITY - Same interface as original
# ============================================================
class SplashScreen(DashboardSplash):
    """
    Drop-in replacement for your original SplashScreen class.
    Same interface, upgraded 3D visuals.
    """
    pass


# ============================================================
# ENTRY POINT
# ============================================================
if __name__ == "__main__":
    win = DashboardSplash()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()