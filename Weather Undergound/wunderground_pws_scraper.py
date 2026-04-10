import requests
import json
import csv
import time
import argparse
import os
from datetime import datetime

# ================== KONFIGURASI ==================
STATION_ID = "MASUKAN_DISINI"           # GANTI dengan stationId
API_KEY = "MASUKAN_API_KEY_DISINI"      # Key dari Network tab
UNITS = "m"                             # m = metric

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Referer": "https://www.wunderground.com/",
    "Accept": "application/json"
}

# Fungsi mengubah derajat angin menjadi teks (NNE, NE, ENE, dll)
def degrees_to_direction(degrees):
    if degrees is None:
        return "-"
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(degrees / 22.5) % 16
    return directions[idx]

# Fungsi format waktu seperti website (3:29 PM)
def format_time(obs_time_local):
    if not obs_time_local:
        return ""
    try:
        dt = datetime.strptime(obs_time_local, "%Y-%m-%d %H:%M:%S")
        hour = dt.hour
        minute = dt.minute
        ampm = "AM" if hour < 12 else "PM"
        hour12 = hour % 12
        if hour12 == 0:
            hour12 = 12
        return f"{hour12}:{minute:02d} {ampm}"
    except:
        return obs_time_local[:16]  # fallback

def format_time_24h(obs_time_local):
    if not obs_time_local:
        return ""
    try:
        dt = datetime.strptime(obs_time_local, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%H:%M")
    except:
        return obs_time_local[11:16] if len(obs_time_local) >= 16 else obs_time_local

# =======================================================

def fetch_history(date_str: str):
    url = f"https://api.weather.com/v2/pws/history/all?stationId={STATION_ID}&format=json&units={UNITS}&date={date_str}&apiKey={API_KEY}"
    print(f"Mengambil data historis tanggal {date_str}...")
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        print(f"Error {resp.status_code}")
        return None
    data = resp.json()
    obs_count = len(data.get("observations", []))
    print(f"Berhasil! Total {obs_count} record")
    return data

def fetch_current():
    url = f"https://api.weather.com/v2/pws/observations/current?stationId={STATION_ID}&format=json&units={UNITS}&apiKey={API_KEY}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        print(f"Error {resp.status_code} saat ambil data live")
        return None
    return resp.json()

def build_row_from_observation(obs):
    metric = obs.get("metric", {})

    temp = metric.get("temp")
    dewpt = metric.get("dewpt")
    humidity = obs.get("humidity")
    windspeed = metric.get("windSpeed")
    windgust = metric.get("windGust")
    winddir_deg = obs.get("winddir")
    pressure = metric.get("pressure") or ""
    precip_rate = metric.get("precipRate")
    precip_total = metric.get("precipTotal")
    solar = obs.get("solarRadiation")

    return {
        "Time": format_time(obs.get("obsTimeLocal")),
        "Temp (°C)": temp,
        "Dew Point (°C)": dewpt,
        "Humidity (%)": humidity,
        "Wind Dir": degrees_to_direction(winddir_deg),
        "Wind Speed (km/h)": windspeed,
        "Gust (km/h)": windgust,
        "Pressure (hPa)": pressure,
        "Rain Rate (mm/h)": precip_rate,
        "Rain Total (mm)": precip_total,
        "Solar Radiation (W/m²)": solar,
    }

def print_poll_row(row):
    print(
        f"[{row['Time']}] "
        f"T={row['Temp (°C)']}°C | "
        f"RH={row['Humidity (%)']}% | "
        f"Wind={row['Wind Dir']} {row['Wind Speed (km/h)']} km/h | "
        f"Gust={row['Gust (km/h)']} km/h | "
        f"RainRate={row['Rain Rate (mm/h)']} mm/h | "
        f"RainTotal={row['Rain Total (mm)']} mm"
    )

def append_row_to_csv(row, filename):
    file_exists = os.path.isfile(filename)
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Time", "Temp (°C)", "Dew Point (°C)", "Humidity (%)",
            "Wind Dir", "Wind Speed (km/h)", "Gust (km/h)",
            "Pressure (hPa)", "Rain Rate (mm/h)", "Rain Total (mm)",
            "Solar Radiation (W/m²)"
        ])
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def save_to_csv(observations, filename, mode="a"):
    if not observations:
        return

    file_exists = os.path.isfile(filename)
    
    with open(filename, mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Time", "Temp (°C)", "Dew Point (°C)", "Humidity (%)",
            "Wind Dir", "Wind Speed (km/h)", "Gust (km/h)",
            "Pressure (hPa)", "Rain Rate (mm/h)", "Rain Total (mm)",
            "Solar Radiation (W/m²)"
        ])
        
        if not file_exists or mode == "w":
            writer.writeheader()
        
        for obs in observations:
            metric = obs.get("metric", {})
            
            # Ambil nilai yang sesuai (history atau current)
            temp = metric.get("tempAvg") or metric.get("temp") or metric.get("tempHigh")
            dewpt = metric.get("dewptAvg") or metric.get("dewpt")
            humidity = obs.get("humidityAvg") or obs.get("humidity")
            windspeed = metric.get("windspeedAvg") or metric.get("windspeed")
            windgust = metric.get("windgustAvg") or metric.get("windgust")
            winddir_deg = obs.get("winddirAvg") or obs.get("winddir")
            pressure = metric.get("pressureMax") or metric.get("pressure") or ""
            precip_rate = metric.get("precipRate")
            precip_total = metric.get("precipTotal")
            solar = obs.get("solarRadiationHigh") or obs.get("solarRadiation")

            row = {
                "Time": format_time_24h(obs.get("obsTimeLocal")),
                "Temp (°C)": temp,
                "Dew Point (°C)": dewpt,
                "Humidity (%)": humidity,
                "Wind Dir": degrees_to_direction(winddir_deg),
                "Wind Speed (km/h)": windspeed,
                "Gust (km/h)": windgust,
                "Pressure (hPa)": pressure,
                "Rain Rate (mm/h)": precip_rate,
                "Rain Total (mm)": precip_total,
                "Solar Radiation (W/m²)": solar,
            }
            writer.writerow(row)

