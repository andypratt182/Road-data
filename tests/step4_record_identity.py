import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests


# ============================================================
# STEP 4
# NATIONAL HIGHWAYS RECORD IDENTITY TEST
# ============================================================
#
# PURPOSE:
# Determine what fields can reliably identify a National
# Highways situationRecord when idG is absent.
#
# IMPORTANT:
# - Road-data repository only
# - No database
# - No production files modified
# - No config.py import
# - closureType NOT supplied
# - Pagination follows exact x-next URLs
# - Retry-After is honoured
# - No manually constructed PageCursor
#
# TARGET ROADS:
# M6, M57, M58, M62
#
# REQUEST WINDOW:
# 2026-08-11 00:00:00 -> 2026-08-18 23:59:59
# ============================================================


API_URL = "https://api.data.nationalhighways.co.uk/roads/v2.0/closures"

START = "2026-08-11T00:00:00"
END = "2026-08-18T23:59:59"

TARGET_ROADS = {"M6", "M57", "M58", "M62"}

# Safety limit for this diagnostic.
# This is deliberately finite so the test cannot accidentally
# become an unlimited pagination job.
MAX_SUCCESSFUL_PAGES = 15

API_KEY = os.environ.get("NATIONAL_HIGHWAYS_API_KEY")

if not API_KEY:
    print("ERROR: NATIONAL_HIGHWAYS_API_KEY is not set.")
    sys.exit(1)


HEADERS = {
    "Ocp-Apim-Subscription-Key": API_KEY,
    "X-Response-MediaType": "application/json",
    "X-Data-Format": "DATEXII",
}


# ============================================================
# HELPERS
# ============================================================

def parse_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        result = datetime.fromisoformat(text)
    except ValueError:
        return None

    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    else:
        result = result.astimezone(timezone.utc)

    return result


def get_nested(record, *path):
    current = record

    for key in path:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def first_value(record, paths):
    for path in paths:
        value = get_nested(record, *path)

        if value not in (None, ""):
            return value

    return None


def extract_id(record):
    return first_value(
        record,
        [
            ("idG",),
            ("id",),
            ("situationRecordId",),
            ("situationRecord", "idG"),
        ],
    )


def extract_version(record):
    return first_value(
        record,
        [
            ("versionG",),
            ("version",),
            ("situationRecord", "versionG"),
        ],
    )


def extract_creation_time(record):
    return first_value(
        record,
        [
            ("situationRecordCreationTime",),
            ("creationTime",),
            ("situationRecord", "situationRecordCreationTime"),
        ],
    )


def extract_version_time(record):
    return first_value(
        record,
        [
            ("situationRecordVersionTime",),
            ("versionTime",),
            ("situationRecord", "situationRecordVersionTime"),
        ],
    )


def extract_road(record):
    candidates = [
        ("road",),
        ("roadName",),
        ("roadNumber",),
        (
            "locationReference",
            "locLocationGroupByList",
            "locationContainedInGroup",
        ),
    ]

    value = first_value(record, candidates)

    if isinstance(value, list):
        for item in value:
            if not isinstance(item, dict):
                continue

            road = get_nested(
                item,
                "locSingleRoadLinearLocation",
                "linearWithinLinearElement",
            )

            if isinstance(road, list):
                for section in road:
                    road_name = get_nested(
                        section,
                        "linearElement",
                        "locLinearElementByCode",
                        "roadName",
                    )

                    if road_name:
                        return str(road_name).upper()

    if value:
        return str(value).upper()

    return None


def extract_description(record):
    value = first_value(
        record,
        [
            ("description",),
            ("comment",),
            ("remarks",),
            ("generalPublicComment",),
        ],
    )

    if isinstance(value, list):
        comments = []

        for item in value:
            if isinstance(item, dict):
                comment = item.get("comment")

                if comment:
                    comments.append(str(comment))

        if comments:
            return " | ".join(comments)

    return str(value) if value else None


