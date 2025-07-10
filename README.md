# 🗺️ LightOre FAA File Converter

This repository contains automation scripts and workflows to **periodically fetch FAA chart data** (e.g., GeoTIFFs, PDFs), **process them**, and **upload the results to an AWS S3 bucket** for use in the [LightOre](https://github.com/YOUR_USERNAME/lightore) app.

## 📦 What It Does

- ⏱️ Automatically runs on a schedule via [GitHub Actions](.github/workflows/fetch_faa_charts.yml)
- 🌐 Downloads latest FAA VFR Sectional and Terminal Area charts, and IFR Low/High charts (ELUS*/EHUS*)
- 🧠 Detects new charts based on filenames or effective dates
- 📁 Organizes downloaded charts into `downloads/sectional/`, `downloads/ifr_low/`, `downloads/ifr_high/`
- 🗺️ Converts GeoTIFFs to map tiles using GDAL, including automatic conversion of paletted TIFFs to RGBA as needed
- ☁️ Uploads resulting tiles to your configured S3 bucket
- 📧 Notifies by email on job completion

---

## 🧰 Repository Structure

- `scripts/download_faa_charts.py` — Downloads and unzips FAA chart .zip files, updates metadata
- `scripts/convert_faa_charts.py` — Converts all downloaded GeoTIFFs to tiles, handling paletted TIFFs automatically
- `.github/workflows/fetch_faa_charts.yml` — GitHub Actions workflow to automate the full process
- `downloads/` — Downloaded and extracted chart files
- `charts/` — (if used) Output directory for processed/converted charts
- `scripts/metadata/faa_chart_log.json` — Metadata log of processed charts

---

## 🚀 How It Works

1. **Download Step:**
   - `download_faa_charts.py` scrapes the FAA VFR and IFR pages, downloads only Sectional, Terminal Area, and ELUS*/EHUS* charts, and unzips them.
   - Skips Alaska, Area, Hawaii, and Pacific charts for IFR.
   - (TODO: Investigate and possibly support other tabs/chart types in the future. See code comments.)
2. **Convert Step:**
   - `convert_faa_charts.py` finds all GeoTIFFs, checks for paletted files, converts to RGBA VRT if needed, and runs `gdal2tiles.py`.
3. **Upload Step:**
   - Tiles are uploaded to S3 by the workflow.
4. **Notification:**
   - Email is sent on completion.

---

## ⚠️ Notes & TODOs

- Only the main VFR Sectional, Terminal Area, and IFR Low/High (ELUS*/EHUS*) charts are currently fetched and processed.
- **Other chart types/tabs (e.g., Helicopter, Grand Canyon, Caribbean, Planning, 56-Day Sets, etc) are skipped.**
- See `download_faa_charts.py` for a `TODO` comment if you want to expand support for more chart types in the future.

---

## 📝 Example Usage (Local)

```sh
# Download charts
python scripts/download_faa_charts.py
# Convert all GeoTIFFs to tiles
python scripts/convert_faa_charts.py
```

---

## 🛠️ Requirements
- Python 3.x
- GDAL (gdalinfo, gdal_translate, gdal2tiles.py)
- AWS CLI (for S3 upload)

---

## 📬 Contact
For questions or contributions, open an issue or PR!

---

# FAA Tile Converter

This repository automates the download, conversion, and upload of FAA VFR and IFR charts using a GitHub Actions workflow.

## Workflow Overview

The workflow performs the following steps:

1. **Download VFR Sectional and Terminal Area charts, and IFR Low/High charts (ELUS*/EHUS*)**
   - Skips Alaska, Area, Hawaii, and Pacific charts.
   - Prints each file as it is downloaded.
2. **Convert downloaded GeoTIFFs to tiles**
   - Uses `gdal2tiles.py`.
   - Handles paletted TIFFs by converting to RGBA VRT first.
3. **Upload resulting tiles to a specified S3 bucket**
4. **Notify by email on job completion**

All file paths and workflow steps are robust and correct for the repo structure and GitHub Actions environment. The code is designed to be clean, maintainable, and extensible for future chart types.

---

## Repository Structure

- `scripts/download_faa_charts.py`: Downloads and unzips FAA chart GeoTIFFs. **(See code for a TODO about supporting additional chart types/tabs in the future.)**
- `scripts/convert_faa_charts.py`: Converts GeoTIFFs to tiles, handling paletted TIFFs.
- `scripts/metadata/faa_chart_log.json`: Metadata log for downloaded charts.
- `.github/workflows/fetch_faa_charts.yml`: GitHub Actions workflow for automation.
- `requirements.txt`: Python dependencies.
- `charts/`: Output directory for chart tiles.

---

## Limitations & TODOs

- **Currently only VFR Sectional, Terminal Area, and IFR Low/High charts are supported.**
- **Other chart types/tabs (e.g., Helicopter, Grand Canyon, Caribbean, Planning, 56-Day Sets) are skipped.**
- See code comments and TODOs for details and future work.

> **TODO:** Investigate and possibly support additional chart types/tabs in the future (e.g., Helicopter, Grand Canyon, Caribbean, Planning, 56-Day Sets).

---

## Usage

The workflow runs automatically on a schedule (Wed/Thu/Fri at 06:00 UTC) or can be triggered manually.

1. **Configure AWS and email secrets** in your repository settings:
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `EMAIL_USER`, `EMAIL_PASSWORD`
2. **Check the workflow file** at `.github/workflows/fetch_faa_charts.yml` for details.

---

## Extending Support

To add support for additional chart types/tabs:
- Update the allowed/skip prefixes in `download_faa_charts.py`.
- Adjust HTML parsing logic as needed.
- Test thoroughly and update documentation.

---

## License

MIT License



