from typing import Any
import re


def get_situations(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return the situations contained in a National Highways response."""

    return (
        payload
        .get("D2Payload", {})
        .get("situation", [])
    )


def get_records(
    situation: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return situation records from a situation."""

    return situation.get(
        "situationRecord",
        [],
    )


def get_management(
    record: dict[str, Any],
) -> dict[str, Any]:
    """Return the road/carriageway/lane management object."""

    return record.get(
        "sitRoadOrCarriagewayOrLaneManagement",
        {},
    )


def get_validity(
    management: dict[str, Any],
) -> dict[str, Any]:
    """Return validity information."""

    return management.get(
        "validity",
        {},
    )


def get_validity_times(
    management: dict[str, Any],
) -> dict[str, Any]:
    """Return the validity time specification."""

    return (
        get_validity(management)
        .get(
            "validityTimeSpecification",
            {},
        )
    )


def get_location_reference(
    management: dict[str, Any],
) -> dict[str, Any]:
    """Return the DATEX II location reference."""

    return management.get(
        "locationReference",
        {},
    )


def get_linear_locations(
    management: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Return all linear locations.

    DATEX II can provide a single location or multiple
    locations grouped inside locLocationGroupByList.
    """

    location_reference = get_location_reference(
        management
    )

    locations = []

    single = location_reference.get(
        "locLinearLocation"
    )

    if single:
        locations.append(single)

    grouped = (
        location_reference
        .get(
            "locLocationGroupByList",
            {},
        )
        .get(
            "locationContainedInGroup",
            [],
        )
    )

    for item in grouped:

        location = item.get(
            "locLinearLocation"
        )

        if location:
            locations.append(location)

    return locations


def get_road_name(
    location: dict[str, Any],
) -> str | None:
    """
    Extract the road name from a DATEX II linear location.
    """

    linear_location = location.get(
        "locSingleRoadLinearLocation",
        {}
    )

    sections = linear_location.get(
        "linearWithinLinearElement",
        []
    )

    for section in sections:

        road_name = (
            section
            .get("linearElement", {})
            .get("locLinearElementByCode", {})
            .get("roadName")
        )

        if road_name:
            return str(road_name).strip().upper()

    return None


def get_direction(
    location: dict[str, Any],
) -> str | None:
    """
    Extract the direction of travel from a DATEX II location.
    """

    linear_location = location.get(
        "locSingleRoadLinearLocation",
        {}
    )

    sections = linear_location.get(
        "linearWithinLinearElement",
        []
    )

    for section in sections:

        direction = section.get(
            "directionOnLinearSection"
        )

        if direction:
            return str(direction).strip()

    return None


def get_location_description(
    location: dict[str, Any],
) -> str | None:
    """Extract the human-readable location description."""

    description = (
        location
        .get(
            "supplementaryPositionalDescription",
            {},
        )
        .get(
            "locationDescription"
        )
    )

    if description:
        return str(description).strip()

    return None


def get_coordinates(
    location: dict[str, Any],
) -> list[dict[str, float]]:
    """
    Extract WGS84 coordinates from DATEX II posList.

    DATEX II supplies:

        latitude longitude latitude longitude ...

    The returned structure is:

        [
            {"lat": ..., "lon": ...},
            ...
        ]
    """

    try:

        pos_list = (
            location
            .get("gmlLineString", {})
            .get("locGmlLineString", {})
            .get("posList")
        )

    except AttributeError:

        return []

    if not pos_list:
        return []

    values = str(pos_list).split()

    coordinates = []

    for index in range(
        0,
        len(values) - 1,
        2,
    ):

        try:

            latitude = float(
                values[index]
            )

            longitude = float(
                values[index + 1]
            )

        except (TypeError, ValueError):

            continue

        coordinates.append(
            {
                "lat": latitude,
                "lon": longitude,
            }
        )

    return coordinates


def extract_road_from_description(
    description: str | None,
) -> str | None:
    """
    Extract a road number from a human-readable description.

    Examples:

        M6 southbound between J18 and J19
        A45 eastbound between M42 and A452
        roundabout at A616/A628
    """

    if not description:
        return None

    matches = re.findall(
        r"\b(?:M|A|B)\d+[A-Z]?\b",
        description.upper(),
    )

    if not matches:
        return None

    return matches[0]


def extract_direction_from_description(
    description: str | None,
) -> str | None:
    """
    Extract a travel direction from a human-readable description.
    """

    if not description:
        return None

    description_lower = description.lower()

    directions = (
        ("northbound", "northbound"),
        ("southbound", "southbound"),
        ("eastbound", "eastbound"),
        ("westbound", "westbound"),
    )

    for search_value, result in directions:

        if search_value in description_lower:
            return result

    return None


def get_lane_information(
    location: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract lane and carriageway information from a location.
    """

    supplementary = location.get(
        "supplementaryPositionalDescription",
        {}
    )

    carriageways = supplementary.get(
        "carriageway",
        []
    )

    result = {
        "lanes": [],
        "number_of_restricted_lanes": 0,
        "number_of_operational_lanes": None,
    }

    for carriageway_item in carriageways:

        carriageway = carriageway_item.get(
            "carriageway",
            {}
        )

        lanes = carriageway_item.get(
            "lane",
            []
        )

        for lane_item in lanes:

            lane_number = lane_item.get(
                "laneNumber"
            )

            lane_status = (
                lane_item
                .get("laneExtensionG", {})
                .get("impactOnLanes", {})
                .get("impactExtensionG", {})
                .get("lanesStatus")
            )

            result["lanes"].append(
                {
                    "number": lane_number,
                    "status": lane_status,
                }
            )

        impact = (
            carriageway_item
            .get("carriagewayExtensionG", {})
            .get("impactOnCarriageway", {})
        )

        restricted = impact.get(
            "numberOfLanesRestricted"
        )

        operational = impact.get(
            "numberOfOperationalLanes"
        )

        if restricted is not None:
            result["number_of_restricted_lanes"] += int(
                restricted
            )

        if operational is not None:
            result["number_of_operational_lanes"] = operational

    return result


def get_comments(
    management: dict[str, Any],
) -> list[str]:
    """Extract public comments."""

    comments = []

    for item in management.get(
        "generalPublicComment",
        []
    ):

        comment = item.get(
            "comment"
        )

        if comment:

            comments.append(
                str(comment).strip()
            )

    return comments


def process_record(
    situation: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    """Convert one DATEX II situation record into clean data."""

    management = get_management(
        record
    )

    validity = get_validity(
        management
    )

    validity_times = get_validity_times(
        management
    )

    locations = []

    for location in get_linear_locations(
        management
    ):

        description = get_location_description(
            location
        )

        road = get_road_name(
            location
        )

        direction = get_direction(
            location
        )

        # Fallback to the human-readable description.
        if not road:
            road = extract_road_from_description(
                description
            )

        if not direction:
            direction = extract_direction_from_description(
                description
            )

        locations.append(
            {
                "road": road,
                "direction": direction,
                "description": description,
                "coordinates": get_coordinates(
                    location
                ),
                "lane_information": get_lane_information(
                    location
                ),
            }
        )

    road = None
    direction = None
    description = None
    lane_information = {
        "lanes": [],
        "number_of_restricted_lanes": 0,
        "number_of_operational_lanes": None,
    }

    if locations:

        road = locations[0].get(
            "road"
        )

        direction = locations[0].get(
            "direction"
        )

        description = locations[0].get(
            "description"
        )

        lane_information = locations[0].get(
            "lane_information",
            lane_information,
        )

    # Final fallback from any available description.
    if not road:
        road = extract_road_from_description(
            description
        )

    if not direction:
        direction = extract_direction_from_description(
            description
        )

    cause = management.get(
        "cause",
        {}
    )

    management_type = management.get(
        "roadOrCarriagewayOrLaneManagementType",
        {}
    )

    # The ID belongs to the management object,
    # not directly to the situationRecord wrapper.
    record_id = management.get(
        "idG"
    )

    return {
        "id": record_id,

        "situation_id": situation.get(
            "idG"
        ),

        "status": validity.get(
            "validityStatus"
        ),

        "start": validity_times.get(
            "overallStartTime"
        ),

        "end": validity_times.get(
            "overallEndTime"
        ),

        "road": road,

        "direction": direction,

        "description": description,

        "type": management_type.get(
            "value"
        ),

        "cause": cause.get(
            "causeType"
        ),

        "comments": get_comments(
            management
        ),

        "locations": locations,

        "coordinates": (
            locations[0].get("coordinates", [])
            if locations
            else []
        ),

        "lanes": lane_information.get(
            "lanes",
            []
        ),

        "number_of_restricted_lanes": lane_information.get(
            "number_of_restricted_lanes",
            0
        ),

        "number_of_operational_lanes": lane_information.get(
            "number_of_operational_lanes"
        ),

        "situation_version": situation.get(
            "situationVersionTime"
        ),
    }


def process_payload(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert an entire National Highways API response into
    a list of simplified closure records.
    """

    closures = []

    for situation in get_situations(
        payload
    ):

        for record in get_records(
            situation
        ):

            closure = process_record(
                situation,
                record
            )

            closures.append(
                closure
            )

    return closures


def filter_closures(
    closures: list[dict[str, Any]],
    road: str | None = None,
    direction: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """
    Filter processed closures by road, direction and status.
    """

    filtered = closures

    if road:

        road = road.strip().upper()

        filtered = [
            closure
            for closure in filtered
            if (closure.get("road") or "").upper()
            == road
        ]

    if direction:

        direction = direction.strip().lower()

        filtered = [
            closure
            for closure in filtered
            if (closure.get("direction") or "").lower()
            == direction
        ]

    if status:

        status = status.strip().lower()

        filtered = [
            closure
            for closure in filtered
            if (closure.get("status") or "").lower()
            == status
        ]

    return filtered
