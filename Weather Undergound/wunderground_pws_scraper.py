import requests
import json
import csv
import time
import argparse
import os
import random
import re
from datetime import datetime, timedelta

# ================== KONFIGURASI ==================
API_KEY = "MASUKAN_API_KEY_DISINI"      # Key dari Network tab
UNITS = "m"                             # m = metric

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Referer": "https://www.wunderground.com/",
    "Accept": "application/json"
}

DEFAULT_BATCH_DELAY = 2.2  # ~27 request/menit (aman di bawah 30 request/menit)
DEFAULT_BATCH_JITTER = 0.4
MAX_RETRIES = 4
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
EMPTY_RESPONSE_STATUSES = {204}
STATION_ID_PATTERN = re.compile(r"^[A-Z0-9]{4,24}$")

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

def parse_input_date(date_str: str):
    if not date_str:
        return None

    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None

def iter_dates(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)

def build_retry_wait(attempt, retry_after_header=None):
    if retry_after_header:
        try:
            return max(1.0, float(retry_after_header))
        except ValueError:
            pass

    # exponential backoff + jitter kecil agar pola request tidak terlalu seragam
    return min(30.0, (2 ** attempt) + random.uniform(0.2, 0.8))

def compute_batch_wait(delay_seconds, jitter_seconds):
    if jitter_seconds <= 0:
        return max(0.0, delay_seconds)

    lower = max(0.0, delay_seconds - jitter_seconds)
    upper = max(lower, delay_seconds + jitter_seconds)
    return random.uniform(lower, upper)

def create_auto_output_dir(base_name):
    root_dir = "output"
    os.makedirs(root_dir, exist_ok=True)

    preferred = os.path.join(root_dir, base_name)
    folder_already_exists = os.path.isdir(preferred)
    os.makedirs(preferred, exist_ok=True)
    if folder_already_exists:
        print(f"Folder {preferred} sudah ada. File dengan nama sama akan ditimpa.")
    return preferred

def resolve_output_dir(mode, date_str, end_date_str=None, station_id=None, manual_output_dir=None):
    if manual_output_dir:
        os.makedirs(manual_output_dir, exist_ok=True)
        print(f"Output folder manual: {manual_output_dir}")
        return manual_output_dir

    if not station_id:
        raise ValueError("Station ID tidak valid")

    start_date = parse_input_date(date_str)
    if not start_date:
        raise ValueError("Tanggal mulai tidak valid")

    start_token = start_date.strftime("%Y%m%d")
    if mode == "history_batch":
        end_date = parse_input_date(end_date_str or "")
        if not end_date:
            raise ValueError("Tanggal akhir tidak valid")
        end_token = end_date.strftime("%Y%m%d")
        base_name = f"pws_{station_id}_{start_token}_{end_token}"
    else:
        base_name = f"pws_{station_id}_{start_token}"

    output_dir = create_auto_output_dir(base_name)
    print(f"Output folder otomatis: {output_dir}")
    return output_dir

def ensure_split_output_dirs(output_dir):
    json_dir = os.path.join(output_dir, "json")
    csv_dir = os.path.join(output_dir, "csv")
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(csv_dir, exist_ok=True)
    return json_dir, csv_dir

def request_json_with_retry(url, date_str, label):
    _, payload = request_json_with_retry_status(url, date_str, label)
    return payload

def request_json_with_retry_status(url, date_str, label):

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            if attempt < MAX_RETRIES:
                wait_s = build_retry_wait(attempt)
                print(f"Request error ({label}): {e}. Retry {attempt + 1}/{MAX_RETRIES} dalam {wait_s:.1f}s...")
                time.sleep(wait_s)
                continue

            print(f"Error request permanen ({label}): {e}")
            return None, None

        if resp.status_code == 200:
            try:
                return resp.status_code, resp.json()
            except ValueError:
                print(f"Response ({label}) untuk {date_str} bukan JSON valid")
                return resp.status_code, None

        if resp.status_code in EMPTY_RESPONSE_STATUSES:
            print(
                f"HTTP {resp.status_code} ({label}) untuk {date_str}: "
                "tidak ada data (no content)."
            )
            return resp.status_code, {"observations": []}

        if resp.status_code in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
            wait_s = build_retry_wait(attempt, resp.headers.get("Retry-After"))
            print(
                f"HTTP {resp.status_code} ({label}) untuk {date_str}. "
                f"Retry {attempt + 1}/{MAX_RETRIES} dalam {wait_s:.1f}s..."
            )
            time.sleep(wait_s)
            continue

        print(f"Error {resp.status_code} ({label}) untuk {date_str}")
        return resp.status_code, None

    return None, None

