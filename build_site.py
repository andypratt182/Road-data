import json
import re
from pathlib import Path
from html import escape


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "road_data.json"
OUTPUT_DIR = ROOT / "site"
OUTPUT_FILE = OUTPUT_DIR / "index.html"


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
        "M58": None,          # Entire road
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
# JUNCTION PARSING
# ============================================================

def normalise_junction(value):
    """
    Convert a junction value such as J15A, 15A or j15
    into a numeric junction number where possible.
    """

    if value is None:
        return None

    match = re.search(r"\bJ?(\d+)", str(value).upper())

    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


def extract_junctions(description):
    """
    Extract junction numbers from a National Highways
    human-readable closure description.

    Examples:

        M6 northbound between J18 and J19
        M1 southbound within J21
        M57 southbound between J6 and J4
        M6 between J45 and J20
    """

    if not description:
        return []

    matches = re.findall(
        r"\bJ(\d+)(?:[A-Z])?\b",
        str(description).upper(),
    )

    junctions = []

    for value in matches:
        try:
            junctions.append(int(value))
        except ValueError:
            continue

    return junctions


# ============================================================
# ROUTE FILTERING
# ============================================================

def closure_matches_route(closure, route_name):
    """
    Determine whether a closure belongs inside one of the
    configured Omega or Axis route boundaries.

    The junctions are deliberately NOT selectable by the user.
    They are enforced internally here.
    """

    route = ROUTES.get(route_name)

    if not route:
        return False

    road = str(closure.get("road") or "").upper().strip()

    if road not in route:
        return False

    description = str(
        closure.get("description") or ""
    )

    # --------------------------------------------------------
    # Entire-road route
    # --------------------------------------------------------

    boundaries = route[road]

    if boundaries is None:
        return True

    start_junction, end_junction = boundaries

    closure_junctions = extract_junctions(
        description
    )

    if not closure_junctions:
        return False

    # --------------------------------------------------------
    # "between Jx and Jy"
    # --------------------------------------------------------

    if len(closure_junctions) >= 2:

        first = closure_junctions[0]
        second = closure_junctions[1]

        closure_high = max(first, second)
        closure_low = min(first, second)

        route_high = max(
            start_junction,
            end_junction,
        )

        route_low = min(
            start_junction,
            end_junction,
        )

        # The closure must sit completely inside the route.
        if (
            closure_high <= route_high
            and closure_low >= route_low
        ):
            return True

        # Also allow a closure which overlaps the route.
        if (
            closure_high >= route_low
            and closure_low <= route_high
        ):
            return True

        return False

    # --------------------------------------------------------
    # "within Jx"
    # --------------------------------------------------------

    junction = closure_junctions[0]

    route_high = max(
        start_junction,
        end_junction,
    )

    route_low = min(
        start_junction,
        end_junction,
    )

    return (
        route_low <= junction <= route_high
    )


def get_route_closures(closures, route_name):
    """
    Return closures belonging to the selected route.
    """

    return [
        closure
        for closure in closures
        if closure_matches_route(
            closure,
            route_name,
        )
    ]


