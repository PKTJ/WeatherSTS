import argparse
import csv
import os
import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def color_text(text, color):
    return f"{color}{text}{RESET}"

# ================== KONFIGURASI ==================
API_KEY = "MASUKAN_API_KEY" # Ganti dengan API Key CheckWX 

# Interval polling (detik). 300 = 5 menit
DEFAULT_POLL_INTERVAL = 300

STATION_INFO_URL = "https://aviationweather.gov/api/data/stationinfo"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

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


def append_live_row(row, filename):
    file_exists = os.path.exists(filename)
    should_write_header = (not file_exists) or os.path.getsize(filename) == 0

    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        if should_write_header:
            writer.writeheader()
        writer.writerow(row)


def read_last_live_record_key(filename):
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

        obs_time = last_row.get("local_time") or last_row.get("observation_time") or "-"
        raw_text = last_row.get("raw_text") or ""
        return obs_time, raw_text
    except Exception:
        return None


def get_nested(data, *path):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def get_first(data, path_options):
    for path in path_options:
        value = get_nested(data, *path)
        if value is not None:
            return value
    return None


def parse_observation_datetime(metar):
    observed = get_first(
        metar,
        [
            ("observed",),
            ("observation_time",),
            ("reportTime",),
            ("receiptTime",),
            ("obsTime",),
        ],
    )

    if isinstance(observed, (int, float)):
        return datetime.fromtimestamp(observed, tz=timezone.utc)

    if not isinstance(observed, str):
        return None

    observed_text = observed.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(observed_text)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def format_direction(value):
    if value is None:
        return ""

    if isinstance(value, str):
        stripped = value.strip().upper()
        if stripped == "VRB":
            return "VRB"
        if stripped == "":
            return ""

    try:
        return f"{int(float(value)):03d}"
    except (TypeError, ValueError):
        return str(value)


def extract_wind_dir(metar):
    wind_dir = get_first(
        metar,
        [
            ("wind", "direction"),
            ("wind", "degrees"),
            ("wind", "dir"),
            ("wind_dir",),
            ("wdir",),
        ],
    )

    if isinstance(wind_dir, str):
        stripped = wind_dir.strip().upper()
        if stripped == "VRB":
            return "VRB"
        if stripped.isdigit():
            try:
                return int(stripped)
            except ValueError:
                return stripped
        return stripped

    if wind_dir is None:
        return ""

    try:
        return int(float(wind_dir))
    except (TypeError, ValueError):
        return wind_dir


def extract_wind_dir_var(metar, raw_text, wind_dir):
    wind_from = get_first(
        metar,
        [
            ("wind", "direction_from"),
            ("wind", "degrees_from"),
            ("wind", "from"),
            ("wind", "variable_from"),
            ("wind_from",),
            ("wdirFrom",),
        ],
    )
    wind_to = get_first(
        metar,
        [
            ("wind", "direction_to"),
            ("wind", "degrees_to"),
            ("wind", "to"),
            ("wind", "variable_to"),
            ("wind_to",),
            ("wdirTo",),
        ],
    )

    if wind_from is not None and wind_to is not None:
        from_text = format_direction(wind_from)
        to_text = format_direction(wind_to)
        if from_text and to_text:
            return f"{from_text}V{to_text}"

    match = re.search(r"\b\d{3}V\d{3}\b", raw_text)
    if match:
        return match.group(0)

    if isinstance(wind_dir, str) and wind_dir.upper() == "VRB":
        return "VRB"

    return ""


def extract_cloud_layers(metar):
    layers = get_first(
        metar,
        [
            ("clouds",),
            ("cloud_layers",),
            ("sky_condition",),
            ("skyCondition",),
        ],
    )
    if not isinstance(layers, list):
        return ""

    result = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue

        cover = (
            layer.get("code")
            or layer.get("sky_cover")
            or layer.get("coverage")
            or layer.get("cover")
            or layer.get("type")
            or ""
        )

        base_raw = (
            layer.get("base_feet_agl")
            or layer.get("cloud_base_ft_agl")
            or layer.get("base")
            or layer.get("base_feet")
            or layer.get("altitude")
            or layer.get("feet")
        )

        if not cover:
            continue

        if base_raw is None:
            result.append(str(cover))
            continue

        try:
            base_ft = int(float(base_raw))
            base_code = f"{base_ft // 100:03d}"
        except (TypeError, ValueError):
            base_code = str(base_raw)

        result.append(f"{cover}{base_code}")

    return " ".join(result)


def extract_auto(raw_text):
    auto = "AUTO" if " AUTO " in f" {raw_text} " else ""
    cor = "COR" if " COR " in f" {raw_text} " else ""
    if auto and cor:
        return "AUTO/COR"
    return auto or cor


