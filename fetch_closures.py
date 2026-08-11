import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

from config import (
API_URL,
HOURS_BACK,
HOURS_FORWARD,
RAW_DATA_DIR,
REQUEST_TIMEOUT,
)

# ============================================================

# ENVIRONMENT

# ============================================================

load_dotenv()

API_KEY = os.getenv(
"NATIONAL_HIGHWAYS_API_KEY"
)

# ============================================================

# API REQUEST

# ============================================================

def fetch_closures():
"""
Fetch road closure data from the National Highways API.

```
The API requires startDateTime and endDateTime in the
format:

    YYYY-MM-DDThh:mm:ss

The API response is returned as JSON.
"""

if not API_KEY:
    raise RuntimeError(
        "NATIONAL_HIGHWAYS_API_KEY is not set."
    )

now = datetime.utcnow().replace(
    microsecond=0
)

start_time = (
    now - timedelta(
        hours=HOURS_BACK
    )
)

end_time = (
    now + timedelta(
        hours=HOURS_FORWARD
    )
)

params = {
    "closureType": "unplanned",
    "startDateTime": start_time.strftime(
        "%Y-%m-%dT%H:%M:%S"
    ),
    "endDateTime": end_time.strftime(
        "%Y-%m-%dT%H:%M:%S"
    ),
}

headers = {
    "Ocp-Apim-Subscription-Key": API_KEY,
    "X-Response-MediaType": "application/json",
    "X-Data-Format": "DATEXII",
}

print("=" * 60)
print("NATIONAL HIGHWAYS API")
print("=" * 60)
print(f"URL: {API_URL}")
print(f"Start: {params['startDateTime']}")
print(f"End:   {params['endDateTime']}")
print()

response = requests.get(
    API_URL,
    params=params,
    headers=headers,
    timeout=REQUEST_TIMEOUT,
)

print(
    f"HTTP status: {response.status_code}"
)

response.raise_for_status()

data = response.json()

return data
```

# ============================================================

# SAVE RAW RESPONSE

# ============================================================

def save_raw_response(data):
"""
Save the complete API response locally.

```
Raw API responses are deliberately kept outside Git
through .gitignore.
"""

timestamp = datetime.utcnow().strftime(
    "%Y%m%d_%H%M%S"
)

filename = (
    RAW_DATA_DIR
    / f"closures_{timestamp}.json"
)

with filename.open(
    "w",
    encoding="utf-8",
) as file:

    json.dump(
        data,
        file,
        indent=2,
        ensure_ascii=False,
    )

print()
print(
    f"Raw response saved to: {filename}"
)

return filename
```

# ============================================================

# MAIN

# ============================================================

def main():

```
try:

    data = fetch_closures()

    save_raw_response(
        data
    )

    payload = data.get(
        "D2Payload",
        {}
    )

    situations = payload.get(
        "situation",
        []
    )

    print(
        f"Situations returned: "
        f"{len(situations)}"
    )

    print()
    print(
        "API request completed successfully."
    )

except requests.HTTPError as error:

    print()
    print(
        f"HTTP ERROR: {error}"
    )

    if error.response is not None:

        print(
            error.response.text
        )

    raise

except Exception as error:

    print()
    print(
        f"ERROR: {error}"
    )

    raise
```

if **name** == "**main**":
main()
