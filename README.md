# Road Data

A web-based road closure and traffic information project using the **National Highways Road and Lane Closures Data Service (DATEX II v2.0)**.

The project retrieves National Highways data, converts the complex DATEX II response into a simpler structure, and presents filtered road information through a web interface.

## Project Goals

The initial goal is to provide a simple webpage where users can filter National Highways road closure data by:

* Motorway
* Direction
* Closure status
* Closure type
* Date/time
* Location
* Planned or unplanned closure

The initial roads of interest are:

* M1
* M6
* M57
* M58
* M62

The project is designed so additional roads can be added later without rebuilding the application.

---

## Data Source

The project uses the official:

**National Highways Road and Lane Closures Data Service (DATEX II) v2.0**

API endpoint:

`https://api.data.nationalhighways.co.uk/roads/v2.0/closures`

The service provides current and future road and lane closure information across the Strategic Road Network.

The API supports:

* Planned closures
* Unplanned closures
* Start/end date filtering
* Modified-since filtering
* Pagination
* DATEX II structured location data
* Road and carriageway information
* Lane information
* Geographic coordinates

The API requires a National Highways subscription key.

---

## Important API Behaviour

### Date/time format

The API expects:

```text
YYYY-MM-DDThh:mm:ss
```

For example:

```text
2026-08-11T14:00:00
```

ISO timestamps containing a timezone suffix should not be used for these query parameters.

### Unplanned closures

For unplanned closures, the National Highways documentation recommends providing explicit `startDateTime` and `endDateTime` values.

The application therefore supplies its own date/time window rather than relying on the API defaults.

### Pagination

The API can return an `x-next` response header containing a URL for the next page.

The collector will eventually handle pagination so that the website can work with the complete result set rather than only the first API page.

---

# Project Architecture

The project is intentionally separated into several layers.

```text
National Highways API
        │
        ▼
fetch_closures.py
        │
        ▼
Clean JSON data
        │
        ▼
Website / filtering
        │
        ▼
User
```

This separation means the webpage does not need to understand the full DATEX II structure.

---

# Planned Repository Structure

```text
Road-data/
│
├── .github/
│   └── workflows/
│
├── site/
│   ├── data/
│   │   └── closures.json
│   │
│   ├── index.html
│   ├── script.js
│   └── style.css
│
├── fetch_closures.py
├── requirements.txt
├── README.md
└── ...
```

Additional files will be added as the project develops.

---

# Data Processing

The National Highways API returns a relatively complex DATEX II structure.

For example, a closure may contain:

* Situation ID
* Situation record ID
* Validity status
* Start time
* End time
* Road name
* Direction
* Cause
* Public comments
* Lane information
* Carriageway information
* Linear road references
* Latitude/longitude coordinates

The project converts this into a simplified structure that the webpage can consume.

Example:

```json
{
  "id": "7-example-close",
  "situation_id": "signs/M6-example",
  "status": "active",
  "start": "2026-08-11T14:00:00Z",
  "end": "2026-08-11T16:00:00Z",
  "road": "M6",
  "direction": "southBound",
  "type": "laneClosures",
  "cause": "roadworks",
  "comments": [
    "M6 southbound between J18 and J17"
  ],
  "locations": [],
  "linear_locations": []
}
```

The exact fields will evolve as the API is inspected and the requirements of the website become clearer.

---

# Website

The website will eventually provide a user-friendly interface for exploring the data.

Possible features include:

### Road filters

```text
☑ M1
☑ M6
☐ M57
☐ M58
☑ M62
```

### Direction

```text
All
Northbound
Southbound
Eastbound
Westbound
```

### Status

```text
All
Active
Planned
Suspended
```

### Closure type

```text
All
Road closures
Lane closures
Other
```

### Date

Users will be able to view closures occurring:

* Now
* Today
* Tomorrow
* Next 7 days
* Custom date range

---

# Future Features

The project may eventually include:

* Interactive map
* Road closure markers
* Closure route geometry
* Search
* Junction filtering
* Lane information
* Carriageway information
* Planned works calendar
* Live/unplanned closure view
* Mobile-friendly interface
* Automatic data refresh
* GitHub Pages hosting
* API refresh through GitHub Actions
* Historical data
* Closure statistics
* Road-specific pages

For example:

```text
M6
────────────────────────────────────

🔴 Active
M6 southbound J18 → J17
Lane closure

🟡 Planned
M6 northbound J14 → J15
Overnight roadworks
```

---

# GitHub Actions

The eventual system will use GitHub Actions to periodically retrieve the latest National Highways data.

The general workflow will be:

```text
GitHub Actions starts
        │
        ▼
National Highways API
        │
        ▼
Fetch latest data
        │
        ▼
Process DATEX II
        │
        ▼
Generate closures.json
        │
        ▼
Commit updated data
        │
        ▼
GitHub Pages
        │
        ▼
Website updated
```

This means the website itself does not need to expose the National Highways API key.

---

# API Key Security

The National Highways subscription key must **never be committed to this repository**.

The key should be stored as a GitHub Actions secret:

```text
NATIONAL_HIGHWAYS_API_KEY
```

Python code should access it through the environment:

```python
import os

api_key = os.environ["NATIONAL_HIGHWAYS_API_KEY"]
```

Never put the actual API key inside:

* Python source files
* HTML
* JavaScript
* JSON
* README files
* GitHub commits

---

# Development Approach

The project will be developed incrementally.

### Phase 1: API inspection

Understand exactly what National Highways returns.

### Phase 2: Data collector

Create a Python collector that:

1. Calls the API.
2. Handles planned and unplanned closures.
3. Handles pagination.
4. Extracts useful fields.
5. Extracts road geometry.
6. Produces clean JSON.

### Phase 3: Filtering

Build reusable filtering functions for:

* Road
* Direction
* Status
* Closure type
* Date/time

### Phase 4: Website

Create the webpage displaying the filtered data.

### Phase 5: Mapping

Use the supplied WGS84 coordinates to display closure locations and affected road sections.

### Phase 6: Automation

Use GitHub Actions to refresh the data automatically.

### Phase 7: Deployment

Publish the website through GitHub Pages.

---

# Design Principle

The project should keep the **data layer separate from the presentation layer**.

The API data should be processed once into clean, predictable JSON.

The webpage should then operate on that JSON.

This avoids putting National Highways API logic directly into the browser and makes the project easier to maintain and expand.

---

# Licence and Data

National Highways data is provided under the **Open Government Licence v3.0**.

The National Highways API documentation should be consulted for the current terms, coverage and usage requirements.

---

## Status

🚧 **Project under development**

The API has been successfully tested and a genuine National Highways DATEX II v2.0 response has been obtained.

The next step is to build the data collection layer and verify the structure against real-world planned and unplanned closure records.
