import json
from pathlib import Path
from html import escape


ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "road_data.json"
OUTPUT_DIR = ROOT / "site"
OUTPUT_FILE = OUTPUT_DIR / "index.html"


def load_data():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def build_page(data):
    closures = data.get("closures", [])
    updated = data.get("updated", "Unknown")

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
        f'<option value="{escape(road)}">{escape(road)}</option>'
        for road in roads
    )

    direction_options = "".join(
        f'<option value="{escape(direction)}">{escape(direction)}</option>'
        for direction in directions
    )

    status_options = "".join(
        f'<option value="{escape(status)}">{escape(status)}</option>'
        for status in statuses
    )

    closure_cards = []

    for closure in closures:
        road = escape(str(closure.get("road") or "Unknown"))
        direction = escape(str(closure.get("direction") or ""))
        status = escape(str(closure.get("status") or "Unknown"))
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

        title = road

        if direction:
            title += f" {direction}"

        closure_cards.append(
            f"""
            <article class="closure"
                     data-road="{road}"
                     data-direction="{direction}"
                     data-status="{status}">

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
        <p>Live and planned road closure information</p>
        <div class="updated">
            Last updated: {escape(updated)}
        </div>
    </div>
</header>

<main class="container">

<section class="filters">

    <h2>Filter closures</h2>

    <div class="filter-row">

        <div class="filter-group">
            <label for="road">Road</label>

            <select id="road">
                <option value="">All roads</option>
                {road_options}
            </select>
        </div>

        <div class="filter-group">
            <label for="direction">Direction</label>

            <select id="direction">
                <option value="">All directions</option>
                {direction_options}
            </select>
        </div>

        <div class="filter-group">
            <label for="status">Status</label>

            <select id="status">
                <option value="">All statuses</option>
                {status_options}
            </select>
        </div>

    </div>

</section>

<section class="summary">

    <div class="summary-card">
        Total closures
        <strong id="total-count">
            {len(closures)}
        </strong>
    </div>

    <div class="summary-card">
        Active
        <strong id="active-count">0</strong>
    </div>

    <div class="summary-card">
        Planned
        <strong id="planned-count">0</strong>
    </div>

</section>

<section class="closures" id="closures">

    {"".join(closure_cards)}

</section>

</main>

<script>
    const roadFilter = document.getElementById("road");
    const directionFilter =
        document.getElementById("direction");
    const statusFilter =
        document.getElementById("status");

    const cards =
        Array.from(document.querySelectorAll(".closure"));

    function updateFilters() {{

        const road = roadFilter.value.toUpperCase();
        const direction =
            directionFilter.value.toLowerCase();
        const status =
            statusFilter.value.toLowerCase();

        let visible = 0;
        let active = 0;
        let planned = 0;

        cards.forEach(card => {{

            const cardRoad =
                card.dataset.road.toUpperCase();

            const cardDirection =
                card.dataset.direction.toLowerCase();

            const cardStatus =
                card.dataset.status.toLowerCase();

            const matchesRoad =
                !road || cardRoad === road;

            const matchesDirection =
                !direction ||
                cardDirection === direction;

            const matchesStatus =
                !status ||
                cardStatus === status;

            const matches =
                matchesRoad &&
                matchesDirection &&
                matchesStatus;

            card.style.display =
                matches ? "" : "none";

            if (matches) {{
                visible++;

                if (cardStatus === "active") {{
                    active++;
                }}

                if (cardStatus === "planned") {{
                    planned++;
                }}
            }}
        }});

        document.getElementById("total-count")
            .textContent = visible;

        document.getElementById("active-count")
            .textContent = active;

        document.getElementById("planned-count")
            .textContent = planned;
    }}

    roadFilter.addEventListener("change", updateFilters);
    directionFilter.addEventListener(
        "change",
        updateFilters
    );
    statusFilter.addEventListener("change", updateFilters);

    updateFilters();
</script>

</body>
</html>
"""

    OUTPUT_DIR.mkdir(exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        file.write(html)

    print(f"Generated {OUTPUT_FILE}")
    print(f"Closures: {len(closures)}")


if __name__ == "__main__":
    data = load_data()
    build_page(data)
