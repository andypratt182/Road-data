import json
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
        "M6": (45, 20),
        "M62": (10, 8),
    },
    "Axis": {
        "M6": (45, 26),
        "M58": "entire",
        "M57": (6, 4),
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
# JUNCTION FILTERING
# ============================================================

def extract_junctions(description):
    """
    Extract junction numbers from a closure description.

    Handles examples such as:

        M6 northbound between J18 and J19
        M62 eastbound between J26 and J27
        M1 southbound within J21
        M6 northbound J45 to J20

    Returns a sorted list of junction numbers.
    """

    import re

    if not description:
        return []

    matches = re.findall(
        r"\bJ(\d+[A-Z]?)\b",
        str(description),
        flags=re.IGNORECASE,
    )

    junctions = []

    for match in matches:
        try:
            number = int(re.match(r"\d+", match).group())
            junctions.append(number)
        except (AttributeError, ValueError):
            continue

    return junctions


def closure_matches_route(closure, route_name):
    """
    Determine whether a closure belongs inside one of the
    configured Omega/Axis route boundaries.
    """

    route = ROUTES.get(route_name)

    if not route:
        return False

    road = str(closure.get("road") or "").upper().strip()

    if road not in route:
        return False

    boundary = route[road]

    # Entire road, e.g. M58
    if boundary == "entire":
        return True

    start_junction, end_junction = boundary

    description = str(
        closure.get("description") or ""
    )

    junctions = extract_junctions(description)

    # If the closure has no junction information, don't
    # automatically include it in a bounded route.
    if not junctions:
        return False

    lower_bound = min(start_junction, end_junction)
    upper_bound = max(start_junction, end_junction)

    # A closure is considered relevant if any referenced
    # junction falls within the configured route.
    for junction in junctions:
        if lower_bound <= junction <= upper_bound:
            return True

    return False


# ============================================================
# BUILD PAGE
# ============================================================

def build_page(data):

    closures = data.get("closures", [])
    updated = data.get("updated", "Unknown")

    # --------------------------------------------------------
    # Route data
    # --------------------------------------------------------

    route_data = {
        "Omega": [],
        "Axis": [],
    }

    for closure in closures:

        for route_name in route_data:

            if closure_matches_route(
                closure,
                route_name,
            ):
                route_data[route_name].append(
                    closure
                )

    # --------------------------------------------------------
    # Generic filters
    # --------------------------------------------------------

    roads = sorted(
        {
            closure.get("road")
            for closure in closures
            if closure.get("road")
        }
    )

    directions = sorted(
        {
            closure.get("direction")
            for closure in closures
            if closure.get("direction")
        }
    )

    statuses = sorted(
        {
            closure.get("status")
            for closure in closures
            if closure.get("status")
        }
    )

    road_options = "".join(
        f'<option value="{escape(str(road))}">'
        f'{escape(str(road))}</option>'
        for road in roads
    )

    direction_options = "".join(
        f'<option value="{escape(str(direction))}">'
        f'{escape(str(direction))}</option>'
        for direction in directions
    )

    status_options = "".join(
        f'<option value="{escape(str(status))}">'
        f'{escape(str(status))}</option>'
        for status in statuses
    )

    # --------------------------------------------------------
    # Closure cards
    # --------------------------------------------------------

    closure_cards = []

    for index, closure in enumerate(closures):

        road_raw = str(
            closure.get("road") or "Unknown"
        )

        direction_raw = str(
            closure.get("direction") or ""
        )

        status_raw = str(
            closure.get("status") or "Unknown"
        )

        description_raw = str(
            closure.get("description") or ""
        )

        closure_type_raw = str(
            closure.get("type") or "Unknown"
        )

        cause_raw = str(
            closure.get("cause") or "Unknown"
        )

        start_raw = closure.get("start")
        end_raw = closure.get("end")

        road = escape(road_raw)
        direction = escape(direction_raw)
        status = escape(status_raw)
        description = escape(description_raw)
        closure_type = escape(closure_type_raw)
        cause = escape(cause_raw)

        start = escape(
            format_datetime(start_raw)
        )

        end = escape(
            format_datetime(end_raw)
        )

        title = road

        if direction:
            title += f" {direction}"

        matching_routes = [
            route_name
            for route_name in route_data
            if closure in route_data[route_name]
        ]

        route_attributes = ",".join(
            matching_routes
        )

        closure_cards.append(
            f"""
            <article class="closure"
                     data-index="{index}"
                     data-road="{road}"
                     data-direction="{direction}"
                     data-status="{status}"
                     data-routes="{escape(route_attributes)}">

                <div class="closure-header">

                    <h3>{title}</h3>

                    <span class="status status-{status}">
                        {status}
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
                        <strong>Type</strong>
                        {closure_type}
                    </div>

                    <div class="detail">
                        <strong>Cause</strong>
                        {cause}
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
    # Route summary counts
    # --------------------------------------------------------

    omega_count = len(route_data["Omega"])
    axis_count = len(route_data["Axis"])

    updated_display = format_datetime(updated)

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    html = f"""<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

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
    opacity: 0.9;
}}

