import os
import subprocess
import json
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DOWNLOAD_DIR = os.path.join(REPO_ROOT, 'downloads')
METADATA_PATH = os.path.join(os.path.dirname(__file__), 'metadata', 'faa_chart_log.json')

# Helper functions for palette detection and conversion
def is_paletted_tiff(tiff_path):
    """
    Returns True if the TIFF is paletted (ColorInterp=Palette), else False.
    """
    try:
        result = subprocess.run([
            'gdalinfo', tiff_path
        ], capture_output=True, text=True, check=True)
        return 'ColorInterp=Palette' in result.stdout
    except Exception as e:
        print(f"Warning: Could not check palette for {tiff_path}: {e}")
        return False

def convert_to_rgba_vrt(tiff_path, vrt_path):
    """
    Converts a paletted TIFF to an RGBA VRT using gdal_translate.
    """
    try:
        subprocess.run([
            'gdal_translate', '-of', 'vrt', '-expand', 'rgba', tiff_path, vrt_path
        ], check=True)
        return True
    except Exception as e:
        print(f"Failed to convert {tiff_path} to RGBA VRT: {e}")
        return False

def run_gdal2tiles(input_path, output_dir):
    try:
        subprocess.run([
            'gdal2tiles.py', input_path, output_dir
        ], check=True)
        return True
    except Exception as e:
        print(f"Failed to run gdal2tiles on {input_path}: {e}")
        return False

def find_tiff_files(root_dir):
    tiffs = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.lower().endswith('.tif') or f.lower().endswith('.tiff'):
                tiffs.append(os.path.join(dirpath, f))
    return tiffs

def main():
    # Load metadata if needed
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, 'r') as f:
            metadata = json.load(f)
    else:
        metadata = {}

    tiff_files = find_tiff_files(DOWNLOAD_DIR)
    print(f"Found {len(tiff_files)} TIFF files to convert.")
    for tiff_path in tiff_files:
        file_name = os.path.basename(tiff_path)
        print(f"Processing {file_name}")
        out_dir = tiff_path.rsplit('.', 1)[0] + '_tiles'
        input_for_tiles = tiff_path
        vrt_path = None
        if is_paletted_tiff(tiff_path):
            vrt_path = tiff_path + '.vrt'
            print(f"TIFF is paletted, converting to RGBA VRT: {vrt_path}")
            if not convert_to_rgba_vrt(tiff_path, vrt_path):
                print(f"Failed to convert {tiff_path} to RGBA, skipping.")
                continue
            input_for_tiles = vrt_path
        if not run_gdal2tiles(input_for_tiles, out_dir):
            print(f"Failed to convert {tiff_path}")
        else:
            print(f"Successfully converted {tiff_path} to tiles at {out_dir}")
        # Optionally, update metadata here if you want to track conversion status

    print("\n\n")  # Two empty lines after each category

if __name__ == "__main__":
    main()
