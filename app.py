from flask import Flask, render_template, request

from config import API_KEY
from fetch_closures import fetch_closures
from data_processor import filter_closures
from route_config import get_directions, get_roads, get_routes

app = Flask(__name__)


@app.route("/")
def index():
    selected_route = request.args.get("route", "")
    selected_direction = request.args.get("direction", "")

    # Only use our configured routes.
    routes = get_routes()

    # Work out which directions are available.
    directions = []

    if selected_route:
        directions = get_directions(selected_route)
    else:
        for route in routes:
            for direction in get_directions(route):
                if direction not in directions:
                    directions.append(direction)

    # Get the roads belonging to the selected route/direction.
    if selected_route and selected_direction:
        roads = get_roads(
            selected_route,
            selected_direction,
        )
    elif selected_route:
        roads = []

        for direction in get_directions(selected_route):
            for road in get_roads(
                selected_route,
                direction,
            ):
                if road not in roads:
                    roads.append(road)
    else:
        roads = []

        for route in routes:
            for direction in get_directions(route):
                for road in get_roads(
                    route,
                    direction,
                ):
                    if road not in roads:
                        roads.append(road)

    # Fetch both types of National Highways closure.
    planned = fetch_closures(
        closure_type="planned"
    )

    unplanned = fetch_closures(
        closure_type="unplanned"
    )

    closures = planned + unplanned

    # Keep only our configured roads.
    closures = [
        closure
        for closure in closures
        if closure.get("road") in roads
    ]

    # Apply direction filter.
    if selected_direction:
        closures = [
            closure
            for closure in closures
            if (
                closure.get("direction")
                or ""
            ).lower()
            == selected_direction.lower()
        ]

    # Sort according to our route order.
    road_order = {
        road: index
        for index, road in enumerate(roads)
    }

    closures.sort(
        key=lambda closure: (
            road_order.get(
                closure.get("road"),
                999,
            ),
            closure.get("start")
            or "",
        )
    )

    return render_template(
        "index.html",
        closures=closures,
        routes=routes,
        directions=directions,
        roads=roads,
        selected_route=selected_route,
        selected_direction=selected_direction,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
    )