.updated {{
    margin-top: 10px;
    font-size: 13px;
    opacity: 0.8;
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
    min-width: 180px;
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
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 15px;
}}

.route-button {{
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    background: #e8edf1;
    cursor: pointer;
    font-weight: bold;
    font-size: 14px;
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

.route-info {{
    margin-top: 10px;
    color: #555;
    font-size: 14px;
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

<p>Live road closure information</p>

<div class="updated">
Last updated: {escape(updated_display)}
</div>

</div>

</header>

<main class="container">

<div class="filters">

<h2>Routes</h2>

<div class="route-buttons">

<button class="route-button active"
        data-route="Omega">
    Omega
</button>

<button class="route-button"
        data-route="Axis">
    Axis
</button>

</div>

Then change:

let selectedRoute = "";

to:

let selectedRoute = "Omega";

That's it.

Result

When you open the site:

OMEGA is selected automatically and shows:

M6 J45 → J20
M62 J10 → J8

Clicking AXIS switches to:

M6 J45 → J26
M58 entire road
M57 J6 → J4

The Northbound/Southbound filter will continue working within whichever route you've selected.

So the dashboard becomes:

ROUTE
[ OMEGA ] [ AXIS ]

DIRECTION
[ All directions ▼ ]

STATUS
[ All statuses ▼ ]

Much cleaner.

<div class="route-info">

Omega: M6 J45–J20, M62 J10–J8

<br>

Axis: M6 J45–J26, M58 entire road, M57 J6–J4

</div>

<h2>Filters</h2>

<div class="filter-row">

<div class="filter-group">

<label for="direction">
Direction
</label>

<select id="direction">

<option value="">
All directions
</option>

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

</div>

<div class="summary">

<div class="summary-card">

Total closures

<strong id="total-count">
{len(closures)}
</strong>

</div>

<div class="summary-card">

Omega

<strong id="omega-count">
{omega_count}
</strong>

</div>

<div class="summary-card">

Axis

<strong id="axis-count">
{axis_count}
</strong>

</div>

<div class="summary-card">

Visible

<strong id="visible-count">
{len(closures)}
</strong>

</div>

</div>

<div id="closures"
     class="closures">

{"".join(closure_cards)}

</div>

<div id="empty"
     class="empty"
     style="display:none;">

No closures match the selected filters.

</div>

</main>

<script>

const closures = Array.from(
    document.querySelectorAll(".closure")
);

const routeButtons = Array.from(
    document.querySelectorAll(".route-button")
);

const directionSelect =
    document.getElementById("direction");

const statusSelect =
    document.getElementById("status");

const visibleCount =
    document.getElementById("visible-count");

let selectedRoute = "Omega";

function updateFilters() {{

    const direction =
        directionSelect.value.toLowerCase();

    const status =
        statusSelect.value.toLowerCase();

    let visible = 0;

    closures.forEach(closure => {{

        const closureDirection =
            (
                closure.dataset.direction || ""
            ).toLowerCase();

        const closureStatus =
            (
                closure.dataset.status || ""
            ).toLowerCase();

        const routes =
            (
                closure.dataset.routes || ""
            ).split(",");

        const routeMatch =
            !selectedRoute ||
            routes.includes(selectedRoute);

        const directionMatch =
            !direction ||
            closureDirection === direction;

        const statusMatch =
            !status ||
            closureStatus === status;

        const show =
            routeMatch &&
            directionMatch &&
            statusMatch;

        closure.style.display =
            show ? "" : "block";

        if (!show) {{
            closure.style.display = "none";
        }}

        if (show) {{
            visible++;
        }}

    }});

    visibleCount.textContent = visible;

    document.getElementById("empty").style.display =
        visible === 0 ? "block" : "none";
}}

routeButtons.forEach(button => {{

    button.addEventListener("click", () => {{

        routeButtons.forEach(
            item => item.classList.remove("active")
        );

        button.classList.add("active");

        selectedRoute =
            button.dataset.route || "";

        updateFilters();

    }});

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

    OUTPUT_DIR.mkdir(exist_ok=True)

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

    print(
        f"Omega: {omega_count}"
    )

    print(
        f"Axis: {axis_count}"
    )


if __name__ == "__main__":
    data = load_data()
    build_page(data)
