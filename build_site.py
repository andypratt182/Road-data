import json
import re
from pathlib import Path
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "road_data.json"
OUTPUT_DIR = ROOT / "site"
OUTPUT_FILE = OUTPUT_DIR / "index.html"

UK_TZ = ZoneInfo("Europe/London")


# ============================================================
# ROUTE DEFINITIONS
# ============================================================

ROUTES = {
    "Omega": {
        "Southbound": [
            ("M6", 45, 21),
            ("M62", 10, 8),
        ],
        "Northbound": [
            ("M62", 8, 10),
            ("M6", 21, 45),
        ],
    },

    "Axis": {
        "Southbound": [
            ("M6", 45, 26),
            ("M58", "entire", "entire"),
            ("M57", 6, 4),
        ],
        "Northbound": [
            ("M57", 4, 6),
            ("M58", "entire", "entire"),
            ("M6", 26, 45),
        ],
    },
}


# ============================================================
# DATA
# ============================================================

def load_data():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# TIME FORMATTING
# ============================================================

def format_datetime(value):
    """
    Convert an API ISO timestamp into a user-friendly UK time.

    Example:
        2026-08-11T14:54:52.52Z
        -> 11 Aug 2026, 15:54
    """

    if not value:
        return "Unknown"

    try:
        timestamp = str(value).strip()

        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"

        dt = datetime.fromisoformat(timestamp)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))

        dt = dt.astimezone(UK_TZ)

        return dt.strftime("%d %b %Y, %H:%M")

    except (ValueError, TypeError):
        return str(value)


# ============================================================
# JUNCTION EXTRACTION
# ============================================================

def extract_junctions(description):
    """
    Extract junction numbers from a closure description.

    Handles:
        J20
        J21
        J21A
        J29a

    Returns a list of tuples:
        [(21, ""), (21, "A")]
    """

    if not description:
        return []

    matches = re.findall(
        r"\bJ(\d+)([A-Z]?)\b",
        str(description),
        flags=re.IGNORECASE,
    )

    junctions = []

    for number, suffix in matches:
        try:
            junctions.append(
                (
                    int(number),
                    suffix.upper(),
                )
            )
        except ValueError:
            continue

    return junctions


def junction_value(junction):
    """
    Convert a junction tuple into a sortable numeric value.

    J21  -> 21.0
    J21A -> 21.1

    This means J21 comes before J21A.
    """

    number, suffix = junction

    if suffix:
        return float(f"{number}.1")

    return float(number)


# ============================================================
# FRIENDLY RESTRICTION TYPE
# ============================================================

def get_restriction_type(closure):
    """
    Convert National Highways API type/cause values into
    user-friendly terminology.

    Raw API values remain available separately.
    """

    raw_type = str(
        closure.get("type") or ""
    ).strip()

    raw_cause = str(
        closure.get("cause") or ""
    ).strip()

    if raw_type == "carriagewayClosures":
        return "Carriageway Closure"

    if raw_type.lower() == "other":

        if raw_cause == "roadMaintenance":
            return "Road Maintenance"

        if raw_cause == "constructionWork":
            return "Construction"

        if raw_cause == "authorityOperation":
            return "Authority Operation"

        return "Other"

    return raw_type or "Other"


# ============================================================
# ROUTE MATCHING
# ============================================================

def closure_matches_route(
    closure,
    route_name,
    direction_name,
):
    """
    Determine whether a closure belongs to a specific
    Omega/Axis directional route.

    A closure is included when:

    1. The road matches the route.
    2. The direction matches the configured direction.
    3. Its junction information falls inside the configured
       route boundary.

    For entire-road sections such as M58, the direction must
    still match.
    """

    route = ROUTES.get(route_name, {})
    sections = route.get(direction_name, [])

    if not sections:
        return False

    road = str(
        closure.get("road") or ""
    ).upper().strip()

    closure_direction = str(
        closure.get("direction") or ""
    ).lower().strip()

    description = str(
        closure.get("description") or ""
    )

    junctions = extract_junctions(
        description
    )

    for section_road, start, end in sections:

        if road != section_road:
            continue

        # ----------------------------------------------------
        # M58 entire road
        # ----------------------------------------------------

        if start == "entire":
            if direction_name == "Southbound":
                return closure_direction == "westbound"

            if direction_name == "Northbound":
                return closure_direction == "eastbound"

        # ----------------------------------------------------
        # Direction mapping
        # ----------------------------------------------------

        expected_direction = None

        if direction_name == "Southbound":

            if section_road == "M6":
                expected_direction = "southbound"

            elif section_road == "M62":
                expected_direction = "westbound"

            elif section_road == "M57":
                expected_direction = "southbound"

        elif direction_name == "Northbound":

            if section_road == "M6":
                expected_direction = "northbound"

            elif section_road == "M62":
                expected_direction = "eastbound"

            elif section_road == "M57":
                expected_direction = "northbound"

        if (
            expected_direction
            and closure_direction != expected_direction
        ):
            continue

        if not junctions:
            continue

        lower = min(
            float(start),
            float(end),
        )

        upper = max(
            float(start),
            float(end),
        )

        for junction in junctions:

            value = junction_value(
                junction
            )

            if lower <= value <= upper:
                return True

    return False


