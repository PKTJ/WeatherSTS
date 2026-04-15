import argparse
import requests
import pandas as pd
from metar import Metar
import pytz
from datetime import datetime, timedelta
from time import sleep
import os
import re


COLOR_RESET = "\033[0m"
COLOR_SUCCESS = "\033[92m"  
COLOR_ERROR = "\033[91m"    
COLOR_WARNING = "\033[93m"  
COLOR_INFO = "\033[97m"     

RANGE_DELAY_SECONDS = 25
RETRY_BACKOFF_SECONDS = [5, 10, 20, 40, 60]
PERMANENT_HTTP_STATUSES = {400, 401, 403, 404}
TRANSIENT_HTTP_STATUSES = {408, 429, 500, 501, 502, 503, 504}


def _init_terminal_colors():
    # Enable ANSI escape processing on modern Windows consoles.
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            enable_vt = 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(handle, mode.value | enable_vt)
    except Exception:
        pass


def _log(message: str, level: str = "info"):
    color_map = {
        "success": COLOR_SUCCESS,
        "error": COLOR_ERROR,
        "warning": COLOR_WARNING,
        "info": COLOR_INFO,
    }
    color = color_map.get(level, COLOR_INFO)
    print(f"{color}{message}{COLOR_RESET}")


def _wait_and_retry(retry_count: int, reason: str) -> bool:
    if retry_count >= len(RETRY_BACKOFF_SECONDS):
        return False
    delay_seconds = RETRY_BACKOFF_SECONDS[retry_count]
    _log(
        f"{reason} Retry {retry_count + 1}/{len(RETRY_BACKOFF_SECONDS)} dalam {delay_seconds} detik.",
        "warning",
    )
    sleep(delay_seconds)
    return True

# ================== METADATA STASIUN ==================
# Tambahkan stasiun lain di sini kalau perlu
STATIONS = {
    # "WIII": {"lat": -6.1256, "lon": 106.6556, "elev_m": 16, "tz": "Asia/Jakarta"},  # default
    "WSSS": {"lat": 1.3508, "lon": 103.9942, "elev_m": 16, "tz": "Asia/Singapore"},
}

def get_station_info(icao):
    return STATIONS.get(icao.upper(), {
        "lat": None, "lon": None, "elev_m": None, "tz": "Asia/Jakarta"
    })


def _safe_numeric(value, unit=None):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if hasattr(value, "value"):
        if unit is not None:
            try:
                converted = value.value(unit)
                if converted is not None:
                    return float(converted)
            except Exception:
                pass
        try:
            converted = value.value()
            if converted is not None:
                return float(converted)
        except Exception:
            pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

