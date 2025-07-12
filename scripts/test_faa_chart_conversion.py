import os
import argparse
import shutil
from download_faa_charts import (
    VFR_CHARTS_URL, IFR_CHARTS_URL,
    IFR_LOW_PREFIXES,
    fetch_vfr_sectional_and_terminal_links, fetch_ifr_low_high_links,
    download_file, unzip_file
)
import subprocess

def test_download_and_convert_sectional():
    # Clean up previous test output
    if os.path.exists("test_downloads/sectional"):
        shutil.rmtree("test_downloads/sectional")
    print("Testing download and conversion of a VFR Sectional chart...")
    links = fetch_vfr_sectional_and_terminal_links(VFR_CHARTS_URL)
    if not links:
        print("No VFR Sectional links found!")
        return
    url = links[0]
    print(f"Downloading: {url}")
    zip_path = download_file(url, "test_downloads/sectional")
    unzip_file(zip_path, "test_downloads/sectional")
    tif_files = [f for f in os.listdir("test_downloads/sectional") if f.lower().endswith('.tif')]
    if not tif_files:
        print("No .tif found after unzip!")
        return
    tif_path = os.path.join("test_downloads/sectional", tif_files[0])
    tile_dir = tif_path + "_tiles"
    print(f"Running gdal2tiles.py on {tif_path}")
    subprocess.run(["gdal2tiles.py", "-z", "5-12", "-w", "none", tif_path, tile_dir], check=True)
    if os.path.isdir(tile_dir):
        print(f"Tiles created in {tile_dir}")
    else:
        print("gdal2tiles.py did not create tile directory!")

def test_download_and_convert_ifr_low():
    # Clean up previous test output
    if os.path.exists("test_downloads/ifr_low"):
        shutil.rmtree("test_downloads/ifr_low")
    print("Testing download and conversion of an IFR Low chart...")
    links = fetch_ifr_low_high_links(IFR_CHARTS_URL, IFR_LOW_PREFIXES)
    if not links:
        print("No IFR Low links found!")
        return
    url = links[0]['url']
    print(f"Downloading: {url}")
    zip_path = download_file(url, "test_downloads/ifr_low")
    unzip_file(zip_path, "test_downloads/ifr_low")
    tif_files = [f for f in os.listdir("test_downloads/ifr_low") if f.lower().endswith('.tif')]
    if not tif_files:
        print("No .tif found after unzip!")
        return
    tif_path = os.path.join("test_downloads/ifr_low", tif_files[0])
    tile_dir = tif_path + "_tiles"
    print(f"Running gdal2tiles.py on {tif_path}")
    subprocess.run(["gdal2tiles.py", "-z", "5-12", "-w", "none", tif_path, tile_dir], check=True)
    if os.path.isdir(tile_dir):
        print(f"Tiles created in {tile_dir}")
    else:
        print("gdal2tiles.py did not create tile directory!")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test FAA chart conversion.")
    parser.add_argument('--chart-type', type=str, default=None, choices=['sectional', 'ifr_low', 'ifr_high'], help='Only test this chart type (for matrix jobs)')
    return parser.parse_args()

def main():
    args = parse_args()
    if args.chart_type == 'sectional':
        test_download_and_convert_sectional()
    elif args.chart_type == 'ifr_low':
        test_download_and_convert_ifr_low()
    elif args.chart_type == 'ifr_high':
        print("IFR High chart testing not implemented.")
    else:
        test_download_and_convert_sectional()
        test_download_and_convert_ifr_low()

if __name__ == "__main__":
    main()
