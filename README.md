# 🗺️ LightOre FAA File Converter

This repository contains automation scripts and workflows to **periodically fetch FAA chart data** (e.g., GeoTIFFs, PDFs), **process them**, and **upload the results to an AWS S3 bucket** for use in the [LightOre](https://github.com/YOUR_USERNAME/lightore) app.

## 📦 What It Does

- ⏱️ Automatically runs on a schedule via [GitHub Actions](.github/workflows/fetch_faa_charts.yml)
- 🌐 Downloads latest FAA VFR Sectional and Terminal Area charts, and IFR Low/High charts (ELUS*/EHUS*)
- 🧠 Detects new charts based on filenames or effective dates
- 📁 Organizes downloaded charts into `downloads/sectional/`, `downloads/ifr_low/`, `downloads/ifr_high/`
- 🗺️ Converts GeoTIFFs to map tiles using GDAL, including automatic conversion of paletted TIFFs to RGBA as needed
- ☁️ Uploads resulting tiles to your configured S3 bucket (with proper cache-control headers)
- 📧 Notifies by email on job completion
- 🧪 Includes E2E and unit tests for download, conversion, and extraction logic
- 🧹 Includes a workflow to clean up S3 buckets

---

## 🐍 Python Scripts

- **`scripts/download_faa_charts.py`** — Downloads and unzips FAA chart .zip files, updates metadata, supports current-check logic to avoid redundant downloads/conversions.
- **`scripts/convert_faa_charts.py`** — Converts all downloaded GeoTIFFs to tiles, handling paletted TIFFs automatically.
- **`scripts/faachart_minimal_e2e.py`** — Minimal E2E test: downloads and extracts a single chart for CI.
- **`scripts/test_faa_chart_conversion.py`** — Unit test for download and conversion of charts.
- **`scripts/test_faa_chart_extraction.py`** — Unit test for link extraction and metadata.
- **`scripts/utils.py`** — Shared helpers for download, extraction, and metadata backup.
- **`scripts/metadata/faa_chart_log.json`** — Metadata log of processed charts, used for current-check logic.

### 🔄 Current-Check Logic
- The `--check-current` flag (used in scripts and workflows) ensures that charts are only downloaded and processed if they are new or updated. This avoids redundant work and saves bandwidth and compute time. The logic checks metadata in `faa_chart_log.json` to determine if a chart is already current.

---

## ⚙️ Workflows (GitHub Actions)

- **`.github/workflows/fetch_faa_charts.yml`**: Main scheduled/manual workflow. Downloads, converts, uploads all chart types, sets cache-control, sends email notification, and uploads logs/artifacts.
- **`.github/workflows/faachart_minimal_e2e_test.yml`**: Minimal E2E test for CI. Downloads, converts, and uploads a single chart (no cache-control header, no current-check).
- **`.github/workflows/faachart_e2e_cachecontrol_test.yml`**: E2E test for current-check and cache-control logic. Ensures S3 uploads use correct headers and redundant work is avoided.
- **`.github/workflows/faachart_s3_cleanup.yml`**: Manual workflow to delete all objects in the S3 test bucket.

### 🗄️ Cache-Control Logic
- The main and E2E cache-control workflows upload tiles to S3 with the header:
  - `--cache-control "public, max-age=31536000, immutable"`
- This instructs browsers and clients to cache tiles for up to one year, reducing load times and bandwidth. The minimal E2E test does not set this header, so it does not test cache-control.

---

## 🚀 How It Works

1. **Download Step:**
   - `download_faa_charts.py` scrapes the FAA VFR and IFR pages, downloads only Sectional, Terminal Area, and ELUS*/EHUS* charts, and unzips them.
   - Skips Alaska, Area, Hawaii, and Pacific charts for IFR.
   - Uses `--check-current` to avoid redundant downloads/conversions.
2. **Convert Step:**
   - `convert_faa_charts.py` finds all GeoTIFFs, checks for paletted files, converts to RGBA VRT if needed, and runs `gdal2tiles.py`.
3. **Upload Step:**
   - Tiles are uploaded to S3 by the workflow, with `--cache-control` for long-term client caching (except in minimal E2E test).
4. **Notification:**
   - Email is sent on completion (see workflow for configuration).
5. **Testing:**
   - Minimal E2E and cache-control E2E workflows validate the pipeline and S3 upload logic.
   - Unit tests for download, conversion, and extraction logic are provided in `scripts/`.
6. **Cleanup:**
   - S3 cleanup workflow can be triggered manually to delete all objects in the test bucket.

---

## 📝 Example Usage (Local)

```sh
# Download charts (with current-check)
python scripts/download_faa_charts.py --check-current
# Convert all GeoTIFFs to tiles
python scripts/convert_faa_charts.py
# Minimal E2E test (for CI)
python scripts/faachart_minimal_e2e.py sectional SEA
# Run unit tests
python scripts/test_faa_chart_conversion.py
python scripts/test_faa_chart_extraction.py
```

---

## 📄 Metadata

- All processed chart metadata is stored in `scripts/metadata/faa_chart_log.json` and is used for current-check logic.

---

## ⚠️ Notes & TODOs

- Only the main VFR Sectional, Terminal Area, and IFR Low/High (ELUS*/EHUS*) charts are currently fetched and processed.
- **Other chart types/tabs (e.g., Helicopter, Grand Canyon, Caribbean, Planning, 56-Day Sets, etc) are skipped.**
- See `download_faa_charts.py` for a `TODO` comment if you want to expand support for more chart types in the future.

---