def extract_direction(record):
    value = first_value(
        record,
        [
            ("direction",),
            ("directionDescription",),
        ],
    )

    if value:
        return str(value)

    # Try DATEX nested location structure.
    locations = get_nested(
        record,
        "locationReference",
        "locLocationGroupByList",
        "locationContainedInGroup",
    )

    if isinstance(locations, list):
        for item in locations:
            sections = get_nested(
                item,
                "locSingleRoadLinearLocation",
                "linearWithinLinearElement",
            )

            if isinstance(sections, list):
                for section in sections:
                    direction = section.get(
                        "directionOnLinearSection"
                    )

                    if direction:
                        return str(direction)

    return None


def extract_validity(record):
    start = first_value(
        record,
        [
            (
                "validity",
                "validityTimeSpecification",
                "overallStartTime",
            ),
            ("overallStartTime",),
            ("startDateTime",),
        ],
    )

    end = first_value(
        record,
        [
            (
                "validity",
                "validityTimeSpecification",
                "overallEndTime",
            ),
            ("overallEndTime",),
            ("endDateTime",),
        ],
    )

    return start, end


def make_fallback_identity(record):
    """
    Candidate identity for records without idG.

    This is deliberately reported as a CANDIDATE only.
    The test does not assume it is valid.
    """

    road = extract_road(record)
    direction = extract_direction(record)
    description = extract_description(record)

    validity_start, validity_end = extract_validity(record)

    creation = extract_creation_time(record)
    version_time = extract_version_time(record)

    return (
        road,
        direction,
        validity_start,
        validity_end,
        description,
        creation,
        version_time,
    )


def extract_records(payload):
    try:
        situations = payload["D2Payload"]["situation"]
    except (KeyError, TypeError):
        return []

    if not isinstance(situations, list):
        return []

    records = []

    for situation in situations:
        if not isinstance(situation, dict):
            continue

        situation_records = situation.get("situationRecord")

        if not isinstance(situation_records, list):
            continue

        records.extend(situation_records)

    return records


def normalise_url(url):
    if not url:
        return None

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return None

    return url


# ============================================================
# REQUEST / PAGINATION
# ============================================================

initial_params = {
    "startDateTime": START,
    "endDateTime": END,
}

url = API_URL

all_records = []
pages = 0
requests_made = 0
rate_limits = []

seen_page_urls = set()


print("=" * 70)
print("STEP 4")
print("NATIONAL HIGHWAYS RECORD IDENTITY TEST")
print("=" * 70)
print()
print("Purpose:")
print("Determine reliable identity fields when idG is absent.")
print()
print("closureType: NOT supplied")
print("Manual PageCursor: NOT supplied")
print("Pagination: exact x-next URL")
print("Rate limiting: Retry-After")
print("Database: NOT used")
print("Production workflow: NOT modified")
print()
print(f"Start: {START}")
print(f"End:   {END}")
print()
print("Target roads:")
print(", ".join(sorted(TARGET_ROADS)))
print()
print("=" * 70)


