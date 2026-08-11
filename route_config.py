ROUTES = {
    "Omega": {
        "Southbound": [
            "M6",
            "M62",
        ],
    },
    "Axis": {
        "Southbound": [
            "M6",
            "M58",
            "M57",
        ],
    },
}


def get_routes():
    """Return the configured route names."""
    return list(ROUTES.keys())


def get_directions(route):
    """Return directions configured for a route."""
    return list(ROUTES.get(route, {}).keys())


def get_roads(route, direction):
    """Return roads for a route and direction in the configured order."""
    return ROUTES.get(route, {}).get(direction, [])
