from typing import Any

import requests

from config import API_BASE_URL, API_KEY
from data_processor import process_payload


def fetch_closures(
    closure_type: str = "planned",
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    modified_since: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch road closure data from the National Highways API.

    The API requires datetime parameters in the format:

        YYYY-MM-DDThh:mm:ss

    Returns a list of simplified closure records.
    """

    url = f"{API_BASE_URL}/closures"

    params: dict[str, str] = {
        "closureType": closure_type,
    }

    if start_datetime:
        params["startDateTime"] = start_datetime

    if end_datetime:
        params["endDateTime"] = end_datetime

    if modified_since:
        params["modifiedSinceDateTime"] = modified_since

    headers = {
        "Ocp-Apim-Subscription-Key": API_KEY,
        "X-Response-MediaType": "application/json",
        "X-Data-Format": "DATEXII",
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    return process_payload(payload)
