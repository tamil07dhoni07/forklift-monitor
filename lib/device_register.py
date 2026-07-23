#!/usr/bin/env python3
# ================================================================
#  device_register.py  —  Gear IQ Device Registration
#  Registers this device to the cloud on every startup.
#  POST {{baseUrl}}/api/devices
# ================================================================

import token

import requests
import logging
from config    import DEVICE_ID, LOCATION
from constants import CLOUD_API_URL, CLOUD_API_KEY
from cloud_auth import get_bearer_token
from cloud_client import cloud_request

log = logging.getLogger('device_register')

# ── Cloud config ─────────────────────────────────────────────────
REGISTER_URL = f'{CLOUD_API_URL}/api/devices'
TENANT_ID    = 'org::7'           # ← change to your tenant
ORG_ID       = 'org::7'           # ← change to your org
# ─────────────────────────────────────────────────────────────────


def register_device() -> bool:
    """
    POST device info to cloud on startup.
    Called once when api_server.py starts.
    """
    payload = {
        'deviceId':       DEVICE_ID,
        'tenantId':       TENANT_ID,
        'organizationId': ORG_ID,
        'location':       LOCATION,
        'status':         'online'
    }

    headers = {
        'Content-Type':  'application/json',
        'Authorization': f'Bearer {CLOUD_API_KEY}',
        'X-Device-Id':   DEVICE_ID,
    }

    log.info('═' * 45)
    log.info(f'📋  Device Registration  →  {REGISTER_URL}')
    log.info(f'    deviceId       : {payload["deviceId"]}')
    log.info(f'    tenantId       : {payload["tenantId"]}')
    log.info(f'    organizationId : {payload["organizationId"]}')
    log.info(f'    location       : {payload["location"]}')
    log.info(f'    status         : {payload["status"]}')
    log.info('═' * 45)

    try:
        resp = requests.post(
            REGISTER_URL,
            json=payload,
            headers=headers,
            timeout=15
        )

        if resp.status_code in (200, 201, 202):
            log.info(f'📋  Registration SUCCESS  →  HTTP {resp.status_code}')
            try:
                log.info(f'📋  Cloud response  →  {resp.json()}')
            except Exception:
                log.info(f'📋  Cloud response  →  {resp.text[:200]}')
            return True

        log.warning(f'📋  Registration FAILED  →  HTTP {resp.status_code}  {resp.text[:200]}')
        return False

    except requests.exceptions.ConnectionError:
        log.warning('📋  Registration FAILED  →  Cannot reach cloud (no internet?)')
        return False
    except requests.exceptions.Timeout:
        log.warning('📋  Registration FAILED  →  Request timed out (15s)')
        return False
    except Exception as e:
        log.error(f'📋  Registration ERROR  →  {e}')
        return False


def unregister_device() -> bool:
    """
    Mark device as offline on shutdown.
    Optional — call from webview_app.py on exit.
    """
    payload = {
        'deviceId':       DEVICE_ID,
        'tenantId':       TENANT_ID,
        'organizationId': ORG_ID,
        'location':       LOCATION,
        'status':         'offline'
    }


    headers = {
        'Content-Type':  'application/json',
        'X-Device-Id':   DEVICE_ID,
    }

    log.info(f'📋  Unregistering device  →  status=offline')
    try:
        resp = cloud_request(
            'POST',
            REGISTER_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        if resp.status_code in (200, 201, 202):
            log.info('📋  Device marked offline  →  ✅')
            return True
        log.warning(f'📋  Unregister failed  →  HTTP {resp.status_code}')
        return False
    except Exception as e:
        log.warning(f'📋  Unregister error  →  {e}')
        return False
