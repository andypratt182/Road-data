from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

import requests

from config import API_BASE_URL, API_KEY
from data_processor import process_payload


class NationalHighwaysRateLimitError(Exception):
    """Raised when the National Highways API rate limit is reached."""


# ============================================================
# CONFIGURATION
# ============================================================

# The API returns a maximum of 500 records per request.
MAX_RECORDS_PER_REQUEST = 500

# Normal production collection window.
#
# We deliberately use 24 hours rather than 7 days because the
# API has a 500-record response limit and the API rate limit
# means that repeatedly splitting large windows is undesirable.
DEFAULT_WINDOW_HOURS = 24

# If a 24-hour window returns 500 records, split it into
# smaller windows.
MIN_WINDOW_MINUTES = 60

# Delay between successful API requests.
#
# This helps avoid repeatedly triggering the API rate limiter.
REQUEST_DELAY_SECONDS = 5

# Individual HTTP request timeout.
REQUEST_TIMEOUT = 60


# ============================================================
# DATE HELPERS
# ============================================================

def _format_api_datetime(value: datetime) -> str:
    """
    Format a datetime for the National Highways API.

    The API requires:

        YYYY-MM-DDThh:mm:ss

    Do NOT append Z.
    """

    return value.strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def _parse_api_datetime(value: str) -> datetime:
    """
    Parse a National Highways API datetime.

    Accepts both:

        YYYY-MM-DDThh:mm:ss

    and timestamps ending in Z.
    """

    value = str(value).strip()

    if value.endswith("Z"):
        value = value[:-1]

    if value.endswith("+00:00"):
        value = value[:-6]

    return datetime.fromisoformat(value)


# ============================================================
# API HELPERS
# ============================================================

def _build_headers() -> dict[str, str]:
    """Build the standard National Highways API headers."""

    return {
        "Ocp-Apim-Subscription-Key": API_KEY,
        "X-Response-MediaType": "application/json",
        "X-Data-Format": "DATEXII",
    }


def _request_closures(
    closure_type: str,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    modified_since: str | None = None,
) -> list[dict[str, Any]]:
    """
    Perform exactly one request to the National Highways
    closures endpoint.
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

    response = requests.get(
        url,
        params=params,
        headers=_build_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 429:

        retry_after = response.headers.get(
            "Retry-After"
        )

        raise NationalHighwaysRateLimitError(
            "National Highways API rate limit reached "
            f"for {closure_type} closures. "
            f"Retry-After: "
            f"{retry_after or 'not specified'}"
        )

    response.raise_for_status()

    payload = response.json()

    return process_payload(payload)


# ============================================================
# DEDUPLICATION
# ============================================================

def _record_key(
    record: dict[str, Any],
) -> str:
    """
    Generate a stable key for a closure.

    Prefer an API identifier where available.
    Otherwise use the main closure fields.
    """

    for field in (
        "id",
        "closureId",
        "eventId",
        "reference",
        "identifier",
    ):

        value = record.get(field)

        if value not in (
            None,
            "",
        ):

            return f"{field}:{value}"

    parts = (
        record.get("road"),
        record.get("direction"),
        record.get("start"),
        record.get("end"),
        record.get("description"),
        record.get("cause"),
        record.get("type"),
    )

    return "|".join(
        str(value or "")
        for value in parts
    )


def _deduplicate(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove duplicate records while preserving order.
    """

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []

    for record in records:

        key = _record_key(record)

        if key in seen:
            continue

        seen.add(key)
        unique.append(record)

    return unique


# ============================================================
# CONTROLLED WINDOW FETCH
# ============================================================

def _fetch_window(
    closure_type: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """
    Fetch a bounded time window.

    If the API returns fewer than 500 records, the response
    is considered complete.

    If exactly 500 records are returned, the window is split
    into two smaller windows.

    This continues until either:

    - each window returns fewer than 500 records, or
    - the minimum window size is reached.
    """

    start_string = _format_api_datetime(start)
    end_string = _format_api_datetime(end)

    print(
        f"Fetching {closure_type} closures: "
        f"{start_string} -> {end_string}"
    )

    records = _request_closures(
        closure_type=closure_type,
        start_datetime=start_string,
        end_datetime=end_string,
    )

    count = len(records)

    print(
        f"Returned {count} records."
    )

    # Safe response.
    if count < MAX_RECORDS_PER_REQUEST:

        return records

    duration = end - start

    minimum_duration = timedelta(
        minutes=MIN_WINDOW_MINUTES
    )

    # We cannot safely subdivide any further.
    if duration <= minimum_duration:

        print(
            "WARNING: Window reached the minimum "
            f"size of {MIN_WINDOW_MINUTES} minutes "
            f"while still returning {count} records."
        )

        print(
            "Keeping this response."
        )

        return records

    midpoint = start + (
        duration / 2
    )

    if midpoint <= start or midpoint >= end:

        print(
            "WARNING: Unable to split this window."
        )

        return records

    print(
        f"Window returned {count} records. "
        "Splitting into two smaller windows."
    )

    # Respect the API rate limit before making another request.
    time.sleep(
        REQUEST_DELAY_SECONDS
    )

    first_records = _fetch_window(
        closure_type=closure_type,
        start=start,
        end=midpoint,
    )

    time.sleep(
        REQUEST_DELAY_SECONDS
    )

    second_records = _fetch_window(
        closure_type=closure_type,
        start=midpoint,
        end=end,
    )

    combined = (
        first_records
        + second_records
    )

    unique = _deduplicate(
        combined
    )

    print(
        f"Combined split windows: "
        f"{len(combined)} records, "
        f"{len(unique)} unique."
    )

    return unique


# ============================================================
# MAIN PUBLIC FUNCTION
# ============================================================

def fetch_closures(
    closure_type: str = "planned",
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    modified_since: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch road closure data from the National Highways API.

    Behaviour:

    1. Explicit start/end dates:
       Fetch that requested window.

    2. No dates supplied:
       Fetch the previous/current 24-hour production window.

    3. If a window returns 500 records:
       Automatically split the window.

    4. Split records are deduplicated.

    5. modified_since requests retain the existing behaviour.

    6. HTTP 429 raises NationalHighwaysRateLimitError.
    """

    # --------------------------------------------------------
    # MODIFIED-SINCE MODE
    # --------------------------------------------------------

    if modified_since:

        return _request_closures(
            closure_type=closure_type,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            modified_since=modified_since,
        )

    # --------------------------------------------------------
    # EXPLICIT DATE WINDOW
    # --------------------------------------------------------

    if start_datetime or end_datetime:

        if not start_datetime or not end_datetime:

            return _request_closures(
                closure_type=closure_type,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
            )

        start = _parse_api_datetime(
            start_datetime
        )

        end = _parse_api_datetime(
            end_datetime
        )

        if end <= start:

            raise ValueError(
                "end_datetime must be later than "
                "start_datetime."
            )

        return _fetch_window(
            closure_type=closure_type,
            start=start,
            end=end,
        )

    # --------------------------------------------------------
    # DEFAULT PRODUCTION WINDOW
    # --------------------------------------------------------

    now = datetime.utcnow().replace(
        microsecond=0
    )

    start = now

    end = now + timedelta(
        hours=DEFAULT_WINDOW_HOURS
    )

    print(
        "No date window supplied."
    )

    print(
        f"Using {DEFAULT_WINDOW_HOURS}-hour window:"
    )

    print(
        f"{_format_api_datetime(start)} "
        f"-> "
        f"{_format_api_datetime(end)}"
    )

    return _fetch_window(
        closure_type=closure_type,
        start=start,
        end=end,
    )
