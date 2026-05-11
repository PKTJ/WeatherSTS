import requests
import pandas as pd
from datetime import datetime, timezone
import os
import sys
import time
import argparse

# ====================== MODEL CONFIGURATION ======================
MODELS = {
    "gfs": {"api_name": "gfs_seamless", "updates_per_day": 4},
    "icon": {"api_name": "icon_seamless", "updates_per_day": 8},
    "ecmwf_ifs": {"api_name": "ecmwf_ifs025", "updates_per_day": 2},
    "gem": {"api_name": "gem_seamless", "updates_per_day": 4},
    "arpege": {"api_name": "arpege_seamless", "updates_per_day": 4},
    "access_g": {"api_name": "bom_access_global", "updates_per_day": 4},
    "era5": {"api_name": "era5_seamless", "updates_per_day": 4},
}

# ====================== HOURLY VARIABLES ======================
HOURLY_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "cape",
    "snowfall",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "pressure_msl",
    "surface_pressure",
    "vapour_pressure_deficit",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "soil_temperature_0cm",
    "soil_temperature_6cm",
    "soil_temperature_18cm",
    "soil_temperature_54cm",
    "soil_moisture_0_to_1cm",
    "et0_fao_evapotranspiration",
    "freezing_level_height",
    "is_day",
]

# ====================== RETRY CONFIGURATION ======================
MAX_RETRIES = 3
BASE_DELAY = 2        # seconds
BACKOFF_FACTOR = 2    # exponential: 2s, 4s, 8s

# ====================== TERMINAL COLORS ======================
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def color_text(text, color):
    """Wrap text with ANSI color codes for terminal output."""
    return f"{color}{text}{RESET}"


# ====================== CLI ARGUMENT PARSING ======================
def validate_date(date_string):
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return date_string
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid date format: '{date_string}'. Use YYYY-MM-DD."
        )


def build_parser():
    parser = argparse.ArgumentParser(
        description="Global Weather Model Data Fetcher - Open-Meteo API"
    )

    # Required arguments
    parser.add_argument(
        "--lat",
        type=float,
        required=True,
        help="Target latitude (example: -6.1256)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        required=True,
        help="Target longitude (example: 106.6556)",
    )

    # Optional date arguments
    parser.add_argument(
        "--date",
        type=validate_date,
        help="Single-day mode: date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--start",
        type=validate_date,
        help="Batch mode: start date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--end",
        type=validate_date,
        help="Batch mode: end date in YYYY-MM-DD format",
    )

    # Optional output directory
    parser.add_argument(
        "--output",
        default="global_model_data",
        help="Output folder (default: global_model_data)",
    )

    # Optional model filter
    parser.add_argument(
        "--model",
        nargs="+",
        choices=list(MODELS.keys()),
        default=None,
        help="Specific model(s) to fetch (default: all). Example: --model gfs icon",
    )

    # Optional filter flag for realtime deduplication behavior
    parser.add_argument(
        "--filter",
        action="store_true",
        default=False,
           help="When enabled, existing CSV rows are preserved and not overwritten by newer rows (keep existing). "
               "Without --filter, older rows can be replaced by data from the latest model run.",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="mode")
    subparsers.add_parser("realtime", help="Realtime mode: continuously poll latest data")

    return parser


def parse_and_validate_args(args=None):
    parser = build_parser()
    parsed = parser.parse_args(args)

    # Validation: --start without --end or vice versa
    if parsed.start and not parsed.end:
        parser.error("--start requires --end. Use both for batch mode.")
    if parsed.end and not parsed.start:
        parser.error("--end requires --start. Use both for batch mode.")

    # Validation: no mode specified
    if not parsed.mode and not parsed.date and not (parsed.start and parsed.end):
        parser.error(
            "No mode selected. Use --date, --start/--end, or the 'realtime' subcommand."
        )

    return parsed


# ====================== API CLIENT ======================
# API endpoint URLs
HISTORICAL_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_model_data(model_name: str, lat: float, lon: float,
                     start_date: str, end_date: str,
                     endpoint: str = "historical") -> dict:
    # Select URL based on endpoint type
    if endpoint == "forecast":
        url = FORECAST_URL
    else:
        url = HISTORICAL_URL

    # Get the API model name
    model_config = MODELS[model_name]
    api_model_name = model_config["api_name"]

    # Build request parameters
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY_VARS),
        "models": api_model_name,
        "timezone": "auto",
    }

    # For forecast endpoint, use forecast_days=1 instead of start/end dates
    if endpoint == "forecast":
        params["forecast_days"] = 1
    else:
        params["start_date"] = start_date
        params["end_date"] = end_date

    # Make the request with 30-second timeout
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def fetch_with_retry(model_name: str, lat: float, lon: float,
                     start_date: str, end_date: str,
                     endpoint: str = "historical") -> dict:
    for attempt in range(MAX_RETRIES + 1):
        try:
            return fetch_model_data(model_name, lat, lon, start_date, end_date, endpoint)
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == MAX_RETRIES:
                print(color_text(
                    f"[{model_name}] All retries exhausted: {e}", RED
                ))
                raise
            delay = BASE_DELAY * (BACKOFF_FACTOR ** attempt)
            print(color_text(
                f"[{model_name}] Retry {attempt + 1}/{MAX_RETRIES} in {delay}s...", YELLOW
            ))
            time.sleep(delay)
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "unknown"
            print(color_text(
                f"[{model_name}] HTTP {status_code}: {e}", RED
            ))
            raise


