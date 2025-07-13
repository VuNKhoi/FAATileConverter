import os
import subprocess
import json
from datetime import datetime, timezone
import shutil
import re
import logging
import argparse
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

REPO_ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD_DIR = REPO_ROOT / 'downloads'
METADATA_PATH = Path(__file__).parent / 'metadata' / 'faa_chart_log.json'

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
    Suppresses gdal2tiles progress bar and logs only concise status.
    Args:
        input_path (str): Path to the .tif input file
        output_dir (str): Destination directory for the tiles
        zoom (str): Zoom level range, e.g., "5-12"
    Returns:
        bool: True if successful, False otherwise
    """
    logging.info(f"🧱 Converting {os.path.basename(input_path)} to tiles...")
    try:
        # Try to use --quiet if available, else suppress stdout/stderr
        cmd = [
            "gdal2tiles.py",
            "-z", zoom,
            "-r", "bilinear",
            "--tiledriver", "PNG",
            "--xyz",
            "-w", "none",
            "--processes", "4",
            "--quiet",  # This flag is available in most modern gdal2tiles
            input_path,
            output_dir
        ]
        # Remove --quiet if not supported (fallback)
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            # If --quiet is not supported, try again without it
            if 'unrecognized arguments: --quiet' in e.stderr.decode(errors='ignore'):
                cmd.remove('--quiet')
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            else:
                raise
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

def convert_tiff(tiff_path: str, zoom: str = "5-12", keep_vrt: bool = False) -> tuple:
    """
    Convert a single TIFF to tiles, handling palette. Returns (file_name, metadata_update_dict or None, success: bool).
    """
    file_name = os.path.basename(tiff_path)
    chart_name = clean_chart_name(file_name)
    out_dir = os.path.join(os.path.dirname(tiff_path), f"{chart_name}_tiles")
    input_for_tiles = tiff_path
    vrt_path = None
    # If paletted, convert to RGBA VRT first
    if is_paletted_tiff(tiff_path):
        vrt_path = tiff_path + '.vrt'
        logging.info(f"🎨 TIFF is paletted, converting to RGBA VRT: {vrt_path}")
        if not convert_to_rgba_vrt(tiff_path, vrt_path):
            return (file_name, None, False)
        input_for_tiles = vrt_path
    success = run_gdal2tiles(input_for_tiles, out_dir, zoom=zoom)
    metadata_update = None
    if success:
        metadata_update = {
            'converted': True,
            'used_vrt': bool(vrt_path),
            'vrt_path': vrt_path if vrt_path else None,
            'tiles_dir': out_dir,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    # Clean up .vrt file if created
    if vrt_path and os.path.exists(vrt_path) and not keep_vrt:
        os.remove(vrt_path)
        logging.info(f"🧹 Removed VRT: {vrt_path}")
    return (file_name, metadata_update, success)


def check_gdal_tools():
    for tool in ['gdalinfo', 'gdal_translate', 'gdal2tiles.py']:
        if shutil.which(tool) is None:
            logging.critical(f"Missing required GDAL tool: {tool}")
            exit(1)

def validate_zoom(zoom: str) -> bool:
    return bool(re.fullmatch(r'\d+(-\d+)?', zoom))


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments once and return the Namespace.
    """
    parser = argparse.ArgumentParser(
        description="""
        Converts FAA GeoTIFF charts into XYZ PNG tiles using GDAL.\n
        Tiles are written to {chart_name}_tiles/. Metadata is saved in faa_chart_log.json.
        """
    )
    parser.add_argument('--zoom', type=str, default=None, help='Zoom level range for gdal2tiles (e.g. 5-12)')
    parser.add_argument('--workers', type=int, default=None, help='Number of parallel workers (default: 4)')
    parser.add_argument('--keep-vrt', action='store_true', help='Keep .vrt files after conversion (for debugging)')
    parser.add_argument('--chart-type', type=str, default=None, choices=['sectional', 'ifr_low', 'ifr_high'], help='Only process this chart type (for matrix jobs)')
    parser.add_argument('--single-tiff', type=str, help='Convert a single TIFF file and exit')
    return parser.parse_args()


def get_zoom_from_env_or_args(args: argparse.Namespace) -> str:
    """
    Get zoom from env FAA_TILE_ZOOM or --zoom argument, default to '5-12'.
    """
    return args.zoom or os.environ.get("FAA_TILE_ZOOM", "5-12")


