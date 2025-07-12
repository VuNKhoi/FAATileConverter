import os
import subprocess
import json
from datetime import datetime, timezone
import shutil
import re
import logging
import argparse
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DOWNLOAD_DIR = os.path.join(REPO_ROOT, 'downloads')
METADATA_PATH = os.path.join(os.path.dirname(__file__), 'metadata', 'faa_chart_log.json')

def is_paletted_tiff(tiff_path: str) -> bool:
    """
    Returns True if the TIFF is paletted (ColorInterp=Palette), else False.
    """
    try:
        result = subprocess.run([
            'gdalinfo', tiff_path
        ], capture_output=True, text=True, check=True)
        return 'ColorInterp=Palette' in result.stdout
    except Exception as e:
        logging.warning(f"⚠️ Could not check palette for {tiff_path}: {e}")
        return False

def convert_to_rgba_vrt(tiff_path: str, vrt_path: str) -> bool:
    """
    Converts a paletted TIFF to an RGBA VRT using gdal_translate.
    """
    try:
        subprocess.run([
            'gdal_translate', '-of', 'vrt', '-expand', 'rgba', tiff_path, vrt_path
        ], check=True)
        return True
    except Exception as e:
        logging.error(f"❌ Failed to convert {tiff_path} to RGBA VRT: {e}\nSkipping {tiff_path}.")
        return False

def run_gdal2tiles(input_path: str, output_dir: str, zoom: str = "5-12") -> bool:
    """
    Convert a GeoTIFF into XYZ tiles using gdal2tiles.
    Args:
        input_path (str): Path to the .tif input file
        output_dir (str): Destination directory for the tiles
        zoom (str): Zoom level range, e.g., "5-12"
    Returns:
        bool: True if successful, False otherwise
    """
    logging.info(f"🧱 Converting {os.path.basename(input_path)} to tiles...")
    try:
        subprocess.run([
            "gdal2tiles.py",
            "-z", zoom,
            "-r", "bilinear",
            "--tiledriver", "PNG",
            "--xyz",
            "-w", "none",
            "--processes", "4",
            input_path,
            output_dir
        ], check=True)
        # Remove non-PNG files from output
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if not file.endswith(".png"):
                    os.remove(os.path.join(root, file))
        logging.info(f"✅ Tile conversion complete: {output_dir}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"❌ gdal2tiles failed: {e}")
        return False
    except Exception as e:
        logging.error(f"❌ Unexpected error: {e}")
        return False

def find_tiff_files(root_dir: str) -> List[str]:
    """
    Recursively find all .tif or .tiff files under root_dir.
    Returns a list of absolute file paths.
    """
    tiffs = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.lower().endswith('.tif') or f.lower().endswith('.tiff'):
                tiffs.append(os.path.join(dirpath, f))
    return tiffs

def clean_chart_name(name: str) -> str:
    """
    Clean chart name for use as a directory: remove/replace problematic characters.
    """
    return re.sub(r'[^A-Za-z0-9_-]', '_', name.rsplit('.', 1)[0])

def convert_tiff(tiff_path: str, metadata: Dict, zoom: str = "5-12") -> bool:
    """
    Convert a single TIFF to tiles, handling palette and metadata.
    Skips if already converted. Returns True if converted, False if skipped or failed.
    """
    file_name = os.path.basename(tiff_path)
    if metadata.get('converted', {}).get(file_name):
        logging.info(f"✅ Already converted: {file_name}")
        return False
    chart_name = clean_chart_name(file_name)
    out_dir = os.path.join(os.path.dirname(tiff_path), f"{chart_name}_tiles")
    input_for_tiles = tiff_path
    vrt_path = None
    # If paletted, convert to RGBA VRT first
    if is_paletted_tiff(tiff_path):
        vrt_path = tiff_path + '.vrt'
        logging.info(f"🎨 TIFF is paletted, converting to RGBA VRT: {vrt_path}")
        if not convert_to_rgba_vrt(tiff_path, vrt_path):
            return False
        input_for_tiles = vrt_path
    success = run_gdal2tiles(input_for_tiles, out_dir, zoom=zoom)
    if success:
        # Update metadata
        metadata.setdefault('converted', {})[file_name] = {
            'converted': True,
            'used_vrt': bool(vrt_path),
            'vrt_path': vrt_path if vrt_path else None,
            'tiles_dir': out_dir,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        with open(METADATA_PATH, 'w') as f:
            json.dump(metadata, f, indent=2)
    # Clean up .vrt file if created
    if vrt_path and os.path.exists(vrt_path):
        os.remove(vrt_path)
        logging.info(f"🧹 Removed VRT: {vrt_path}")
    return success

def process_all_tiffs(tiff_files: List[str], metadata: Dict, zoom: str) -> List[str]:
    """
    Process all TIFFs, return a list of files that failed to convert.
    """
    failed = []
    for tiff_path in tiff_files:
        file_name = os.path.basename(tiff_path)
        logging.info(f"🚩 Processing {file_name}")
        try:
            if not convert_tiff(tiff_path, metadata, zoom=zoom):
                # Only count as failed if not already converted and not successful
                if not metadata.get('converted', {}).get(file_name):
                    failed.append(file_name)
        except Exception as e:
            logging.error(f"❌ Exception during conversion of {file_name}: {e}")
            failed.append(file_name)
    return failed

def print_conversion_summary(tiff_files: List[str], metadata: Dict, failed: List[str]) -> None:
    """
    Print a summary of the conversion process.
    """
    logging.info("\n🎉✅ Conversion complete.")
    logging.info(f"Total TIFFs found: {len(tiff_files)}")
    logging.info(f"Total converted: {len(metadata.get('converted', {}))}")
    if failed:
        logging.warning(f"❌ Failed to convert {len(failed)} files:")
        for f in failed:
            logging.warning(f"  - {f}")
    else:
        logging.info("🎉 All files converted successfully.")

def get_zoom_from_env_or_args() -> str:
    """
    Get zoom from env FAA_TILE_ZOOM or --zoom argument, default to '5-12'.
    """
    parser = argparse.ArgumentParser(description="Convert FAA TIFFs to tiles.")
    parser.add_argument('--zoom', type=str, default=None, help='Zoom level range for gdal2tiles (e.g. 5-12)')
    args, _ = parser.parse_known_args()
    zoom = args.zoom or os.environ.get("FAA_TILE_ZOOM", "5-12")
    return zoom

def main() -> None:
    """
    Main conversion routine: finds TIFFs, handles palette, runs tiling, and logs results.
    """
    # Load metadata if needed
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, 'r') as f:
            metadata = json.load(f)
    else:
        metadata = {}

    tiff_files = find_tiff_files(DOWNLOAD_DIR)
    logging.info(f"Found {len(tiff_files)} TIFF files to convert.")
    zoom = get_zoom_from_env_or_args()
    failed = process_all_tiffs(tiff_files, metadata, zoom)
    print_conversion_summary(tiff_files, metadata, failed)

if __name__ == "__main__":
    main()