while url and pages < MAX_SUCCESSFUL_PAGES:

    if url in seen_page_urls:
        print()
        print("ERROR: x-next returned a URL already visited.")
        print("Pagination loop detected.")
        break

    seen_page_urls.add(url)

    params = initial_params if pages == 0 else None

    print()
    print("=" * 70)
    print(f"PAGE {pages + 1}")
    print("=" * 70)

    if params:
        print("Parameters:")
        print(json.dumps(params, indent=2))
    else:
        print("URL obtained directly from previous x-next.")

    while True:

        requests_made += 1

        started = time.monotonic()

        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=60,
        )

        elapsed = time.monotonic() - started

        print()
        print(f"API request #{requests_made}")
        print(f"HTTP status: {response.status_code}")
        print(f"Elapsed: {elapsed:.3f}s")

        params = None

        if response.status_code == 429:

            retry_after = response.headers.get(
                "Retry-After"
            )

            print()
            print("HTTP 429 RATE LIMIT")
            print(
                "Retry-After:",
                retry_after or "not supplied",
            )

            if not retry_after:
                print(
                    "No Retry-After supplied."
                )
                print(
                    "Stopping safely."
                )
                url = None
                break

            try:
                delay = max(
                    0,
                    int(float(retry_after)),
                )
            except ValueError:
                print(
                    "Invalid Retry-After value."
                )
                print(
                    "Stopping safely."
                )
                url = None
                break

            rate_limits.append(delay)

            print(
                f"Waiting {delay} seconds "
                "before retrying the same page."
            )

            time.sleep(delay)
            continue

        if response.status_code != 200:

            print()
            print("REQUEST FAILED")
            print(response.text[:5000])

            url = None
            break

        break

    if not url:
        break

    try:
        payload = response.json()
    except Exception as exc:
        print()
        print("JSON decode failed:")
        print(exc)
        url = None
        break

    records = extract_records(payload)

    print()
    print(f"Situation records: {len(records)}")

    all_records.extend(records)

    pages += 1

    next_url = normalise_url(
        response.headers.get("x-next")
    )

    if next_url:
        print("x-next: PRESENT")
        url = next_url
        print("Following exact x-next URL.")
    else:
        print("x-next: NOT PRESENT")
        url = None


# ============================================================
# IDENTITY ANALYSIS
# ============================================================

print()
print("=" * 70)
print("IDENTITY ANALYSIS")
print("=" * 70)
print()

total = len(all_records)

with_id = []
without_id = []

for record in all_records:

    record_id = extract_id(record)

    if record_id:
        with_id.append(record)
    else:
        without_id.append(record)

print(f"Total records examined: {total}")
print(f"Records with idG:       {len(with_id)}")
print(f"Records without idG:    {len(without_id)}")

if total:
    print(
        f"idG coverage: "
        f"{len(with_id) / total * 100:.2f}%"
    )


# ============================================================
# ID DUPLICATE ANALYSIS
# ============================================================

ids = [
    str(extract_id(record))
    for record in with_id
]

id_counts = Counter(ids)

duplicate_ids = {
    record_id: count
    for record_id, count in id_counts.items()
    if count > 1
}

print()
print("ID DUPLICATION")
print("-" * 70)
print(f"Unique idG values: {len(id_counts)}")
print(f"Duplicate idG values: {len(duplicate_ids)}")

if duplicate_ids:

    print()
    print("Sample duplicate idG values:")

    for record_id, count in list(
        sorted(
            duplicate_ids.items(),
            key=lambda item: -item[1],
        )
    )[:10]:

        print(
            f"{record_id}: {count} records"
        )


# ============================================================
# FIELD COVERAGE
# ============================================================

fields = {
    "idG": extract_id,
    "versionG": extract_version,
    "creationTime": extract_creation_time,
    "versionTime": extract_version_time,
    "road": extract_road,
    "direction": extract_direction,
    "description": extract_description,
}

print()
print("FIELD COVERAGE")
print("-" * 70)

for name, extractor in fields.items():

    count = 0

    for record in all_records:

        value = extractor(record)

        if value not in (None, ""):
            count += 1

    print(
        f"{name}: "
        f"{count}/{total}"
        f" ({count / total * 100:.2f}%)"
        if total
        else f"{name}: 0/0"
    )


# ============================================================
# TARGET ROAD ANALYSIS
# ============================================================

road_records = defaultdict(list)

for record in all_records:

    road = extract_road(record)

    if not road:
        continue

    road = road.upper()

    if road in TARGET_ROADS:
        road_records[road].append(record)


print()
print("=" * 70)
print("TARGET ROAD IDENTITY ANALYSIS")
print("=" * 70)

for road in sorted(TARGET_ROADS):

    records = road_records.get(road, [])

    road_with_id = [
        record
        for record in records
        if extract_id(record)
    ]

    road_without_id = [
        record
        for record in records
        if not extract_id(record)
    ]

    print()
    print(road)
    print("-" * 70)
    print(f"Records:              {len(records)}")
    print(f"With idG:             {len(road_with_id)}")
    print(f"Without idG:          {len(road_without_id)}")


