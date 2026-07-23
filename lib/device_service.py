#!/usr/bin/env python3
# ================================================================
# device_service.py
# Get device details from Gear IQ Cloud
# GET /api/devices/by-device-id/{deviceId}
# ================================================================

import logging

from config import DEVICE_ID
from constants import CLOUD_API_URL
from cloud_client import cloud_request

log = logging.getLogger("device_service")

DEVICE_DETAILS_URL = (
    f"{CLOUD_API_URL}/api/devices/by-device-id/{DEVICE_ID}"
)


def get_device_details(device_id: str = DEVICE_ID):
    """
    Fetch device details from the cloud.

    Returns:
        dict : Device details on success
        None : On failure
    """

    url = f"{CLOUD_API_URL}/api/devices/by-device-id/{device_id}"

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

            log.info("Device details fetched successfully.")
            log.debug(data)

            return data

        log.warning(
            "Failed to fetch device details. "
            "HTTP %s: %s",
            resp.status_code,
            resp.text[:200],
        )

        return None

    except Exception as e:
        log.exception("Error fetching device details: %s", e)
        return None