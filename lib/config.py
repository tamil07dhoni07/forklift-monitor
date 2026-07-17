# ================================================================
#  config.py  —  Gear IQ Device Configuration
#  Device ID is auto-generated on first install and saved.
#  Never changes after that — unique per device.
# ================================================================

import json
import os
import uuid
import socket

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')


def _generate_device_id() -> str:
    """
    Generate a unique device ID using MAC address.
    Format: GIQ-XXXXXXXXXXXX  (always same for same hardware)
    """
    mac = uuid.getnode()
    mac_str = ''.join(f'{(mac >> i) & 0xff:02X}' for i in range(0, 48, 8)[::-1])
    return f'GIQ-{mac_str}'


def _get_hostname() -> str:
    try:
        return socket.gethostname()
    except:
        return 'unknown-host'


def _create_default_config() -> dict:
    device_id = _generate_device_id()
    config = {
        'device_id': device_id,
        'location':  'Not Set',
        'hostname':  _get_hostname(),
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print(f'[Config] First run  →  Created config.json')
    print(f'[Config] Device ID  →  {device_id}  (auto-generated from MAC)')
    return config


def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        print(f'[Config] config.json not found  →  generating new device ID ...')
        return _create_default_config()
    try:
        with open(CONFIG_FILE, 'r') as f:
            cfg = json.load(f)
        print(f'[Config] Loaded  →  device_id={cfg.get("device_id")}  '
              f'location={cfg.get("location")}  '
              f'hostname={cfg.get("hostname")}')
        return cfg
    except json.JSONDecodeError as e:
        print(f'[Config] ERROR  →  Invalid config.json: {e}  →  regenerating ...')
        return _create_default_config()


_cfg = load_config()

DEVICE_ID = _cfg.get('device_id', _generate_device_id())
LOCATION  = _cfg.get('location',  'Not Set')
HOSTNAME  = _cfg.get('hostname',  _get_hostname())