def extract_wx_string(metar):
    wx_value = get_first(metar, [("wx_string",), ("wxString",), ("present_weather",)])
    if wx_value is not None:
        if isinstance(wx_value, list):
            return " ".join(str(item) for item in wx_value)
        return str(wx_value)

    conditions = get_first(metar, [("conditions",)])
    if not isinstance(conditions, list):
        return ""

    intensity_map = {
        "light": "-",
        "moderate": "",
        "heavy": "+",
        "vicinity": "VC",
    }

    tokens = []
    for condition in conditions:
        if not isinstance(condition, dict):
            continue

        code = condition.get("code") or condition.get("abbr") or condition.get("text")
        if not code:
            continue

        code_text = str(code).strip()
        intensity_prefix = intensity_map.get(str(condition.get("intensity", "")).lower(), "")

        if intensity_prefix and not code_text.startswith(("+", "-", "VC")):
            tokens.append(f"{intensity_prefix}{code_text}")
        else:
            tokens.append(code_text)

    return " ".join(tokens)


def extract_recent_weather(raw_text):
    matches = re.findall(r"\bRE[A-Z]{2,}\b", raw_text)
    return ",".join(matches)


def extract_rvr(raw_text):
    matches = re.findall(r"\bR\d{2}[LCR]?/\w+\b", raw_text)
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


def extract_station_coordinates(metar):
    latitude = get_first(metar, [("station", "latitude"), ("station", "lat"), ("latitude",), ("lat",)])
    longitude = get_first(metar, [("station", "longitude"), ("station", "lon"), ("longitude",), ("lon",)])

    if latitude is not None and longitude is not None:
        return latitude, longitude

    location = get_nested(metar, "station", "location")
    if isinstance(location, dict):
        latitude = location.get("latitude") or location.get("lat")
        longitude = location.get("longitude") or location.get("lon")
        if latitude is not None and longitude is not None:
            return latitude, longitude

    if isinstance(location, (list, tuple)) and len(location) >= 2:
        # Format koordinat umum: [lon, lat]
        return location[1], location[0]

    return None, None


