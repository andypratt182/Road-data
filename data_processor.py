"""
National Highways D2 road-closure data processor.

Parses the raw D2Payload structure returned by the National Highways API.

Expected structure:

D2Payload
└── situation[]
    └── situationRecord[]
        └── sitRoadOrCarriagewayOrLaneManagement

The processor deliberately works from the raw D2 structure rather than
assuming the API has already normalised the records.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_list(value: Any) -> list:
    """Return value as a list."""
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _first(value: Any, default: Any = None) -> Any:
    """Return the first item from a list-like value."""
    if isinstance(value, list):
        return value[0] if value else default

    return value if value is not None else default


def _nested(data: Any, *keys: str, default: Any = None) -> Any:
    """
    Safely walk a nested dictionary.

    Returns default if any part of the path is missing.
    """
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current is None:
            return default

    return current


def _text(value: Any, default: str = "") -> str:
    """Convert a value to a clean string."""
    if value is None:
        return default

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def _float(value: Any, default: float | None = None) -> float | None:
    """Safely convert a value to float."""
    if value is None or value == "":
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int | None = None) -> int | None:
    """Safely convert a value to int."""
    if value is None or value == "":
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_datetime(value: Any) -> datetime | None:
    """
    Parse National Highways ISO timestamps.

    Examples:
        2026-08-18T20:00:00.00Z
        2026-08-19T05:00:00Z
    """
    if not value:
        return None

    text = _text(value)

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Raw D2 record discovery
# ---------------------------------------------------------------------------

def extract_raw_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract raw National Highways situation records.

    The API response is expected to contain:

        D2Payload.situation[].situationRecord[]

    Each situationRecord normally contains a single record type such as:

        sitRoadOrCarriagewayOrLaneManagement

    The returned objects contain the actual situationRecord dictionaries.
    """

    if not isinstance(payload, dict):
        return []

    d2payload = payload.get("D2Payload", payload)

    if not isinstance(d2payload, dict):
        return []

    situations = _as_list(d2payload.get("situation"))

    records: list[dict[str, Any]] = []

    for situation in situations:
        if not isinstance(situation, dict):
            continue

        situation_records = _as_list(situation.get("situationRecord"))

        for situation_record in situation_records:
            if not isinstance(situation_record, dict):
                continue

            records.append(situation_record)

    return records


