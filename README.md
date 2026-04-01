# METAR Script

Kumpulan script Python untuk mengambil data METAR dari dua sumber:

- NOAA (AviationWeather) untuk history dan monitoring real-time.
- CheckWX untuk monitoring real-time decoded.

## Penjelasan Penting

Jika tujuan Anda adalah mengambil history METAR (hari ini atau tanggal tertentu), gunakan script NOAA:

```bash
python metar_NOAA.py ...
```

## Struktur Workspace

- `metar_NOAA.py`: ambil history METAR dan monitoring real-time berbasis NOAA.
- `metar_WXaggregator.py`: monitoring METAR real-time berbasis CheckWX (decoded).
- `README.md`: dokumentasi penggunaan.

## Persyaratan

- Python 3.9+
- Paket Python `requests`

Install dependency:

```bash
pip install requests
```

## Konfigurasi Awal

Sebelum menjalankan script, ubah konfigurasi berikut di file terkait:

1. `metar_NOAA.py`
- `ICAO = "MASUKAN_KODE_ICAO_DISINI"`

2. `metar_WXaggregator.py`
- `API_KEY = "MASUKAN_API_KEY"`
- `ICAO = "MASUKAN_KODE_ICAO_DISINI"`

## Penggunaan Script NOAA (History + Realtime)

Gunakan script ini jika ingin data history METAR.

Template command:

```bash
python metar_NOAA.py <mode> [opsi]
```

### 1. History Hari Ini

```bash
python metar_NOAA.py today
```

Output:

- Mengambil data METAR tanggal hari ini (UTC).
- Menyimpan ke CSV dengan format nama `ICAO_YYYYMMDD.csv`.

### 2. History Tanggal Tertentu

```bash
python metar_NOAA.py history --date 2026-03-31
```

Parameter:

- `--date` wajib dengan format `YYYY-MM-DD`.

Output:

- Data difilter sesuai tanggal yang diminta.
- Disimpan ke CSV dengan format nama `ICAO_YYYYMMDD.csv`.

### 3. Monitoring Real-time NOAA

```bash
python metar_NOAA.py realtime
```

Perilaku:

- Polling setiap 5 menit.
- Menampilkan data hanya saat ada perubahan observasi terbaru.
- Hentikan dengan `Ctrl + C`.

### Bantuan Command NOAA

```bash
python metar_NOAA.py -h
python metar_NOAA.py history -h
```

## Penggunaan Script CheckWX (Realtime Decoded)

Script ini khusus monitoring real-time menggunakan endpoint decoded dari CheckWX.

```bash
python metar_WXaggregator.py
```

Perilaku:

- Polling default setiap 5 menit (`POLL_INTERVAL = 300`).
- Menampilkan data baru jika waktu observasi berubah.
- Membutuhkan API key CheckWX yang valid.

## Contoh Kolom Data yang Ditampilkan

- `observation_time`
- `raw_text`
- `report_type`
- `temp_c`
- `dewpoint_c`
- `wind_dir`
- `wind_speed_kt`
- `visibility`
- `pressure_mb`

## Catatan

- NOAA cocok untuk kebutuhan history dan bisa dipakai realtime.
- CheckWX pada project ini dipakai untuk realtime decoded.
- Untuk ganti bandara, ubah nilai `ICAO` di masing-masing script.