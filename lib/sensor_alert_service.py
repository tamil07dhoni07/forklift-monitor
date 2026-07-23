#!/usr/bin/env python3
# ================================================================
# sensor_alert_service.py
# Fetch sensor alert configuration for a device
# GET /api/devices/by-device-id/{deviceId}/sensor-alert-config
# ================================================================

import logging

from config import DEVICE_ID
from constants import CLOUD_API_URL
from cloud_client import cloud_request

log = logging.getLogger("sensor_alert_service")


def get_sensor_alert_config(device_id: str = DEVICE_ID):
    """
    Fetch sensor alert configuration for a device.

    Returns:
        dict : Complete response from cloud
        None : On failure
    """

    url = (
        f"{CLOUD_API_URL}/api/devices/"
        f"by-device-id/{device_id}/sensor-alert-config"
    )

    headers = {
        "Content-Type": "application/json",
        "X-Device-Id": device_id,
    }

    try:
        resp = cloud_request(
            "GET",
            url,
            headers=headers,
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()

            log.info(
                "Fetched sensor alert configuration for device %s",
                device_id,
            )

            return data

        log.warning(
            "Failed to fetch alert configuration. "
            "HTTP %s : %s",
            resp.status_code,
            resp.text[:200],
        )

        return None

    except Exception as e:
        log.exception("Error fetching sensor alert configuration: %s", e)
        return None