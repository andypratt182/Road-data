from datetime import datetime, timedelta

from fetch_closures import fetch_closures


def main():
    """
    Test the National Highways Road and Lane Closures API.
    """

    now = datetime.now().replace(microsecond=0)
    start = now - timedelta(hours=6)
    end = now

    start_datetime = start.strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    end_datetime = end.strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    print("=" * 60)
    print("NATIONAL HIGHWAYS API TEST")
    print("=" * 60)

    print(f"Start: {start_datetime}")
    print(f"End:   {end_datetime}")
    print()

    for closure_type in ("planned", "unplanned"):

        print("-" * 60)
        print(f"Testing: {closure_type}")
        print("-" * 60)

        try:

            closures = fetch_closures(
                closure_type=closure_type,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
            )

            print(
                f"Closures returned: {len(closures)}"
            )

            for index, closure in enumerate(
                closures[:10],
                start=1,
            ):

                print()
                print(f"{index}.")
                print(
                    f"   ID:          {closure.get('id')}"
                )
                print(
                    f"   Road:        {closure.get('road')}"
                )
                print(
                    f"   Direction:   {closure.get('direction')}"
                )
                print(
                    f"   Status:      {closure.get('status')}"
                )
                print(
                    f"   Start:       {closure.get('start')}"
                )
                print(
                    f"   End:         {closure.get('end')}"
                )
                print(
                    f"   Type:        {closure.get('type')}"
                )
                print(
                    f"   Cause:       {closure.get('cause')}"
                )
                print(
                    f"   Description: {closure.get('description')}"
                )

        except Exception as exc:

            print(
                f"ERROR: {exc}"
            )

    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
