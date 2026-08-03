import logging
import requests
import os
import sys

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../..")
)

sys.path.insert(0, PROJECT_ROOT)
from lib.CloudService.cloud_auth import get_bearer_token

log = logging.getLogger("cloud_client")


DEFAULT_TIMEOUT = 15


def cloud_request(method, url, **kwargs):
    """
    Common wrapper for all cloud API calls.

    Automatically:
      - Adds Bearer token
      - Retries once if token expired (401)
    """

    headers = kwargs.pop("headers", {})
    headers = headers.copy()

    token = get_bearer_token()

    if not token:
        raise Exception("Unable to obtain cloud bearer token")

    headers["Authorization"] = f"Bearer {token}"

    kwargs["headers"] = headers

    response = requests.request(method, url, **kwargs)

    if response.status_code != 401:
        return response

    log.info("Bearer token expired. Refreshing...")

    token = get_bearer_token(force_refresh=True)

    if not token:
        return response

    headers["Authorization"] = f"Bearer {token}"

    kwargs["headers"] = headers

    return requests.request(method, url, **kwargs)