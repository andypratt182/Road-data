from typing import Any
import re


def get_situations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the situations contained in a National Highways response."""
    return payload.get("D2Payload", {}).get("situation", [])


def get_records(situation: dict[str, Any]) -> list[dict[str, Any]]:
    """Return situation records from a situation."""
    return situation.get("situationRecord", [])


def get_management(record: dict[str, Any]) -> dict[str, Any]:
    """Return the road/carriageway/lane management object."""
    return record.get("sitRoadOrCarriagewayOrLaneManagement", {})


def get_validity(management: dict[str, Any]) -> dict[str, Any]:
    """Return validity information."""
    return management.get("validity", {})


def get_validity_times(management: dict[str, Any]) -> dict[str, Any]:
    """Return the validity time specification."""
    return get_validity(management).get("validityTimeSpecification", {})


def get_location_reference(management: dict[str, Any]) -> dict[str, Any]:
    """Return the DATEX II location reference."""
    return management.get("locationReference", {})


def get_linear_locations(management: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return all DATEX II linear locations.

    National Highways can place locations inside
    locLocationGroupByList.locationContainedInGroup rather
    than directly under locationReference.
    """
    location_reference = get_location_reference(management)

    locations: list[dict[str, Any]] = []

    direct_location = location_reference.get("locLinearLocation")
    if direct_location:
        locations.append(direct_location)

    grouped_locations = (
        location_reference
        .get("locLocationGroupByList", {})
        .get("locationContainedInGroup", [])
    )

    for item in grouped_locations:
        location = item.get("locLinearLocation")
        if location:
            locations.append(location)

    return locations


