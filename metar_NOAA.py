import requests
import json
import csv
from datetime import datetime, timedelta, timezone
import time
import argparse
import sys
import re
from zoneinfo import ZoneInfo

ICAO = "MASUKAN_KODE_ICAO_DISINI"  # Ganti dengan ICAO yang diinginkan
BASE_URL = "https://aviationweather.gov/api/data/metar"
STATION_INFO_URL = "https://aviationweather.gov/api/data/stationinfo"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def color_text(text, color):
    return f"{color}{text}{RESET}"

def get_field(metar, *keys):
    """Ambil field pertama yang tersedia dari beberapa kandidat key."""
    for key in keys:
        if key in metar and metar[key] is not None:
            return metar[key]
    return None

def get_observation_datetime(metar):
    """Normalisasi waktu observasi dari berbagai format API (lama/baru)."""
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

def fetch_metar(hours=None):
    """Fetch METAR dari NOAA API"""
    params = {
        "ids": ICAO,
        "format": "json"
    }
    if hours:
        params["hours"] = hours

    try:
        response = requests.get(BASE_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Struktur JSON NOAA kadang list langsung, kadang di dalam 'data'
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
    """Ambil lat/lon stasiun dari ICAO."""
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
    """Ambil metadata stasiun: latitude, longitude, elevation."""
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
    """Deteksi timezone stasiun berdasarkan koordinat ICAO."""
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
    """Deteksi SPECI atau METAR"""
    raw = get_field(metar, "raw_text", "rawOb") or ""
    if raw.startswith("SPECI"):
        return "SPECI"
    metar_type = get_field(metar, "metar_type", "metarType")
    if metar_type == "SPECI":
        return "SPECI"
    return "METAR"


def extract_cloud_layers(metar):
    """Normalisasi cloud layers ke format METAR ringkas (mis. FEW016 BKN300)."""
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
                # METAR cloud base ditulis dalam ratusan feet, 3 digit.
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

def save_to_csv(metars, filename, station_timezone="UTC", station_metadata=None):
    """Simpan history ke CSV"""
    if not metars:
        print(color_text("Tidak ada data untuk disimpan.", YELLOW))
        return
    
    fieldnames = [
        "observation_time",
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

    station_metadata = station_metadata or {}

    try:
        tzinfo = ZoneInfo(station_timezone)
    except Exception:
        tzinfo = timezone.utc
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in metars:
            obs_dt = get_observation_datetime(m)
            raw_text = get_field(m, "raw_text", "rawOb") or ""
            remarks = extract_remarks(raw_text)
            writer.writerow({
                "observation_time": obs_dt.isoformat() if obs_dt else "",
                "local_time": obs_dt.astimezone(tzinfo).strftime("%Y-%m-%d %H:%M:%S") if obs_dt else "",
                "raw_text": raw_text,
                "report_type": is_speci(m),
                "temp_c": get_field(m, "temp_c", "temp"),
                "dewpoint_c": get_field(m, "dewpoint_c", "dewp"),
                "wind_dir": get_field(m, "wind_dir", "wdir"),
                "wind_speed_kt": get_field(m, "wind_speed_kt", "wspd"),
                "wind_gust_kt": get_field(m, "wind_gust_kt", "wgst"),
                "wind_dir_var": extract_wind_dir_var(m),
                "visibility": get_field(m, "visibility", "visib"),
                "pressure_mb": get_field(m, "altim_in_mb", "pressure_mb", "altim"),
                "cloud_layers": extract_cloud_layers(m),
                "wx_string": extract_wx_string(m),
                "flight_category": get_field(m, "flight_category", "flightCategory"),
                "auto": extract_auto(m),
                "recent_weather": extract_recent_weather(m),
                "rvr": extract_rvr(m),
                "remarks": remarks,
                "rmk_indicators": extract_rmk_indicators(remarks),
                "latitude": station_metadata.get("latitude"),
                "longitude": station_metadata.get("longitude"),
                "elevation_m": station_metadata.get("elevation_m"),
            })
    print(color_text(f"Data berhasil disimpan ke: {filename}", GREEN))

def history_mode(target_date=None):
    """Mode 1 & 2: Ambil history"""
    now = datetime.now(timezone.utc)
    
    if target_date is None:  # Hari ini
        hours = 48  # aman untuk cover 24 jam + buffer
        date_str = now.strftime("%Y-%m-%d")
        print(f"Mengambil data METAR {ICAO} untuk hari ini ({date_str})...")
    else:
        target = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        hours = int((now - target).total_seconds() / 3600) + 24  # buffer
        if hours > 360:  # batas NOAA ~15 hari
            hours = 360
        date_str = target_date
        print(f"Mengambil data METAR {ICAO} untuk tanggal {date_str}...")

    metars = fetch_metar(hours=hours)
    
    # Filter sesuai tanggal yang diminta
    filtered = []
    for m in metars:
        obs_dt = get_observation_datetime(m)
        if obs_dt:
            obs_date = obs_dt.date()
            if obs_date.strftime("%Y-%m-%d") == date_str:
                filtered.append(m)
    
    if filtered:
        filename = f"{ICAO}_{date_str.replace('-', '')}.csv"
        station_timezone = resolve_station_timezone(ICAO)
        station_metadata = get_station_metadata(ICAO)
        print(color_text(f"Timezone stasiun {ICAO}: {station_timezone}", YELLOW))
        save_to_csv(
            filtered,
            filename,
            station_timezone=station_timezone,
            station_metadata=station_metadata,
        )
        print(f"Total data: {len(filtered)} record")
    else:
        print(color_text("Tidak ada data ditemukan untuk tanggal tersebut.", RED))

def realtime_mode():
    """Mode 3: Real-time monitoring (jalan terus)"""
    print(f"Mode Real-time {ICAO} aktif. Polling setiap 5 menit...")
    print("Tekan Ctrl+C untuk stop.\n")
    
    last_raw_text = None
    last_obs_time = None
    
    while True:
        try:
            metars = fetch_metar()  # latest only
            if not metars:
                print(color_text("Tidak ada data dari server", YELLOW))
                time.sleep(300)
                continue

            latest = metars[0]  # data paling baru
            raw_text = get_field(latest, "raw_text", "rawOb") or ""
            obs_dt = get_observation_datetime(latest)
            obs_time = obs_dt.isoformat() if obs_dt else "-"
            report_type = is_speci(latest)
            temp_c = get_field(latest, "temp_c", "temp")
            dewpoint_c = get_field(latest, "dewpoint_c", "dewp")
            wind_dir = get_field(latest, "wind_dir", "wdir")
            wind_speed_kt = get_field(latest, "wind_speed_kt", "wspd")
            visibility = get_field(latest, "visibility", "visib")
            pressure_mb = get_field(latest, "altim_in_mb", "pressure_mb", "altim")

            # Hanya tampil kalau ada perubahan (raw_text atau waktu observasi berbeda)
            if raw_text != last_raw_text or obs_time != last_obs_time:
                print(color_text("=" * 80, GREEN))
                print(color_text(f"Time {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}", GREEN))
                print(f"observation_time : {obs_time}")
                print(f"raw_text         : {raw_text}")
                print(f"report_type      : {report_type}")
                print(f"temp_c           : {temp_c if temp_c is not None else '-'}")
                print(f"dewpoint_c       : {dewpoint_c if dewpoint_c is not None else '-'}")
                print(f"wind_dir         : {wind_dir if wind_dir is not None else '-'}")
                print(f"wind_speed_kt    : {wind_speed_kt if wind_speed_kt is not None else '-'}")
                print(f"visibility       : {visibility if visibility is not None else '-'}")
                print(f"pressure_mb      : {pressure_mb if pressure_mb is not None else '-'}")
                print(color_text("=" * 80, GREEN))
                
                last_raw_text = raw_text
                last_obs_time = obs_time
            else:
                print(color_text(f"[{datetime.now().strftime('%H:%M:%S')}] Tidak ada perubahan data...", YELLOW))

        except KeyboardInterrupt:
            print(color_text("\nReal-time monitoring dihentikan.", YELLOW))
            break
        except Exception as e:
            print(color_text(f"Error: {e}", RED))

        time.sleep(300)  # 5 menit

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="METAR WSSS NOAA Scraper")
    subparsers = parser.add_subparsers(dest="mode", help="Pilih mode")

    # History hari ini
    today_parser = subparsers.add_parser("today", help="Ambil history hari ini")
    
    # History tanggal tertentu
    date_parser = subparsers.add_parser("history", help="Ambil history tanggal tertentu")
    date_parser.add_argument("--date", required=True, help="Format: YYYY-MM-DD (contoh: 2026-03-31)")

    # Real-time
    realtime_parser = subparsers.add_parser("realtime", help="Mode monitoring real-time")

    args = parser.parse_args()

    if args.mode == "today":
        history_mode()
    elif args.mode == "history":
        history_mode(args.date)
    elif args.mode == "realtime":
        realtime_mode()
    else:
        parser.print_help()

# Sumber data ini diambil dari NOAA jadi: 
# Kode sumber ini sebaiknya digunakan hanya untuk bandara yang berada di amerika serikat
# Banyak bandara eropa yang terkadang memiliki delay dan tidak stabil untuk update data real-tim
# Beberapa bandara di asia juga terkadang mengalami masalah serupa, jadi pastikan untuk melakukan testing terlebih dahulu sebelum digunakan untuk monitoring real-time.