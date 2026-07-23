#!/usr/bin/env python3
# ================================================================
#  mail_notifier.py  —  Gear IQ Crash / Error Email Alerts
#
#  Usage (anywhere in your code):
#
#    from mail_notifier import send_error, watch
#
#    # Send a manual alert
#    send_error("API server failed", exception_obj)
#
#    # Auto-catch crashes in a function
#    @watch("Cloud Sync")
#    def my_function():
#        ...
#
#    # Protect the whole main() loop
#    watch("Webview App")(main)()
# ================================================================

import os
import sys
import smtplib
import traceback
import logging
import functools
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import DEVICE_ID, LOCATION

# ── ① EMAIL CONFIG — fill these ─────────────────────────────────
SMTP_HOST     = 'smtp.office365.com'
SMTP_PORT     = 587
SMTP_USER     = 'thamilarasan.santhakumar@bonbloc.com'
SMTP_PASSWORD = 'Tamil@12341234'   # ← use your NEW password after changing it

DEV_TEAM_MAIL = [
    'thamilarasan.santhakumar@bonbloc.com',  # ← add more team emails here
]


# ────────────────────────────────────────────────────────────────

IST = timezone(timedelta(hours=5, minutes=30))

log = logging.getLogger('mail_notifier')


# ════════════════════════════════════════════════════════════════
#  CORE — build and send the email
# ════════════════════════════════════════════════════════════════

def send_error(service: str, error: Exception | str, tb: str = None):
    """
    Send a crash/error email to the dev team.

    Args:
        service : name of the crashed service e.g. "API Server"
        error   : the Exception object or a plain string message
        tb      : optional traceback string (auto-captured if not given)
    """
    try:
        now   = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S IST')
        err_str = str(error)
        tb_str  = tb or traceback.format_exc()

        subject = f'[Gear IQ ⚠️] {service} crashed — {DEVICE_ID}'

        # ── HTML body ──────────────────────────────────────────
        body_html = f"""
<html><body style="font-family:Arial,sans-serif;color:#1e293b;background:#f8fafc;padding:24px">
  <div style="max-width:640px;margin:auto;background:#fff;border-radius:12px;
              box-shadow:0 2px 8px rgba(0,0,0,.08);overflow:hidden">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#ef4444,#dc2626);padding:24px 28px">
      <h2 style="color:#fff;margin:0;font-size:20px">⚠️ Application Crash Alert</h2>
      <p style="color:rgba(255,255,255,.85);margin:6px 0 0;font-size:13px">Gear IQ Forklift Monitor</p>
    </div>

    <!-- Details -->
    <div style="padding:24px 28px">
      <table style="width:100%;border-collapse:collapse;font-size:14px">
        <tr><td style="padding:8px 0;color:#64748b;width:140px">Device ID</td>
            <td style="padding:8px 0;font-weight:600">{DEVICE_ID}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b">Location</td>
            <td style="padding:8px 0">{LOCATION}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b">Service</td>
            <td style="padding:8px 0;font-weight:600;color:#ef4444">{service}</td></tr>
        <tr><td style="padding:8px 0;color:#64748b">Time (IST)</td>
            <td style="padding:8px 0">{now}</td></tr>
      </table>

      <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0">

      <p style="margin:0 0 8px;color:#64748b;font-size:13px;font-weight:600">ERROR MESSAGE</p>
      <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;
                  padding:12px 16px;font-size:14px;color:#b91c1c;word-break:break-all">
        {err_str}
      </div>

      <p style="margin:16px 0 8px;color:#64748b;font-size:13px;font-weight:600">TRACEBACK</p>
      <pre style="background:#0f172a;color:#94a3b8;padding:16px;border-radius:8px;
                  font-size:12px;overflow-x:auto;white-space:pre-wrap;word-break:break-all;margin:0">{tb_str or "No traceback available"}</pre>
    </div>

    <!-- Footer -->
    <div style="background:#f1f5f9;padding:14px 28px;font-size:12px;color:#94a3b8;text-align:center">
      Gear IQ Forklift Monitor — Auto-alert from {DEVICE_ID}
    </div>
  </div>
</body></html>
"""

        # ── Plain text fallback ────────────────────────────────
        body_text = (
            f"GEAR IQ CRASH ALERT\n"
            f"{'='*50}\n"
            f"Device   : {DEVICE_ID}\n"
            f"Location : {LOCATION}\n"
            f"Service  : {service}\n"
            f"Time     : {now}\n"
            f"{'='*50}\n"
            f"ERROR:\n{err_str}\n\n"
            f"TRACEBACK:\n{tb_str or 'No traceback available'}\n"
        )

        # ── Build MIME message ─────────────────────────────────
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'Gear IQ Monitor <{SMTP_USER}>'
        msg['To']      = ', '.join(DEV_TEAM_MAIL)

        msg.attach(MIMEText(body_text, 'plain'))
        msg.attach(MIMEText(body_html, 'html'))

        # ── Send ───────────────────────────────────────────────
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, DEV_TEAM_MAIL, msg.as_string())

        log.info(f'📧 Crash alert sent → {DEV_TEAM_MAIL}')

    except smtplib.SMTPAuthenticationError:
        log.error('Email auth failed — check SMTP_USER and SMTP_PASSWORD (use Gmail App Password)')
    except smtplib.SMTPException as e:
        log.error(f'SMTP error: {e}')
    except Exception as e:
        log.error(f'Failed to send crash email: {e}')


# ════════════════════════════════════════════════════════════════
#  DECORATOR — wrap any function to catch + email crashes
# ════════════════════════════════════════════════════════════════

def watch(service_name: str):
    """
    Decorator / wrapper that catches any unhandled exception,
    emails the dev team, then re-raises.

    Usage:
        @watch("API Server")
        def main():
            ...

        # Or inline:
        watch("Cloud Sync")(run_loop)()
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                tb = traceback.format_exc()
                log.error(f'[{service_name}] CRASH: {e}')
                send_error(service_name, e, tb)
                raise   # re-raise so the process/thread exits normally
        return wrapper
    return decorator


# ════════════════════════════════════════════════════════════════
#  GLOBAL EXCEPTION HOOK — catches anything not caught elsewhere
# ════════════════════════════════════════════════════════════════

def install_global_hook(service_name: str = 'Unknown Service'):
    """
    Call once at startup to email the team on ANY unhandled exception.

    Usage:
        install_global_hook("Webview App")
    """
    def handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        log.critical(f'Unhandled exception in {service_name}:\n{tb_str}')
        send_error(f'{service_name} — Unhandled Exception', exc_value, tb_str)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = handle_exception
    log.info(f'Global crash hook installed for: {service_name}')


# ════════════════════════════════════════════════════════════════
#  QUICK TEST  —  python3 mail_notifier.py
# ════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
    print(f'Sending test email to: {DEV_TEAM_MAIL}')
    try:
        raise ValueError('This is a test crash from Gear IQ device '+DEVICE_ID+' at '+LOCATION)
    except Exception as e:
        send_error('Test Service', e)
    print('Done — check your inbox.')