def check_station_exists_on_dashboard(station_id):
    url = f"https://www.wunderground.com/dashboard/pws/{station_id}"

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
        except requests.RequestException as e:
            if attempt < MAX_RETRIES:
                wait_s = build_retry_wait(attempt)
                print(
                    f"Dashboard check error: {e}. "
                    f"Retry {attempt + 1}/{MAX_RETRIES} dalam {wait_s:.1f}s..."
                )
                time.sleep(wait_s)
                continue

            print(f"Dashboard check gagal permanen: {e}")
            return None

        body_lower = (resp.text or "").lower()
        looks_like_404_page = "error 404" in body_lower and "page not found" in body_lower

        if resp.status_code == 404 or looks_like_404_page:
            return False

        if resp.status_code == 200:
            return True

        if resp.status_code in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
            wait_s = build_retry_wait(attempt, resp.headers.get("Retry-After"))
            print(
                f"Dashboard check HTTP {resp.status_code}. "
                f"Retry {attempt + 1}/{MAX_RETRIES} dalam {wait_s:.1f}s..."
            )
            time.sleep(wait_s)
            continue

        print(f"Dashboard check status {resp.status_code}; tidak bisa memastikan station.")
        return None

    return None

def extract_obs_date(obs):
    obs_time_local = obs.get("obsTimeLocal")
    if isinstance(obs_time_local, str) and len(obs_time_local) >= 10:
        try:
            return datetime.strptime(obs_time_local[:10], "%Y-%m-%d").date()
        except ValueError:
            pass

    obs_time_utc = obs.get("obsTimeUtc")
    if isinstance(obs_time_utc, str) and len(obs_time_utc) >= 10:
        try:
            return datetime.strptime(obs_time_utc[:10], "%Y-%m-%d").date()
        except ValueError:
            pass

    return None

def collect_observation_dates(data, start_date=None, end_date=None):
    obs_dates = []
    for obs in data.get("observations", []):
        d = extract_obs_date(obs)
        if not d:
            continue
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue
        obs_dates.append(d)
    return sorted(set(obs_dates))

def fallback_scan_window_daily(window_start, window_end, global_start, global_end, station_id):
    print(
        f"Fallback cek harian untuk window "
        f"{window_start.strftime('%Y-%m-%d')} s/d {window_end.strftime('%Y-%m-%d')}"
    )

    unresolved_dates = []
    for day in iter_dates(window_start, window_end):
        day_token = day.strftime("%Y%m%d")
        url_daily_single = (
            "https://api.weather.com/v2/pws/history/daily"
            f"?stationId={station_id}&format=json&units={UNITS}"
            f"&date={day_token}&apiKey={API_KEY}"
        )

        day_data = request_json_with_retry(url_daily_single, day_token, "discovery/daily-single")
        if day_data is None:
            unresolved_dates.append(day_token)
            continue

        obs_dates = collect_observation_dates(day_data, global_start, global_end)
        if obs_dates:
            return min(obs_dates), unresolved_dates

    return None, unresolved_dates

def find_first_available_date(start_date, end_date, station_id):
    print(
        f"Auto-start aktif: mencari tanggal pertama yang punya data dari "
        f"{start_date.strftime('%Y-%m-%d')} sampai {end_date.strftime('%Y-%m-%d')}"
    )

    current_start = start_date
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=30), end_date)
        start_token = current_start.strftime("%Y%m%d")
        end_token = current_end.strftime("%Y%m%d")

        print(f"Scan window {start_token} s/d {end_token}...")
        url_daily = (
            "https://api.weather.com/v2/pws/history/daily"
            f"?stationId={station_id}&format=json&units={UNITS}"
            f"&startDate={start_token}&endDate={end_token}&apiKey={API_KEY}"
        )

        data = request_json_with_retry(url_daily, start_token, "discovery/daily")
        if data is None:
            print("Scan window gagal. Menjalankan fallback cek harian...")
            first_date, unresolved_dates = fallback_scan_window_daily(
                current_start,
                current_end,
                start_date,
                end_date,
                station_id,
            )
            if first_date:
                print(f"Tanggal pertama dengan data ditemukan: {first_date.strftime('%Y-%m-%d')}")
                return first_date

            if unresolved_dates:
                preview = ", ".join(unresolved_dates[:10])
                if len(unresolved_dates) > 10:
                    preview += ", ..."
                print(f"Fallback harian masih gagal di tanggal: {preview}")
                print("Untuk menjaga kepastian data, proses auto-start dihentikan.")
                return None
        else:
            obs_dates = collect_observation_dates(data, start_date, end_date)
            if obs_dates:
                first_date = min(obs_dates)
                print(f"Tanggal pertama dengan data ditemukan: {first_date.strftime('%Y-%m-%d')}")
                return first_date

        current_start = current_end + timedelta(days=1)

    print("Tidak ditemukan data dalam rentang tanggal yang diminta.")
    return None