# ============================================================
# JUNCTION POSITION FOR SORTING
# ============================================================

def get_route_sort_value(
    closure,
    route_name,
    direction_name,
):
    """
    Return the junction position used to order closures
    along the selected route.

    The ordering follows the actual direction of travel.

    Example:

        Omega Southbound M6 J45 -> J21

        J45
        J40
        J30
        J21

    Omega Northbound M6 J21 -> J45

        J21
        J30
        J40
        J45
    """

    road = str(
        closure.get("road") or ""
    ).upper().strip()

    description = str(
        closure.get("description") or ""
    )

    junctions = extract_junctions(
        description
    )

    if not junctions:
        return 9999

    values = [
        junction_value(junction)
        for junction in junctions
    ]

    route = ROUTES.get(
        route_name,
        {}
    )

    sections = route.get(
        direction_name,
        []
    )

    for section_road, start, end in sections:

        if road != section_road:
            continue

        if start == "entire":
            return 5000

        if direction_name == "Southbound":
            return -max(values)

        return min(values)

    return 9999


# ============================================================
# BUILD PAGE
# ============================================================

def build_page(data):

    closures = data.get(
        "closures",
        []
    )

    updated = data.get(
        "updated",
        "Unknown"
    )

    # --------------------------------------------------------
    # Determine route membership
    # --------------------------------------------------------

    route_membership = {}

    for index, closure in enumerate(
        closures
    ):

        route_membership[index] = []

        for route_name in ROUTES:

            for direction_name in ROUTES[
                route_name
            ]:

                if closure_matches_route(
                    closure,
                    route_name,
                    direction_name,
                ):

                    route_membership[
                        index
                    ].append(
                        f"{route_name}:{direction_name}"
                    )

    # --------------------------------------------------------
    # Direction options
    # --------------------------------------------------------

    direction_options = """
        <option value="">All directions</option>
        <option value="Northbound">Northbound</option>
        <option value="Southbound">Southbound</option>
    """

    # --------------------------------------------------------
    # Status options
    # --------------------------------------------------------

    statuses = sorted(
        {
            str(
                closure.get(
                    "status"
                )
                or ""
            )
            for closure in closures
            if closure.get("status")
        }
    )

    status_options = "".join(
        f'<option value="{escape(status)}">'
        f'{escape(status.title())}'
        f'</option>'
        for status in statuses
    )

    # --------------------------------------------------------
    # Closure cards
    # --------------------------------------------------------

    closure_cards = []

    for index, closure in enumerate(
        closures
    ):

        road_raw = str(
            closure.get("road")
            or "Unknown"
        )

        direction_raw = str(
            closure.get("direction")
            or ""
        )

        status_raw = str(
            closure.get("status")
            or "Unknown"
        )

        description_raw = str(
            closure.get("description")
            or ""
        )

        raw_type = str(
            closure.get("type")
            or "Unknown"
        )

        raw_cause = str(
            closure.get("cause")
            or "Unknown"
        )

        friendly_type = get_restriction_type(
            closure
        )

        start_raw = closure.get(
            "start"
        )

        end_raw = closure.get(
            "end"
        )

        road = escape(
            road_raw
        )

        direction = escape(
            direction_raw
        )

        status = escape(
            status_raw
        )

        description = escape(
            description_raw
        )

        friendly_type_html = escape(
            friendly_type
        )

        raw_type_html = escape(
            raw_type
        )

        raw_cause_html = escape(
            raw_cause
        )

        start = escape(
            format_datetime(
                start_raw
            )
        )

        end = escape(
            format_datetime(
                end_raw
            )
        )

        title = road

        if direction:
            title += f" {direction}"

        route_attributes = ",".join(
            route_membership[index]
        )

        closure_cards.append(
            f"""
            <article
                class="closure"
                data-index="{index}"
                data-road="{road}"
                data-direction="{direction}"
                data-status="{status}"
                data-routes="{escape(route_attributes)}"
            >

                <div class="closure-header">

                    <h3>{title}</h3>

                    <span class="status status-{status}">
                        {escape(status_raw.title())}
                    </span>

                </div>

                <p>{description}</p>

                <div class="details">

                    <div class="detail">
                        <strong>Road</strong>
                        {road}
                    </div>

                    <div class="detail">
                        <strong>Direction</strong>
                        {direction or "Unknown"}
                    </div>

                    <div class="detail">
                        <strong>Restriction Type</strong>
                        {friendly_type_html}
                    </div>

                    <div class="detail">
                        <strong>Cause</strong>
                        {raw_cause_html}
                    </div>

                    <div class="detail">
                        <strong>Raw Type</strong>
                        {raw_type_html}
                    </div>

                    <div class="detail">
                        <strong>Raw Cause</strong>
                        {raw_cause_html}
                    </div>

                    <div class="detail">
                        <strong>Start</strong>
                        {start}
                    </div>

                    <div class="detail">
                        <strong>End</strong>
                        {end}
                    </div>

                </div>

            </article>
            """
        )

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    html = f"""<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>National Highways Road Data</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    font-family: Arial, sans-serif;
    margin: 0;
    background: #f4f6f8;
    color: #222;
}}

header {{
    background: #003b5c;
    color: white;
    padding: 25px 20px;
}}

.container {{
    max-width: 1400px;
    margin: auto;
    padding: 0 20px;
}}

header h1 {{
    margin: 0 0 5px;
}}

header p {{
    margin: 0;
    opacity: .9;
}}

.updated {{
    margin-top: 10px;
    font-size: 13px;
    opacity: .8;
}}

.filters {{
    background: white;
    padding: 20px;
    margin: 20px 0;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,.08);
}}

.filter-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
}}

.filter-group {{
    display: flex;
    flex-direction: column;
    min-width: 200px;
}}

label {{
    font-weight: bold;
    margin-bottom: 5px;
}}

select {{
    padding: 9px;
    border: 1px solid #ccc;
    border-radius: 5px;
    font-size: 14px;
}}

.route-buttons {{
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
}}

.route-button {{
    padding: 10px 22px;
    border: 0;
    border-radius: 6px;
    background: #d9e1e6;
    cursor: pointer;
    font-weight: bold;
}}

.route-button.active {{
    background: #003b5c;
    color: white;
}}

.summary {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(180px, 1fr));
    gap: 15px;
    margin-bottom: 20px;
}}

.summary-card {{
    background: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 6px rgba(0,0,0,.08);
}}

.summary-card strong {{
    display: block;
    font-size: 28px;
    margin-top: 5px;
}}

.closures {{
    display: grid;
    gap: 15px;
    padding-bottom: 30px;
}}

.closure {{
    background: white;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 6px rgba(0,0,0,.08);
}}

.closure-header {{
    display: flex;
    justify-content: space-between;
    gap: 15px;
    align-items: center;
}}

.closure-header h3 {{
    margin: 0;
}}

.status {{
    padding: 5px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: bold;
    text-transform: uppercase;
}}

.status-active {{
    background: #ffdede;
    color: #a00000;
}}

.status-planned {{
    background: #fff1c7;
    color: #795900;
}}

.status-suspended {{
    background: #e5e5e5;
    color: #555;
}}

.details {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
    margin-top: 15px;
}}

.detail {{
    background: #f7f8fa;
    padding: 10px;
    border-radius: 5px;
}}

.detail strong {{
    display: block;
    margin-bottom: 3px;
}}

.empty {{
    background: white;
    padding: 30px;
    text-align: center;
    border-radius: 8px;
}}

@media (max-width: 600px) {{

    .container {{
        padding: 0 10px;
    }}

    .closure-header {{
        flex-direction: column;
        align-items: flex-start;
    }}

}}

</style>

</head>

<body>

<header>

<div class="container">

<h1>National Highways Road Data</h1>

<p>Omega & Axis route monitoring dashboard</p>

<div class="updated">
Last updated: {escape(updated_display := format_datetime(updated))}
</div>

</div>

</header>

<main class="container">

<section class="filters">

<h2>Route</h2>

<div class="route-buttons">

<button
    class="route-button active"
    data-route="Omega"
>
    OMEGA
</button>

<button
    class="route-button"
    data-route="Axis"
>
    AXIS
</button>

</div>

<div class="filter-row">

<div class="filter-group">

<label for="direction">
Direction
</label>

<select id="direction">

{direction_options}

</select>

</div>

<div class="filter-group">

<label for="status">
Status
</label>

<select id="status">

<option value="">
All statuses
</option>

{status_options}

</select>

</div>

</div>

</section>

<section class="summary">

<div class="summary-card">

Total closures

<strong id="total-count">
0
</strong>

</div>

<div class="summary-card">

Omega

<strong id="omega-count">
{sum(
    1
    for routes in route_membership.values()
    if any(
        r.startswith("Omega:")
        for r in routes
    )
)}
</strong>

</div>

<div class="summary-card">

Axis

<strong id="axis-count">
{sum(
    1
    for routes in route_membership.values()
    if any(
        r.startswith("Axis:")
        for r in routes
    )
)}
</strong>

</div>

<div class="summary-card">

Visible

<strong id="visible-count">
0
</strong>

</div>

</section>

<section
    class="closures"
    id="closures"
>

{"".join(closure_cards)}

</section>

<div
    class="empty"
    id="empty"
    style="display:none;"
>

No closures match the selected filters.

</div>

</main>

<script>

let selectedRoute = "Omega";

const routeButtons =
    document.querySelectorAll(
        ".route-button"
    );

const directionSelect =
    document.getElementById(
        "direction"
    );

const statusSelect =
    document.getElementById(
        "status"
    );

const cards =
    document.querySelectorAll(
        ".closure"
    );

const totalCount =
    document.getElementById(
        "total-count"
    );

const visibleCount =
    document.getElementById(
        "visible-count"
    );

const empty =
    document.getElementById(
        "empty"
    );


function updateFilters() {{

    const direction =
        directionSelect.value;

    const status =
        statusSelect.value;

    let visible = [];

    cards.forEach(card => {{

        const routes =
            card.dataset.routes
                .split(",")
                .filter(Boolean);

        const roadDirection =
            direction
                ? selectedRoute + ":" + direction
                : null;

        const routeMatch =
            roadDirection
                ? routes.includes(
                    roadDirection
                  )
                : routes.some(
                    route =>
                        route.startsWith(
                            selectedRoute + ":"
                        )
                  );

        const statusMatch =
            !status ||
            card.dataset.status === status;

        const show =
            routeMatch &&
            statusMatch;

        card.style.display =
            show ? "" : "none";

        if (show) {{
            visible.push(card);
        }}

    }});

    // --------------------------------------------------------
    // Sort visible records by route order
    // --------------------------------------------------------

    visible.sort((a, b) => {{

        const aIndex =
            parseInt(
                a.dataset.index,
                10
            );

        const bIndex =
            parseInt(
                b.dataset.index,
                10
            );

        return aIndex - bIndex;

    }});

    const container =
        document.getElementById(
            "closures"
        );

    visible.forEach(card =>
        container.appendChild(card)
    );

    totalCount.textContent =
        cards.length;

    visibleCount.textContent =
        visible.length;

    empty.style.display =
        visible.length
            ? "none"
            : "block";

}}


routeButtons.forEach(button => {{

    button.addEventListener(
        "click",
        () => {{

            selectedRoute =
                button.dataset.route;

            routeButtons.forEach(
                item =>
                    item.classList.remove(
                        "active"
                    )
            );

            button.classList.add(
                "active"
            );

            updateFilters();

        }}
    );

}});


directionSelect.addEventListener(
    "change",
    updateFilters
);

statusSelect.addEventListener(
    "change",
    updateFilters
);


updateFilters();

</script>

</body>

</html>
"""

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        file.write(html)

    print(
        f"Generated {OUTPUT_FILE}"
    )

    print(
        f"Closures: {len(closures)}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    data = load_data()

    build_page(data)
