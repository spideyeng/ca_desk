# python freight.py --route AG-CHINA --vessel VLCC --start 2023-01-01 --end 2024-12-31

import argparse

def main():
    parser = argparse.ArgumentParser(description="Synthetic Freight Curve Generator")
    parser.add_argument("--route", required=True, help="Route key, e.g. AG-CHINA")
    parser.add_argument("--vessel", required=True, help="Vessel type, e.g. VLCC")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--bunker", default="Fujairah_HSFO", help="Bunker region")

    args = parser.parse_args()

    vessel = VLCC if args.vessel == "VLCC" else LNGC
    route = ROUTES[args.route]

    curve = SyntheticFreightCurve(
        vessel=vessel,
        route=route,
        bunker_price_fn=bunker_price_provider,
        bunker_region=args.bunker
    )

    df = curve.to_dataframe(args.start, args.end)
    print(df.head())
    print(df.tail())


if __name__ == "__main__":
    main()