# =======================================================

def fetch_history(date_str: str, station_id: str):
    print(f"Mengambil data historis tanggal {date_str}...")
    url_all = f"https://api.weather.com/v2/pws/history/all?stationId={station_id}&format=json&units={UNITS}&date={date_str}&apiKey={API_KEY}"
    data = request_json_with_retry(url_all, date_str, "history/all")
    if data is None:
        return None

    observations = data.get("observations", [])
    obs_count = len(observations)
    if obs_count > 0:
        print(f"Berhasil! Total {obs_count} record")
        return data

    print("Observations kosong dari endpoint history/all, mencoba fallback history/hourly...")
    url_hourly = (
        "https://api.weather.com/v2/pws/history/hourly"
        f"?stationId={station_id}&format=json&units={UNITS}"
        f"&startDate={date_str}&endDate={date_str}&apiKey={API_KEY}"
    )
    fallback_data = request_json_with_retry(url_hourly, date_str, "history/hourly")
    if fallback_data is None:
        print("Fallback history/hourly gagal. Data harian dianggap kosong.")
        return data

    fallback_obs_count = len(fallback_data.get("observations", []))
    if fallback_obs_count > 0:
        print(f"Fallback berhasil! Total {fallback_obs_count} record")
        return fallback_data

    print("Fallback history/hourly juga kosong.")
    return fallback_data

def run_history_batch(start_date_str, end_date_str, delay_seconds, jitter_seconds, output_dir, station_id):
    start_date = parse_input_date(start_date_str)
    end_date = parse_input_date(end_date_str)

    if not start_date or not end_date:
        print("Format tanggal tidak valid. Gunakan YYYYMMDD atau YYYY-MM-DD")
        return

    if end_date < start_date:
        print("Tanggal akhir tidak boleh lebih kecil dari tanggal mulai")
        return

    today = datetime.now().date()
    if start_date > today:
        print(
            f"Tanggal mulai {start_date.strftime('%Y-%m-%d')} berada di masa depan. "
            "Tidak ada data historis untuk diproses."
        )
        return

    if end_date > today:
        print(
            f"Tanggal akhir {end_date.strftime('%Y-%m-%d')} berada di masa depan, "
            f"disesuaikan menjadi {today.strftime('%Y-%m-%d')}"
        )
        end_date = today

    json_dir, csv_dir = ensure_split_output_dirs(output_dir)

    total_days = (end_date - start_date).days + 1
    merged_csv = os.path.join(
        csv_dir,
        f"pws_{station_id}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv",
    )

    print(
        f"Mulai batch history {start_date.strftime('%Y-%m-%d')} s/d {end_date.strftime('%Y-%m-%d')} "
        f"({total_days} hari)"
    )
    print(
        f"Throttle: delay dasar {delay_seconds:.2f}s, jitter +/- {jitter_seconds:.2f}s "
        f"(rekomendasi aman untuk menghindari spam)"
    )

    success_days = 0
    days_with_data = 0
    empty_days = []
    failed_days = []
    merged_rows = 0
    merged_mode = "w"

    for idx, current_date in enumerate(iter_dates(start_date, end_date), start=1):
        date_str = current_date.strftime("%Y%m%d")
        print(f"[{idx}/{total_days}] Proses {date_str}")

        data = fetch_history(date_str, station_id)
        if data is None:
            failed_days.append(date_str)
        else:
            observations = data.get("observations", [])
            json_path = os.path.join(json_dir, f"pws_{station_id}_{date_str}.json")
            csv_path = os.path.join(csv_dir, f"pws_{station_id}_{date_str}.csv")

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            if observations:
                save_to_csv(observations, csv_path, mode="w")
                save_to_csv(observations, merged_csv, mode=merged_mode)
                merged_mode = "a"
                merged_rows += len(observations)
                days_with_data += 1
            else:
                empty_days.append(date_str)
                print(f"Data kosong untuk {date_str} (observations=[]). JSON tetap disimpan.")

            success_days += 1

        if idx < total_days:
            sleep_seconds = compute_batch_wait(delay_seconds, jitter_seconds)
            print(f"Tunggu {sleep_seconds:.2f}s sebelum request berikutnya...")
            time.sleep(sleep_seconds)

    print("\n===== RINGKASAN BATCH =====")
    print(f"Total hari diproses : {total_days}")
    print(f"Sukses request      : {success_days}")
    print(f"Ada data            : {days_with_data}")
    print(f"Kosong              : {len(empty_days)}")
    print(f"Gagal               : {len(failed_days)}")

    if merged_rows > 0:
        print(f"CSV gabungan        : {merged_csv} ({merged_rows} baris)")
    else:
        print("CSV gabungan        : tidak dibuat (tidak ada observations)")

    print(f"Folder JSON         : {json_dir}")
    print(f"Folder CSV          : {csv_dir}")

    if failed_days:
        print("Tanggal gagal       : " + ", ".join(failed_days))

    if empty_days:
        print("Tanggal kosong      : " + ", ".join(empty_days))

