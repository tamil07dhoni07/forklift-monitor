#!/usr/bin/env python3
# ================================================================
#  update_checker.py  —  Gear IQ Software Update Service
#
#  Logic:
#    1. Every CHECK_INTERVAL seconds, call GET /api/v1/version
#    2. Cloud returns: { "version": <int> }
#    3. Compare with local VERSION from constants.py
#    4. If cloud_version != local VERSION  →  run install.sh
#    5. If versions match                  →  do nothing
#
#  Run:   python3 update_checker.py
#  Logs:  update_checker.log
# ================================================================

import os
import sys
import time
import logging
import subprocess
import requests

# Import local version from constants.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import VERSION, CLOUD_API_URL, CLOUD_API_KEY, DEVICE_ID

# ── Config ────────────────────────────────────────────────────
CHECK_INTERVAL_SEC = 300          # check every 5 minutes
INSTALL_SCRIPT     = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'install.sh')
VERSION_ENDPOINT   = f'{CLOUD_API_URL}/version'
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('update_checker.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger('update_checker')


# ════════════════════════════════════════════════════════════════
#  GET VERSION FROM CLOUD
#  Cloud API should respond with:  { "version": 2 }
# ════════════════════════════════════════════════════════════════
def get_cloud_version() -> int | None:
    """
    Call GET /api/v1/version and return the cloud version integer.
    Returns None if the request fails.
    """
    try:
        resp = requests.get(
            VERSION_ENDPOINT,
            headers={
                'Authorization': f'Bearer {CLOUD_API_KEY}',
                'X-Device-Id':   DEVICE_ID,
            },
            timeout=10
        )
        if resp.status_code == 200:
            cloud_version = resp.json().get('version')
            if cloud_version is not None:
                return int(cloud_version)
            log.warning('Cloud response missing "version" field')
        else:
            log.warning(f'Version check returned HTTP {resp.status_code}')
    except requests.exceptions.ConnectionError:
        log.warning('Cannot reach cloud — skipping version check')
    except requests.exceptions.Timeout:
        log.warning('Version check timed out')
    except Exception as e:
        log.error(f'Version check error: {e}')
    return None


# ════════════════════════════════════════════════════════════════
#  RUN INSTALL.SH
# ════════════════════════════════════════════════════════════════
def run_update(cloud_version: int):
    """
    Execute install.sh to update the software.
    install.sh lives in the same folder as this file.
    """
    log.info(f'🔄 Update triggered: local={VERSION} → cloud={cloud_version}')
    log.info(f'   Running: {INSTALL_SCRIPT}')

    if not os.path.isfile(INSTALL_SCRIPT):
        log.error(f'install.sh not found at: {INSTALL_SCRIPT}')
        return

    if not os.access(INSTALL_SCRIPT, os.X_OK):
        log.info('Making install.sh executable...')
        os.chmod(INSTALL_SCRIPT, 0o755)

    try:
        # Run install.sh with sudo; output goes to log in real time
        result = subprocess.run(
            ['sudo', 'bash', INSTALL_SCRIPT],
            cwd=os.path.dirname(INSTALL_SCRIPT),
            capture_output=False,    # let output print to terminal / journald
            timeout=1800             # 30 min max for the install
        )
        if result.returncode == 0:
            log.info('✅ install.sh completed successfully')
        else:
            log.error(f'install.sh exited with code {result.returncode}')
    except subprocess.TimeoutExpired:
        log.error('install.sh timed out after 30 minutes')
    except Exception as e:
        log.error(f'Failed to run install.sh: {e}')


# ════════════════════════════════════════════════════════════════
#  CHECK LOOP
# ════════════════════════════════════════════════════════════════
def check_once():
    """Single version check cycle."""
    log.info(f'Checking version  (local={VERSION})...')

    cloud_version = get_cloud_version()

    if cloud_version is None:
        log.info('Version check skipped — cloud unreachable')
        return

    log.info(f'  local version = {VERSION}')
    log.info(f'  cloud version = {cloud_version}')

    if cloud_version != VERSION:
        log.info(f'⚠️  Version mismatch → starting update')
        run_update(cloud_version)
    else:
        log.info('✅ Version up to date — no update needed')


def main():
    log.info('🚀 Update Checker started')
    log.info(f'   Local version : {VERSION}')
    log.info(f'   Version URL   : {VERSION_ENDPOINT}')
    log.info(f'   Check interval: {CHECK_INTERVAL_SEC}s')
    log.info(f'   install.sh    : {INSTALL_SCRIPT}')

    while True:
        try:
            check_once()
        except Exception as e:
            log.exception(f'Unexpected error: {e}')
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == '__main__':
    main()


# ================================================================
#  CLOUD API — what your cloud server must return
# ================================================================
#
#  GET /api/v1/version
#  Headers:
#    Authorization: Bearer <API_KEY>
#    X-Device-Id:   FL-2024
#
#  Response 200:
#  {
#    "version": 1       ← same as device, no update
#  }
#  or
#  {
#    "version": 2       ← different → triggers install.sh
#  }
#
# ================================================================
#  FILE STRUCTURE
# ================================================================
#
#  /home/linaro/forklift-monitor/
#  ├── constants.py        ← VERSION = 1  (this file)
#  ├── update_checker.py   ← this service
#  ├── install.sh          ← executed on version mismatch
#  ├── api_server.py
#  └── cloud_sync.py
#
# ================================================================
#  SYSTEMD UNIT  /etc/systemd/system/geariq-updater.service
# ================================================================
#
#  [Unit]
#  Description=Gear IQ Software Update Checker
#  After=network.target
#
#  [Service]
#  ExecStart=/usr/bin/python3 /home/linaro/forklift-monitor/update_checker.py
#  WorkingDirectory=/home/linaro/forklift-monitor
#  Restart=always
#  RestartSec=10
#  User=linaro
#
#  [Install]
#  WantedBy=multi-user.target
#
#  sudo systemctl daemon-reload
#  sudo systemctl enable geariq-updater
#  sudo systemctl start  geariq-updater
#  sudo systemctl status geariq-updater
