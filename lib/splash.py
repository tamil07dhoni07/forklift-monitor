#!/usr/bin/env python3

import gi
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")

# ---------------- Industrial color palette ----------------
BG_COLOR = "#14161a"          # near-black steel
PANEL_COLOR = "#1d2025"       # dark gunmetal panel
ACCENT_YELLOW = "#ffcc00"     # safety / hazard yellow
ACCENT_YELLOW_DIM = "#ffcc0055"
TEXT_WHITE = "#f2f2f2"
TEXT_GREY = "#9aa0a6"

CSS = f"""
window {{
    background-color: {BG_COLOR};
}}

progressbar {{
    font-family: 'Consolas', 'DejaVu Sans Mono', monospace;
    font-weight: bold;
}}

progressbar trough {{
    background-color: #000000;
    border: 2px solid {ACCENT_YELLOW};
    border-radius: 0px;
    min-height: 28px;
}}

progressbar progress {{
    background-image: none;
    background-color: {ACCENT_YELLOW};
    border-radius: 0px;
}}

progressbar text {{
    color: {TEXT_WHITE};
}}
"""


class HazardStripe(Gtk.DrawingArea):
    """Diagonal black/yellow hazard stripe bar, industrial warning style."""

    def __init__(self, height=14):
        super().__init__()
        self.set_size_request(-1, height)
        self.connect("draw", self.on_draw)

    def on_draw(self, widget, cr):
        alloc = widget.get_allocation()
        width, height = alloc.width, alloc.height

        # black base
        cr.set_source_rgb(0, 0, 0)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        # yellow diagonal stripes
        cr.set_source_rgb(1.0, 0.8, 0.0)
        stripe_width = height * 1.6
        offset = -stripe_width
        while offset < width:
            cr.move_to(offset, height)
            cr.line_to(offset + stripe_width / 2, 0)
            cr.line_to(offset + stripe_width, 0)
            cr.line_to(offset + stripe_width / 2, height)
            cr.close_path()
            cr.fill()
            offset += stripe_width * 1.4

        return False


class SplashScreen(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)

        self.set_title("BonBloc Technology - Forklift Monitoring System")
        self.set_decorated(False)
        self.fullscreen()

        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        self.override_background_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(0.078, 0.086, 0.102, 1)
        )

        # ---------------- Root layout ----------------
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        # Top hazard stripe
        root.pack_start(HazardStripe(14), False, False, 0)

        # ---------------- Center content ----------------
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_halign(Gtk.Align.CENTER)
        outer.set_valign(Gtk.Align.CENTER)
        outer.set_spacing(18)
        outer.set_vexpand(True)
        root.pack_start(outer, True, True, 0)

        # ---------------- Logo ----------------
        if os.path.exists(LOGO_PATH):
            logo = Gtk.Image.new_from_file(LOGO_PATH)
            outer.pack_start(logo, False, False, 0)

        # ---------------- Warning icon row ----------------
        icon_row = Gtk.Label()
        icon_row.set_markup(
            f"<span font='22' foreground='{ACCENT_YELLOW}'>⚠  🏗  ⚠</span>"
        )
        outer.pack_start(icon_row, False, False, 0)

        # ---------------- Company ----------------
        title = Gtk.Label()
        title.set_markup(
            f"<span font='32' weight='bold' foreground='{TEXT_WHITE}' "
            "letter_spacing='1500'>BONBLOC TECHNOLOGY</span>"
        )
        outer.pack_start(title, False, False, 0)

        subtitle = Gtk.Label()
        subtitle.set_markup(
            f"<span font='16' weight='bold' foreground='{ACCENT_YELLOW}' "
            "letter_spacing='2000'>FORKLIFT MONITORING SYSTEM</span>"
        )
        outer.pack_start(subtitle, False, False, 0)

        divider = Gtk.Label()
        divider.set_markup(
            f"<span font='11' foreground='{TEXT_GREY}'>"
            "INDUSTRIAL FLEET TELEMETRY &amp; SAFETY PLATFORM"
            "</span>"
        )
        outer.pack_start(divider, False, False, 6)

        # ---------------- Progress ----------------
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_size_request(560, 30)
        outer.pack_start(self.progress, False, False, 14)

        # ---------------- Status ----------------
        self.status = Gtk.Label()
        self.status.set_markup(
            f"<span font='13' foreground='{TEXT_WHITE}'>"
            "&gt; SYSTEM BOOT SEQUENCE INITIATED..."
            "</span>"
        )
        outer.pack_start(self.status, False, False, 0)

        # ---------------- Footer ----------------
        footer = Gtk.Label()
        footer.set_markup(
            f"<span font='10' foreground='{TEXT_GREY}'>"
            "© BonBloc Technology  |  Version 1.0  |  All Systems Nominal"
            "</span>"
        )
        footer.set_margin_bottom(24)
        root.pack_start(footer, False, False, 0)

        # Bottom hazard stripe
        root.pack_start(HazardStripe(14), False, False, 0)

        self.steps = [
            "Initializing Sensor Network...",
            "Connecting to Forklift Fleet...",
            "Loading Telemetry Database...",
            "Calibrating Load Sensors...",
            "Starting API Server...",
            "Launching Dashboard...",
        ]

        self.current = 0

        GLib.timeout_add(700, self.update_progress)

    def update_progress(self):

        if self.current < len(self.steps):

            text = self.steps[self.current]

            self.status.set_markup(
                f"<span font='13' foreground='#ffffff'>&gt; {text}</span>"
            )

            value = (self.current + 1) / len(self.steps)

            self.progress.set_fraction(value)
            self.progress.set_text(f"{int(value*100)} %  -  SYSTEM READY IN PROGRESS")

            self.current += 1

            return True

        Gtk.main_quit()
        return False


if __name__ == "__main__":
    win = SplashScreen()
    win.show_all()
    Gtk.main()