def fetch_current(station_id):
    url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units={UNITS}&apiKey={API_KEY}"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if resp.status_code != 200:
        print(f"Error {resp.status_code} saat ambil data live")
        return None
    return resp.json()

def normalize_station_id(raw_station):
    station_id = (raw_station or "").strip().upper()
    if not station_id:
        raise ValueError("--station wajib diisi")

    if not STATION_ID_PATTERN.fullmatch(station_id):
        raise ValueError(
            "Format --station tidak valid. Gunakan huruf/angka tanpa spasi, "
            "contoh: ISINGA249"
        )

    return station_id

def validate_station_id(station_id):
    dashboard_exists = check_station_exists_on_dashboard(station_id)
    if dashboard_exists is False:
        print(
            f"Station {station_id} tidak ditemukan di dashboard Weather Underground (404). "
            "Kemungkinan typo station ID."
        )
        return False

    if dashboard_exists is True:
        print(f"Station {station_id} ditemukan di dashboard Weather Underground.")

    today_token = datetime.now().strftime("%Y%m%d")
    yesterday_token = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    probes = [
        (
            "station-check/current",
            "https://api.weather.com/v2/pws/observations/current"
            f"?stationId={station_id}&format=json&units={UNITS}&apiKey={API_KEY}",
            "today",
        ),
        (
            "station-check/daily",
            "https://api.weather.com/v2/pws/history/daily"
            f"?stationId={station_id}&format=json&units={UNITS}&date={today_token}&apiKey={API_KEY}",
            today_token,
        ),
        (
            "station-check/daily-yesterday",
            "https://api.weather.com/v2/pws/history/daily"
            f"?stationId={station_id}&format=json&units={UNITS}&date={yesterday_token}&apiKey={API_KEY}",
            yesterday_token,
        ),
    ]

    saw_empty_response = False
    for label, url, ref_date in probes:
        status_code, data = request_json_with_retry_status(url, ref_date, label)

        if status_code == 200 and data is not None:
            observations = data.get("observations", []) if isinstance(data, dict) else []
            if observations:
                print(f"Station {station_id} terverifikasi ({label}, {len(observations)} record).")
                return True

            print(f"Probe {label} sukses tetapi observations kosong.")
            saw_empty_response = True
            continue

        if status_code in EMPTY_RESPONSE_STATUSES:
            saw_empty_response = True
            continue

        if status_code in {401, 403}:
            print(
                f"Station {station_id} gagal diverifikasi karena API key tidak punya akses "
                f"(HTTP {status_code})."
            )
            return False

        if status_code == 404:
            print(f"Station {station_id} tidak ditemukan oleh endpoint API ({label}).")
            return False

    if dashboard_exists is True and saw_empty_response:
        print(
            f"Station {station_id} valid, tetapi data saat ini kosong. "
            "Proses tetap diizinkan."
        )
        return True

    print(
        f"Station {station_id} tidak terverifikasi. "
        "Cek kemungkinan typo station ID atau akses station pada akun Anda."
    )
    return False

def build_row_from_observation(obs):
    metric = obs.get("metric", {})

    temp = metric.get("temp")
    dewpt = metric.get("dewpt")
    humidity = obs.get("humidity")
    windspeed = metric.get("windSpeed")
    windgust = metric.get("windGust")
    winddir_deg = obs.get("winddir")
    heat_index = metric.get("heatindexAvg") or metric.get("heatindex") or metric.get("heatindexHigh")
    pressure = metric.get("pressure") or ""
    precip_rate = metric.get("precipRate")
    precip_total = metric.get("precipTotal")
    solar = obs.get("solarRadiation")

    return {
        "Time": format_time_24h(obs.get("obsTimeLocal")),
        "Temp (°C)": temp,
        "Heat Index (°C)": heat_index,
        "Dew Point (°C)": dewpt,
        "Humidity (%)": humidity,
        "Wind Direction (°)": winddir_deg,
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
        f"HI={row['Heat Index (°C)']}°C | "
        f"RH={row['Humidity (%)']}% | "
        f"Wind={row['Wind Direction (°)']}° {row['Wind Speed (km/h)']} km/h | "
        f"Gust={row['Gust (km/h)']} km/h | "
        f"RainRate={row['Rain Rate (mm/h)']} mm/h | "
        f"RainTotal={row['Rain Total (mm)']} mm"
    )

def append_row_to_csv(row, filename):
    file_exists = os.path.isfile(filename)
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Time", "Temp (°C)", "Heat Index (°C)", "Dew Point (°C)", "Humidity (%)",
            "Wind Direction (°)", "Wind Speed (km/h)", "Gust (km/h)",
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
            "Time", "Temp (°C)", "Heat Index (°C)", "Dew Point (°C)", "Humidity (%)",
            "Wind Direction (°)", "Wind Speed (km/h)", "Gust (km/h)",
            "Pressure (hPa)", "Rain Rate (mm/h)", "Rain Total (mm)",
            "Solar Radiation (W/m²)"
        ])
        
        if not file_exists or mode == "w":
            writer.writeheader()
        
        for obs in observations:
            metric = obs.get("metric", {})

            temp = metric.get("tempAvg") or metric.get("temp") or metric.get("tempHigh")
            heat_index = metric.get("heatindexAvg") or metric.get("heatindex") or metric.get("heatindexHigh")
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
                "Heat Index (°C)": heat_index,
                "Dew Point (°C)": dewpt,
                "Humidity (%)": humidity,
                "Wind Direction (°)": winddir_deg,
                "Wind Speed (km/h)": windspeed,
                "Gust (km/h)": windgust,
                "Pressure (hPa)": pressure,
                "Rain Rate (mm/h)": precip_rate,
                "Rain Total (mm)": precip_total,
                "Solar Radiation (W/m²)": solar,
            }
            writer.writerow(row)

