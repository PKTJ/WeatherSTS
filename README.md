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

3. `Weather Undergound/wunderground_pws_scraper.py`
- `STATION_ID = "MASUKAN_DISINI"`
- `API_KEY = "MASUKAN_API_KEY_DISINI"`
- `UNITS = "m"`

## Cara Menjalankan Script

### 1. Script NOAA

File ini dipakai untuk history METAR dan realtime NOAA.

#### Lihat bantuan

```bash
python metar_NOAA.py -h
```

#### Ambil history hari ini

```bash
python metar_NOAA.py today
```

#### Ambil history tanggal tertentu

```bash
python metar_NOAA.py history --date 2026-03-31
```

#### Monitoring realtime NOAA

```bash
python metar_NOAA.py realtime
```

#### Bantuan khusus mode history

```bash
python metar_NOAA.py history -h
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
python "Weather Undergound/wunderground_pws_scraper.py" --mode history --date 20260101
```

#### Jalankan polling realtime

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --mode poll --interval 60
```

### Cara Mendapatkan API Key Weather Underground

1. Buka website Weather Underground.
2. Pilih PWS yang ingin diambil datanya dengan mengisi `STASIUN_ID` sama dengan title PWS yang anda cari.
3. Buka Developer Tools di browser.
4. Masuk ke tab `Network`.
5. Lakukan request dari halaman PWS tersebut.
6. Cari request yang memanggil endpoint Weather.com / Weather Underground
7. Di request URL atau headers, ambil nilai `current?apiKey=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` beruba 30 kombinasi unik angka dan huruf.

Catatan penting:

- Satu API key bisa digunakan untuk request lebih dari satu PWS selama aksesnya valid.
- Jika ingin pindah PWS, cukup ganti `STATION_ID` di file script.
- Format tanggal untuk mode history adalah `YYYYMMDD`, misalnya `20260101`.

Panduan visual:

![Panduan Weather Underground](Asset/Animation.gif)

## Ringkasan Perintah

```bash
python metar_NOAA.py today
python metar_NOAA.py history --date 2026-03-31
python metar_NOAA.py realtime
python metar_WXaggregator.py
python wunderground_pws_scraper.py --mode history --date 20260101
python wunderground_pws_scraper.py --mode poll --interval 60
```

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
