#!/usr/bin/env python3

from ultralytics import settings

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')

from gi.repository import Gtk, WebKit2, GLib
import subprocess
import os
import time
import signal
import requests

BASE_DIR = "/home/linaro/forklift-monitor"
HOME_URL = "http://127.0.0.1:5000/"


def start_services():
    print("Starting API Server...")

    # Start Camera Stream
    start_camera()

    time.sleep(2)

    subprocess.Popen([
        "python3",
        os.path.join(BASE_DIR, "lib", "api_server.py")
    ])

    time.sleep(1)

    print("Starting Sensor Logger...")
    subprocess.Popen([
        "python3",
        os.path.join(BASE_DIR, "lib", "dual_sensor_logger.py")
    ])

    time.sleep(1)

    print("Starting Cloud Sync...")
    subprocess.Popen([
        "python3",
        os.path.join(BASE_DIR, "lib", "cloud_sync.py")
    ])

    print("Starting version Update...")
    subprocess.Popen([
        "python3",
        os.path.join(BASE_DIR, "lib", "update_checker.py")
    ])

def start_camera():
    result = subprocess.run(
        ["pgrep", "-f", "mjpg_streamer"],
        stdout=subprocess.DEVNULL
    )

    if result.returncode != 0:
        subprocess.Popen([
            "mjpg_streamer",
            "-i", "input_uvc.so -d /dev/video10 -r 1280x720 -f 30",
            "-o", "output_http.so -p 8080 -w /usr/share/mjpg-streamer/www"
        ])


class ForkliftApp(Gtk.Window):

    def __init__(self, splash):

        Gtk.Window.__init__(self)

        self.splash = splash

        self.set_title("Forklift Monitoring System")
        self.maximize()

        self.webview = WebKit2.WebView()
        settings = self.webview.get_settings()

        settings.set_enable_javascript(True)
        settings.set_enable_media_stream(True)
        settings.set_enable_webgl(True)
        settings.set_enable_developer_extras(True)
        settings.set_allow_file_access_from_file_urls(True)
        settings.set_allow_universal_access_from_file_urls(True)

        self.add(self.webview)

        self.webview.connect("load-changed", self.page_loaded)

        self.show_all()
        self.present()

        print("Loading Dashboard...")
        #self.webview.load_uri(HOME_URL)
        self.webview.load_uri("http://127.0.0.1:8080/?action=stream")

    def page_loaded(self, webview, event):

        if event == WebKit2.LoadEvent.FINISHED:

            print("Dashboard Loaded")

            try:
                self.splash.terminate()
            except:
                pass


def create_dashboard(splash):

    print("Creating GTK Window...")

    app = ForkliftApp(splash)

    return False


if __name__ == "__main__":

    print("Starting Splash...")

    splash = subprocess.Popen([
        "python3",
        os.path.join(BASE_DIR, "lib", "splash.py")
    ])

    start_services()

    print("Waiting for Flask...")

    while True:

        try:

            r = requests.get(
                "http://127.0.0.1:5000/",
                timeout=1
            )

            if r.status_code == 200:
                print("Flask Ready")
                break

        except Exception:
            pass

        time.sleep(0.5)

    print("Starting GTK...")

    GLib.idle_add(create_dashboard, splash)

    Gtk.main()