# ============================================================
# HTML
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
    # Build closure cards
    # --------------------------------------------------------

    closure_cards = []

    for index, closure in enumerate(closures):

        road = escape(
            str(
                closure.get("road")
                or "Unknown"
            )
        )

        direction = escape(
            str(
                closure.get("direction")
                or ""
            )
        )

        status = escape(
            str(
                closure.get("status")
                or "Unknown"
            )
        )

        description = escape(
            str(
                closure.get("description")
                or ""
            )
        )

        closure_type = escape(
            str(
                closure.get("type")
                or "Unknown"
            )
        )

        cause = escape(
            str(
                closure.get("cause")
                or "Unknown"
            )
        )

        start = escape(
            str(
                closure.get("start")
                or "Unknown"
            )
        )

        end = escape(
            str(
                closure.get("end")
                or "Unknown"
            )
        )

        # Store the raw values as data attributes so the
        # JavaScript filtering can operate on them.

        raw_road = escape(
            str(
                closure.get("road")
                or ""
            )
        )

        raw_direction = escape(
            str(
                closure.get("direction")
                or ""
            )
        )

        raw_status = escape(
            str(
                closure.get("status")
                or ""
            )
        )

        raw_description = escape(
            str(
                closure.get("description")
                or ""
            )
        )

        title = road

        if direction:
            title += f" {direction}"

        closure_cards.append(
            f"""
            <article
                class="closure"
                data-index="{index}"
                data-road="{raw_road}"
                data-direction="{raw_direction}"
                data-status="{raw_status}"
                data-description="{raw_description}"
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
    # Route configuration for JavaScript
    # --------------------------------------------------------

    routes_json = json.dumps(
        ROUTES
    )

    closures_json = json.dumps(
        closures,
        ensure_ascii=False,
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

.route-description {{
    margin-top: 10px;
    padding: 12px;
    background: #eef5f8;
    border-left: 4px solid #003b5c;
    border-radius: 4px;
    font-size: 14px;
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

    <p>
        Omega &amp; Axis route monitoring
    </p>

    <div class="updated">
        Last updated: {escape(str(updated))}
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

                <option value="">
                    Select route
                </option>

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

                <option value="">
                    Select direction
                </option>

                <option value="southbound">
                    Southbound
                </option>

                <option value="northbound">
                    Northbound
                </option>

            </select>

        </div>

    </div>


    <div
        id="route-description"
        class="route-description"
    >
        Select a route and direction to display
        the relevant closures.
    </div>

</section>


<section class="summary">

    <div class="summary-card">

        Matching closures

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

</section>


<section
    id="closures"
    class="closures"
>

    <div class="empty">

        Select a route and direction above.

    </div>

</section>

</main>


<script>

const closures = {closures_json};

const routes = {routes_json};


function extractJunctions(description) {{

    if (!description) {{
        return [];
    }}

    const matches = description
        .toUpperCase()
        .match(/\\bJ(\\d+)(?:[A-Z])?\\b/g);

    if (!matches) {{
        return [];
    }}

    return matches.map(
        value => parseInt(
            value.replace(/[^0-9]/g, ""),
            10
        )
    );
}}


function closureMatchesRoute(
    closure,
    routeName
) {{

    const route = routes[routeName];

    if (!route) {{
        return false;
    }}

    const road = (
        closure.road || ""
    ).toUpperCase().trim();

    if (!Object.prototype.hasOwnProperty.call(
        route,
        road
    )) {{
        return false;
    }}

    const boundaries = route[road];

    // null means the entire road is included.
    if (boundaries === null) {{
        return true;
    }}

    const description = (
        closure.description || ""
    );

    const junctions = extractJunctions(
        description
    );

    if (!junctions.length) {{
        return false;
    }}

    const routeHigh = Math.max(
        boundaries[0],
        boundaries[1]
    );

    const routeLow = Math.min(
        boundaries[0],
        boundaries[1]
    );

    // A closure between two junctions.
    if (junctions.length >= 2) {{

        const closureHigh = Math.max(
            junctions[0],
            junctions[1]
        );

        const closureLow = Math.min(
            junctions[0],
            junctions[1]
        );

        return (
            closureHigh >= routeLow &&
            closureLow <= routeHigh
        );
    }}

    // A closure within one junction.
    const junction = junctions[0];

    return (
        junction >= routeLow &&
        junction <= routeHigh
    );
}}


function getRouteDescription(routeName) {{

    if (routeName === "Omega") {{

        return `
            <strong>Omega:</strong>
            M6 J45–J20,
            M62 J10–J8
        `;

    }}

    if (routeName === "Axis") {{

        return `
            <strong>Axis:</strong>
            M6 J45–J26,
            M58 entire road,
            M57 J6–J4
        `;

    }}

    return "Select a route and direction to display the relevant closures.";
}}


function render() {{

    const routeName =
        document.getElementById(
            "route"
        ).value;

    const direction =
        document.getElementById(
            "direction"
        ).value.toLowerCase();


    const description =
        document.getElementById(
            "route-description"
        );

    const container =
        document.getElementById(
            "closures"
        );


    if (!routeName || !direction) {{

        description.innerHTML =
            "Select a route and direction to display the relevant closures.";

        container.innerHTML = `
            <div class="empty">
                Select a route and direction above.
            </div>
        `;

        document.getElementById(
            "total-count"
        ).textContent = "0";

        document.getElementById(
            "active-count"
        ).textContent = "0";

        document.getElementById(
            "planned-count"
        ).textContent = "0";

        return;
    }}


    description.innerHTML =
        getRouteDescription(
            routeName
        );


    const filtered = closures.filter(
        closure => {{

            const closureDirection = (
                closure.direction || ""
            ).toLowerCase();

            return (
                closureDirection === direction &&
                closureMatchesRoute(
                    closure,
                    routeName
                )
            );

        }}
    );


    document.getElementById(
        "total-count"
    ).textContent =
        filtered.length;


    document.getElementById(
        "active-count"
    ).textContent =
        filtered.filter(
            closure =>
                (
                    closure.status || ""
                ).toLowerCase() === "active"
        ).length;


    document.getElementById(
        "planned-count"
    ).textContent =
        filtered.filter(
            closure =>
                (
                    closure.status || ""
                ).toLowerCase() === "planned"
        ).length;


    if (!filtered.length) {{

        container.innerHTML = `
            <div class="empty">
                No closures found for this
                route and direction.
            </div>
        `;

        return;
    }}


    container.innerHTML =
        filtered.map(
            closure => {{

                const road =
                    closure.road || "Unknown";

                const direction =
                    closure.direction || "";

                const status =
                    closure.status || "Unknown";

                const description =
                    closure.description || "";

                const type =
                    closure.type || "Unknown";

                const cause =
                    closure.cause || "Unknown";

                const start =
                    closure.start || "Unknown";

                const end =
                    closure.end || "Unknown";


                return `

                    <article class="closure">

                        <div class="closure-header">

                            <h3>
                                ${{road}}
                                ${{direction}}
                            </h3>

                            <span
                                class="status status-${{status}}"
                            >
                                ${{status}}
                            </span>

                        </div>


                        <p>
                            ${{description}}
                        </p>


                        <div class="details">

                            <div class="detail">
                                <strong>Road</strong>
                                ${{road}}
                            </div>

                            <div class="detail">
                                <strong>Direction</strong>
                                ${{direction || "Unknown"}}
                            </div>

                            <div class="detail">
                                <strong>Type</strong>
                                ${{type}}
                            </div>

                            <div class="detail">
                                <strong>Cause</strong>
                                ${{cause}}
                            </div>

                            <div class="detail">
                                <strong>Start</strong>
                                ${{start}}
                            </div>

                            <div class="detail">
                                <strong>End</strong>
                                ${{end}}
                            </div>

                        </div>

                    </article>

                `;

            }}
        ).join("");

}}


document
    .getElementById("route")
    .addEventListener(
        "change",
        render
    );


document
    .getElementById("direction")
    .addEventListener(
        "change",
        render
    );

</script>

</body>

</html>
"""

    OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        file.write(html)

    print(
        f"Generated {OUTPUT_FILE}"
    )

    print(
        f"Closures: {len(closures)}"
    )


if __name__ == "__main__":

    data = load_data()

    build_page(data)
