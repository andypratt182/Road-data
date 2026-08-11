from flask import Flask, render_template, request

from data_processor import filter_closures
from fetch_closures import fetch_closures


app = Flask(__name__)


def get_filter_values(
    closures: list[dict],
) -> tuple[list[str], list[str], list[str]]:
    """Build sorted filter values from the available closure data."""

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

    return roads, directions, statuses


@app.route("/")
def index():

    road = request.args.get(
        "road",
        "",
    ).strip().upper()

    direction = request.args.get(
        "direction",
        "",
    ).strip()

    status = request.args.get(
        "status",
        "",
    ).strip()

    error = None

    try:

        # Fetch planned closures.
        planned = fetch_closures(
            closure_type="planned"
        )

        # Fetch unplanned/live closures.
        unplanned = fetch_closures(
            closure_type="unplanned"
        )

        # Combine both feeds.
        closures = planned + unplanned

        # Build dropdown values from the complete dataset.
        roads, directions, statuses = get_filter_values(
            closures
        )

        # Apply the selected filters.
        closures = filter_closures(
            closures,
            road=road or None,
            direction=direction or None,
            status=status or None,
        )

    except Exception as exc:

        closures = []

        roads = []
        directions = []
        statuses = []

        error = str(exc)

    return render_template(
        "index.html",

        closures=closures,

        roads=roads,

        directions=directions,

        statuses=statuses,

        selected_road=road,

        selected_direction=direction,

        selected_status=status,

        error=error,
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )
