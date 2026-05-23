# Weather Data Scraping

Python scripts for retrieving METAR data from several sources:

- NOAA (AviationWeather) for history and real-time monitoring.
- CheckWX for decoded real-time monitoring.
- Weather Underground (PWS) for history and polling personal station data.
- OGIMET for METAR history based on date ranges and extended parsing.

## Workspace Structure

- `metar_NOAA.py`: retrieves METAR history and real-time monitoring from NOAA.
- `metar_WXaggregator.py`: real-time METAR monitoring based on CheckWX (decoded).
- `metar_OGIMET.py`: retrieves METAR history from OGIMET (single date or date range).
- `inf_global_model.py`: fetches global weather model data (GFS, ICON, ECMWF, GEM, ARPEGE, ACCESS-G, ERA5) from Open-Meteo API.
- `Weather Undergound/wunderground_pws_scraper.py`: history and polling for Weather Underground PWS data.
- `ogimet_data/`: default CSV output folder for the OGIMET script.
- `global_model_data/`: default CSV output folder for the global model script.
- `Asset/Animation.gif`: visual guide for getting the Weather Underground API key.
- `README.md`: usage documentation.

## Requirements

- Python 3.9+
- Python packages are listed in `requirements.txt`

Install dependencies (recommended):

```bash
pip install -r requirements.txt
```

Optional but recommended: use a virtual environment

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

## Initial Configuration

Before running the scripts, update the following configuration in the related files:

### What is ICAO?

ICAO is the unique 4-letter airport code.

- Examples: `WIII`, `WSSS`, `RJTT`, `KJFK`.
- In this README, the commands use the placeholder `<ICAO_CODE>` so you can replace it with your target airport.

### Where Should ICAO Be Filled In?

- `metar_NOAA.py`: provide it through the command argument `--icao <ICAO_CODE>`.
- `metar_OGIMET.py`: provide it through the command argument `--icao <ICAO_CODE>`.
- `metar_WXaggregator.py`: provide it through the command argument `--icao <ICAO_CODE>`.
- `Weather Undergound/wunderground_pws_scraper.py`: it does not use ICAO, but uses a station ID through the `--station` argument.

## How to Run the Scripts

Run all commands from the project root folder.

### 1. NOAA Script

This file is used for NOAA METAR history and real-time monitoring.

#### Show help

```bash
python metar_NOAA.py -h
```

#### Get today's history

```bash
python metar_NOAA.py --icao <ICAO_CODE> today
```

#### Get history for a specific date

```bash
python metar_NOAA.py --icao <ICAO_CODE> history --date 2026-03-31
```

#### NOAA real-time monitoring

```bash
python metar_NOAA.py --icao <ICAO_CODE> realtime
```

#### History mode help

```bash
python metar_NOAA.py --icao <ICAO_CODE> history -h
```

### 2. CheckWX Script

This file is used for decoded real-time monitoring from CheckWX.

#### Run real-time monitoring

```bash
python metar_WXaggregator.py --icao <ICAO_CODE>
```

### 3. Weather Underground Script

This file is located in the `Weather Undergound` folder and is used for Weather Underground PWS data.

#### Run history

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE>  --date 2026-01-01
```

#### Run today's history

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE>  today
```

#### Run real-time polling

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE>  today --interval 60
```

#### Run batch history (date range)

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE>  --start 2026-01-01 --end 2026-04-14
```

