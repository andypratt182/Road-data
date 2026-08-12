from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urljoin

import requests

from config import API_BASE_URL, API_KEY
from data_processor import process_payload


class NationalHighwaysRateLimitError(Exception):
    """Raised when the National Highways API rate limit is reached."""


# ============================================================
# CONFIGURATION
# ============================================================

MAX_RECORDS_PER_REQUEST = 500

DEFAULT_WINDOW_HOURS = 24

MIN_WINDOW_MINUTES = 60

# Delay between successful paginated requests.
REQUEST_DELAY_SECONDS = 5

# Additional safety margin after a 429 Retry-After response.
RATE_LIMIT_SAFETY_SECONDS = 2

# Maximum number of retries for a rate-limited request.
MAX_RATE_LIMIT_RETRIES = 5

REQUEST_TIMEOUT = 60


# ============================================================
# DATE HELPERS
# ============================================================

def _format_api_datetime(value: datetime) -> str:
    """Format a datetime for the National Highways API."""

    return value.strftime(
        "%Y-%m-%dT%H:%M:%S"
    )


def _parse_api_datetime(value: str) -> datetime:
    """Parse a National Highways API datetime."""

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
    Fetch National Highways closures while following x-next
    pagination.

    Every API page is passed through the existing
    process_payload() function.

    HTTP 429 responses are retried using the API's Retry-After
    value plus a small safety margin.
    """

    first_url = f"{API_BASE_URL}/closures"

    params: dict[str, str] = {
        "closureType": closure_type,
    }

    if start_datetime:
        params["startDateTime"] = start_datetime

    if end_datetime:
        params["endDateTime"] = end_datetime

    if modified_since:
        params["modifiedSinceDateTime"] = modified_since

    headers = _build_headers()

    all_records: list[dict[str, Any]] = []

    next_url: str | None = first_url
    next_params: dict[str, str] | None = params

    page_number = 0
    request_count = 0

    seen_urls: set[str] = set()

    while next_url:

        page_number += 1

        # ----------------------------------------------------
        # Protect against a broken/repeating x-next URL.
        # ----------------------------------------------------

        if next_url in seen_urls:
            raise RuntimeError(
                "National Highways API returned a repeated "
                f"x-next URL on page {page_number}: {next_url}"
            )

        seen_urls.add(next_url)

        print(
            f"National Highways request "
            f"{request_count + 1}"
        )

        print(
            f"Page: {page_number}"
        )

        print(
            f"URL: {next_url}"
        )

        # ----------------------------------------------------
        # Retry loop for HTTP 429.
        #
        # IMPORTANT:
        # We do NOT advance to the next page when a 429 occurs.
        # We retry the exact same URL.
        # ----------------------------------------------------

        rate_limit_retry = 0

        while True:

            request_count += 1

            response = requests.get(
                next_url,
                params=next_params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code != 429:
                break

            rate_limit_retry += 1

            retry_after_header = response.headers.get(
                "Retry-After"
            )

            try:
                retry_after = int(
                    retry_after_header
                )
            except (
                TypeError,
                ValueError,
            ):
                retry_after = 15

            wait_seconds = (
                max(
                    retry_after,
                    1,
                )
                + RATE_LIMIT_SAFETY_SECONDS
            )

            print(
                "WARNING: National Highways API rate limit "
                f"reached for page {page_number}."
            )

            print(
                "Retry-After: "
                f"{retry_after_header or 'not specified'}"
            )

            print(
                f"Waiting {wait_seconds} seconds "
                f"before retry "
                f"{rate_limit_retry}/"
                f"{MAX_RATE_LIMIT_RETRIES}..."
            )

            if rate_limit_retry > MAX_RATE_LIMIT_RETRIES:

                raise NationalHighwaysRateLimitError(
                    "National Highways API rate limit persisted "
                    f"after {MAX_RATE_LIMIT_RETRIES} retries "
                    f"on page {page_number}."
                )

            time.sleep(
                wait_seconds
            )

            print(
                f"Retrying page {page_number}..."
            )

        # ----------------------------------------------------
        # Normal HTTP error handling.
        # ----------------------------------------------------

        response.raise_for_status()

        payload = response.json()

        # ----------------------------------------------------
        # EXISTING PRODUCTION PARSER.
        #
        # Do not alter the payload or replace the parser.
        # ----------------------------------------------------

        page_records = process_payload(
            payload
        )

        page_count = len(
            page_records
        )

        print(
            f"Page {page_number}: "
            f"{page_count} processed records"
        )

        all_records.extend(
            page_records
        )

        # ----------------------------------------------------
        # Follow x-next.
        # ----------------------------------------------------

        x_next = response.headers.get(
            "x-next"
        )

        if x_next:
            x_next = x_next.strip()

        if not x_next:

            next_url = None
            next_params = None

            print(
                f"Pagination complete after "
                f"{page_number} page(s)."
            )

            break

        next_url = urljoin(
            response.url,
            x_next,
        )

        # x-next already contains the continuation parameters.
        next_params = None

        print(
            f"x-next found: continuing to page "
            f"{page_number + 1}"
        )

        # ----------------------------------------------------
        # Small delay between successful requests.
        # ----------------------------------------------------

        time.sleep(
            REQUEST_DELAY_SECONDS
        )

    # ========================================================
    # DEDUPLICATION
    # ========================================================

    unique_records = _deduplicate(
        all_records
    )

    print(
        "National Highways collection complete."
    )

    print(
        f"Pages retrieved: {page_number}"
    )

    print(
        f"Requests made: {request_count}"
    )

    print(
        f"All processed records: "
        f"{len(all_records)}"
    )

    print(
        f"Unique processed records: "
        f"{len(unique_records)}"
    )

    return unique_records


# ============================================================
# DEDUPLICATION
# ============================================================

def _record_key(
    record: dict[str, Any],
) -> str:
    """Generate a stable key for a closure."""

    for field in (
        "id",
        "closureId",
        "eventId",
        "reference",
        "identifier",
    ):

        value = record.get(
            field
        )

        if value not in (
            None,
            "",
        ):

            return (
                f"{field}:{value}"
            )

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
    """Remove duplicate records while preserving order."""

    seen: set[str] = set()
    unique: list[dict[str, Any]] = []

    for record in records:

        key = _record_key(
            record
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        unique.append(
            record
        )

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

    If the API returns 500 records, split the window.
    """

    start_string = _format_api_datetime(
        start
    )

    end_string = _format_api_datetime(
        end
    )

    print(
        f"Fetching {closure_type} closures: "
        f"{start_string} -> {end_string}"
    )

    records = _request_closures(
        closure_type=closure_type,
        start_datetime=start_string,
        end_datetime=end_string,
    )

    count = len(
        records
    )

    print(
        f"Returned {count} records."
    )

    if count < MAX_RECORDS_PER_REQUEST:
        return records

    duration = end - start

    minimum_duration = timedelta(
        minutes=MIN_WINDOW_MINUTES
    )

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
    Fetch road closure data from National Highways.

    Existing public interface retained.
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
