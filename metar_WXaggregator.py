import requests
import time
from datetime import datetime, timedelta

# ================== KONFIGURASI ==================
API_KEY = "MASUKAN_API_KEY" # Ganti dengan API Key CheckWX 
ICAO     = "MASUKAN_KODE_ICAO_DISINI" # Ganti dengan ICAO yang diinginkan

# Interval polling (detik). 300 = 5 menit
POLL_INTERVAL = 300

# Header untuk API CheckWX
HEADERS = {
    "X-API-Key": API_KEY
}

# URL endpoint decoded (paling lengkap)
URL = f"https://api.checkwx.com/v2/metar/{ICAO}/decoded"

# Variabel untuk mendeteksi perubahan data
last_observed = None
# ================================================

print(f"Monitoring METAR {ICAO} via CheckWX API (setiap {POLL_INTERVAL//60} menit)\n")

while True:
    # Waktu sekarang dalam WIB (UTC+7)
    wib_time = (datetime.utcnow() + timedelta(hours=7)).strftime("%H:%M:%S")
    
    try:
        response = requests.get(URL, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get("results", 0) > 0 and data["data"]:
                metar = data["data"][0]
                
                observed = metar.get("observed")
                raw_text = metar.get("raw_text", "N/A")
                
                # Mapping field supaya mirip template lama kamu
                report_type = metar.get("report", {}).get("type", "METAR")
                temp_c = metar.get("temperature", {}).get("celsius")
                dewpoint_c = metar.get("dewpoint", {}).get("celsius")
                wind_dir = metar.get("wind", {}).get("direction", "VRB")
                wind_speed_kt = metar.get("wind", {}).get("speed", {}).get("kts")
                visibility = metar.get("visibility", {}).get("text", "N/A")
                pressure_mb = metar.get("pressure", {}).get("mb")
                
                # Cek apakah ada data baru
                if observed != last_observed:
                    print(f"[{wib_time}] Data BARU diterima!")
                    print(f"observation_time   : {observed}")
                    print(f"raw_text           : {raw_text}")
                    print(f"report_type        : {report_type}")
                    print(f"temp_c             : {temp_c}")
                    print(f"dewpoint_c         : {dewpoint_c}")
                    print(f"wind_dir           : {wind_dir}")
                    print(f"wind_speed_kt      : {wind_speed_kt}")
                    print(f"visibility         : {visibility}")
                    print(f"pressure_mb        : {pressure_mb}")
                    print("-" * 80)
                    
                    last_observed = observed
                else:
                    print(f"[{wib_time}] Tidak ada perubahan data...")
        
        elif response.status_code == 429:
            print(f"[{wib_time}] ⚠️ Rate limit exceeded (429). Tunggu sebentar...")
        else:
            print(f"[{wib_time}] ❌ Error HTTP {response.status_code}: {response.text[:100]}")
            
    except requests.exceptions.RequestException as e:
        print(f"[{wib_time}] ❌ Koneksi error: {e}")
    except Exception as e:
        print(f"[{wib_time}] ❌ Unexpected error: {e}")
    
    # Tunggu sampai interval berikutnya
    time.sleep(POLL_INTERVAL)