# ====================== RESPONSE PARSER ======================
def parse_response(response_json: dict, model_name: str,
                   lat: float, lon: float) -> pd.DataFrame:
    hourly_data = response_json.get("hourly", {})

    # Build the DataFrame starting with the datetime column
    # Convert ISO format "YYYY-MM-DDTHH:MM" to "YYYY-MM-DD HH:MM"
    raw_times = hourly_data.get("time", [])
    data = {"datetime": [t.replace("T", " ") if isinstance(t, str) else t for t in raw_times]}

    # Add each hourly variable; use None if not present in response
    for var in HOURLY_VARS:
        data[var] = hourly_data.get(var, [None] * len(data["datetime"]))

    df = pd.DataFrame(data)

    # Add metadata columns
    df["model"] = model_name.upper()
    df["latitude"] = lat
    df["longitude"] = lon
    df["timezone"] = response_json.get("timezone", "UTC")
    df["utc_offset_seconds"] = response_json.get("utc_offset_seconds", 0)

    # Reorder columns: datetime, model, latitude, longitude, timezone, utc_offset_seconds, then hourly vars
    column_order = ["datetime", "model", "latitude", "longitude", "timezone", "utc_offset_seconds"] + HOURLY_VARS
    df = df[column_order]

    return df


# ====================== CSV WRITER WITH DEDUPLICATION ======================
def write_model_csv(df: pd.DataFrame, model_name: str, output_dir: str, keep_existing: bool = True) -> int:
    # 1. Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # 2. Build filepath as {output_dir}/{model_name}.csv
    filepath = os.path.join(output_dir, f"{model_name}.csv")

    # 3. If file exists, read existing CSV and concatenate
    if os.path.exists(filepath):
        existing_df = pd.read_csv(filepath)
        if keep_existing:
            # keep='first' → existing data preserved, new duplicates skipped
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            rows_before = len(combined_df)
            combined_df = combined_df.drop_duplicates(subset=["datetime"], keep="first")
        else:
            # keep='last' → new data overwrites existing duplicates
            combined_df = pd.concat([existing_df, df], ignore_index=True)
            rows_before = len(combined_df)
            combined_df = combined_df.drop_duplicates(subset=["datetime"], keep="last")
    else:
        combined_df = df.copy()
        rows_before = len(combined_df)
        combined_df = combined_df.drop_duplicates(subset=["datetime"], keep="last")

    duplicates_removed = rows_before - len(combined_df)

    # 4. Sort by datetime ascending
    combined_df = combined_df.sort_values(by="datetime", ascending=True).reset_index(drop=True)

    # 5. Write to CSV (index=False)
    combined_df.to_csv(filepath, index=False)

    # 6. Log the number of duplicates handled (if any)
    if duplicates_removed > 0:
        action = "skipped" if keep_existing else "updated"
        print(color_text(
            f"[{model_name}] {duplicates_removed} duplicate row(s) {action}.", YELLOW
        ))

    return duplicates_removed


# ====================== BATCH MODE ======================
def run_batch(lat: float, lon: float, start_date: str, end_date: str, output_dir: str, models: dict = None, keep_existing: bool = True):
    if models is None:
        models = MODELS

    print(f"BATCH mode: {start_date} to {end_date}")
    print(f"Coordinates: {lat}, {lon}")
    print(f"Output: {output_dir}/")
    print(f"Models: {', '.join(models.keys())}\n")

    success_count = 0
    error_count = 0

    for model_name in models:
        print(f"  Fetching {model_name.upper()}...", end=" ")
        try:
            response_json = fetch_with_retry(
                model_name, lat, lon, start_date, end_date, endpoint="historical"
            )
            df = parse_response(response_json, model_name, lat, lon)
            duplicates = write_model_csv(df, model_name, output_dir, keep_existing)
            action = "skipped" if keep_existing else "updated"
            print(color_text(f"OK ({len(df)} rows, {duplicates} duplicates {action})", GREEN))
            success_count += 1
        except Exception as e:
            print(color_text(f"FAILED: {e}", RED))
            error_count += 1

    print(f"\nDone: {success_count} succeeded, {error_count} failed.")


