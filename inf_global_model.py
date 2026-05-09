"""
inf_global_model.py - CLI tool for fetching global weather model data from Open-Meteo API.

Supports batch date ranges, single-date queries, and real-time polling
with model-aware update scheduling. Output is stored as separate CSV files
per model with deduplication and chronological sorting.
"""

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
    "ecmwf_aifs": {"api_name": "ecmwf_aifs025", "updates_per_day": 2},
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
    "snowfall",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "pressure_msl",
    "visibility",
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
    """
    Validate and parse a date string in YYYY-MM-DD format.

    Args:
        date_string: String to validate as a date.

    Returns:
        The validated date string if format is correct.

    Raises:
        argparse.ArgumentTypeError: If the date format is invalid.
    """
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return date_string
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Format tanggal tidak valid: '{date_string}'. Gunakan format YYYY-MM-DD."
        )


def build_parser():
    """
    Build and return the argparse parser for the global model CLI.

    Returns:
        argparse.ArgumentParser: Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Global Weather Model Data Fetcher - Open-Meteo API"
    )

    # Required arguments
    parser.add_argument(
        "--lat",
        type=float,
        required=True,
        help="Latitude target (contoh: -6.1256)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        required=True,
        help="Longitude target (contoh: 106.6556)",
    )

    # Optional date arguments
    parser.add_argument(
        "--date",
        type=validate_date,
        help="Mode single day: tanggal dalam format YYYY-MM-DD",
    )
    parser.add_argument(
        "--start",
        type=validate_date,
        help="Mode batch: tanggal mulai dalam format YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        type=validate_date,
        help="Mode batch: tanggal akhir dalam format YYYY-MM-DD",
    )

    # Optional output directory
    parser.add_argument(
        "--output",
        default="global_model_data",
        help="Folder output (default: global_model_data)",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="mode")
    subparsers.add_parser("realtime", help="Mode realtime: polling data terbaru secara kontinu")

    return parser


def parse_and_validate_args(args=None):
    """
    Parse CLI arguments and perform cross-field validation.

    Args:
        args: Optional list of argument strings (for testing). If None, uses sys.argv.

    Returns:
        argparse.Namespace: Validated parsed arguments.

    Exits:
        With non-zero status code if validation fails.
    """
    parser = build_parser()
    parsed = parser.parse_args(args)

    # Validation: --start without --end or vice versa
    if parsed.start and not parsed.end:
        parser.error("--start membutuhkan --end. Gunakan keduanya untuk mode batch.")
    if parsed.end and not parsed.start:
        parser.error("--end membutuhkan --start. Gunakan keduanya untuk mode batch.")

    # Validation: no mode specified
    if not parsed.mode and not parsed.date and not (parsed.start and parsed.end):
        parser.error(
            "Tidak ada mode yang dipilih. Gunakan --date, --start/--end, atau subcommand 'realtime'."
        )

    return parsed


# ====================== API CLIENT ======================

# API endpoint URLs
HISTORICAL_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_model_data(model_name: str, lat: float, lon: float,
                     start_date: str, end_date: str,
                     endpoint: str = "historical") -> dict:
    """
    Fetch data for a single model from Open-Meteo API.

    Args:
        model_name: Key from MODELS dict (e.g., "gfs", "icon")
        lat: Target latitude
        lon: Target longitude
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        endpoint: "historical" or "forecast"

    Returns:
        JSON response dict from the API.

    Raises:
        requests.HTTPError: On HTTP error responses (4xx/5xx).
        requests.Timeout: On request timeout.
        requests.ConnectionError: On network connection issues.
    """
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
    """
    Fetch model data with retry logic and exponential backoff.

    Wraps fetch_model_data() with resilience handling:
    - Retries up to MAX_RETRIES times on timeout or connection errors
    - Uses exponential backoff: BASE_DELAY * (BACKOFF_FACTOR ** attempt)
    - Logs each retry attempt with model name and attempt number
    - On HTTP errors, logs error with model name and status code (no retry)
    - After all retries exhausted, raises the exception to the caller

    Args:
        model_name: Key from MODELS dict (e.g., "gfs", "icon")
        lat: Target latitude
        lon: Target longitude
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        endpoint: "historical" or "forecast"

    Returns:
        JSON response dict from the API.

    Raises:
        requests.HTTPError: On HTTP error responses (4xx/5xx), immediately without retry.
        requests.Timeout: After all retries exhausted on timeout.
        requests.ConnectionError: After all retries exhausted on connection failure.
    """
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
    """
    Parse Open-Meteo API JSON response into a DataFrame.

    Extracts the "hourly" key from the response, uses the "time" array as the
    datetime column, and adds each hourly variable as a column. Missing variables
    are filled with None/NaN.

    Args:
        response_json: JSON response dict from the Open-Meteo API.
        model_name: Model identifier (e.g., "gfs", "icon").
        lat: Target latitude used in the request.
        lon: Target longitude used in the request.

    Returns:
        DataFrame with columns: datetime, model, latitude, longitude,
        and all 13 Hourly_Variables.
    """
    hourly_data = response_json.get("hourly", {})

    # Build the DataFrame starting with the datetime column
    data = {"datetime": hourly_data.get("time", [])}

    # Add each hourly variable; use None if not present in response
    for var in HOURLY_VARS:
        data[var] = hourly_data.get(var, [None] * len(data["datetime"]))

    df = pd.DataFrame(data)

    # Add metadata columns
    df["model"] = model_name.upper()
    df["latitude"] = lat
    df["longitude"] = lon

    # Reorder columns: datetime, model, latitude, longitude, then hourly vars
    column_order = ["datetime", "model", "latitude", "longitude"] + HOURLY_VARS
    df = df[column_order]

    return df


# ====================== CSV WRITER WITH DEDUPLICATION ======================


def write_model_csv(df: pd.DataFrame, model_name: str, output_dir: str) -> int:
    """
    Write DataFrame to model-specific CSV file with deduplication and sorting.

    Creates the output directory if it doesn't exist. If the CSV file already
    exists, reads existing data, concatenates with new data, removes duplicate
    rows based on the datetime column (keeping the first occurrence), sorts by
    datetime ascending, and writes the result back.

    Args:
        df: New data to write/append.
        model_name: Model identifier (used for filename).
        output_dir: Target directory for CSV files.

    Returns:
        Number of duplicate rows skipped.
    """
    # 1. Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # 2. Build filepath as {output_dir}/{model_name}.csv
    filepath = os.path.join(output_dir, f"{model_name}.csv")

    # 3. If file exists, read existing CSV into a DataFrame
    if os.path.exists(filepath):
        existing_df = pd.read_csv(filepath)
        # 4. Concatenate existing + new data
        combined_df = pd.concat([existing_df, df], ignore_index=True)
    else:
        combined_df = df.copy()

    # 5. Count rows before dedup
    rows_before = len(combined_df)

    # 6. Drop duplicates based on datetime column (keep='first')
    combined_df = combined_df.drop_duplicates(subset=["datetime"], keep="first")

    # 7. Count rows after dedup → difference = duplicates_removed
    rows_after = len(combined_df)
    duplicates_removed = rows_before - rows_after

    # 8. Sort by datetime ascending
    combined_df = combined_df.sort_values(by="datetime", ascending=True).reset_index(drop=True)

    # 9. Write to CSV (index=False)
    combined_df.to_csv(filepath, index=False)

    # 10. Log the number of duplicates skipped (if any)
    if duplicates_removed > 0:
        print(color_text(
            f"[{model_name}] {duplicates_removed} duplicate row(s) skipped.", YELLOW
        ))

    # 11. Return duplicates_removed
    return duplicates_removed


# ====================== BATCH MODE ======================


def run_batch(lat: float, lon: float, start_date: str, end_date: str, output_dir: str):
    """
    Fetch historical forecast data for a date range for all models.

    Iterates over all 8 models, calls fetch_with_retry() with the historical
    endpoint, parses the response, and writes to per-model CSV files.
    On error for a model, logs the error and continues to the next model.

    Args:
        lat: Target latitude.
        lon: Target longitude.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        output_dir: Directory for output CSV files.
    """
    print(f"Mode BATCH: {start_date} sampai {end_date}")
    print(f"Koordinat: {lat}, {lon}")
    print(f"Output: {output_dir}/")
    print(f"Models: {', '.join(MODELS.keys())}\n")

    success_count = 0
    error_count = 0

    for model_name in MODELS:
        print(f"  Fetching {model_name.upper()}...", end=" ")
        try:
            response_json = fetch_with_retry(
                model_name, lat, lon, start_date, end_date, endpoint="historical"
            )
            df = parse_response(response_json, model_name, lat, lon)
            duplicates = write_model_csv(df, model_name, output_dir)
            print(color_text(f"OK ({len(df)} rows, {duplicates} duplicates skipped)", GREEN))
            success_count += 1
        except Exception as e:
            print(color_text(f"GAGAL: {e}", RED))
            error_count += 1

    print(f"\nSelesai: {success_count} berhasil, {error_count} gagal.")


# ====================== SINGLE DATE MODE ======================


def run_single_date(lat: float, lon: float, date: str, output_dir: str):
    """
    Fetch historical forecast data for a single date for all models.

    Sets start_date and end_date both to the provided date value, then
    iterates over all 8 models using the same logic as run_batch().
    On error for a model, logs the error and continues to the next model.

    Args:
        lat: Target latitude.
        lon: Target longitude.
        date: Target date in YYYY-MM-DD format.
        output_dir: Directory for output CSV files.
    """
    print(f"Mode SINGLE DATE: {date}")
    print(f"Koordinat: {lat}, {lon}")
    print(f"Output: {output_dir}/")
    print(f"Models: {', '.join(MODELS.keys())}\n")

    success_count = 0
    error_count = 0

    for model_name in MODELS:
        print(f"  Fetching {model_name.upper()}...", end=" ")
        try:
            response_json = fetch_with_retry(
                model_name, lat, lon, date, date, endpoint="historical"
            )
            df = parse_response(response_json, model_name, lat, lon)
            duplicates = write_model_csv(df, model_name, output_dir)
            print(color_text(f"OK ({len(df)} rows, {duplicates} duplicates skipped)", GREEN))
            success_count += 1
        except Exception as e:
            print(color_text(f"GAGAL: {e}", RED))
            error_count += 1

    print(f"\nSelesai: {success_count} berhasil, {error_count} gagal.")


# ====================== REALTIME MODE ======================


def calculate_next_update(model_name: str, last_fetch_time: datetime) -> datetime:
    """
    Calculate when a model's next update is expected.

    Based on updates_per_day, divides 24h into equal intervals.
    E.g., GFS (4/day) → every 6 hours starting from 00:00 UTC.
    Returns the next scheduled update time after last_fetch_time.

    Args:
        model_name: Key from MODELS dict (e.g., "gfs", "icon").
        last_fetch_time: The last time this model was fetched (UTC).

    Returns:
        datetime: The next scheduled update time (UTC).
    """
    from datetime import timedelta

    updates_per_day = MODELS[model_name]["updates_per_day"]
    interval_hours = 24 / updates_per_day
    interval_seconds = interval_hours * 3600

    return last_fetch_time + timedelta(seconds=interval_seconds)


def should_fetch_model(model_name: str, last_fetched, now: datetime) -> bool:
    """
    Determine if a model should be fetched based on its update schedule.

    If never fetched (last_fetched is None), always fetch.
    Otherwise, check if enough time has passed since last fetch based on
    the model's updates_per_day (interval = 24h / updates_per_day).

    Args:
        model_name: Key from MODELS dict.
        last_fetched: The last time this model was fetched (datetime or None).
        now: Current UTC time.

    Returns:
        True if the model should be fetched, False otherwise.
    """
    if last_fetched is None:
        return True

    updates_per_day = MODELS[model_name]["updates_per_day"]
    interval_hours = 24 / updates_per_day
    interval_seconds = interval_hours * 3600

    elapsed = (now - last_fetched).total_seconds()
    return elapsed >= interval_seconds


def run_realtime(lat: float, lon: float, output_dir: str):
    """
    Continuously poll for latest forecast data with model-aware scheduling.

    Uses the forecast endpoint (not historical) and respects each model's
    update frequency. Displays status messages each cycle showing which
    models were fetched and which were skipped. Sleeps 15 minutes between
    check cycles. Handles KeyboardInterrupt for graceful shutdown with summary.

    Args:
        lat: Target latitude.
        lon: Target longitude.
        output_dir: Directory for output CSV files.
    """
    CHECK_INTERVAL = 900  # 15 minutes in seconds

    print(f"Mode REALTIME: polling kontinu")
    print(f"Koordinat: {lat}, {lon}")
    print(f"Output: {output_dir}/")
    print(f"Check interval: {CHECK_INTERVAL // 60} menit")
    print(f"Tekan Ctrl+C untuk berhenti.\n")

    # Track last fetch time per model (None = never fetched)
    last_fetched = {model: None for model in MODELS}
    total_fetches = 0
    total_errors = 0

    try:
        while True:
            now = datetime.now(timezone.utc)
            fetched_this_cycle = []
            skipped_this_cycle = []

            for model_name in MODELS:
                if should_fetch_model(model_name, last_fetched[model_name], now):
                    try:
                        response_json = fetch_with_retry(
                            model_name, lat, lon, "", "", endpoint="forecast"
                        )
                        df = parse_response(response_json, model_name, lat, lon)
                        write_model_csv(df, model_name, output_dir)
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
        print(f"\nRealtime monitoring dihentikan.")
        print(f"Total fetches: {total_fetches}, Errors: {total_errors}")


# ====================== MAIN ENTRY POINT ======================


def main():
    """
    Main function that ties all components together.

    Parses CLI arguments, creates the output directory, and routes
    to the appropriate mode function based on parsed arguments.
    Handles top-level exceptions gracefully.
    """
    try:
        args = parse_and_validate_args()

        # Create output directory
        os.makedirs(args.output, exist_ok=True)

        # Route to appropriate mode
        if args.mode == "realtime":
            run_realtime(args.lat, args.lon, args.output)
        elif args.date:
            run_single_date(args.lat, args.lon, args.date, args.output)
        elif args.start and args.end:
            run_batch(args.lat, args.lon, args.start, args.end, args.output)
        else:
            # This shouldn't be reached due to parse_and_validate_args validation,
            # but included as a safety net.
            print(color_text("Error: Tidak ada mode yang dipilih.", RED))
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nProses dibatalkan oleh pengguna.")
        sys.exit(0)
    except SystemExit:
        # Let argparse exits pass through
        raise
    except Exception as e:
        print(color_text(f"Error fatal: {e}", RED))
        sys.exit(1)


if __name__ == "__main__":
    main()