# ================== PARSING FUNCTION ==================
def parse_metar(raw_report: str, icao: str):
    try:
        m = Metar.Metar(raw_report, strict=False)
        if not m.time:
            raise ValueError("No observation time found in METAR")
        obs_time_utc = m.time.replace(tzinfo=pytz.UTC)

        station = get_station_info(icao)
        tz = pytz.timezone(station["tz"])
        local_time = obs_time_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")

        # Report type
        report_type = "SPECI" if raw_report.startswith("SPECI") else "METAR"

        # Suhu & Tekanan
        temp_c = round(m.temp.value("C"), 1) if m.temp else None
        dewpoint_c = round(m.dewpt.value("C"), 1) if m.dewpt else None
        pressure_mb = round(m.press.value("MB"), 1) if m.press else None

        # Angin
        try:
            wind_dir = m.wind_dir.value() if m.wind_dir else ("VRB" if "VRB" in raw_report else None)
        except (AttributeError, TypeError):
            wind_dir = "VRB" if "VRB" in raw_report else None
        try:
            wind_speed_kt = round(m.wind_speed.value("KT"), 1) if m.wind_speed else 0
        except (AttributeError, TypeError):
            wind_speed_kt = 0
        try:
            wind_gust_kt = round(m.wind_gust.value("KT"), 1) if m.wind_gust else None
        except (AttributeError, TypeError):
            wind_gust_kt = None
        wind_dir_var = None
        if m.wind_dir_from and m.wind_dir_to:
            wind_dir_var = f"{int(m.wind_dir_from.value())}V{int(m.wind_dir_to.value())}"

        # Visibilitas & Awan
        visibility = m.vis.value() if m.vis else None
        sky_layers = m.sky or []
        cloud_parts = []
        for cover, height, _ in sky_layers:
            height_ft = _safe_numeric(height, "FT")
            if height_ft is not None:
                cloud_parts.append(f"{cover}{int(round(height_ft / 100)):03d}")
            else:
                cloud_parts.append(cover)
        cloud_layers = " ".join(cloud_parts) or None

        # Cuaca sekarang
        wx_string = " ".join([f"{w[0]}{w[1] or ''}{w[2] or ''}" for w in m.weather]) or None

        # Flight category
        vis_sm = _safe_numeric(m.vis, "SM") if m.vis else 10
        if vis_sm is None:
            vis_sm = 10
        ceiling_ft = None
        for cover, height, _ in sky_layers:
            if cover in ("BKN", "OVC") and height:
                height_ft = _safe_numeric(height, "FT")
                if height_ft is not None:
                    ceiling_ft = height_ft
                    break
        ceiling_ft = ceiling_ft if ceiling_ft is not None else 10000
        if vis_sm < 1 or ceiling_ft < 500:
            flight_category = "LIFR"
        elif vis_sm < 3 or ceiling_ft < 1000:
            flight_category = "IFR"
        elif vis_sm < 5 or ceiling_ft < 3000:
            flight_category = "MVFR"
        else:
            flight_category = "VFR"

        # Auto / COR
        auto = ""
        if "AUTO" in raw_report:
            auto += "AUTO"
        if "COR" in raw_report:
            auto += "/COR" if auto else "COR"

        # Remarks & tambahan
        remarks_source = m.remarks
        remarks = remarks_source() if callable(remarks_source) else (remarks_source or "")
        remarks = str(remarks)
        recent_match = re.search(r"\bRE[A-Z]{2,4}\b", remarks)
        recent_weather = recent_match.group(0) if recent_match else None
        rvr = None  # bisa ditambah parsing manual kalau sering muncul
        rmk_indicators = []
        for ind in ["WSHFT", "PK WND", "PRESFR", "PRESRR", "TSE", "TS"]:
            if ind in remarks and ind not in rmk_indicators:
                rmk_indicators.append(ind)
        rmk_indicators = " ".join(rmk_indicators) if rmk_indicators else None

        return {
            "observation_time": obs_time_utc.isoformat(),
            "local_time": local_time,
            "raw_text": raw_report,
            "report_type": report_type,
            "temp_c": temp_c,
            "dewpoint_c": dewpoint_c,
            "pressure_mb": pressure_mb,
            "wind_dir": wind_dir,
            "wind_speed_kt": wind_speed_kt,
            "wind_gust_kt": wind_gust_kt,
            "wind_dir_var": wind_dir_var,
            "visibility": visibility,
            "cloud_layers": cloud_layers,
            "wx_string": wx_string,
            "flight_category": flight_category,
            "auto": auto,
            "recent_weather": recent_weather,
            "rvr": rvr,
            "remarks": remarks,
            "rmk_indicators": rmk_indicators,
            "latitude": station["lat"],
            "longitude": station["lon"],
            "elevation_m": station["elev_m"],
        }
    except Exception as e:
        _log(f"Parse error: {e} → raw disimpan", "warning")
        return {
            "observation_time": None, "local_time": None, "report_type": "METAR",
            "raw_text": raw_report, "temp_c": None, "dewpoint_c": None, "pressure_mb": None,
            "wind_dir": None, "wind_speed_kt": None, "wind_gust_kt": None, "wind_dir_var": None,
            "visibility": None, "cloud_layers": None, "wx_string": None,
            "flight_category": None, "auto": None, "recent_weather": None,
            "rvr": None, "remarks": None, "rmk_indicators": None,
            "latitude": None, "longitude": None, "elevation_m": None,
        }

