import requests
import json
import csv
import os
from datetime import datetime, timedelta, timezone
import time
import argparse
import sys
import re
from zoneinfo import ZoneInfo

BASE_URL = "https://aviationweather.gov/api/data/metar"
STATION_INFO_URL = "https://aviationweather.gov/api/data/stationinfo"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

CSV_FIELDNAMES = [
    "local_time",
    "raw_text",
    "report_type",
    "temp_c",
    "dewpoint_c",
    "wind_dir",
    "wind_speed_kt",
    "wind_gust_kt",
    "wind_dir_var",
    "visibility",
    "pressure_mb",
    "cloud_layers",
    "wx_string",
    "flight_category",
    "auto",
    "recent_weather",
    "rvr",
    "remarks",
    "rmk_indicators",
    "latitude",
    "longitude",
    "elevation_m",
]


def color_text(text, color):
    return f"{color}{text}{RESET}"

def get_field(metar, *keys):
    """Return the first available field from multiple candidate keys."""
    for key in keys:
        if key in metar and metar[key] is not None:
            return metar[key]
    return None

def get_observation_datetime(metar):
    """Normalize observation time from multiple API formats (legacy/current)."""
    time_str = get_field(metar, "observation_time", "reportTime", "receiptTime")
    if isinstance(time_str, str):
        try:
            return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    epoch = get_field(metar, "obsTime")
    if isinstance(epoch, (int, float)):
        return datetime.fromtimestamp(epoch, tz=timezone.utc)

    return None

