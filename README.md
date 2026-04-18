# METAR Script

Kumpulan script Python untuk mengambil data METAR dari beberapa sumber:

- NOAA (AviationWeather) untuk history dan monitoring real-time.
- CheckWX untuk monitoring real-time decoded.
- Weather Underground (PWS) untuk history dan polling data stasiun personal.
- OGIMET untuk history METAR berbasis rentang tanggal dan parsing lanjutan.

## Struktur Workspace

- `metar_NOAA.py`: ambil history METAR dan monitoring real-time berbasis NOAA.
- `metar_WXaggregator.py`: monitoring METAR real-time berbasis CheckWX (decoded).
- `metar_OGIMET.py`: ambil history METAR dari OGIMET (single date atau date range).
- `Weather Undergound/wunderground_pws_scraper.py`: history dan polling PWS Weather Underground.
- `ogimet_data/`: folder default output CSV dari script OGIMET.
- `Asset/Animation.gif`: panduan visual ambil API key Weather Underground.
- `README.md`: dokumentasi penggunaan.

## Persyaratan

- Python 3.9+
- Paket Python ada di file `requirements.txt`

Install dependency (disarankan):

```bash
pip install -r requirements.txt
```

Opsional (direkomendasikan): gunakan virtual environment

```bash
python -m venv .venv
```

Windows PowerShell:

```bash
& ".venv/Scripts/Activate.ps1"
pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Konfigurasi Awal

Sebelum menjalankan script, ubah konfigurasi berikut di file terkait:

### Apa itu ICAO?

ICAO adalah kode unik bandara yang terdiri dari 4 huruf.

- Contoh: `WIII`, `WSSS`, `RJTT`, `KJFK`.
- Di README ini, contoh perintah memakai placeholder `<ICAO_CODE>` supaya bisa diganti sesuai bandara tujuan Anda.

### ICAO Diisi di Mana?

- `metar_NOAA.py`: isi lewat argument command `--icao <ICAO_CODE>`.
- `metar_OGIMET.py`: isi lewat argument command `--icao <ICAO_CODE>`.
- `metar_WXaggregator.py`: isi langsung di variabel `ICAO = "..."` pada file script.
- `Weather Undergound/wunderground_pws_scraper.py`: tidak memakai ICAO, tetapi memakai station ID lewat argument `--station`.

1. `metar_WXaggregator.py`
- `API_KEY = "MASUKAN_API_KEY"`
- `ICAO = "MASUKAN_KODE_ICAO_DISINI"`

2. `Weather Undergound/wunderground_pws_scraper.py`
- `API_KEY = "MASUKAN_API_KEY_DISINI"`
- `UNITS = "m"`
- `STATION_ID` tidak perlu diubah di file karena sekarang wajib diisi dari CLI dengan `--station`.

3. `metar_OGIMET.py`
- Jalankan dengan parameter `--icao` dan salah satu mode tanggal:
	- single day: `--date YYYY-MM-DD`
	- range day: `--start YYYY-MM-DD --end YYYY-MM-DD`

## Cara Menjalankan Script

Jalankan semua command dari folder root project.

### 1. Script NOAA

File ini dipakai untuk history METAR dan realtime NOAA.

#### Lihat bantuan

```bash
python metar_NOAA.py -h
```

#### Ambil history hari ini

```bash
python metar_NOAA.py --icao <ICAO_CODE> today
```

#### Ambil history tanggal tertentu

```bash
python metar_NOAA.py --icao <ICAO_CODE> history --date 2026-03-31
```

#### Monitoring realtime NOAA

```bash
python metar_NOAA.py --icao <ICAO_CODE> realtime
```

#### Bantuan khusus mode history

```bash
python metar_NOAA.py --icao <ICAO_CODE> history -h
```

### 2. Script CheckWX

File ini dipakai untuk monitoring realtime decoded dari CheckWX.

#### Jalankan monitoring realtime

```bash
python metar_WXaggregator.py
```

### 3. Script Weather Underground

File ini berada di folder `Weather Undergound` dan dipakai untuk data PWS Weather Underground.

#### Jalankan history

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 --date 2026-01-01
```