def _unwrap_management_record(
    situation_record: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Find the sitRoadOrCarriagewayOrLaneManagement object.

    The API can return different situation record types. We only process
    road/carriageway/lane-management records here.
    """

    record = situation_record.get(
        "sitRoadOrCarriagewayOrLaneManagement"
    )

    if isinstance(record, dict):
        return record

    return None


# ---------------------------------------------------------------------------
# Location extraction
# ---------------------------------------------------------------------------

def _extract_locations(record: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract every locationContainedInGroup entry.

    A single National Highways record can contain many location segments.
    We deliberately retain all of them rather than only taking the first.
    """

    groups = _nested(
        record,
        "locationReference",
        "locLocationGroupByList",
        "locationContainedInGroup",
        default=[],
    )

    locations: list[dict[str, Any]] = []

    for group in _as_list(groups):
        if not isinstance(group, dict):
            continue

        linear_location = group.get("locLinearLocation", {})

        if not isinstance(linear_location, dict):
            linear_location = {}

        supplementary = linear_location.get(
            "supplementaryPositionalDescription",
            {},
        )

        if not isinstance(supplementary, dict):
            supplementary = {}

        single_road_location = group.get(
            "locSingleRoadLinearLocation",
            {},
        )

        if not isinstance(single_road_location, dict):
            single_road_location = {}

        linear_sections = _as_list(
            single_road_location.get(
                "linearWithinLinearElement"
            )
        )

        if not linear_sections:
            linear_sections = [{}]

        for section in linear_sections:
            if not isinstance(section, dict):
                continue

            linear_element = _nested(
                section,
                "linearElement",
                "locLinearElementByCode",
                default={},
            )

            if not isinstance(linear_element, dict):
                linear_element = {}

            from_distance = _nested(
                section,
                "fromPoint",
                "locDistanceFromLinearElementStart",
                "distanceAlong",
            )

            to_distance = _nested(
                section,
                "toPoint",
                "locDistanceFromLinearElementStart",
                "distanceAlong",
            )

            carriageway_items = _as_list(
                supplementary.get("carriageway")
            )

            carriageway = {}
            if carriageway_items:
                first_carriageway = carriageway_items[0]

                if isinstance(first_carriageway, dict):
                    carriageway = first_carriageway

            carriageway_value = _nested(
                carriageway,
                "carriageway",
                "value",
            )

            carriageway_extended = _nested(
                carriageway,
                "carriageway",
                "extendedValueG",
            )

            impact = _nested(
                carriageway,
                "carriagewayExtensionG",
                "impactOnCarriageway",
                default={},
            )

            if not isinstance(impact, dict):
                impact = {}

            locations.append(
                {
                    "road_name": _text(
                        linear_element.get("roadName")
                    ),
                    "direction": _text(
                        section.get("directionOnLinearSection")
                    ),
                    "direction_relative": _text(
                        section.get(
                            "directionRelativeOnLinearSection"
                        )
                    ),
                    "height_grade": _text(
                        _nested(
                            section,
                            "heightGradeOfLinearSection",
                            "value",
                        )
                    ),
                    "height_grade_extended": _text(
                        _nested(
                            section,
                            "heightGradeOfLinearSection",
                            "extendedValueG",
                        )
                    ),
                    "linear_element_id": _text(
                        linear_element.get(
                            "linearElementIdentifier"
                        )
                    ),
                    "linear_element_type": _text(
                        _nested(
                            linear_element,
                            "linearElementByCodeExtensionG",
                            "linearElementType",
                        )
                    ),
                    "from_distance": _float(from_distance),
                    "to_distance": _float(to_distance),
                    "location_description": _text(
                        supplementary.get(
                            "locationDescription"
                        )
                    ),
                    "carriageway": _text(
                        carriageway_value
                    ),
                    "carriageway_extended": _text(
                        carriageway_extended
                    ),
                    "lanes_restricted": _int(
                        impact.get(
                            "numberOfLanesRestricted"
                        )
                    ),
                    "lanes_operational": _int(
                        impact.get(
                            "numberOfOperationalLanes"
                        )
                    ),
                    "pos_list": _text(
                        _nested(
                            linear_location,
                            "gmlLineString",
                            "locGmlLineString",
                            "posList",
                        )
                    ),
                }
            )

    return locations


# ---------------------------------------------------------------------------
# Cause extraction
# ---------------------------------------------------------------------------

def _extract_cause(record: dict[str, Any]) -> tuple[str, Any]:
    """Extract causeType and detailed cause."""
    cause = record.get("cause", {})

    if not isinstance(cause, dict):
        return "", None

    cause_type = _text(cause.get("causeType"))

    detailed = cause.get("detailedCauseType")

    return cause_type, detailed


# ---------------------------------------------------------------------------
# Comment extraction
# ---------------------------------------------------------------------------

def _extract_comments(record: dict[str, Any]) -> list[str]:
    """Extract all general public comments."""
    comments = []

    for item in _as_list(record.get("generalPublicComment")):
        if not isinstance(item, dict):
            continue

        comment = _text(item.get("comment"))

        if comment:
            comments.append(comment)

    return comments


# ---------------------------------------------------------------------------
# Main record parser
# ---------------------------------------------------------------------------

def parse_situation_record(
    situation_record: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Parse one raw D2 situationRecord.

    Returns a normalised dictionary suitable for the existing application.

    Important:
    A record may have several locationContainedInGroup entries. The parser
    retains them all in the `locations` field while also exposing the first
    usable location at top level for compatibility with simpler consumers.
    """

    record = _unwrap_management_record(situation_record)

    if record is None:
        return None

    management_type = _text(
        _nested(
            record,
            "roadOrCarriagewayOrLaneManagementType",
            "value",
        )
    )

    validity = record.get("validity", {})

    if not isinstance(validity, dict):
        validity = {}

    validity_spec = validity.get(
        "validityTimeSpecification",
        {},
    )

    if not isinstance(validity_spec, dict):
        validity_spec = {}

    start_raw = validity_spec.get("overallStartTime")
    end_raw = validity_spec.get("overallEndTime")

    start_dt = _parse_datetime(start_raw)
    end_dt = _parse_datetime(end_raw)

    source = record.get("source", {})

    if not isinstance(source, dict):
        source = {}

    source_identification = _text(
        source.get("sourceIdentification")
    )

    cause_type, detailed_cause = _extract_cause(record)

    comments = _extract_comments(record)

    locations = _extract_locations(record)

    # Use the first location containing an actual road name as the primary
    # location. This is important because a record can contain several
    # location segments and some may not contain the same metadata.
    primary_location = next(
        (
            location
            for location in locations
            if location.get("road_name")
        ),
        locations[0] if locations else {},
    )

    return {
        # Identity / version
        "id": _text(record.get("idG")),
        "idG": _text(record.get("idG")),
        "version": _text(record.get("versionG")),
        "versionG": _text(record.get("versionG")),

        # Record metadata
        "creation_time": _text(
            record.get("situationRecordCreationTime")
        ),
        "version_time": _text(
            record.get("situationRecordVersionTime")
        ),
        "probability": _text(
            record.get("probabilityOfOccurrence")
        ),
        "probability_of_occurrence": _text(
            record.get("probabilityOfOccurrence")
        ),
        "compliance": _text(
            record.get("complianceOption")
        ),

        # Closure / management
        "management_type": management_type,
        "road_or_carriageway_or_lane_management_type":
            management_type,

        # Validity
        "validity_status": _text(
            validity.get("validityStatus")
        ),
        "start": _text(start_raw),
        "end": _text(end_raw),
        "start_datetime": start_dt,
        "end_datetime": end_dt,

        # Source / cause
        "source": source_identification,
        "source_identification": source_identification,
        "cause_type": cause_type,
        "detailed_cause": detailed_cause,

        # Comments
        "comments": comments,
        "comment": comments[0] if comments else "",

        # Primary location
        "road_name": _text(
            primary_location.get("road_name")
        ),
        "direction": _text(
            primary_location.get("direction")
        ),
        "direction_relative": _text(
            primary_location.get("direction_relative")
        ),
        "linear_element_type": _text(
            primary_location.get("linear_element_type")
        ),
        "from_distance": primary_location.get(
            "from_distance"
        ),
        "to_distance": primary_location.get(
            "to_distance"
        ),
        "location_description": _text(
            primary_location.get(
                "location_description"
            )
        ),
        "carriageway": _text(
            primary_location.get("carriageway")
        ),
        "carriageway_extended": _text(
            primary_location.get(
                "carriageway_extended"
            )
        ),
        "lanes_restricted": primary_location.get(
            "lanes_restricted"
        ),
        "lanes_operational": primary_location.get(
            "lanes_operational"
        ),

        # All location segments
        "locations": locations,

        # Restrictions
        "width_restriction": bool(
            _nested(
                record,
                "roadOrCarriagewayOrLaneManagementExtensionG",
                "hasWidthRestrictionFlag",
                default=False,
            )
        ),
        "height_restriction": bool(
            _nested(
                record,
                "roadOrCarriagewayOrLaneManagementExtensionG",
                "hasHeightRestrictionFlag",
                default=False,
            )
        ),
        "weight_restriction": bool(
            _nested(
                record,
                "roadOrCarriagewayOrLaneManagementExtensionG",
                "hasWeightRestrictionFlag",
                default=False,
            )
        ),
        "contra_flow": bool(
            _nested(
                record,
                "roadOrCarriagewayOrLaneManagementExtensionG",
                "hasContraFlow",
                default=False,
            )
        ),

        # Preserve the complete raw record for downstream processing/debugging.
        "raw_record": record,
    }


# ---------------------------------------------------------------------------
# Payload parser
# ---------------------------------------------------------------------------

def parse_d2_payload(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Parse all supported records from a complete D2Payload response.

    Only sitRoadOrCarriagewayOrLaneManagement records are returned.
    """

    parsed: list[dict[str, Any]] = []

    for situation_record in extract_raw_records(payload):
        result = parse_situation_record(situation_record)

        if result is not None:
            parsed.append(result)

    return parsed


# ---------------------------------------------------------------------------
# Compatibility aliases
# ---------------------------------------------------------------------------

def process_data(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Backwards-compatible entry point.

    Existing callers can continue calling process_data().
    """
    return parse_d2_payload(payload)


def process_payload(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compatibility alias for process_data()."""
    return parse_d2_payload(payload)


def process_records(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compatibility alias for process_data()."""
    return parse_d2_payload(payload)


# ---------------------------------------------------------------------------
# Overlap filtering
# ---------------------------------------------------------------------------

def records_overlapping_window(
    records: list[dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    """
    Return records whose validity interval overlaps the requested window.

    Correct overlap rule:

        record_start <= window_end
        AND
        record_end >= window_start

    This deliberately does NOT require the record to start inside the window.
    """

    result = []

    for record in records:
        start = record.get("start_datetime")
        end = record.get("end_datetime")

        if start is None or end is None:
            continue

        if start <= window_end and end >= window_start:
            result.append(record)

    return result


def filter_by_roads(
    records: list[dict[str, Any]],
    roads: set[str] | list[str] | tuple[str, ...],
) -> list[dict[str, Any]]:
    """Filter parsed records by road name."""
    wanted = {
        _text(road).upper()
        for road in roads
        if _text(road)
    }

    return [
        record
        for record in records
        if _text(record.get("road_name")).upper() in wanted
    ]


# ---------------------------------------------------------------------------
# Record formatting
# ---------------------------------------------------------------------------

def format_record(record: dict[str, Any]) -> str:
    """Create a compact human-readable representation."""
    return (
        f"{record.get('road_name', '')} | "
        f"{record.get('direction', '')} | "
        f"{record.get('management_type', '')} | "
        f"{record.get('validity_status', '')} | "
        f"{record.get('start', '')} -> "
        f"{record.get('end', '')} | "
        f"{record.get('comment', '')}"
    )


__all__ = [
    "extract_raw_records",
    "parse_situation_record",
    "parse_d2_payload",
    "process_data",
    "process_payload",
    "process_records",
    "records_overlapping_window",
    "filter_by_roads",
    "format_record",
]
