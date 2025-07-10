# 🗺️ LightOre FAA File Converter

This repository contains automation scripts and workflows to **periodically fetch FAA chart data** (e.g., GeoTIFFs, PDFs), **process them**, and **upload the results to an AWS S3 bucket** for use in the [LightOre](https://github.com/YOUR_USERNAME/lightore) app.

## 📦 What It Does

- ⏱️ Automatically runs every 2 days via [GitHub Actions](.github/workflows/fetch_faa_charts.yml)
- 🌐 Downloads latest FAA charts (e.g., TPP PDFs, GeoTIFFs)
- 🧠 Detects new charts based on filenames or effective dates
- 📁 Organizes downloaded charts into `charts/YYYY-MM-DD/`
- ☁️ Uploads charts to your configured S3 bucket

---

## 🧰 Repository Structure