def get_road_name(location: dict[str, Any]) -> str | None:
    """Extract the road name from a DATEX II linear location."""
    sections = (
        location
        .get("locSingleRoadLinearLocation", {})
        .get("linearWithinLinearElement", [])
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


def get_direction(location: dict[str, Any]) -> str | None:
    """Extract the direction from a DATEX II linear location."""
    sections = (
        location
        .get("locSingleRoadLinearLocation", {})
        .get("linearWithinLinearElement", [])
    )

    for section in sections:
        direction = section.get("directionOnLinearSection")

        if direction:
            return str(direction).strip()

    return None


def get_location_description(location: dict[str, Any]) -> str | None:
    """Extract the human-readable location description."""
    description = (
        location
        .get("supplementaryPositionalDescription", {})
        .get("locationDescription")
    )

    if description:
        return str(description).strip()

    return None


def get_coordinates(location: dict[str, Any]) -> list[dict[str, float]]:
    """Extract WGS84 coordinates from a DATEX II posList."""
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

    coordinates: list[dict[str, float]] = []

    for index in range(0, len(values) - 1, 2):
        try:
            coordinates.append(
                {
                    "lat": float(values[index]),
                    "lon": float(values[index + 1]),
                }
            )
        except (TypeError, ValueError):
            continue

    return coordinates


def extract_roads_from_text(text: str | None) -> list[str]:
    """
    Extract UK road identifiers from free text.

    Handles M roads, A roads and B roads, for example:
    M56, M62, A45, A616, A628, B6105.
    """
    if not text:
        return []

    matches = re.findall(
        r"\b(?:M|A|B)\d+[A-Z]?\b",
        str(text).upper(),
    )

    roads: list[str] = []

    for road in matches:
        if road not in roads:
            roads.append(road)

    return roads


def extract_road_from_description(
    description: str | None,
) -> str | None:
    """Extract the first road number from a description."""
    roads = extract_roads_from_text(description)

    return roads[0] if roads else None


def extract_direction_from_description(
    description: str | None,
) -> str | None:
    """Extract a travel direction from free text."""
    if not description:
        return None

    text = str(description).lower()

    for direction in (
        "northbound",
        "southbound",
        "eastbound",
        "westbound",
    ):
        if direction in text:
            return direction

    return None


def extract_directions_from_text(
    text: str | None,
) -> list[str]:
    """Extract all travel directions mentioned in free text."""
    if not text:
        return []

    text = str(text).lower()

    directions: list[str] = []

    for direction in (
        "northbound",
        "southbound",
        "eastbound",
        "westbound",
    ):
        if direction in text:
            directions.append(direction)

    return directions


def get_lane_information(
    location: dict[str, Any],
) -> dict[str, Any]:
    """Extract lane and carriageway restriction information."""
    supplementary = location.get(
        "supplementaryPositionalDescription",
        {},
    )

    carriageways = supplementary.get("carriageway", [])

    result: dict[str, Any] = {
        "lanes": [],
        "number_of_restricted_lanes": 0,
        "number_of_operational_lanes": None,
    }

    for carriageway_item in carriageways:

        lanes = carriageway_item.get("lane", [])

        for lane_item in lanes:

            lane_number = lane_item.get("laneNumber")

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
            try:
                result["number_of_restricted_lanes"] += int(
                    restricted
                )
            except (TypeError, ValueError):
                pass

        if operational is not None:
            result["number_of_operational_lanes"] = operational

    return result


def get_carriageway_information(
    location: dict[str, Any],
) -> dict[str, Any]:
    """Extract carriageway classification."""
    carriageways = (
        location
        .get("supplementaryPositionalDescription", {})
        .get("carriageway", [])
    )

    values: list[str] = []
    extended_values: list[str] = []

    for item in carriageways:

        carriageway = item.get(
            "carriageway",
            {},
        )

        value = carriageway.get("value")
        extended_value = carriageway.get(
            "extendedValueG"
        )

        if value and value not in values:
            values.append(str(value))

        if (
            extended_value
            and extended_value not in extended_values
        ):
            extended_values.append(
                str(extended_value)
            )

    return {
        "values": values,
        "extended_values": extended_values,
    }


def get_comments(
    management: dict[str, Any],
) -> list[str]:
    """Extract general public comments."""
    comments: list[str] = []

    for item in management.get(
        "generalPublicComment",
        [],
    ):

        comment = item.get("comment")

        if comment:
            comments.append(
                str(comment).strip()
            )

    return comments


def process_record(
    situation: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert one DATEX II situation record into
    the application's normalised representation.
    """

    management = get_management(record)

    validity = get_validity(management)

    validity_times = get_validity_times(
        management
    )

    comments = get_comments(
        management
    )

    locations: list[dict[str, Any]] = []

    for location in get_linear_locations(
        management
    ):

        description = get_location_description(
            location
        )

        road = (
            get_road_name(location)
            or extract_road_from_description(
                description
            )
        )

        direction = (
            get_direction(location)
            or extract_direction_from_description(
                description
            )
        )

        locations.append(
            {
                "road": road,
                "direction": direction,
                "description": description,
                "coordinates": get_coordinates(
                    location
                ),
                "lane_information":
                    get_lane_information(
                        location
                    ),
                "carriageway_information":
                    get_carriageway_information(
                        location
                    ),
            }
        )

    # --------------------------------------------------------
    # Aggregate information from ALL locations.
    # --------------------------------------------------------

    roads: list[str] = []
    directions: list[str] = []
    descriptions: list[str] = []

    total_restricted_lanes = 0

    operational_values: list[int] = []

    all_lanes: list[dict[str, Any]] = []

    all_coordinates: list[
        dict[str, float]
    ] = []

    for location in locations:

        road = location.get("road")

        direction = location.get(
            "direction"
        )

        description = location.get(
            "description"
        )

        if road and road not in roads:
            roads.append(road)

        if (
            direction
            and direction not in directions
        ):
            directions.append(
                direction
            )

        if (
            description
            and description not in descriptions
        ):
            descriptions.append(
                description
            )

        lane_information = location.get(
            "lane_information",
            {},
        )

        total_restricted_lanes += int(
            lane_information.get(
                "number_of_restricted_lanes"
            )
            or 0
        )

        operational = lane_information.get(
            "number_of_operational_lanes"
        )

        if operational is not None:
            try:
                operational_values.append(
                    int(operational)
                )
            except (
                TypeError,
                ValueError,
            ):
                pass

        all_lanes.extend(
            lane_information.get(
                "lanes",
                [],
            )
        )

        all_coordinates.extend(
            location.get(
                "coordinates",
                [],
            )
        )

    # --------------------------------------------------------
    # IMPORTANT FALLBACK
    #
    # Some National Highways records have no usable
    # structured linear location, but the public comment
    # still identifies the road and direction.
    #
    # Example from Test 5:
    #
    # "M56 Westbound Jct 14 entry slip road closure"
    #
    # Therefore use the public comment as the final
    # fallback rather than returning an unidentified record.
    # --------------------------------------------------------

    comment_text = " ".join(
        comments
    )

    comment_roads = extract_roads_from_text(
        comment_text
    )

    for road in comment_roads:

        if road not in roads:
            roads.append(road)

    comment_directions = (
        extract_directions_from_text(
            comment_text
        )
    )

    for direction in comment_directions:

        if direction not in directions:
            directions.append(
                direction
            )

    # --------------------------------------------------------
    # Primary compatibility fields.
    #
    # Existing code can continue using:
    #   road
    #   direction
    #
    # while the new fields:
    #   roads
    #   directions
    #
    # preserve the complete information.
    # --------------------------------------------------------

    primary_road = (
        roads[0]
        if roads
        else None
    )

    primary_direction = (
        directions[0]
        if directions
        else None
    )

    primary_description = (
        descriptions[0]
        if descriptions
        else None
    )

    cause = management.get(
        "cause",
        {},
    )

    management_type = management.get(
        "roadOrCarriagewayOrLaneManagementType",
        {},
    )

    extension = management.get(
        "roadOrCarriagewayOrLaneManagementExtensionG",
        {},
    )

    return {
        # ----------------------------------------------------
        # Identity
        # ----------------------------------------------------

        "id": management.get(
            "idG"
        ),

        "version": management.get(
            "versionG"
        ),

        "situation_id": situation.get(
            "idG"
        ),

        # ----------------------------------------------------
        # Validity
        # ----------------------------------------------------

        "status": validity.get(
            "validityStatus"
        ),

        "start": validity_times.get(
            "overallStartTime"
        ),

        "end": validity_times.get(
            "overallEndTime"
        ),

        # ----------------------------------------------------
        # Road / direction
        # ----------------------------------------------------

        "road": primary_road,

        "roads": roads,

        "direction": primary_direction,

        "directions": directions,

        # ----------------------------------------------------
        # Description / comments
        # ----------------------------------------------------

        "description": primary_description,

        "descriptions": descriptions,

        "comments": comments,

        # ----------------------------------------------------
        # Event classification
        # ----------------------------------------------------

        "type": management_type.get(
            "value"
        ),

        "cause": cause.get(
            "causeType"
        ),

        # ----------------------------------------------------
        # Complete location information
        # ----------------------------------------------------

        "locations": locations,

        "coordinates": all_coordinates,

        # ----------------------------------------------------
        # Lane information
        # ----------------------------------------------------

        "lanes": all_lanes,

        "number_of_restricted_lanes":
            total_restricted_lanes,

        "number_of_operational_lanes": (
            operational_values[0]
            if operational_values
            else None
        ),

        # ----------------------------------------------------
        # Restriction flags
        # ----------------------------------------------------

        "width_restriction": bool(
            extension.get(
                "hasWidthRestrictionFlag",
                False,
            )
        ),

        "height_restriction": bool(
            extension.get(
                "hasHeightRestrictionFlag",
                False,
            )
        ),

        "weight_restriction": bool(
            extension.get(
                "hasWeightRestrictionFlag",
                False,
            )
        ),

        "contra_flow": bool(
            extension.get(
                "hasContraFlow",
                False,
            )
        ),

        # ----------------------------------------------------
        # Situation metadata
        # ----------------------------------------------------

        "situation_version":
            situation.get(
                "situationVersionTime"
            ),
    }


def process_payload(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Convert the complete National Highways
    API response into normalised records.
    """

    closures: list[
        dict[str, Any]
    ] = []

    for situation in get_situations(
        payload
    ):

        for record in get_records(
            situation
        ):

            closures.append(
                process_record(
                    situation,
                    record,
                )
            )

    return closures


def filter_closures(
    closures: list[dict[str, Any]],
    road: str | None = None,
    direction: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """
    Filter processed closures.

    Road and direction filtering now searches the
    complete aggregated lists rather than only the
    first location.
    """

    filtered = closures

    if road:

        road = road.strip().upper()

        filtered = [
            closure
            for closure in filtered
            if road in [
                value.upper()
                for value in closure.get(
                    "roads",
                    [],
                )
            ]
            or (
                closure.get("road")
                or ""
            ).upper() == road
        ]

    if direction:

        direction = (
            direction
            .strip()
            .lower()
        )

        filtered = [
            closure
            for closure in filtered
            if direction in [
                value.lower()
                for value in closure.get(
                    "directions",
                    [],
                )
            ]
            or (
                closure.get(
                    "direction"
                )
                or ""
            ).lower() == direction
        ]

    if status:

        status = (
            status
            .strip()
            .lower()
        )

        filtered = [
            closure
            for closure in filtered
            if (
                closure.get(
                    "status"
                )
                or ""
            ).lower() == status
        ]

    return filtered