def main():
    parser = argparse.ArgumentParser(description="Weather Underground PWS Scraper - Fixed CSV")
    parser.add_argument("--mode", choices=["history", "poll"], default="history")
    parser.add_argument("--date", type=str, help="YYYYMMDD (untuk mode history)")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()

    if args.mode == "history":
        date_str = args.date or datetime.now().strftime("%Y%m%d")
        data = fetch_history(date_str)
        if data:
            obs = data.get("observations", [])
            base = f"pws_{STATION_ID}_{date_str}"
            with open(f"{base}.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            save_to_csv(obs, f"{base}.csv", mode="w")
            print(f"Selesai! File CSV & JSON sudah siap: {base}.csv")

    else:  # polling live
        print(f"Polling live setiap {args.interval} detik... (Ctrl+C untuk stop)")
        last_ts = None
        csv_file = f"pws_{STATION_ID}_live.csv"
        while True:
            try:
                data = fetch_current()
                if not data:
                    time.sleep(args.interval)
                    continue

                obs = data.get("observations", [])
                if not obs:
                    print("Tidak ada observations di response live")
                    time.sleep(args.interval)
                    continue

                latest = obs[0]
                ts = latest.get("epoch")

                if ts == last_ts:
                    print("Belum ada data baru")
                else:
                    row = build_row_from_observation(latest)
                    print_poll_row(row)
                    append_row_to_csv(row, csv_file)
                    last_ts = ts

                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nDihentikan.")
                break
            except Exception as e:
                print(f"Error polling: {e}")
                time.sleep(args.interval)

if __name__ == "__main__":
    main()