# ================== MAIN SCRAPER ==================
def scrape_day(icao: str, target_date: datetime, output_dir: str):
    begin = target_date.strftime("%Y%m%d0000")
    end = target_date.strftime("%Y%m%d2359")
    date_str = target_date.strftime("%Y%m%d")

    url = f"https://www.ogimet.com/cgi-bin/getmetar?icao={icao}&begin={begin}&end={end}&header=yes"
    _log(f"Mengambil {icao} tanggal {target_date.strftime('%Y-%m-%d')}...", "info")

    retry_count = 0
    while True:
        try:
            r = requests.get(url, timeout=30)
            status_code = r.status_code
            if status_code in PERMANENT_HTTP_STATUSES:
                _log(f"Gagal request permanen HTTP {status_code}. Tidak retry.", "error")
                _log(
                    f"Tanggal {target_date.strftime('%Y-%m-%d')} dilewati, lanjut ke tanggal berikutnya (jika ada).",
                    "warning",
                )
                return

            if status_code in TRANSIENT_HTTP_STATUSES:
                should_retry = _wait_and_retry(retry_count, f"HTTP {status_code} terdeteksi.")
                if should_retry:
                    retry_count += 1
                    continue
                _log(
                    f"Gagal request: HTTP {status_code} setelah {len(RETRY_BACKOFF_SECONDS)} retry.",
                    "error",
                )
                _log(
                    f"Tanggal {target_date.strftime('%Y-%m-%d')} dilewati, lanjut ke tanggal berikutnya (jika ada).",
                    "warning",
                )
                return

            if status_code >= 400:
                _log(f"Gagal request HTTP {status_code}. Tidak retry.", "error")
                _log(
                    f"Tanggal {target_date.strftime('%Y-%m-%d')} dilewati, lanjut ke tanggal berikutnya (jika ada).",
                    "warning",
                )
                return

            break
        except (requests.Timeout, requests.ConnectionError) as e:
            should_retry = _wait_and_retry(retry_count, f"Gangguan koneksi/timeout: {e}.")
            if should_retry:
                retry_count += 1
                continue
            _log(f"Gagal request: {e}", "error")
            _log(
                f"Tanggal {target_date.strftime('%Y-%m-%d')} dilewati, lanjut ke tanggal berikutnya (jika ada).",
                "warning",
            )
            return
        except requests.RequestException as e:
            status_code = e.response.status_code if e.response is not None else None
            if status_code in PERMANENT_HTTP_STATUSES:
                _log(f"Gagal request permanen HTTP {status_code}. Tidak retry.", "error")
                _log(
                    f"Tanggal {target_date.strftime('%Y-%m-%d')} dilewati, lanjut ke tanggal berikutnya (jika ada).",
                    "warning",
                )
                return

            should_retry = _wait_and_retry(retry_count, f"Request error: {e}.")
            if should_retry:
                retry_count += 1
                continue
            _log(f"Gagal request: {e}", "error")
            _log(
                f"Tanggal {target_date.strftime('%Y-%m-%d')} dilewati, lanjut ke tanggal berikutnya (jika ada).",
                "warning",
            )
            return

    lines = r.text.strip().split("\n")
    if len(lines) <= 1:
        _log("  Tidak ada data", "info")
        return

    data = []
    for line in lines[1:]:  # skip header
        if not line.strip():
            continue
        cols = line.split(",", 6)
        if len(cols) < 7:
            continue
        _, y, m, d, h, mi, report = cols
        try:
            obs_time = datetime(int(y), int(m), int(d), int(h), int(mi), tzinfo=pytz.UTC)
            row = parse_metar(report, icao)
            row["observation_time"] = obs_time.isoformat() 
            data.append(row)
        except Exception as e:
            _log(f"Row parse error: {e}", "warning")
            pass

    if not data:
        _log("  Tidak ada record valid", "warning")
        return

    df = pd.DataFrame(data)
    filename = os.path.join(output_dir, f"{icao}_{date_str}.csv")
    df.to_csv(filename, index=False)
    _log(f"{len(data)} record → {filename}", "success")

# ================== ARGUMENT PARSER ==================
if __name__ == "__main__":
    _init_terminal_colors()
    parser = argparse.ArgumentParser(description="Ogimet METAR Scraper + Parser")
    parser.add_argument("--icao", required=True, help="Kode ICAO (contoh: WIII)")
    parser.add_argument("--date", help="Mode single day: YYYY-MM-DD")
    parser.add_argument("--start", help="Mode range: tanggal mulai YYYY-MM-DD")
    parser.add_argument("--end", help="Mode range: tanggal akhir YYYY-MM-DD")
    parser.add_argument("--output", default="ogimet_data", help="Folder output (default: ogimet_data)")

    args = parser.parse_args()
    os.makedirs(args.output, exist_ok=True)
    run_ok = True

    if args.date:
        # Mode single day
        target = datetime.strptime(args.date, "%Y-%m-%d")
        scrape_day(args.icao, target, args.output)
    elif args.start and args.end:
        # Mode range
        start = datetime.strptime(args.start, "%Y-%m-%d")
        end = datetime.strptime(args.end, "%Y-%m-%d")
        current = start
        while current <= end:
            scrape_day(args.icao, current, args.output)
            sleep(RANGE_DELAY_SECONDS) 
            current += timedelta(days=1)
    else:
        _log("Harus pakai --date atau --start + --end", "error")
        run_ok = False

    if run_ok:
        _log(f"\nSelesai! Semua file CSV ada di folder: {args.output}", "success")
    else:
        _log("Program dihentikan karena parameter belum lengkap.", "warning")