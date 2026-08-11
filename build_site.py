import json
from pathlib import Path
from html import escape


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "road_data.json"
OUTPUT_DIR = ROOT / "site"
OUTPUT_FILE = OUTPUT_DIR / "index.html"


# ============================================================
# ROUTE CONFIGURATION
# ============================================================

ROUTES = {
    "Omega": ["M6", "M62"],
    "Axis": ["M6", "M58", "M57"],
}

DIRECTIONS = {
    "Northbound": "northbound",
    "Southbound": "southbound",
}


# ============================================================
# DATA
# ============================================================

def load_data():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def route_for_closure(closure):
    """
    Determine which configured route a closure belongs to.

    A closure can belong to more than one route because M6 is
    shared by Omega and Axis.
    """
    road = str(closure.get("road") or "").upper()

    matches = []

    for route_name, roads in ROUTES.items():
        if road in roads:
            matches.append(route_name)

    return matches


# ============================================================
# PAGE GENERATION
# ============================================================

def build_page(data):
    closures = data.get("closures", [])
    updated = data.get("updated", "Unknown")

    closure_cards = []

    for closure in closures:
        raw_road = str(closure.get("road") or "")
        raw_direction = str(closure.get("direction") or "")
        raw_status = str(closure.get("status") or "Unknown")

        road = escape(raw_road)
        direction = escape(raw_direction)
        status = escape(raw_status)

        description = escape(
            str(closure.get("description") or "")
        )

        closure_type = escape(
            str(closure.get("type") or "Unknown")
        )

        cause = escape(
            str(closure.get("cause") or "Unknown")
        )

        start = escape(
            str(closure.get("start") or "Unknown")
        )

        end = escape(
            str(closure.get("end") or "Unknown")
        )

        # Determine configured routes.
        routes = route_for_closure(closure)

        # Store route names as a data attribute so JavaScript
        # can filter the card.
        route_data = ",".join(routes)

        # Road order is handled in JavaScript using the route
        # definitions below.
        closure_cards.append(
            f"""
            <article
                class="closure"
                data-road="{road}"
                data-direction="{direction}"
                data-status="{status}"
                data-routes="{escape(route_data)}"
            >

                <div class="closure-header">

                    <div>
                        <h3>{road}</h3>

                        <div class="route-label">
                            {direction or "Direction unknown"}
                        </div>
                    </div>

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

    route_options = "".join(
        f'<option value="{escape(route)}">'
        f'{escape(route)}'
        f'</option>'
        for route in ROUTES
    )

    direction_options = "".join(
        f'<option value="{escape(value)}">'
        f'{escape(name)}'
        f'</option>'
        for name, value in DIRECTIONS.items()
    )

    route_config_js = json.dumps(ROUTES)

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

.filters h2 {{
    margin-top: 0;
}}

.filter-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
}}

.filter-group {{
    display: flex;
    flex-direction: column;
    min-width: 220px;
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
    margin: 0 0 5px;
    font-size: 20px;
}}

.route-label {{
    color: #666;
    font-size: 14px;
    text-transform: capitalize;
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

.route-description {{
    margin-top: 8px;
    color: #666;
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

<h2>Route filters</h2>

<div class="filter-row">

<div class="filter-group">

<label for="route">
Route
</label>

<select id="route">

<option value="">
Select route
</option>

{route_options}

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

{direction_options}

</select>

</div>

</div>


<div id="route-description"
     class="route-description">

Select a route and direction to view road closures.

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


<section id="closures"
         class="closures">

{''.join(closure_cards)}

</section>


<div id="empty"
     class="empty"
     style="display:none;">

No closures found for the selected route and direction.

</div>


</main>


<script>

const ROUTES = {route_config_js};


const routeSelect =
    document.getElementById("route");

const directionSelect =
    document.getElementById("direction");

const routeDescription =
    document.getElementById("route-description");

const closureContainer =
    document.getElementById("closures");

const emptyMessage =
    document.getElementById("empty");

const totalCount =
    document.getElementById("total-count");

const activeCount =
    document.getElementById("active-count");

const plannedCount =
    document.getElementById("planned-count");


const cards =
    Array.from(
        document.querySelectorAll(".closure")
    );


function updatePage() {{

    const route =
        routeSelect.value;

    const direction =
        directionSelect.value;


    if (route) {{

        const roads =
            ROUTES[route];

        routeDescription.textContent =
            route +
            " route: " +
            roads.join(" → ") +
            (direction
                ? " • " + direction
                : "");

    }} else {{

        routeDescription.textContent =
            "Select a route and direction to view road closures.";

    }}


    let visibleCards = [];


    cards.forEach(card => {{

        const road =
            card.dataset.road;

        const cardDirection =
            card.dataset.direction.toLowerCase();

        const cardRoutes =
            card.dataset.routes
                .split(",")
                .filter(Boolean);


        let routeMatch = true;
        let directionMatch = true;


        if (route) {{

            routeMatch =
                cardRoutes.includes(route) &&
                ROUTES[route].includes(road);

        }}


        if (direction) {{

            directionMatch =
                cardDirection === direction;

        }}


        const visible =
            routeMatch &&
            directionMatch;


        card.style.display =
            visible ? "" : "none";


        if (visible) {{
            visibleCards.push(card);
        }}

    }});


    /*
     * Sort visible closures according to the
     * configured route order.
     */
    if (route) {{

        const roadOrder =
            ROUTES[route];

        visibleCards.sort(
            (a, b) => {{

                const roadA =
                    a.dataset.road;

                const roadB =
                    b.dataset.road;

                const indexA =
                    roadOrder.indexOf(roadA);

                const indexB =
                    roadOrder.indexOf(roadB);

                return indexA - indexB;

            }}
        );


        visibleCards.forEach(card => {{
            closureContainer.appendChild(card);
        }});

    }}


    /*
     * Update summary counters.
     */
    let active = 0;
    let planned = 0;


    visibleCards.forEach(card => {{

        const status =
            card.dataset.status
                .toLowerCase();

        if (status === "active") {{
            active++;
        }}

        if (status === "planned") {{
            planned++;
        }}

    }});


    totalCount.textContent =
        visibleCards.length;

    activeCount.textContent =
        active;

    plannedCount.textContent =
        planned;


    emptyMessage.style.display =
        visibleCards.length === 0
            ? "block"
            : "none";

}}


routeSelect.addEventListener(
    "change",
    updatePage
);

directionSelect.addEventListener(
    "change",
    updatePage
);


/*
 * Start with no closures displayed until
 * the user chooses a route and direction.
 */
updatePage();

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


if __name__ == "__main__":
    data = load_data()
    build_page(data)
