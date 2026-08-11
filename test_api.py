from datetime import datetime, timedelta


from data_processor import process_payload
from fetch_closures import fetch_closures


def main():
    now = datetime.now()

    start = now.strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    end = (
        now + timedelta(days=1)
    ).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    print("=" * 60)
    print("NATIONAL HIGHWAYS API TEST")
    print("=" * 60)

    print()
    print(f"Start: {start}")
    print(f"End:   {end}")
    print()

    try:

        payload = fetch_closures(
            closure_type="planned",
            start_datetime=start,
            end_datetime=end,
        )

    except Exception as exc:

        print(
            f"API ERROR: {exc}"
        )

        return

    print(
        "API request successful"
    )

    d2payload = payload.get(
        "D2Payload",
        {}
    )

    situations = d2payload.get(
        "situation",
        []
    )

    print(
        f"Situations returned: "
        f"{len(situations)}"
    )

    print()

    closures = process_payload(
        payload
    )

    print(
        f"Processed closures: "
        f"{len(closures)}"
    )

    print()
    print("-" * 60)

    for index, closure in enumerate(
        closures[:20],
        start=1
    ):

        print(
            f"{index}. "
            f"{closure.get('road') or 'Unknown road'} "
            f"{closure.get('direction') or ''}"
        )

        print(
            f"   Status: "
            f"{closure.get('status')}"
        )

        print(
            f"   Start: "
            f"{closure.get('start')}"
        )

        print(
            f"   End: "
            f"{closure.get('end')}"
        )

        print(
            f"   Location: "
            f"{closure.get('description')}"
        )

        print(
            f"   Cause: "
            f"{closure.get('cause')}"
        )

        print()

    if len(closures) > 20:

        print(
            f"... and "
            f"{len(closures) - 20} more"
        )

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