# ====================== SINGLE DATE MODE ======================
def run_single_date(lat: float, lon: float, date: str, output_dir: str, models: dict = None, keep_existing: bool = True):
    if models is None:
        models = MODELS

    print(f"Mode SINGLE DATE: {date}")
    print(f"Coordinates: {lat}, {lon}")
    print(f"Output: {output_dir}/")
    print(f"Models: {', '.join(models.keys())}\n")

    success_count = 0
    error_count = 0

    for model_name in models:
        print(f"  Fetching {model_name.upper()}...", end=" ")
        try:
            response_json = fetch_with_retry(
                model_name, lat, lon, date, date, endpoint="historical"
            )
            df = parse_response(response_json, model_name, lat, lon)
            duplicates = write_model_csv(df, model_name, output_dir, keep_existing)
            action = "skipped" if keep_existing else "updated"
            print(color_text(f"OK ({len(df)} rows, {duplicates} duplicates {action})", GREEN))
            success_count += 1
        except Exception as e:
            print(color_text(f"FAILED: {e}", RED))
            error_count += 1

    print(f"\nDone: {success_count} succeeded, {error_count} failed.")


# ====================== REALTIME MODE ======================
def calculate_next_update(model_name: str, last_fetch_time: datetime) -> datetime:
    from datetime import timedelta

    updates_per_day = MODELS[model_name]["updates_per_day"]
    interval_hours = 24 / updates_per_day
    interval_seconds = interval_hours * 3600

    return last_fetch_time + timedelta(seconds=interval_seconds)


def should_fetch_model(model_name: str, last_fetched, now: datetime) -> bool:
    if last_fetched is None:
        return True

    updates_per_day = MODELS[model_name]["updates_per_day"]
    interval_hours = 24 / updates_per_day
    interval_seconds = interval_hours * 3600

    elapsed = (now - last_fetched).total_seconds()
    return elapsed >= interval_seconds


def run_realtime(lat: float, lon: float, output_dir: str, models: dict = None, keep_existing: bool = True):
    if models is None:
        models = MODELS

    CHECK_INTERVAL = 900  # 15 minutes in seconds

    filter_mode = "ON (preserve existing rows)" if keep_existing else "OFF (overwrite with latest rows)"
    print(f"REALTIME mode: continuous polling")
    print(f"Coordinates: {lat}, {lon}")
    print(f"Output: {output_dir}/")
    print(f"Check interval: {CHECK_INTERVAL // 60} minutes")
    print(f"Models: {', '.join(models.keys())}")
    print(f"Filter: {filter_mode}")
    print(f"Press Ctrl+C to stop.\n")

    # Track last fetch time per model (None = never fetched)
    last_fetched = {model: None for model in models}
    total_fetches = 0
    total_errors = 0

    try:
        while True:
            now = datetime.now(timezone.utc)
            fetched_this_cycle = []
            skipped_this_cycle = []

            for model_name in models:
                if should_fetch_model(model_name, last_fetched[model_name], now):
                    try:
                        response_json = fetch_with_retry(
                            model_name, lat, lon, "", "", endpoint="forecast"
                        )
                        df = parse_response(response_json, model_name, lat, lon)
                        write_model_csv(df, model_name, output_dir, keep_existing)
                        last_fetched[model_name] = now
                        fetched_this_cycle.append(model_name)
                        total_fetches += 1
                    except Exception as e:
                        print(color_text(f"  [{model_name}] Error: {e}", RED))
                        total_errors += 1
                else:
                    skipped_this_cycle.append(model_name)

            # Status message
            timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
            fetched_str = ", ".join(f.upper() for f in fetched_this_cycle) or "-"
            skipped_str = ", ".join(s.upper() for s in skipped_this_cycle) or "-"
            print(f"[{timestamp}] Fetched: {fetched_str} | Skipped: {skipped_str}")

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        print(f"\nRealtime monitoring stopped.")
        print(f"Total fetches: {total_fetches}, Errors: {total_errors}")


# ====================== MAIN ENTRY POINT ======================
def main():
    try:
        args = parse_and_validate_args()

        # Create output directory
        os.makedirs(args.output, exist_ok=True)

        # Filter models if --model is specified
        if args.model:
            selected_models = {k: MODELS[k] for k in args.model}
        else:
            selected_models = MODELS

        # Route to appropriate mode
        if args.mode == "realtime":
            run_realtime(args.lat, args.lon, args.output, selected_models, args.filter)
        elif args.date:
            run_single_date(args.lat, args.lon, args.date, args.output, selected_models, args.filter)
        elif args.start and args.end:
            run_batch(args.lat, args.lon, args.start, args.end, args.output, selected_models, args.filter)
        else:
            # This shouldn't be reached due to parse_and_validate_args validation,
            # but included as a safety net.
            print(color_text("Error: No mode selected.", RED))
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nProcess canceled by user.")
        sys.exit(0)
    except SystemExit:
        # Let argparse exits pass through
        raise
    except Exception as e:
        print(color_text(f"Error fatal: {e}", RED))
        sys.exit(1)


if __name__ == "__main__":
    main()
