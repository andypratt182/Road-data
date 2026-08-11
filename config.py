import os
from pathlib import Path

from dotenv import load_dotenv


# Project paths

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# Environment variables

load_dotenv()


# National Highways API

API_BASE_URL = os.getenv(
    "NATIONAL_HIGHWAYS_API_BASE_URL",
    "https://api.data.nationalhighways.co.uk/roads/v2.0",
)

API_KEY = os.getenv(
    "NATIONAL_HIGHWAYS_API_KEY"
)


if not API_KEY:
    raise RuntimeError(
        "NATIONAL_HIGHWAYS_API_KEY is not configured."
    )
