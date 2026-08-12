from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests

from config import API_BASE_URL, API_KEY
from data_processor import process_payload


# ============================================================
# CONFIGURATION
# ============================================================

# National Highways currently returns a maximum of 500
# situation records per response page.
PAGE_SIZE = 500

# Safety limits. These are deliberately conservative while
# the importer is being validated.
MAX_PAGES = 100
MAX_REQUESTS = 120

# Individual HTTP request timeout.
REQUEST_TIMEOUT = 60

# Target roads for the Road-data project.
TARGET_ROADS = {
    "M6",
    "M57",
    "M58",
    "M62",
}


# ============================================================
# EXCEPTIONS
# ============================================================

class NationalHighwaysRateLimitError(Exception):
    """Raised when the National Highways API rate limit is reached."""


class NationalHighwaysPaginationError(Exception):
    """Raised when the National Highways pagination chain is invalid."""


# ============================================================
# HEADERS
# ============================================================

def _build_headers() -> dict[str, str]:
    """Build the standard National Highways API headers."""

    return {
        "Ocp-Apim-Subscription-Key": API_KEY,
        "X-Response-MediaType": "application/json",
        "X-Data-Format": "DATEXII",
    }


# ============================================================
# DATETIME HELPERS
# ============================================================

def _parse_datetime(
    value: str | None,
) -> datetime | None:
    """
    Parse a National Highways/DATEX II datetime.

    Returned datetimes are timezone-aware UTC values.
    """

    if not value:
        return None

    text = str(value).strip()

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        value_datetime = datetime.fromisoformat(text)
    except ValueError:
        return None

    if value_datetime.tzinfo is None:
        value_datetime = value_datetime.replace(
            tzinfo=timezone.utc
        )
    else:
        value_datetime = value_datetime.astimezone(
            timezone.utc
        )

    return value_datetime


# ============================================================
# OVERLAP CHECK
# ============================================================

def _overlaps_window(
    closure: dict[str, Any],
    requested_start: datetime | None,
    requested_end: datetime | None,
) -> bool:
    """
    Confirm that a closure overlaps the requested window.

    This is a defensive local check.

    The API has already been shown to perform overlap-based
    filtering, but we keep this check so the importer does
    not accidentally retain a closure completely outside the
    requested period.
    """

    if requested_start is None or requested_end is None:
        return True

    closure_start = _parse_datetime(
        closure.get("start")
    )

    closure_end = _parse_datetime(
        closure.get("end")
    )

    if closure_start is None or closure_end is None:
        return False

    return (
        closure_start <= requested_end
        and closure_end >= requested_start
    )


# ============================================================
# ROAD FILTER
# ============================================================

def _is_target_road(
    closure: dict[str, Any],
) -> bool:
    """Return True when the closure belongs to a target road."""

    road = closure.get("road_name")

    if not road:
        return False

    return str(road).strip().upper() in TARGET_ROADS


# ============================================================
# SINGLE HTTP REQUEST
# ============================================================

