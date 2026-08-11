from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests

from config import API_BASE_URL, API_KEY
from data_processor import process_payload


class NationalHighwaysRateLimitError(Exception):
    """Raised when the National Highways API rate limit is reached."""


# National Highways appears to cap closure responses at 500 records.
# Treat 500 as potentially truncated and split the requested window.
MAX_RECORDS_PER_REQUEST = 500

# Default collection window when the caller does not provide dates.
DEFAULT_WINDOW_DAYS = 7

# Do not recursively split below this duration.
MIN_WINDOW_MINUTES = 15

# API timeout for an individual request.
REQUEST_TIMEOUT = 60


def _format_api_datetime(value: datetime) -> str:
    """
    Format a datetime exactly as required by the National Highways API.

    Required format:
        YYYY-MM-DDThh:mm:ss

    The API rejects the trailing 'Z'.
    """

    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _parse_api_datetime(value: str) -> datetime:
    """
    Parse an API date string into a naive datetime.

    National Highways date-window parameters use UTC values without
    a timezone suffix, so the returned datetime is intentionally naive.
    """

    value = str(value).strip()

    if value.endswith("Z"):
        value = value[:-1]

    if value.endswith("+00:00"):
        value = value[:-6]

    return datetime.fromisoformat(value)


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
    Make one request to the National Highways closures endpoint.

    This function deliberately performs only ONE API request.
    Window splitting is handled by fetch_closures().
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
            f"National Highways API rate limit reached "
            f"for {closure_type} closures. "
            f"Retry-After: "
            f"{retry_after or 'not specified'}"
        )

    response.raise_for_status()

    payload = response.json()

    return process_payload(payload)


def _deduplicate(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove duplicate closure records while preserving order.
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


def _record_key(
    record: dict[str, Any],
) -> str:
    """
    Generate a stable identifier for a closure record.

    Prefer known identifiers when available. Fall back to a
    deterministic representation of the record.
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

    # Stable fallback using the most useful closure fields.
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


def _fetch_window_recursive(
    closure_type: str,
    start: datetime,
    end: datetime,
    depth: int = 0,
) -> list[dict[str, Any]]:
    """
    Fetch one time window.

    If the API returns MAX_RECORDS_PER_REQUEST or more records,
    split the window into two halves and fetch each half recursively.

    This protects us against the API's 500-record response cap.
    """

    if end <= start:
        return []

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

    record_count = len(records)

    print(
        f"Returned {record_count} records "
        f"for {closure_type} window."
    )

    # Below the cap means the response is safe to keep.
    if record_count < MAX_RECORDS_PER_REQUEST:
        return records

    duration = end - start

    minimum_duration = timedelta(
        minutes=MIN_WINDOW_MINUTES
    )

    # Safety stop. If the API is still returning 500 records
    # at the minimum window size, we cannot safely split further.
    if duration <= minimum_duration:

        print(
            "WARNING: Window reached the minimum "
            f"size of {MIN_WINDOW_MINUTES} minutes "
            f"but still returned "
            f"{record_count} records."
        )

        print(
            "Keeping the response because the "
            "window cannot safely be split further."
        )

        return records

    midpoint = start + (
        duration / 2
    )

    # Make sure rounding never produces an empty window.
    if midpoint <= start or midpoint >= end:

        print(
            "WARNING: Unable to split window further. "
            "Keeping current response."
        )

        return records

    print(
        f"Response reached {record_count} records. "
        "Splitting window..."
    )

    first_records = _fetch_window_recursive(
        closure_type=closure_type,
        start=start,
        end=midpoint,
        depth=depth + 1,
    )

    second_records = _fetch_window_recursive(
        closure_type=closure_type,
        start=midpoint,
        end=end,
        depth=depth + 1,
    )

    combined = (
        first_records
        + second_records
    )

    unique = _deduplicate(combined)

    print(
        f"Combined split windows: "
        f"{len(combined)} records, "
        f"{len(unique)} unique."
    )

    return unique


def fetch_closures(
    closure_type: str = "planned",
    start_datetime: str | None = None,
    end_datetime: str | None = None,
    modified_since: str | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch road closure data from the National Highways API.

    Behaviour:

    1. If an explicit start/end window is supplied, fetch that window.
    2. If no dates are supplied, automatically fetch the previous/current
       7-day collection window.
    3. Any response containing 500 or more records is automatically split
       into smaller windows.
    4. Split results are combined and deduplicated.
    5. HTTP 429 is raised as NationalHighwaysRateLimitError.
    """

    # ------------------------------------------------------------
    # MODIFIED-SINCE REQUESTS
    # ------------------------------------------------------------

    # modifiedSinceDateTime is a different API query mode and should
    # not be combined with automatic time-window splitting.
    if modified_since:

        return _request_closures(
            closure_type=closure_type,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            modified_since=modified_since,
        )

    # ------------------------------------------------------------
    # EXPLICIT DATE WINDOW
    # ------------------------------------------------------------

    if start_datetime or end_datetime:

        if not start_datetime or not end_datetime:

            # Preserve the existing behaviour for callers that
            # deliberately provide only one boundary.
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

        return _fetch_window_recursive(
            closure_type=closure_type,
            start=start,
            end=end,
        )

    # ------------------------------------------------------------
    # DEFAULT 7-DAY WINDOW
    # ------------------------------------------------------------

    # Use UTC for the API window. The API expects the date values
    # without a timezone suffix.
    now = datetime.utcnow().replace(
        microsecond=0
    )

    start = now

    end = now + timedelta(
        days=DEFAULT_WINDOW_DAYS
    )

    print(
        f"No date window supplied. "
        f"Using {DEFAULT_WINDOW_DAYS}-day window:"
    )

    print(
        f"{_format_api_datetime(start)} "
        f"-> "
        f"{_format_api_datetime(end)}"
    )

    return _fetch_window_recursive(
        closure_type=closure_type,
        start=start,
        end=end,
    )
