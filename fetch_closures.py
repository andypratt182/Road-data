from typing import Any
import time

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

    Automatically retries when the API returns HTTP 429
    (Too Many Requests).
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

    max_attempts = 5

    for attempt in range(1, max_attempts + 1):

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=30,
        )

        if response.status_code == 429:

            retry_after = response.headers.get("Retry-After")

            try:
                wait_seconds = int(retry_after)
            except (TypeError, ValueError):
                wait_seconds = 30 * attempt

            if attempt == max_attempts:
                response.raise_for_status()

            print(
                f"National Highways API rate limit reached. "
                f"Retrying in {wait_seconds} seconds "
                f"(attempt {attempt}/{max_attempts})..."
            )

            time.sleep(wait_seconds)
            continue

        response.raise_for_status()

        payload = response.json()

        return process_payload(payload)

    raise RuntimeError(
        "Unable to fetch National Highways road closure data."
    )
