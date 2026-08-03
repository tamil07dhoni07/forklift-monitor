import logging
import requests
import os
import sys

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../..")
)

sys.path.insert(0, PROJECT_ROOT)
from lib.Utils.constants import (
    AUTH_URL,
    LOGIN_USERNAME,
    LOGIN_PASSWORD,
)

log = logging.getLogger("cloud_auth")

_token = None


def get_bearer_token(force_refresh=False):
    """
    Login and return JWT token.
    Token is cached until force_refresh=True.
    """
    global _token

    if _token and not force_refresh:
        return _token

    payload = {
        "username": LOGIN_USERNAME,
        "password": LOGIN_PASSWORD,
    }

    try:
        response = requests.post(
            AUTH_URL,
            json=payload,
            timeout=15,
        )

        response.raise_for_status()

        data = response.json()

        # Adjust according to actual API response
        _token = (
            data.get("token")
            or data.get("access_token")
            or data.get("jwt")
            or data.get("data", {}).get("token")
        )

        if not _token:
            raise Exception(f"Token not found in response: {data}")

        log.info("Cloud login successful.")

        return _token

    except Exception as e:
        log.error(f"Cloud login failed: {e}")
        return None