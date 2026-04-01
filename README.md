# METAR Script

Script Python untuk mengambil data METAR dari API AviationWeather (NOAA), baik untuk riwayat harian maupun monitoring real-time.

## Fitur

- Ambil riwayat METAR untuk hari ini.
- Ambil riwayat METAR untuk tanggal tertentu.
- Monitoring METAR real-time (polling tiap 5 menit).
- Ekspor data riwayat ke file CSV.
- Deteksi tipe laporan `METAR` atau `SPECI`.

## Persyaratan

- Python 3.9+
- Paket Python `requests`

Install dependency:

```bash
pip install requests
```

## Struktur Workspace

- `metar_wsss.py`: script utama.
- `README.md`: dokumentasi penggunaan.

## Cara Menjalankan

Masuk ke folder project, lalu jalankan perintah berikut:

```bash
python metar_wsss.py <mode> [opsi]
```

### 1. Ambil History Hari Ini

```bash
python metar_wsss.py today
```

Hasil:

- Mengambil data METAR untuk tanggal hari ini (UTC).
- Menyimpan file CSV dengan format nama: `ICAO_YYYYMMDD.csv`.

### 2. Ambil History Tanggal Tertentu

```bash
python metar_wsss.py history --date 2026-03-31
```

Parameter:

- `--date` wajib, format `YYYY-MM-DD`.

Hasil:

- Data difilter sesuai tanggal yang diminta.
- Output disimpan ke CSV dengan nama `ICAO_YYYYMMDD.csv`.

### 3. Monitoring Real-time

```bash
python metar_wsss.py realtime
```

Perilaku:

- Script berjalan terus dan polling data terbaru setiap 5 menit.
- Data hanya ditampilkan jika ada perubahan laporan terbaru.
- Hentikan dengan `Ctrl + C`.

## Contoh Kolom CSV Output

- `observation_time`
- `raw_text`
- `report_type`
- `temp_c`
- `dewpoint_c`
- `wind_dir`
- `wind_speed_kt`
- `visibility`
- `pressure_mb`

## Catatan Penting

- ICAO yang dipakai saat ini adalah nilai konstanta `ICAO` di script.
- Pada file saat ini, nilainya adalah `LTAC`.
- Jika ingin bandara lain, ubah variabel `ICAO` di `metar_wsss.py`.

## Bantuan Command

Untuk melihat bantuan mode:

```bash
python metar_wsss.py -h
python metar_wsss.py history -h
```