def get_station_metadata(icao, requests_module):
    metadata = {
        "latitude": None,
        "longitude": None,
        "elevation_m": None,
    }

    try:
        response = requests_module.get(
            STATION_INFO_URL,
            params={"ids": icao, "format": "json"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        station = data[0] if isinstance(data, list) and data else data
        if isinstance(station, dict):
            metadata["latitude"] = station.get("lat")
            metadata["longitude"] = station.get("lon")
            metadata["elevation_m"] = station.get("elev")
    except Exception:
        pass

    return metadata


def resolve_station_timezone(station_metadata, requests_module):
    latitude = station_metadata.get("latitude")
    longitude = station_metadata.get("longitude")
    if latitude is None or longitude is None:
        return "UTC"

    try:
        response = requests_module.get(
            OPEN_METEO_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
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


def build_csv_row(metar, tzinfo, station_metadata=None):
    station_metadata = station_metadata or {}

    obs_dt = parse_observation_datetime(metar)
    observed_raw = get_first(
        metar,
        [
            ("observed",),
            ("observation_time",),
            ("reportTime",),
            ("receiptTime",),
        ],
    )
    raw_text = get_first(metar, [("raw_text",), ("raw",), ("rawOb",)]) or ""

    report_type = get_first(metar, [("report", "type"), ("report_type",), ("type",)])
    if isinstance(report_type, str):
        report_type = report_type.strip().upper()
    if not report_type:
        report_type = "SPECI" if raw_text.startswith("SPECI") else "METAR"

    wind_dir = extract_wind_dir(metar)
    remarks = extract_remarks(raw_text)

    pressure_mb = get_first(
        metar,
        [
            ("pressure", "mb"),
            ("pressure", "hpa"),
            ("barometer", "mb"),
            ("barometer", "hpa"),
            ("pressure_mb",),
            ("altim_in_mb",),
            ("altim",),
        ],
    )

    latitude = station_metadata.get("latitude")
    longitude = station_metadata.get("longitude")
    elevation_m = station_metadata.get("elevation_m")

    if latitude is None or longitude is None:
        parsed_lat, parsed_lon = extract_station_coordinates(metar)
        if latitude is None:
            latitude = parsed_lat
        if longitude is None:
            longitude = parsed_lon

    if elevation_m is None:
        elevation_m = get_first(
            metar,
            [
                ("elevation", "meters"),
                ("elevation", "m"),
                ("elevation_m",),
                ("station", "elevation_m"),
            ],
        )

    return {
        "observation_time": obs_dt.isoformat() if obs_dt else (observed_raw or ""),
        "local_time": obs_dt.astimezone(tzinfo).strftime("%Y-%m-%d %H:%M:%S") if obs_dt else "",
        "raw_text": raw_text,
        "report_type": report_type,
        "temp_c": get_first(metar, [("temperature", "celsius"), ("temperature", "c"), ("temp_c",), ("temp",)]),
        "dewpoint_c": get_first(metar, [("dewpoint", "celsius"), ("dewpoint", "c"), ("dewpoint_c",), ("dewp",)]),
        "wind_dir": wind_dir,
        "wind_speed_kt": get_first(metar, [("wind", "speed", "kts"), ("wind", "speed_kts"), ("wind", "kts"), ("wind_speed_kt",), ("wspd",)]),
        "wind_gust_kt": get_first(metar, [("wind", "gust", "kts"), ("wind", "gust_kts"), ("wind", "gusts", "kts"), ("wind_gust_kt",), ("wgst",)]),
        "wind_dir_var": extract_wind_dir_var(metar, raw_text, wind_dir),
        "visibility": get_first(metar, [("visibility", "text"), ("visibility", "meters"), ("visibility", "miles"), ("visibility",), ("visib",)]) or "",
        "pressure_mb": pressure_mb,
        "cloud_layers": extract_cloud_layers(metar),
        "wx_string": extract_wx_string(metar),
        "flight_category": get_first(metar, [("flight_category",), ("flightCategory",)]),
        "auto": extract_auto(raw_text),
        "recent_weather": extract_recent_weather(raw_text),
        "rvr": extract_rvr(raw_text),
        "remarks": remarks,
        "rmk_indicators": extract_rmk_indicators(remarks),
        "latitude": latitude,
        "longitude": longitude,
        "elevation_m": elevation_m,
    }



def monitor_metar(icao, poll_interval):
    try:
        import requests
    except ModuleNotFoundError:
        print(color_text("Module requests belum terpasang. Jalankan: py -m pip install requests", RED))
        return

    headers = {
        "X-API-Key": API_KEY
    }
    url = f"https://api.checkwx.com/v2/metar/{icao}/decoded"
    live_csv_file = f"{icao}_live.csv"

    station_metadata = get_station_metadata(icao, requests)
    station_timezone = resolve_station_timezone(station_metadata, requests)

    try:
        tzinfo = ZoneInfo(station_timezone)
    except Exception:
        tzinfo = timezone.utc

    # Variabel untuk mendeteksi perubahan data
    last_record_key = read_last_live_record_key(live_csv_file)

    print(color_text(f"Monitoring METAR {icao} via CheckWX API (setiap {poll_interval//60} menit)\n", GREEN))
    print(color_text(f"Timezone stasiun {icao}: {station_timezone}", GREEN))
    print(color_text(f"Live CSV aktif: {live_csv_file}", GREEN))

    while True:
        # Waktu sekarang dalam WIB (UTC+7)
        wib_time = (datetime.utcnow() + timedelta(hours=7)).strftime("%H:%M:%S")

        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if data.get("results", 0) > 0 and data["data"]:
                    metar = data["data"][0]

                    row = build_csv_row(metar, tzinfo, station_metadata)
                    observed = row.get("local_time") or row.get("observation_time") or "-"
                    raw_text = row.get("raw_text") or ""
                    record_key = (observed, raw_text)

                    # Cek apakah ada data baru
                    if record_key != last_record_key:
                        print(color_text(f"[{wib_time}] Data BARU diterima!", GREEN))
                        print(f"local_time         : {observed}")
                        print(f"raw_text           : {raw_text or 'N/A'}")
                        print(f"report_type        : {row.get('report_type')}")
                        print(f"temp_c             : {row.get('temp_c')}")
                        print(f"dewpoint_c         : {row.get('dewpoint_c')}")
                        print(f"wind_dir           : {row.get('wind_dir')}")
                        print(f"wind_speed_kt      : {row.get('wind_speed_kt')}")
                        print(f"wind_gust_kt       : {row.get('wind_gust_kt')}")
                        print(f"visibility         : {row.get('visibility')}")
                        print(f"pressure_mb        : {row.get('pressure_mb')}")
                        print(f"flight_category    : {row.get('flight_category')}")

                        append_live_row(row, live_csv_file)

                        print(color_text(f"Record live tersimpan ke {live_csv_file}", GREEN))
                        print(color_text("-" * 80, GREEN))

                        last_record_key = record_key
                    else:
                        print(color_text(f"[{wib_time}] Tidak ada perubahan data...", YELLOW))

            elif response.status_code == 429:
                print(color_text(f"[{wib_time}] Rate limit exceeded (429). Tunggu sebentar...", YELLOW))
            else:
                print(color_text(f"[{wib_time}] Error HTTP {response.status_code}: {response.text[:100]}", RED))

        except requests.exceptions.RequestException as e:
            print(color_text(f"[{wib_time}] Koneksi error: {e}", RED))
        except Exception as e:
            print(color_text(f"[{wib_time}] Unexpected error: {e}", RED))

        # Tunggu sampai interval berikutnya
        time.sleep(poll_interval)


def parse_args():
    parser = argparse.ArgumentParser(description="Realtime METAR monitor dari CheckWX + rekam live CSV.")
    parser.add_argument("--icao", required=True, help="Kode ICAO, contoh: WSSS")
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Interval polling dalam detik (default: {DEFAULT_POLL_INTERVAL})",
    )
    args = parser.parse_args()

    if args.interval <= 0:
        parser.error("--interval harus lebih besar dari 0")

    return args


def main():
    args = parse_args()
    monitor_metar(args.icao.upper(), args.interval)


if __name__ == "__main__":
    main()