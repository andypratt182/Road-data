from flask import Flask, render_template, request

from data_processor import filter_closures
from fetch_closures import fetch_closures


app = Flask(__name__)


@app.route("/")
def index():
    road = request.args.get("road", "").strip().upper()
    direction = request.args.get("direction", "").strip()

    try:
        data = fetch_closures(
            closure_type="planned"
        )

        closures = filter_closures(
            data,
            road=road or None,
            direction=direction or None,
        )

        error = None

    except Exception as exc:
        closures = []
        error = str(exc)

    return render_template(
        "index.html",
        closures=closures,
        selected_road=road,
        selected_direction=direction,
        error=error,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
    )
