import requests
import json
import csv
from datetime import datetime, timedelta, timezone
import time
import argparse
import sys

ICAO = "MASUKAN_KODE_ICAO_DISINI"  # Ganti dengan ICAO yang diinginkan
BASE_URL = "https://aviationweather.gov/api/data/metar"

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
        print(f"❌ Error fetching data: {e}")
        return []

def is_speci(metar):
    """Deteksi SPECI atau METAR"""
    raw = get_field(metar, "raw_text", "rawOb") or ""
    if raw.startswith("SPECI"):
        return "SPECI"
    metar_type = get_field(metar, "metar_type", "metarType")
    if metar_type == "SPECI":
        return "SPECI"
    return "METAR"

def save_to_csv(metars, filename):
    """Simpan history ke CSV"""
    if not metars:
        print("Tidak ada data untuk disimpan.")
        return
    
    fieldnames = ["observation_time", "raw_text", "report_type", "temp_c", "dewpoint_c", 
                  "wind_dir", "wind_speed_kt", "visibility", "pressure_mb"]
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for m in metars:
            obs_dt = get_observation_datetime(m)
            writer.writerow({
                "observation_time": obs_dt.isoformat() if obs_dt else "",
                "raw_text": get_field(m, "raw_text", "rawOb"),
                "report_type": is_speci(m),
                "temp_c": get_field(m, "temp_c", "temp"),
                "dewpoint_c": get_field(m, "dewpoint_c", "dewp"),
                "wind_dir": get_field(m, "wind_dir", "wdir"),
                "wind_speed_kt": get_field(m, "wind_speed_kt", "wspd"),
                "visibility": get_field(m, "visibility", "visib"),
                "pressure_mb": get_field(m, "altim_in_mb", "pressure_mb", "altim"),
            })
    print(f"✅ Data berhasil disimpan ke: {filename}")

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
        save_to_csv(filtered, filename)
        print(f"Total data: {len(filtered)} record")
    else:
        print("❌ Tidak ada data ditemukan untuk tanggal tersebut.")

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
                print("⚠️  Tidak ada data dari server")
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
                print("=" * 80)
                print(f"Time {datetime.now().strftime('%Y-%m-%d %H:%M:%S WIB')}")
                print(f"observation_time : {obs_time}")
                print(f"raw_text         : {raw_text}")
                print(f"report_type      : {report_type}")
                print(f"temp_c           : {temp_c if temp_c is not None else '-'}")
                print(f"dewpoint_c       : {dewpoint_c if dewpoint_c is not None else '-'}")
                print(f"wind_dir         : {wind_dir if wind_dir is not None else '-'}")
                print(f"wind_speed_kt    : {wind_speed_kt if wind_speed_kt is not None else '-'}")
                print(f"visibility       : {visibility if visibility is not None else '-'}")
                print(f"pressure_mb      : {pressure_mb if pressure_mb is not None else '-'}")
                print("=" * 80)
                
                last_raw_text = raw_text
                last_obs_time = obs_time
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Tidak ada perubahan data...")

        except KeyboardInterrupt:
            print("\nReal-time monitoring dihentikan.")
            break
        except Exception as e:
            print(f"Error: {e}")

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