#### Run batch history with custom throttle

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE> --start 2026-01-01 --end 2026-04-14 --request-delay 2.2 --request-jitter 0.4
```

#### Run batch history with the available-data search algorithm

```bash
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE> --start 2026-01-01 --end 2026-04-14 --auto-start
```

### 4. OGIMET Script

This file is used to retrieve METAR history from OGIMET and save it to CSV.

#### Single date

```bash
python metar_OGIMET.py --icao <ICAO_CODE> --date 2026-04-14
```

#### Date range

```bash
python metar_OGIMET.py --icao <ICAO_CODE> --start 2026-04-10 --end 2026-04-14
```

#### Custom output folder

```bash
python metar_OGIMET.py --icao <ICAO_CODE> --date 2026-04-14 --output ogimet_data
```

### 5. Global Model Script (Open-Meteo)

This file is used to fetch global weather model data (GFS, ICON, ECMWF IFS/AIFS, GEM, ARPEGE, ACCESS-G, ERA5) from the Open-Meteo API.

#### Show help

```bash
python inf_global_model.py -h
```

#### Batch mode (date range)

```bash
python inf_global_model.py --lat <LAT> --lon <LON> --start 2025-04-01 --end 2025-04-30
```

#### Single date

```bash
python inf_global_model.py --lat <LAT> --lon <LON> --date 2025-06-15
```

#### Realtime polling

```bash
python inf_global_model.py --lat <LAT> --lon <LON> realtime
```

#### Realtime polling with filter (preserve existing data)

```bash
python inf_global_model.py --lat <LAT> --lon <LON> --filter realtime
```

#### Custom output folder

```bash
python inf_global_model.py --lat <LAT> --lon <LON> --date 2025-06-15 --output my_data
```

#### Fetch specific models only

```bash
python inf_global_model.py --lat <LAT> --lon <LON> --date 2025-06-15 --model gfs icon
```

```bash
python inf_global_model.py --lat <LAT> --lon <LON> --start 2025-04-01 --end 2025-04-30 --model ecmwf_ifs gem
```

```bash
python inf_global_model.py --lat <LAT> --lon <LON> realtime --model gfs icon gem
```

#### Quiet fallback logs

```bash
python inf_global_model.py --lat <LAT> --lon <LON> --start 2025-04-01 --end 2025-04-30 --quiet-fallback
```

#### Disable fallback for testing

```bash
python inf_global_model.py --lat <LAT> --lon <LON> --start 2025-04-01 --end 2025-04-30 --no-fallback
```

#### Notes

- Available models: `gfs`, `icon`, `ecmwf_ifs`, `gem`, `arpege`, `access_g`, `era5`.
- If `--model` is not provided, all 7 models are fetched by default.
- `--filter`: when enabled, existing rows in the CSV are preserved and not overwritten by new rows. Without `--filter`, older rows can be replaced by data from the latest model run. This is useful in realtime mode when new model runs can update already-passed timestamps.

- Output is stored as separate CSV files per model (e.g., `gfs.csv`, `icon.csv`, `ecmwf_ifs.csv`) inside the output folder (default: `global_model_data/`).
- Deduplication: if data for the same datetime already exists in the CSV, it will not be written again.
- Data in each CSV is always sorted chronologically.
- Realtime mode respects each model's update frequency (e.g., ICON 8x/day, GFS 4x/day, ECMWF 2x/day) and only fetches when new data is expected.
- The script retries up to 3 times with exponential backoff on network errors.
- If one model fails, the script continues fetching the remaining models.

### How to Get the Weather Underground API Key

1. Open the Weather Underground website.
2. Choose the PWS you want to retrieve data from.
3. Open Developer Tools in the browser.
4. Go to the `Network` tab.
5. Trigger a request from that PWS page.
6. Find the request that calls the Weather.com / Weather Underground endpoint.
7. In the request URL or headers, take the value `current?apiKey=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`, which is a 30-character combination of letters and numbers.

Important notes:

- One API key can be used for requests to more than one PWS as long as the access is valid.
- If you want to switch PWS, just change the `--station` value in the command.
- Realtime polling is display-only: data is shown in the terminal and is not saved into any file.
- Date formats for `--date`, `--start`, and `--end` can be `YYYYMMDD` or `YYYY-MM-DD`.
- Safe recommendation for `--request-delay` is `2.0` to `2.5` seconds (default `2.2`) so it stays below about 30 requests/minute.
- The script already has auto retry + backoff for HTTP `429/5xx` and connection errors.
- If `--output-dir` is not provided, the script automatically creates or reuses the output folder inside `output/`.
- If the automatic/manual output folder already exists, files with the same name will be overwritten.
- Use `--auto-start` when using `--start/--end` if you want the script to automatically move the start date to the first day that actually has data.

Visual guide:

![Weather Underground Guide](Asset/Animation.gif)

## Command Summary

```bash
python metar_NOAA.py --icao <ICAO_CODE> today
python metar_NOAA.py --icao <ICAO_CODE> history --date 2026-03-31
python metar_NOAA.py --icao <ICAO_CODE> realtime
python metar_WXaggregator.py --icao <ICAO_CODE>
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE> --date 2026-01-01
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE> today
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE> today --interval 60
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE> --start 2026-01-01 --end 2026-04-14 --request-delay 2.2 --request-jitter 0.4
python "Weather Undergound/wunderground_pws_scraper.py" --station <STATION_CODE> --start 2026-01-01 --end 2026-04-14 --auto-start
python metar_OGIMET.py --icao <ICAO_CODE> --date 2026-04-14
python metar_OGIMET.py --icao <ICAO_CODE> --start 2026-04-10 --end 2026-04-14
python inf_global_model.py --lat <LAT> --lon <LON> --date 2025-06-15
python inf_global_model.py --lat <LAT> --lon <LON> --start 2025-04-01 --end 2025-04-30
python inf_global_model.py --lat <LAT> --lon <LON> realtime
python inf_global_model.py --lat <LAT> --lon <LON> --filter realtime
python inf_global_model.py --lat <LAT> --lon <LON> --date 2025-06-15 --model gfs icon
```

## Example Columns in the Output

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

## How to Read NOAA CSV Output

Each CSV row represents one METAR/SPECI report at a specific station-local time.

### 1) Time and report identity

- `local_time`: local station time (timezone-converted), example `2026-04-14 10:00:00`.
- `report_type`: report type, `METAR` (routine) or `SPECI` (special report when significant changes occur).
- `raw_text`: the original raw METAR text; this is the main reference if you want to validate parsing.

### 2) Temperature, humidity, pressure

- `temp_c`: air temperature (C).
- `dewpoint_c`: dew point (C). A small difference between temperature and dew point usually indicates high humidity.
- `pressure_mb`: air pressure (hPa/mb).

### 3) Wind

- `wind_dir`: main wind direction (degrees from true north) or `VRB` if variable.
- `wind_speed_kt`: average wind speed (knots).
- `wind_gust_kt`: maximum gust speed (knots).
- `wind_dir_var`: wind direction variation.

### 4) Visibility, clouds, current weather

- `visibility`: horizontal visibility (as provided by the NOAA source).
- `cloud_layers`: compact METAR cloud layer format.
	- `FEW016` means a few clouds around 1600 ft AGL.
	- `BKN`/`OVC` are usually used for operational ceiling evaluation.
- `wx_string`: current weather phenomena (present weather).

### 5) Flight category and report quality

- `flight_category`: operational classification (`VFR`, `MVFR`, `IFR`, `LIFR`).
- `auto`: automatic/correction status.
	- `AUTO`: automatic report.
	- `COR`: correction report.
	- `AUTO/COR`: both detected in the raw report.

### 6) Additional information from the raw METAR

- `recent_weather`: recent weather phenomenon marked as `RE...` (example `RERA`, `RETS`).
- `rvr`: Runway Visual Range if present (example `R23/1200FT`).
- `remarks`: the part after the `RMK` token in the raw METAR.
- `rmk_indicators`: important indicators detected in the remarks, such as `WSHFT`, `PK WND`, `PRESFR`, `PRESRR`.

### 7) Station metadata

- `latitude`, `longitude`: station coordinates.
- `elevation_m`: station elevation (meters).

## Quick Interpretation Tips

- Bad conditions first: `flight_category` = `IFR/LIFR`, low `visibility`, and low `cloud_layers` dominated by `BKN/OVC`.
- Significant weather potential: `wx_string` contains `TS`, `FG`, `SHRA`, or intensity symbols such as `+`.
- Dangerous wind potential: high `wind_gust_kt`, wide `wind_dir_var` (`xxxVyyy`), or `VRB`.
- Short event analysis: check `recent_weather`, `rvr`, and `rmk_indicators` for signs of rapid change.

## Empty Values in CSV

Some columns may be empty because they are not always reported in every METAR, especially `rvr`, `recent_weather`, `remarks`, or `wind_gust_kt`. Empty values are not an error as long as the file is created and the other columns are read normally.

## Notes

- NOAA is suitable for history and can also be used in real-time.
- CheckWX in this project is used for decoded real-time monitoring.
- OGIMET is suitable for batch/range history with daily CSV output.
- Global Model (Open-Meteo) is suitable for NWP model data (GFS, ICON, ECMWF, etc.) with batch, single-date, or realtime polling modes.