# ============================================================
# FALLBACK IDENTITY ANALYSIS
# ============================================================

fallback_counts = Counter()

fallback_examples = {}

for record in without_id:

    key = make_fallback_identity(record)

    fallback_counts[key] += 1

    if key not in fallback_examples:
        fallback_examples[key] = record


duplicate_fallbacks = {
    key: count
    for key, count in fallback_counts.items()
    if count > 1
}


print()
print("=" * 70)
print("CANDIDATE FALLBACK IDENTITY")
print("=" * 70)
print()
print(
    "The following is an analytical candidate only."
)
print(
    "It has NOT been declared a production identifier."
)
print()
print(
    "Candidate fields:"
)
print(
    "road + direction + validity start + validity end"
)
print(
    "+ description + creation time + version time"
)
print()
print(
    f"Records without idG: {len(without_id)}"
)
print(
    f"Unique candidate identities: "
    f"{len(fallback_counts)}"
)
print(
    f"Candidate identities occurring more than once: "
    f"{len(duplicate_fallbacks)}"
)


# ============================================================
# SAMPLE RECORDS WITHOUT ID
# ============================================================

print()
print("=" * 70)
print("SAMPLE RECORDS WITHOUT idG")
print("=" * 70)

if not without_id:

    print("No records without idG were found.")

else:

    for number, record in enumerate(
        without_id[:10],
        start=1,
    ):

        validity_start, validity_end = (
            extract_validity(record)
        )

        print()
        print(f"Record {number}")
        print(f"Road: {extract_road(record)}")
        print(
            f"Direction: "
            f"{extract_direction(record)}"
        )
        print(
            f"versionG: "
            f"{extract_version(record)}"
        )
        print(
            f"Creation: "
            f"{extract_creation_time(record)}"
        )
        print(
            f"Version time: "
            f"{extract_version_time(record)}"
        )
        print(
            f"Validity start: "
            f"{validity_start}"
        )
        print(
            f"Validity end: "
            f"{validity_end}"
        )
        print(
            f"Description: "
            f"{extract_description(record)}"
        )

        print()
        print(
            "Available top-level fields:"
        )
        print(
            ", ".join(
                sorted(record.keys())
            )
        )


# ============================================================
# CONCLUSION
# ============================================================

print()
print("=" * 70)
print("STEP 4 RESULT")
print("=" * 70)
print()

if not all_records:

    print(
        "RESULT: NO RECORDS WERE AVAILABLE "
        "FOR IDENTITY ANALYSIS."
    )

else:

    if without_id:

        print(
            "RESULT: idG IS NOT A COMPLETE "
            "RECORD IDENTITY FIELD."
        )

        print(
            f"{len(without_id)} of {total} "
            "records examined have no idG."
        )

        print()
        print(
            "A fallback identity must therefore "
            "be derived from other record fields."
        )

    else:

        print(
            "RESULT: idG WAS PRESENT ON ALL "
            "RECORDS EXAMINED."
        )

    print()
    print(
        "Candidate fallback identity analysis "
        "has been completed."
    )

    if duplicate_fallbacks:

        print(
            "WARNING: Some fallback identities "
            "occur more than once."
        )

        print(
            "The candidate composite MUST NOT "
            "yet be treated as a unique identifier."
        )

    else:

        print(
            "No duplicate candidate fallback "
            "identities were found in the "
            "examined records."
        )

print()
print(f"Successful pages retrieved: {pages}")
print(f"API requests made: {requests_made}")
print(f"Rate limits encountered: {len(rate_limits)}")

if rate_limits:
    print(
        "Retry-After values observed:",
        ", ".join(
            str(value)
            for value in rate_limits
        ),
    )

print()
print("No database was used.")
print("No production files were modified.")
print("STEP 4 COMPLETE.")
