from flask import Flask, render_template, request

from data_processor import filter_closures
from fetch_closures import fetch_closures


app = Flask(__name__)


@app.route("/")
def index():
    road = request.args.get("road", "").strip().upper()
    direction = request.args.get("direction", "").strip()
    status = request.args.get("status", "").strip().lower()

    try:
        # Fetch planned closures from National Highways.
        data = fetch_closures(
            closure_type="planned"
        )

        # Build the available filter options from the returned data.
        roads = sorted(
            {
                closure.get("road")
                for closure in data
                if closure.get("road")
            }
        )

        directions = sorted(
            {
                closure.get("direction")
                for closure in data
                if closure.get("direction")
            }
        )

        statuses = sorted(
            {
                closure.get("status")
                for closure in data
                if closure.get("status")
            }
        )

        # Apply the selected filters.
        closures = filter_closures(
            data,
            road=road or None,
            direction=direction or None,
            status=status or None,
        )

        error = None

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
