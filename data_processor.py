from typing import Any


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
        locations.append(
            single
        )

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
            locations.append(
                location
            )

    return locations


def get_road_name(
    location: dict[str, Any],
) -> str | None:
    """Extract the road name from a linear location."""

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
            return road_name

    return None


def get_direction(
    location: dict[str, Any],
) -> str | None:
    """Extract the direction of travel."""

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
            return direction

    return None


def get_location_description(
    location: dict[str, Any],
) -> str | None:
    """Extract the human-readable location description."""

    return (
        location
        .get(
            "supplementaryPositionalDescription",
            {},
        )
        .get(
            "locationDescription"
        )
    )


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

    values = pos_list.split()

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

        except ValueError:

            continue

        coordinates.append(
            {
                "lat": latitude,
                "lon": longitude,
            }
        )

    return coordinates


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
                comment.strip()
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

        locations.append(
            {
                "road": get_road_name(
                    location
                ),
                "direction": get_direction(
                    location
                ),
                "description": get_location_description(
                    location
                ),
                "coordinates": get_coordinates(
                    location
                ),
            }
        )

    road = None
    direction = None
    description = None

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

    cause = management.get(
        "cause",
        {}
    )

    management_type = management.get(
        "roadOrCarriagewayOrLaneManagementType",
        {}
    )

    return {
        "id": record.get(
            "idG"
        ),

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
        road = road.upper()

        filtered = [
            closure
            for closure in filtered
            if (closure.get("road") or "").upper() == road
        ]

    if direction:
        direction = direction.lower()

        filtered = [
            closure
            for closure in filtered
            if (closure.get("direction") or "").lower()
            == direction
        ]

    if status:
        status = status.lower()

        filtered = [
            closure
            for closure in filtered
            if (closure.get("status") or "").lower()
            == status
        ]

    return filtered
