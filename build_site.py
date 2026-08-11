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
            {
                "road": "M6",
                "start": 45,
                "end": 20,
                "direction": "southbound",
            },
            {
                "road": "M62",
                "start": 10,
                "end": 8,
                "direction": "westbound",
            },
        ],
        "Northbound": [
            {
                "road": "M62",
                "start": 8,
                "end": 10,
                "direction": "eastbound",
            },
            {
                "road": "M6",
                "start": 20,
                "end": 45,
                "direction": "northbound",
            },
        ],
    },

    "Axis": {
        "Southbound": [
            {
                "road": "M6",
                "start": 45,
                "end": 26,
                "direction": "southbound",
            },
            {
                "road": "M58",
                "start": None,
                "end": None,
                "direction": "westbound",
                "entire": True,
            },
            {
                "road": "M57",
                "start": 6,
                "end": 4,
                "direction": "southbound",
            },
        ],
        "Northbound": [
            {
                "road": "M57",
                "start": 4,
                "end": 6,
                "direction": "northbound",
            },
            {
                "road": "M58",
                "start": None,
                "end": None,
                "direction": "eastbound",
                "entire": True,
            },
            {
                "road": "M6",
                "start": 26,
                "end": 45,
                "direction": "northbound",
            },
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

    Examples handled:

        M6 northbound between J18 and J19
        M62 westbound between J26 and J27
        M1 southbound within J21
        M6 northbound J45 to J20

    Returns a list of junction numbers.
    """

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
            number_match = re.match(r"\d+", match)

            if number_match:
                junctions.append(int(number_match.group()))

        except (AttributeError, ValueError):
            continue

    return junctions


# ============================================================
# DIRECTION NORMALISATION
# ============================================================

def normalise_direction(value):
    """
    Normalise API direction values so comparisons are consistent.
    """

    if not value:
        return ""

    return str(value).strip().lower()


# ============================================================
# ROUTE MATCHING
# ============================================================

def closure_matches_leg(closure, leg):
    """
    Determine whether a closure belongs to a specific route leg.

    A closure must match:

        1. Road
        2. Direction
        3. Junction boundary

    Entire-road legs, such as M58, only require road and direction.
    """

    road = str(
        closure.get("road") or ""
    ).strip().upper()

    required_road = str(
        leg.get("road") or ""
    ).strip().upper()

    if road != required_road:
        return False

    closure_direction = normalise_direction(
        closure.get("direction")
    )

    required_direction = normalise_direction(
        leg.get("direction")
    )

    if closure_direction != required_direction:
        return False

    # Entire road, such as M58
    if leg.get("entire") is True:
        return True

    description = str(
        closure.get("description") or ""
    )

    junctions = extract_junctions(description)

    if not junctions:
        return False

    start_junction = leg.get("start")
    end_junction = leg.get("end")

    if start_junction is None or end_junction is None:
        return False

    lower_bound = min(
        start_junction,
        end_junction,
    )

    upper_bound = max(
        start_junction,
        end_junction,
    )

    # A closure is relevant if at least one of its
    # referenced junctions falls inside this route leg.
    for junction in junctions:
        if lower_bound <= junction <= upper_bound:
            return True

    return False


def closure_matches_route(
    closure,
    route_name,
    direction_name,
):
    """
    Determine whether a closure belongs to the selected
    route and direction.
    """

    route = ROUTES.get(route_name)

    if not route:
        return False

    legs = route.get(direction_name)

    if not legs:
        return False

    for leg in legs:
        if closure_matches_leg(
            closure,
            leg,
        ):
            return True

    return False


# ============================================================
# ROUTE DESCRIPTION
# ============================================================

def route_description(route_name, direction_name):
    """
    Generate a human-readable description of the selected route.
    """

    route = ROUTES.get(route_name, {})
    legs = route.get(direction_name, [])

    descriptions = []

    for leg in legs:

        road = leg["road"]
        direction = leg["direction"].title()

        if leg.get("entire"):
            descriptions.append(
                f"{road} entire road {direction}"
            )
            continue

        start = leg["start"]
        end = leg["end"]

        descriptions.append(
            f"{road} J{start} → J{end} {direction}"
        )

    return " • ".join(descriptions)


# ============================================================
# BUILD PAGE
# ============================================================

def build_page(data):

    closures = data.get(
        "closures",
        [],
    )

    updated = data.get(
        "updated",
        "Unknown",
    )

    # --------------------------------------------------------
    # Pre-calculate route membership
    # --------------------------------------------------------

    route_membership = {}

    for index, closure in enumerate(closures):

        route_membership[index] = []

        for route_name in ROUTES:

            for direction_name in ROUTES[route_name]:

                if closure_matches_route(
                    closure,
                    route_name,
                    direction_name,
                ):
                    route_membership[index].append(
                        f"{route_name}:{direction_name}"
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
        closure_type = escape(
            closure_type_raw
        )
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

        memberships = ",".join(
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
                data-memberships="{escape(memberships)}"
            >

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
    # Counts
    # --------------------------------------------------------

    omega_count = sum(
        1
        for memberships in route_membership.values()
        if any(
            item.startswith("Omega:")
            for item in memberships
        )
    )

    axis_count = sum(
        1
        for memberships in route_membership.values()
        if any(
            item.startswith("Axis:")
            for item in memberships
        )
    )

    updated_display = format_datetime(
        updated
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

<title>National Highways Road Dashboard</title>

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
    padding: 10px;
    border: 1px solid #ccc;
    border-radius: 5px;
    font-size: 14px;
    background: white;
}}

.route-info {{
    margin-top: 15px;
    padding: 12px 15px;
    background: #eef5f8;
    border-left: 4px solid #003b5c;
    border-radius: 4px;
    font-size: 14px;
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

    .filter-group {{
        width: 100%;
    }}

}}

</style>

</head>

<body>

<header>

<div class="container">

<h1>National Highways Road Dashboard</h1>

<p>
Omega & Axis route monitoring
</p>

<div class="updated">
Last updated: {escape(updated_display)}
</div>

</div>

</header>


<main class="container">

<section class="filters">

<h2>Route Filters</h2>

<div class="filter-row">

<div class="filter-group">

<label for="route">
Route
</label>

<select id="route">

<option value="Omega">
Omega
</option>

<option value="Axis">
Axis
</option>

</select>

</div>


<div class="filter-group">

<label for="direction">
Direction
</label>

<select id="direction">

<option value="Southbound">
Southbound
</option>

<option value="Northbound">
Northbound
</option>

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

<option value="active">
Active
</option>

<option value="planned">
Planned
</option>

<option value="suspended">
Suspended
</option>

</select>

</div>

</div>


<div
    id="route-info"
    class="route-info"
>
{escape(route_description("Omega", "Southbound"))}
</div>

</section>


<section class="summary">

<div class="summary-card">

Total route closures

<strong id="total-count">
0
</strong>

</div>


<div class="summary-card">

Active

<strong id="active-count">
0
</strong>

</div>


<div class="summary-card">

Planned

<strong id="planned-count">
0
</strong>

</div>


<div class="summary-card">

Suspended

<strong id="suspended-count">
0
</strong>

</div>

</section>


<section
    id="closures"
    class="closures"
>

{"".join(closure_cards)}

</section>


<div
    id="empty"
    class="empty"
    style="display:none;"
>

No closures match the selected route and filters.

</div>

</main>


<script>

const ROUTE_DESCRIPTIONS = {{

    Omega: {{

        Southbound:
            "{escape(route_description('Omega', 'Southbound'))}",

        Northbound:
            "{escape(route_description('Omega', 'Northbound'))}"

    }},

    Axis: {{

        Southbound:
            "{escape(route_description('Axis', 'Southbound'))}",

        Northbound:
            "{escape(route_description('Axis', 'Northbound'))}"

    }}

}};


let selectedRoute = "Omega";

let selectedDirection = "Southbound";


const routeSelect =
    document.getElementById("route");

const directionSelect =
    document.getElementById("direction");

const statusSelect =
    document.getElementById("status");

const routeInfo =
    document.getElementById("route-info");

const closureElements =
    Array.from(
        document.querySelectorAll(".closure")
    );

const emptyMessage =
    document.getElementById("empty");


function updateDashboard() {{

    selectedRoute =
        routeSelect.value;

    selectedDirection =
        directionSelect.value;

    const selectedStatus =
        statusSelect.value;

    routeInfo.textContent =
        ROUTE_DESCRIPTIONS[selectedRoute][selectedDirection];


    let visibleCount = 0;
    let activeCount = 0;
    let plannedCount = 0;
    let suspendedCount = 0;


    const membership =
        selectedRoute + ":" + selectedDirection;


    closureElements.forEach(
        function(closure) {{

            const memberships =
                closure.dataset.memberships
                    .split(",")
                    .filter(Boolean);

            const status =
                closure.dataset.status
                    .toLowerCase();


            const matchesRoute =
                memberships.includes(
                    membership
                );


            const matchesStatus =
                !selectedStatus ||
                status === selectedStatus;


            const visible =
                matchesRoute &&
                matchesStatus;


            closure.style.display =
                visible ? "" : "none";


            if (visible) {{

                visibleCount++;


                if (status === "active") {{
                    activeCount++;
                }}

                if (status === "planned") {{
                    plannedCount++;
                }}

                if (status === "suspended") {{
                    suspendedCount++;
                }}

            }}

        }}
    );


    document.getElementById(
        "total-count"
    ).textContent = visibleCount;


    document.getElementById(
        "active-count"
    ).textContent = activeCount;


    document.getElementById(
        "planned-count"
    ).textContent = plannedCount;


    document.getElementById(
        "suspended-count"
    ).textContent = suspendedCount;


    emptyMessage.style.display =
        visibleCount === 0
            ? "block"
            : "none";

}}


routeSelect.addEventListener(
    "change",
    updateDashboard
);


directionSelect.addEventListener(
    "change",
    updateDashboard
);


statusSelect.addEventListener(
    "change",
    updateDashboard
);


updateDashboard();

</script>

</body>

</html>
"""

    # --------------------------------------------------------
    # Write output
    # --------------------------------------------------------

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

    print(
        f"Omega closures: {omega_count}"
    )

    print(
        f"Axis closures: {axis_count}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    data = load_data()

    build_page(data)