def _request_page(
    url: str,
    params: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Perform exactly one HTTP request.

    Returns:

        (processed_records, x_next)

    A 429 is raised to the caller. The caller is responsible
    for observing Retry-After before attempting the same URL
    again.
    """

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
            retry_after
            if retry_after
            else "not supplied"
        )

    response.raise_for_status()

    payload = response.json()

    closures = process_payload(
        payload
    )

    x_next = response.headers.get(
        "x-next"
    )

    return closures, x_next


# ============================================================
# RETRY-AFTER
# ============================================================

def _retry_after_seconds(
    error: NationalHighwaysRateLimitError,
) -> int:
    """Convert a Retry-After value into seconds."""

    try:
        return max(
            0,
            int(str(error)),
        )
    except (TypeError, ValueError):
        return 60


# ============================================================
# PAGINATED FETCH
# ============================================================

def fetch_national_highways(
    start_datetime: str,
    end_datetime: str,
) -> list[dict[str, Any]]:
    """
    Fetch National Highways closures for a date window.

    Important behaviour:

    - closureType is NOT supplied.
    - The first request uses startDateTime/endDateTime.
    - Subsequent requests use the exact x-next URL returned
      by National Highways.
    - PageCursor is never constructed manually.
    - HTTP 429 honours Retry-After.
    - No arbitrary fixed retry delay is used.
    - Records are parsed through this repository's existing
      data_processor.py.
    - Only M6, M57, M58 and M62 are retained.
    - A local overlap check is applied defensively.
    """

    requested_start = _parse_datetime(
        start_datetime
    )

    requested_end = _parse_datetime(
        end_datetime
    )

    if requested_start is None:
        raise ValueError(
            f"Invalid start_datetime: {start_datetime}"
        )

    if requested_end is None:
        raise ValueError(
            f"Invalid end_datetime: {end_datetime}"
        )

    if requested_end <= requested_start:
        raise ValueError(
            "end_datetime must be later than "
            "start_datetime"
        )

    url = f"{API_BASE_URL}/closures"

    params = {
        "startDateTime": start_datetime,
        "endDateTime": end_datetime,
    }

    all_records: list[dict[str, Any]] = []

    page_number = 0
    request_count = 0

    while True:

        page_number += 1

        if page_number > MAX_PAGES:
            raise NationalHighwaysPaginationError(
                f"Maximum page limit of {MAX_PAGES} "
                "was reached."
            )

        # ----------------------------------------------------
        # REQUEST / RATE LIMIT HANDLING
        # ----------------------------------------------------

        while True:

            request_count += 1

            if request_count > MAX_REQUESTS:
                raise NationalHighwaysPaginationError(
                    f"Maximum request limit of "
                    f"{MAX_REQUESTS} was reached."
                )

            print(
                f"National Highways request "
                f"{request_count}"
            )

            print(
                f"Page: {page_number}"
            )

            print(
                f"URL: {url}"
            )

            try:

                records, x_next = _request_page(
                    url=url,
                    params=params,
                )

                break

            except NationalHighwaysRateLimitError as exc:

                wait_seconds = _retry_after_seconds(
                    exc
                )

                print(
                    "HTTP 429 rate limit received."
                )

                print(
                    f"Retry-After: "
                    f"{wait_seconds} seconds"
                )

                print(
                    "Waiting for Retry-After "
                    "before retrying the same page."
                )

                time.sleep(
                    wait_seconds
                )

        # ----------------------------------------------------
        # PAGE RESULT
        # ----------------------------------------------------

        print(
            f"Records returned on page "
            f"{page_number}: {len(records)}"
        )

        all_records.extend(
            records
        )

        # ----------------------------------------------------
        # PAGINATION
        # ----------------------------------------------------

        if not x_next:

            print(
                "x-next not present."
            )

            print(
                "Pagination complete."
            )

            break

        # The API supplies an absolute URL in the live
        # responses. urljoin also safely handles a relative
        # continuation URL should that ever occur.
        next_url = urljoin(
            url,
            x_next,
        )

        if next_url == url:

            raise NationalHighwaysPaginationError(
                "x-next returned the same URL as "
                "the current request."
            )

        print(
            "x-next received."
        )

        print(
            f"Next page URL: {next_url}"
        )

        # From this point onward we MUST use the exact
        # continuation URL. Do not add or reconstruct
        # PageCursor ourselves.
        url = next_url

        # Parameters are already embedded in x-next.
        params = None

    # ========================================================
    # TARGET ROAD + OVERLAP FILTER
    # ========================================================

    filtered: list[dict[str, Any]] = []

    for closure in all_records:

        if not _is_target_road(
            closure
        ):
            continue

        if not _overlaps_window(
            closure,
            requested_start,
            requested_end,
        ):
            continue

        filtered.append(
            closure
        )

    print()
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
        f"Target-road overlapping records: "
        f"{len(filtered)}"
    )

    return filtered


# ============================================================
# SIMPLE ROAD GROUPING
# ============================================================

def group_by_road(
    closures: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Group normalised closures by road.

    This is deliberately small and independent of the rest
    of the Road-data application.
    """

    grouped = {
        road: []
        for road in sorted(
            TARGET_ROADS
        )
    }

    for closure in closures:

        road = str(
            closure.get("road_name") or ""
        ).strip().upper()

        if road in grouped:
            grouped[road].append(
                closure
            )

    return grouped
