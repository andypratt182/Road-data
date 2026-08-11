import json
import os
from datetime import datetime, timedelta

import requests

API_URL = "https://api.data.nationalhighways.co.uk/roads/v2.0/closures"

# How far back and forward we ask the API for data.

HOURS_BACK = 6
HOURS_FORWARD = 24

# Roads we initially care about.

TARGET_ROADS = {
"M1",
"M6",
"M57",
"M58",
"M62",
}

def get_api_key():
"""Return the National Highways API subscription key."""

```
api_key = os.environ.get(
    "NATIONAL_HIGHWAYS_API_KEY"
)

if not api_key:
    raise RuntimeError(
        "NATIONAL_HIGHWAYS_API_KEY environment variable "
        "has not been set."
    )

return api_key
```

def build_date_range():
"""
Build the API date range.

```
National Highways requires:

    YYYY-MM-DDThh:mm:ss

No timezone suffix is included.
"""

now = datetime.now()

start = now - timedelta(
    hours=HOURS_BACK
)

end = now + timedelta(
    hours=HOURS_FORWARD
)

return (
    start.strftime("%Y-%m-%dT%H:%M:%S"),
    end.strftime("%Y-%m-%dT%H:%M:%S"),
)
```

def fetch_page(
api_key,
start_datetime,
end_datetime,
closure_type="unplanned",
):
"""Fetch one page from the National Highways API."""

```
params = {
    "closureType": closure_type,
    "startDateTime": start_datetime,
    "endDateTime": end_datetime,
}

headers = {
    "Ocp-Apim-Subscription-Key": api_key,
    "X-Response-MediaType": "application/json",
    "X-Data-Format": "DATEXII",
}

print(
    f"Requesting {closure_type} closures:"
)

print(
    f"  Start: {start_datetime}"
)

print(
    f"  End:   {end_datetime}"
)

response = requests.get(
    API_URL,
    params=params,
    headers=headers,
    timeout=60,
)

print(
    f"HTTP status: {response.status_code}"
)

response.raise_for_status()

return response
```

def save_raw_response(
response,
closure_type,
):
"""Save the raw API response for inspection."""

```
output_folder = "raw"

os.makedirs(
    output_folder,
    exist_ok=True,
)

filename = (
    f"{output_folder}/"
    f"{closure_type}_closures.json"
)

data = response.json()

with open(
    filename,
    "w",
    encoding="utf-8",
) as file:

    json.dump(
        data,
        file,
        indent=2,
        ensure_ascii=False,
    )

print(
    f"Raw response saved to {filename}"
)

return data
```

def extract_situations(data):
"""Return the situation list from a National Highways response."""

```
payload = data.get(
    "D2Payload",
    {}
)

return payload.get(
    "situation",
    []
)
```

def find_roads(situations):
"""
Inspect situation records and identify the roads they relate to.

```
This is deliberately diagnostic for now.

We are NOT filtering the API response yet because the
road information can occur at different levels within
the DATEX II location structure.
"""

roads = set()

for situation in situations:

    records = situation.get(
        "situationRecord",
        []
    )

    for record in records:

        management = record.get(
            "sitRoadOrCarriagewayOrLaneManagement",
            {}
        )

        location_reference = management.get(
            "locationReference",
            {}
        )

        linear_location = (
            location_reference.get(
                "locLinearLocation",
                {}
            )
        )

        single_road_location = (
            location_reference.get(
                "locSingleRoadLinearLocation",
                {}
            )
        )

        linear_sections = (
            single_road_location.get(
                "linearWithinLinearElement",
                []
            )
        )

        for section in linear_sections:

            linear_element = (
                section.get(
                    "linearElement",
                    {}
                )
            )

            by_code = (
                linear_element.get(
                    "locLinearElementByCode",
                    {}
                )
            )

            road_name = by_code.get(
                "roadName"
            )

            if road_name:
                roads.add(
                    road_name
                )

        # Keep this variable referenced so the
        # structure remains obvious while we inspect
        # future variants of the API response.
        _ = linear_location

return sorted(roads)
```

def inspect_response(
data,
closure_type,
):
"""Print a basic summary of the returned data."""

```
situations = extract_situations(
    data
)

print()
print("==============================")
print(
    f"{closure_type.upper()} CLOSURES"
)
print("==============================")

print(
    f"Situations returned: "
    f"{len(situations)}"
)

roads = find_roads(
    situations
)

print(
    f"Roads discovered: "
    f"{len(roads)}"
)

if roads:

    print(
        "Road names:"
    )

    for road in roads:
        print(
            f"  {road}"
        )

print()
```

def main():
print(
"===================================="
)

```
print(
    "NATIONAL HIGHWAYS API COLLECTOR"
)

print(
    "===================================="
)

api_key = get_api_key()

start_datetime, end_datetime = (
    build_date_range()
)

for closure_type in (
    "unplanned",
    "planned",
):

    try:

        response = fetch_page(
            api_key,
            start_datetime,
            end_datetime,
            closure_type,
        )

        data = save_raw_response(
            response,
            closure_type,
        )

        inspect_response(
            data,
            closure_type,
        )

    except requests.RequestException as error:

        print(
            f"ERROR fetching "
            f"{closure_type} closures:"
        )

        print(
            error
        )

print(
    "===================================="
)

print(
    "Collection complete"
)

print(
    "===================================="
)
```

if **name** == "**main**":
main()