def fetch_metar(icao, hours=None):
    """Fetch METAR data from the NOAA API."""
    params = {
        "ids": icao,
        "format": "json"
    }
    if hours:
        params["hours"] = hours

    try:
        response = requests.get(BASE_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # NOAA JSON can be either a direct list or nested under 'data'.
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "data" in data:
            return data["data"]
        else:
            return data if data else []
    except Exception as e:
        print(color_text(f"Error fetching data: {e}", RED))
        return []

def get_station_latlon(icao):
    """Get station lat/lon from ICAO."""
    try:
        response = requests.get(
            STATION_INFO_URL,
            params={"ids": icao, "format": "json"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        station = data[0] if isinstance(data, list) and data else data
        if not isinstance(station, dict):
            return None, None

        lat = station.get("lat")
        lon = station.get("lon")
        return lat, lon
    except Exception:
        return None, None


def get_station_metadata(icao):
    """Get station metadata: latitude, longitude, elevation."""
    try:
        response = requests.get(
            STATION_INFO_URL,
            params={"ids": icao, "format": "json"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        station = data[0] if isinstance(data, list) and data else data
        if not isinstance(station, dict):
            return {"latitude": None, "longitude": None, "elevation_m": None}

        return {
            "latitude": station.get("lat"),
            "longitude": station.get("lon"),
            "elevation_m": station.get("elev"),
        }
    except Exception:
        return {"latitude": None, "longitude": None, "elevation_m": None}

def resolve_station_timezone(icao):
    """Detect station timezone from ICAO coordinates."""
    lat, lon = get_station_latlon(icao)
    if lat is None or lon is None:
        return "UTC"

    try:
        response = requests.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m",
                "timezone": "auto",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        tz_name = data.get("timezone")
        if tz_name:
            return tz_name
    except Exception:
        pass

    return "UTC"

def is_speci(metar):
    """Detect whether the report is SPECI or METAR."""
    raw = get_field(metar, "raw_text", "rawOb") or ""
    if raw.startswith("SPECI"):
        return "SPECI"
    metar_type = get_field(metar, "metar_type", "metarType")
    if metar_type == "SPECI":
        return "SPECI"
    return "METAR"


def extract_cloud_layers(metar):
    """Normalize cloud layers to compact METAR format (e.g., FEW016 BKN300)."""
    layers = get_field(metar, "sky_condition", "skyCondition", "clouds", "cloudLayers")
    if not isinstance(layers, list):
        return ""

    result = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        cover = (
            layer.get("sky_cover")
            or layer.get("coverage")
            or layer.get("cover")
            or layer.get("type")
            or ""
        )
        base_raw = (
            layer.get("cloud_base_ft_agl")
            or layer.get("base")
            or layer.get("base_feet_agl")
            or layer.get("altitude")
        )

        base_code = ""
        if base_raw is not None:
            try:
                base_ft = int(float(base_raw))
                # METAR cloud base is encoded in hundreds of feet, 3 digits.
                base_code = f"{base_ft // 100:03d}"
            except (ValueError, TypeError):
                base_code = str(base_raw)

        if cover and base_code:
            result.append(f"{cover}{base_code}")
        elif cover:
            result.append(str(cover))

    return " ".join(result)


def extract_auto(metar):
    raw = get_field(metar, "raw_text", "rawOb") or ""
    auto = "AUTO" if " AUTO " in f" {raw} " else ""
    cor = "COR" if " COR " in f" {raw} " else ""
    if auto and cor:
        return "AUTO/COR"
    return auto or cor


def extract_wx_string(metar):
    wx_value = get_field(metar, "wx_string", "wxString", "present_weather")
    if wx_value is None:
        return ""
    if isinstance(wx_value, list):
        return " ".join(str(item) for item in wx_value)
    return str(wx_value)


def extract_recent_weather(metar):
    raw = get_field(metar, "raw_text", "rawOb") or ""
    matches = re.findall(r"\bRE[A-Z]{2,}\b", raw)
    return ",".join(matches)


def extract_wind_dir_var(metar):
    wind_from = get_field(metar, "wind_dir_from", "wdirFrom")
    wind_to = get_field(metar, "wind_dir_to", "wdirTo")
    if wind_from is not None and wind_to is not None:
        return f"{wind_from}V{wind_to}"

    raw = get_field(metar, "raw_text", "rawOb") or ""
    match = re.search(r"\b\d{3}V\d{3}\b", raw)
    if match:
        return match.group(0)

    wind_dir = get_field(metar, "wind_dir", "wdir")
    if str(wind_dir).upper() == "VRB":
        return "VRB"
    return ""


def extract_rvr(metar):
    raw = get_field(metar, "raw_text", "rawOb") or ""
    matches = re.findall(r"\bR\d{2}[LCR]?/\w+\b", raw)
    return ", ".join(matches)


def extract_remarks(raw_text):
    if " RMK " in f" {raw_text} ":
        return raw_text.split(" RMK ", 1)[1].strip()
    return ""


def extract_rmk_indicators(remarks):
    if not remarks:
        return ""
    indicators = []
    for token in ["WSHFT", "PK WND", "PRESFR", "PRESRR"]:
        if token in remarks:
            indicators.append(token)
    return ",".join(indicators)


def build_csv_row(metar, tzinfo, station_metadata=None):
    station_metadata = station_metadata or {}
    obs_dt = get_observation_datetime(metar)
    raw_text = get_field(metar, "raw_text", "rawOb") or ""
    remarks = extract_remarks(raw_text)

    return {
        "observation_time": obs_dt.isoformat() if obs_dt else "",
        "local_time": obs_dt.astimezone(tzinfo).strftime("%Y-%m-%d %H:%M:%S") if obs_dt else "",
        "raw_text": raw_text,
        "report_type": is_speci(metar),
        "temp_c": get_field(metar, "temp_c", "temp"),
        "dewpoint_c": get_field(metar, "dewpoint_c", "dewp"),
        "wind_dir": get_field(metar, "wind_dir", "wdir"),
        "wind_speed_kt": get_field(metar, "wind_speed_kt", "wspd"),
        "wind_gust_kt": get_field(metar, "wind_gust_kt", "wgst"),
        "wind_dir_var": extract_wind_dir_var(metar),
        "visibility": get_field(metar, "visibility", "visib"),
        "pressure_mb": get_field(metar, "altim_in_mb", "pressure_mb", "altim"),
        "cloud_layers": extract_cloud_layers(metar),
        "wx_string": extract_wx_string(metar),
        "flight_category": get_field(metar, "flight_category", "flightCategory"),
        "auto": extract_auto(metar),
        "recent_weather": extract_recent_weather(metar),
        "rvr": extract_rvr(metar),
        "remarks": remarks,
        "rmk_indicators": extract_rmk_indicators(remarks),
        "latitude": station_metadata.get("latitude"),
        "longitude": station_metadata.get("longitude"),
        "elevation_m": station_metadata.get("elevation_m"),
    }


def append_live_row(metar, filename, station_timezone="UTC", station_metadata=None):
    station_metadata = station_metadata or {}
    try:
        tzinfo = ZoneInfo(station_timezone)
    except Exception:
        tzinfo = timezone.utc

    row = build_csv_row(metar, tzinfo, station_metadata)
    file_exists = os.path.exists(filename)
    should_write_header = (not file_exists) or os.path.getsize(filename) == 0

    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        if should_write_header:
            writer.writeheader()
        writer.writerow(row)


def read_last_live_record_key(filename):
    """Read the last live record so restart does not immediately duplicate entries."""
    if not os.path.exists(filename):
        return None

    try:
        last_row = None
        with open(filename, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                last_row = row

        if not last_row:
            return None

        obs_time = last_row.get("observation_time") or last_row.get("local_time") or "-"
        raw_text = last_row.get("raw_text") or ""
        return obs_time, raw_text
    except Exception:
        return None

def save_to_csv(metars, filename, station_timezone="UTC", station_metadata=None):
    """Save history rows to CSV."""
    if not metars:
        print(color_text("No data to save.", YELLOW))
        return

    station_metadata = station_metadata or {}

    try:
        tzinfo = ZoneInfo(station_timezone)
    except Exception:
        tzinfo = timezone.utc
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for m in metars:
            writer.writerow(build_csv_row(m, tzinfo, station_metadata))
    print(color_text(f"Data successfully saved to: {filename}", GREEN))

def history_mode(icao, target_date=None):
    """Modes 1 and 2: fetch historical data."""
    now = datetime.now(timezone.utc)
    
    if target_date is None:  # Today
        hours = 48  # Safe window for 24h coverage plus buffer.
        date_str = now.strftime("%Y-%m-%d")
        print(f"Fetching METAR data for {icao} for today ({date_str})...")
    else:
        target = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        hours = int((now - target).total_seconds() / 3600) + 24  # buffer
        if hours > 360:  # NOAA limit is around 15 days.
            hours = 360
        date_str = target_date
        print(f"Fetching METAR data for {icao} for date {date_str}...")

    metars = fetch_metar(icao, hours=hours)
    
    # Filter to the requested date.
    filtered = []
    for m in metars:
        obs_dt = get_observation_datetime(m)
        if obs_dt:
            obs_date = obs_dt.date()
            if obs_date.strftime("%Y-%m-%d") == date_str:
                filtered.append(m)
    
    if filtered:
        filename = f"{icao}_{date_str.replace('-', '')}.csv"
        station_timezone = resolve_station_timezone(icao)
        station_metadata = get_station_metadata(icao)
        print(color_text(f"Station timezone for {icao}: {station_timezone}", YELLOW))
        save_to_csv(
            filtered,
            filename,
            station_timezone=station_timezone,
            station_metadata=station_metadata,
        )
        print(f"Total data: {len(filtered)} records")
    else:
        print(color_text("No data found for that date.", RED))

def realtime_mode(icao):
    """Mode 3: realtime monitoring (continuous + live CSV logging)."""
    print(f"Realtime mode for {icao} is active. Polling every 5 minutes...")
    print("Press Ctrl+C to stop.\n")

    station_timezone = resolve_station_timezone(icao)
    station_metadata = get_station_metadata(icao)
    live_filename = f"{icao}_live.csv"
    print(color_text(f"Station timezone for {icao}: {station_timezone}", YELLOW))
    print(color_text(f"File live: {live_filename}", YELLOW))

    try:
        tzinfo = ZoneInfo(station_timezone)
    except Exception:
        tzinfo = timezone.utc

    # Use the last stored record so restart does not rewrite the same data.
    last_record_key = read_last_live_record_key(live_filename)
    
    while True:
        try:
            metars = fetch_metar(icao)  # latest only
            if not metars:
                print(color_text("No data from server", YELLOW))
                time.sleep(300)
                continue

            latest = metars[0]  # newest data
            raw_text = get_field(latest, "raw_text", "rawOb") or ""
            obs_dt = get_observation_datetime(latest)
            local_time = obs_dt.astimezone(tzinfo).strftime("%Y-%m-%d %H:%M:%S") if obs_dt else "-"
            record_key = (local_time, raw_text)
            report_type = is_speci(latest)
            temp_c = get_field(latest, "temp_c", "temp")
            dewpoint_c = get_field(latest, "dewpoint_c", "dewp")
            wind_dir = get_field(latest, "wind_dir", "wdir")
            wind_speed_kt = get_field(latest, "wind_speed_kt", "wspd")
            visibility = get_field(latest, "visibility", "visib")
            pressure_mb = get_field(latest, "altim_in_mb", "pressure_mb", "altim")

            # Print and save only when observation data changes.
            if record_key != last_record_key:
                print(color_text("=" * 80, GREEN))
                print(color_text(f"Time {datetime.now().strftime('%Y-%m-%d %H:%M:%S local')}", GREEN))
                print(f"local_time       : {local_time}")
                print(f"raw_text         : {raw_text}")
                print(f"report_type      : {report_type}")
                print(f"temp_c           : {temp_c if temp_c is not None else '-'}")
                print(f"dewpoint_c       : {dewpoint_c if dewpoint_c is not None else '-'}")
                print(f"wind_dir         : {wind_dir if wind_dir is not None else '-'}")
                print(f"wind_speed_kt    : {wind_speed_kt if wind_speed_kt is not None else '-'}")
                print(f"visibility       : {visibility if visibility is not None else '-'}")
                print(f"pressure_mb      : {pressure_mb if pressure_mb is not None else '-'}")
                print(color_text("=" * 80, GREEN))

                append_live_row(
                    latest,
                    live_filename,
                    station_timezone=station_timezone,
                    station_metadata=station_metadata,
                )
                print(color_text(f"Live record saved to {live_filename}", GREEN))

                last_record_key = record_key
            else:
                print(color_text(f"[{datetime.now().strftime('%H:%M:%S')}] No data changes...", YELLOW))

        except KeyboardInterrupt:
            print(color_text("\nRealtime monitoring stopped.", YELLOW))
            break
        except Exception as e:
            print(color_text(f"Error: {e}", RED))

        time.sleep(300)  # 5 minutes

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="METAR NOAA Scraper")
    parser.add_argument("--icao", required=True, help="4-character ICAO code (example: WSSS)")
    subparsers = parser.add_subparsers(dest="mode", help="Select mode")

    # Today history
    today_parser = subparsers.add_parser("today", help="Fetch today's history")
    
    # Specific-date history
    date_parser = subparsers.add_parser("history", help="Fetch history for a specific date")
    date_parser.add_argument("--date", required=True, help="Format: YYYY-MM-DD (example: 2026-03-31)")

    # Realtime
    realtime_parser = subparsers.add_parser("realtime", help="Realtime monitoring mode")

    args = parser.parse_args()
    icao = args.icao.strip().upper()

    if args.mode == "today":
        history_mode(icao)
    elif args.mode == "history":
        history_mode(icao, args.date)
    elif args.mode == "realtime":
        realtime_mode(icao)
    else:
        parser.print_help()

# Data source note (NOAA):
# This source works best for airports in the United States.
# Some airports in Europe may have delayed or unstable realtime updates.
# Similar issues can also occur at some airports in Asia, so test before production monitoring.