def get_workers_from_env_or_args(args: argparse.Namespace) -> int:
    """
    Get number of parallel workers from env FAA_TILE_WORKERS or --workers argument, default to 4.
    """
    return args.workers or int(os.environ.get("FAA_TILE_WORKERS", 4))


def convert_single_tiff(tiff_path, zoom="5-12", keep_vrt=False, metadata=None):
    """Convert a single TIFF file to tiles and update metadata if provided."""
    file_name, metadata_update, success = convert_tiff(tiff_path, zoom, keep_vrt)
    if metadata is not None and success and metadata_update:
        metadata.setdefault('converted', {})[file_name] = metadata_update
        backup_and_save_metadata(metadata, METADATA_PATH)
    if not success:
        logging.error(f"❌ Failed to convert {file_name}")
    return success

def process_all_tiffs(tiff_files: List[str], metadata: Dict[str, Dict], zoom: str, workers: int, keep_vrt: bool = False) -> List[str]:
    """
    Process all TIFFs in parallel, return a list of files that failed to convert.
    Only update metadata in the main thread after all conversions.
    Shows a global progress bar for all conversions.
    """
    failed = []
    already_converted = set(metadata.get('converted', {}).keys())
    jobs = [tiff_path for tiff_path in tiff_files if os.path.basename(tiff_path) not in already_converted]
    def tiff_task(tiff_path):
        success = convert_single_tiff(tiff_path, zoom, keep_vrt, metadata)
        if not success:
            failed.append(os.path.basename(tiff_path))
        return success
    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(tqdm(executor.map(tiff_task, jobs), total=len(jobs), desc="Converting TIFFs", unit="file"))
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

def backup_and_save_metadata(metadata: dict, path: Path) -> None:
    """
    Backup the existing metadata file and atomically save the new metadata.
    """
    if path.exists():
        shutil.copy(str(path), str(path) + '.bak')
    tmp_path = str(path) + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    os.replace(tmp_path, path)

def main() -> None:
    """
    Main conversion routine: finds TIFFs, handles palette, runs tiling, and logs results.
    """
    check_gdal_tools()  # Ensure required GDAL tools are available before proceeding
    # Load metadata if needed
    if METADATA_PATH.exists():
        with open(METADATA_PATH, 'r') as f:
            metadata = json.load(f)
    else:
        metadata = {}

    args = parse_args()
    # Add CLI for single-file conversion
    import sys
    if args.single_tiff:
        tiff_path = args.single_tiff
        zoom = args.zoom or "5-12"
        keep_vrt = args.keep_vrt
        # Load metadata if needed
        if METADATA_PATH.exists():
            with open(METADATA_PATH, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {}
        success = convert_single_tiff(tiff_path, zoom, keep_vrt, metadata)
        print(f"Single TIFF conversion {'succeeded' if success else 'failed'} for {tiff_path}")
        exit(0)
    # Only process TIFFs for the specified chart type if given
    if args.chart_type:
        tiff_files = []
        chart_dir = DOWNLOAD_DIR / args.chart_type
        if chart_dir.exists():
            for root, _, files in os.walk(str(chart_dir)):
                for f in files:
                    if f.lower().endswith('.tif') or f.lower().endswith('.tiff'):
                        tiff_files.append(os.path.join(root, f))
        logging.info(f"Found {len(tiff_files)} TIFF files to convert for chart type {args.chart_type}.")
    else:
        tiff_files = find_tiff_files(str(DOWNLOAD_DIR))
        logging.info(f"Found {len(tiff_files)} TIFF files to convert.")
    zoom = get_zoom_from_env_or_args(args)
    if not validate_zoom(zoom):
        logging.critical(f"Invalid zoom value: {zoom}. Must be a number or range like 5-12.")
        exit(1)
    workers = get_workers_from_env_or_args(args)
    logging.info(f"🚀 Using {workers} parallel workers.")
    # Process all TIFFs and update metadata
    failed = process_all_tiffs(tiff_files, metadata, zoom, workers, keep_vrt=args.keep_vrt)
    # Save metadata with backup and atomic write
    backup_and_save_metadata(metadata, METADATA_PATH)
    print_conversion_summary(tiff_files, metadata, failed)

if __name__ == "__main__":
    main()
