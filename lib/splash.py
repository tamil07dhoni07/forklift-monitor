#!/usr/bin/env python3

import gi
import os

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")


class SplashScreen(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)

        self.set_title("BonBloc Technology")
        self.set_decorated(False)
        self.fullscreen()
        self.override_background_color(
            Gtk.StateFlags.NORMAL,
            Gdk.RGBA(0.05, 0.08, 0.12, 1)
        )

        # ---------------- Main Layout ----------------
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_halign(Gtk.Align.CENTER)
        outer.set_valign(Gtk.Align.CENTER)
        outer.set_spacing(20)

        # ---------------- Logo ----------------
        if os.path.exists(LOGO_PATH):
            logo = Gtk.Image.new_from_file(LOGO_PATH)
            outer.pack_start(logo, False, False, 0)

        # ---------------- Company ----------------
        title = Gtk.Label()
        title.set_markup(
            "<span font='30' weight='bold' foreground='white'>"
            "BonBloc Technology"
            "</span>"
        )
        outer.pack_start(title, False, False, 0)

        subtitle = Gtk.Label()
        subtitle.set_markup(
            "<span font='16' foreground='#8ec8ff'>"
            "Forklift Monitoring System"
            "</span>"
        )
        outer.pack_start(subtitle, False, False, 0)

        # ---------------- Progress ----------------
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_size_request(500, 28)
        outer.pack_start(self.progress, False, False, 10)

        # ---------------- Status ----------------
        self.status = Gtk.Label()
        self.status.set_markup(
            "<span font='14' foreground='#ffffff'>Initializing...</span>"
        )
        outer.pack_start(self.status, False, False, 0)

        self.add(outer)

        self.steps = [
            "Loading Database...",
            "Loading Sensors...",
            "Starting API Server...",
            "Opening Dashboard..."
        ]

        self.current = 0

        GLib.timeout_add(1000, self.update_progress)

    def update_progress(self):

        if self.current < len(self.steps):

            text = self.steps[self.current]

            self.status.set_markup(
                f"<span font='14' foreground='#ffffff'>{text}</span>"
            )

            value = (self.current + 1) / len(self.steps)

            self.progress.set_fraction(value)
            self.progress.set_text(f"{int(value*100)} %")

            self.current += 1

            return True

        Gtk.main_quit()
        return False


if __name__ == "__main__":
    win = SplashScreen()
    win.show_all()
    Gtk.main()