def main():
    parser = argparse.ArgumentParser(description="Weather Underground PWS Scraper")
    parser.add_argument("--station", required=True, help="Station ID PWS, contoh: ISINGA249")
    parser.add_argument("today", nargs="?", choices=["today"], help="Keyword mode hari ini")
    parser.add_argument("--date", type=str, help="Tanggal history (YYYYMMDD atau YYYY-MM-DD)")
    parser.add_argument("--start", type=str, help="Tanggal mulai batch (YYYYMMDD atau YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="Tanggal akhir batch (YYYYMMDD atau YYYY-MM-DD)")
    parser.add_argument("--auto-start", action="store_true", help="Mode batch: cari otomatis tanggal pertama yang punya data")
    parser.add_argument("--interval", type=int, help="Interval polling realtime (detik), hanya untuk mode today realtime")
    parser.add_argument("--request-delay", type=float, default=DEFAULT_BATCH_DELAY, help="Delay dasar antar request batch (detik)")
    parser.add_argument("--request-jitter", type=float, default=DEFAULT_BATCH_JITTER, help="Jitter random delay batch (detik)")
    parser.add_argument("--output-dir", type=str, help="Opsional: folder output manual (jika tidak diisi, dibuat folder otomatis)")
    args = parser.parse_args()

    try:
        station_id = normalize_station_id(args.station)
    except ValueError as e:
        parser.error(str(e))

    if not validate_station_id(station_id):
        raise SystemExit(1)

    if args.request_delay < 0:
        parser.error("--request-delay tidak boleh negatif")

    if args.request_jitter < 0:
        parser.error("--request-jitter tidak boleh negatif")

    if args.interval is not None and args.interval <= 0:
        parser.error("--interval harus lebih besar dari 0")

    has_today = args.today == "today"
    has_date = bool(args.date)
    has_start = bool(args.start)
    has_end = bool(args.end)

    if has_date and has_today:
        parser.error("Gunakan salah satu: --date atau keyword today")

    if has_start != has_end:
        parser.error("Mode batch wajib isi --start dan --end sekaligus")

    if has_start and (has_date or has_today):
        parser.error("Mode batch (--start/--end) tidak bisa digabung dengan --date atau today")

    if args.interval is not None and not has_today:
        parser.error("--interval hanya bisa dipakai bersama keyword today")

    if has_start and has_end:
        input_start = parse_input_date(args.start)
        input_end = parse_input_date(args.end)
        if not input_start or not input_end:
            parser.error("Format --start/--end tidak valid. Gunakan YYYYMMDD atau YYYY-MM-DD")

        if input_end < input_start:
            parser.error("Nilai --end tidak boleh lebih kecil dari --start")

        today = datetime.now().date()
        if input_start > today:
            print(
                f"Tanggal mulai {input_start.strftime('%Y-%m-%d')} berada di masa depan. "
                "Tidak ada data historis untuk diproses."
            )
            return

        if input_end > today:
            print(
                f"Tanggal akhir {input_end.strftime('%Y-%m-%d')} berada di masa depan, "
                f"disesuaikan menjadi {today.strftime('%Y-%m-%d')}"
            )
            input_end = today

        effective_start = input_start
        if args.auto_start:
            discovered_start = find_first_available_date(input_start, input_end, station_id)
            if not discovered_start:
                print("Batch dibatalkan karena tidak ada data di rentang tanggal tersebut.")
                return

            if discovered_start > input_start:
                print(
                    f"Tanggal mulai digeser otomatis dari {input_start.strftime('%Y-%m-%d')} "
                    f"ke {discovered_start.strftime('%Y-%m-%d')}"
                )
            effective_start = discovered_start

        effective_start_str = effective_start.strftime("%Y%m%d")
        effective_end_str = input_end.strftime("%Y%m%d")

        if args.request_delay < 1.8:
            print(
                "Peringatan: --request-delay < 1.8 detik berisiko kena rate limit. "
                "Rekomendasi aman 2.0 - 2.5 detik"
            )

        output_dir = resolve_output_dir(
            mode="history_batch",
            date_str=effective_start_str,
            end_date_str=effective_end_str,
            station_id=station_id,
            manual_output_dir=args.output_dir,
        )

        run_history_batch(
            start_date_str=effective_start_str,
            end_date_str=effective_end_str,
            delay_seconds=args.request_delay,
            jitter_seconds=args.request_jitter,
            output_dir=output_dir,
            station_id=station_id,
        )
        return

    if has_date or has_today:
        if has_date:
            parsed_history_date = parse_input_date(args.date)
            if not parsed_history_date:
                parser.error("Format --date tidak valid. Gunakan YYYYMMDD atau YYYY-MM-DD")
        else:
            parsed_history_date = datetime.now().date()

        if parsed_history_date > datetime.now().date():
            print(
                f"Tanggal {parsed_history_date.strftime('%Y-%m-%d')} berada di masa depan. "
                "Gunakan tanggal <= hari ini."
            )
            return

        if has_today and args.interval is not None:
            print(f"Polling live station {station_id} setiap {args.interval} detik... (Ctrl+C untuk stop)")
            if args.output_dir:
                os.makedirs(args.output_dir, exist_ok=True)
                csv_file = os.path.join(args.output_dir, f"pws_{station_id}_live.csv")
            else:
                csv_file = f"pws_{station_id}_live.csv"

            last_ts = None
            while True:
                try:
                    data = fetch_current(station_id)
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
            return

        date_str = parsed_history_date.strftime("%Y%m%d")
        data = fetch_history(date_str, station_id)
        if data:
            obs = data.get("observations", [])
            output_dir = resolve_output_dir(
                mode="history",
                date_str=date_str,
                station_id=station_id,
                manual_output_dir=args.output_dir,
            )
            json_dir, csv_dir = ensure_split_output_dirs(output_dir)
            json_path = os.path.join(json_dir, f"pws_{station_id}_{date_str}.json")
            csv_path = os.path.join(csv_dir, f"pws_{station_id}_{date_str}.csv")

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            if obs:
                save_to_csv(obs, csv_path, mode="w")
                print(f"Selesai! File CSV & JSON sudah siap: {csv_path}")
                print(f"File JSON            : {json_path}")
            else:
                print(f"Response sukses tapi observations kosong. File JSON disimpan di: {json_path}")
        return

    parser.error("Gunakan salah satu mode: --date <tanggal>, today, atau --start <tanggal> --end <tanggal>")


if __name__ == "__main__":
    main()