#### Jalankan history hari ini

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 today
```

#### Jalankan polling realtime

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 today --interval 60
```

#### Jalankan history batch (date range)

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 --start 2026-01-01 --end 2026-04-14
```

#### Jalankan history batch dengan throttle custom

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 --start 2026-01-01 --end 2026-04-14 --request-delay 2.2 --request-jitter 0.4
```

#### Jalankan history batch dengan algoritma pencarian data yang tersedia

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 --start 2026-01-01 --end 2026-04-14 --auto-start
```

### 4. Script OGIMET

File ini dipakai untuk mengambil history METAR dari OGIMET dan menyimpan ke CSV.

#### Single date

```bash
python metar_OGIMET.py --icao <ICAO_CODE> --date 2026-04-14
```

#### Date range

```bash
python metar_OGIMET.py --icao <ICAO_CODE> --start 2026-04-10 --end 2026-04-14
```

#### Custom folder output

```bash
python metar_OGIMET.py --icao <ICAO_CODE> --date 2026-04-14 --output ogimet_data
```

### Cara Mendapatkan API Key Weather Underground

1. Buka website Weather Underground.
2. Pilih PWS yang ingin diambil datanya.
3. Buka Developer Tools di browser.
4. Masuk ke tab `Network`.
5. Lakukan request dari halaman PWS tersebut.
6. Cari request yang memanggil endpoint Weather.com / Weather Underground
7. Di request URL atau headers, ambil nilai `current?apiKey=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` beruba 30 kombinasi unik angka dan huruf.

Catatan penting:

- Satu API key bisa digunakan untuk request lebih dari satu PWS selama aksesnya valid.
- Jika ingin pindah PWS, cukup ganti nilai `--station` pada command.
- Format tanggal untuk `--date`, `--start`, dan `--end` bisa `YYYYMMDD` atau `YYYY-MM-DD`.
- Rekomendasi aman `--request-delay 2.0` sampai `2.5` detik (default `2.2`) agar tetap di bawah sekitar 30 request/menit.
- Script sudah punya auto retry + backoff untuk HTTP `429/5xx` dan error koneksi.
- Jika tidak isi `--output-dir`, script otomatis membuat atau memakai ulang folder output di dalam folder `output/`.
- Jika folder output otomatis/manual sudah ada, file dengan nama yang sama akan langsung ditimpa (overwrite).
- Gunakan `--auto-start` saat memakai `--start/--end` jika ingin script otomatis geser tanggal mulai ke hari pertama yang benar-benar punya data.

Panduan visual:

![Panduan Weather Underground](Asset/Animation.gif)

## Ringkasan Perintah

```bash
python metar_NOAA.py --icao <ICAO_CODE> today
python metar_NOAA.py --icao <ICAO_CODE> history --date 2026-03-31
python metar_NOAA.py --icao <ICAO_CODE> realtime
python metar_WXaggregator.py
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 --date 2026-01-01
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 today
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 today --interval 60
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 --start 2026-01-01 --end 2026-04-14 --request-delay 2.2 --request-jitter 0.4
python "Weather Undergound/wunderground_pws_scraper.py" --station ISINGA249 --start 2026-01-01 --end 2026-04-14 --auto-start
python metar_OGIMET.py --icao <ICAO_CODE> --date 2026-04-14
python metar_OGIMET.py --icao <ICAO_CODE> --start 2026-04-10 --end 2026-04-14
```

## Contoh Kolom Data yang Ditampilkan

- `observation_time`
- `local_time`
- `raw_text`
- `report_type`
- `temp_c`
- `dewpoint_c`
- `wind_dir`
- `wind_speed_kt`
- `wind_gust_kt`
- `wind_dir_var`
- `visibility`
- `pressure_mb`
- `cloud_layers`
- `wx_string`
- `flight_category`
- `auto`
- `recent_weather`
- `rvr`
- `remarks`
- `rmk_indicators`
- `latitude`, `longitude`, `elevation_m`

## Cara Membaca Output CSV NOAA

Setiap baris CSV mewakili satu laporan METAR/SPECI pada waktu observasi tertentu.

### 1) Waktu dan identitas laporan

- `observation_time`: waktu observasi dalam UTC (format ISO), contoh `2026-04-14T03:00:00+00:00`.
- `local_time`: waktu lokal stasiun (hasil konversi timezone), contoh `2026-04-14 10:00:00`.
- `report_type`: tipe laporan, `METAR` (rutin) atau `SPECI` (laporan khusus saat ada perubahan signifikan).
- `raw_text`: teks METAR mentah asli; ini referensi utama jika ingin validasi parsing.

### 2) Suhu, kelembapan, tekanan

- `temp_c`: suhu udara (C).
- `dewpoint_c`: titik embun (C). Selisih kecil antara suhu dan dew point biasanya menandakan kelembapan tinggi.
- `pressure_mb`: tekanan udara (hPa/mb).

### 3) Angin

- `wind_dir`: arah angin utama (derajat dari utara sejati) atau `VRB` jika variable.
- `wind_speed_kt`: kecepatan angin rata-rata (knot).
- `wind_gust_kt`: hembusan maksimum/gust (knot).
- `wind_dir_var`: variasi arah angin.

### 4) Visibilitas, awan, cuaca kini

- `visibility`: jarak pandang horizontal (sesuai format dari sumber NOAA).
- `cloud_layers`: lapisan awan format ringkas METAR.
	- `FEW016` artinya awan sedikit di sekitar 1600 ft AGL.
	- `BKN`/`OVC` biasanya dipakai untuk evaluasi ceiling operasional.
- `wx_string`: fenomena cuaca saat ini (present weather).

### 5) Kategori penerbangan dan kualitas laporan

- `flight_category`: klasifikasi operasional (`VFR`, `MVFR`, `IFR`, `LIFR`).
- `auto`: status otomatis/koreksi laporan.
	- `AUTO`: laporan otomatis.
	- `COR`: laporan koreksi.
	- `AUTO/COR`: keduanya terdeteksi di raw report.

### 6) Informasi lanjutan dari raw METAR

- `recent_weather`: fenomena cuaca terbaru bertanda `RE...` (contoh `RERA`, `RETS`).
- `rvr`: Runway Visual Range jika ada (contoh `R23/1200FT`).
- `remarks`: bagian setelah token `RMK` pada raw METAR.
- `rmk_indicators`: indikator penting yang terdeteksi di remarks, misalnya `WSHFT`, `PK WND`, `PRESFR`, `PRESRR`.

### 7) Metadata stasiun

- `latitude`, `longitude`: koordinat stasiun.
- `elevation_m`: elevasi stasiun (meter).

## Tips Interpretasi Cepat

- Prioritas kondisi buruk: `flight_category` = `IFR/LIFR`, `visibility` rendah, `cloud_layers` dominan `BKN/OVC` rendah.
- Potensi cuaca signifikan: `wx_string` berisi `TS`, `FG`, `SHRA`, atau simbol intensitas seperti `+`.
- Potensi angin berbahaya: `wind_gust_kt` tinggi, `wind_dir_var` lebar (`xxxVyyy`), atau `VRB`.
- Analisis event singkat: cek `recent_weather`, `rvr`, dan `rmk_indicators` untuk sinyal perubahan cepat.

## Catatan Nilai Kosong di CSV

Sebagian kolom bisa kosong karena tidak selalu dilaporkan pada setiap METAR, terutama `rvr`, `recent_weather`, `remarks`, atau `wind_gust_kt`. Nilai kosong bukan error selama file tetap terbentuk dan kolom lain terbaca normal.

## Catatan

- NOAA cocok untuk kebutuhan history dan bisa dipakai realtime.
- CheckWX pada project ini dipakai untuk realtime decoded.
- OGIMET cocok untuk history batch/range dengan output CSV harian.