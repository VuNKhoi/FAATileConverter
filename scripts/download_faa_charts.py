import requests
from bs4 import BeautifulSoup
import os
import zipfile
import json
from datetime import datetime, timezone
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from typing import Dict, Any
import shutil
import argparse
from scripts.utils import download_and_extract_zip, backup_and_save_metadata

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Constants
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DOWNLOAD_DIR = os.path.join(REPO_ROOT, 'downloads')
METADATA_PATH = os.path.join(os.path.dirname(__file__), 'metadata', 'faa_chart_log.json')

# FAA Chart URL and Prefix Constants
VFR_CHARTS_URL = "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/"
IFR_CHARTS_URL = "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/ifr/"

# Prefixes for IFR charts to fetch
IFR_LOW_PREFIXES = ["ELUS"]  # Enroute Low Altitude, Conterminous US
IFR_HIGH_PREFIXES = ["EHUS"]  # Enroute High Altitude, Conterminous US
IFR_SKIP_PREFIXES = (
    'ELAK', 'EHAA', 'ELHI', 'EHPH', 'ELPA', 'EHPA', 'AREA', 'EHAK', 'EPHI'  # Removed duplicate 'EHPH'
)

def load_metadata():
    """Load chart processing metadata from JSON file. Handles missing or corrupt files gracefully."""
    if os.path.exists(METADATA_PATH):
        try:
            with open(METADATA_PATH, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load metadata (corrupt?): {e}. Returning empty metadata.")
            return {}
    return {}

def save_metadata(data):
    """Save chart processing metadata to JSON file."""
    os.makedirs(os.path.dirname(METADATA_PATH), exist_ok=True)
    with open(METADATA_PATH, "w") as f:
        json.dump(data, f, indent=2)

def make_absolute_url(base_url, href):
    """Convert a relative or absolute href to a full URL based on base_url."""
    if href.startswith('http'):
        return href
    if href.startswith('/'):
        return 'https://www.faa.gov' + href
    return base_url.rstrip('/') + '/' + href

def fetch_vfr_sectional_and_terminal_links(base_url):
    """Extract VFR Sectional and Terminal Area chart .zip links from the FAA VFR page."""
    try:
        resp = requests.get(base_url)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch VFR page: {base_url}: {e}")
        return []
    try:
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        logger.error(f"Failed to parse VFR page HTML: {e}")
        return []
    links = []
    for tab_id in ['sectional', 'terminalArea']:
        tab = soup.find('div', id=tab_id)
        if not tab:
            logger.warning(f"Tab {tab_id} not found in VFR page.")
            continue
        for a_tag in tab.find_all('a', href=True):
            href = a_tag['href']
            if href.endswith('.zip'):
                links.append(make_absolute_url(base_url, href))
    return links

def fetch_ifr_low_high_links(base_url, allowed_prefixes):
    """Extract IFR Low/High chart links from FAA IFR page tables, matching allowed prefixes."""
    import re
    try:
        resp = requests.get(base_url)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch IFR page: {base_url}: {e}")
        return []
    try:
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        logger.error(f"Failed to parse IFR page HTML: {e}")
        return []
    results = []
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) < 2:
                continue
            chart_code = cells[0].get_text(strip=True)
            if not any(chart_code.startswith(prefix) for prefix in allowed_prefixes):
                continue
            if chart_code.startswith(IFR_SKIP_PREFIXES):
                continue
            published_date = None
            date_match = re.search(r'([A-Z][a-z]{2} \d{1,2} \d{4})', cells[1].get_text())
            if date_match:
                try:
                    published_date = datetime.strptime(date_match.group(1), '%b %d %Y').strftime('%Y-%m-%d')
                except Exception as e:
                    logger.warning(f"Failed to parse published date for {chart_code}: {e}")
                    published_date = None
            for a_tag in cells[1].find_all('a', href=True):
                link_text = a_tag.get_text(strip=True).lower()
                href = a_tag['href']
                if 'geo-tiff' in link_text and href.endswith('.zip'):
                    results.append({
                        'chart_code': chart_code,
                        'published_date': published_date,
                        'url': make_absolute_url(base_url, href)
                    })
    return results

def download_file(url, dest_folder, retries=3, delay=5):
    """Download a file from url to dest_folder, returning the local file path. Skips if already exists. Retries on failure."""
    os.makedirs(dest_folder, exist_ok=True)
    local_filename = os.path.join(dest_folder, url.split('/')[-1])
    if os.path.exists(local_filename):
        logger.info(f"✅ Already exists, skipping download: {os.path.basename(local_filename)}")
        return local_filename
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            logger.info(f"⬇️ Downloaded: {os.path.basename(local_filename)}")
            return local_filename
        except Exception as e:
            logger.warning(f"⚠️ Download failed (attempt {attempt}/{retries}) for {url}: {e}")
            if attempt < retries:
                time.sleep(delay)
            else:
                raise

def unzip_file(zip_path, extract_to):
    """Unzip a .zip file to the given directory. Removes the zip after extraction."""
    logger.info(f"\U0001F4E6 Unzipping: {os.path.basename(zip_path)} to {extract_to}")
    os.makedirs(extract_to, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    except Exception as e:
        logger.error(f"Failed to unzip {zip_path}: {e}")
        return
    try:
        os.remove(zip_path)
        logger.info(f"\U0001F9F9 Removed zip: {os.path.basename(zip_path)}")
    except Exception as e:
        logger.warning(f"\u26A0\uFE0F Could not remove zip {zip_path}: {e}")

def is_vfr_chart_current(metadata, url):
    """Check if a VFR chart (by url) is already current in metadata."""
    fname = os.path.basename(url)
    return metadata.get('vfr', {}).get(fname) is not None

def is_ifr_chart_current(metadata, entry, chart_type):
    """Check if an IFR chart (by entry) is already current in metadata."""
    key = f"{entry['chart_code']}_{entry['published_date']}"
    return metadata.get(chart_type, {}).get(key) is not None

def process_vfr_charts(metadata: Dict[str, Any], check_current=False) -> Dict[str, Any]:
    """Download and extract VFR Sectional & Terminal charts with progress bar and parallel downloads. Skips if current if check_current is True."""
    logger.info("🚩 Starting VFR Sectional & Terminal chart download...")
    vfr_links = fetch_vfr_sectional_and_terminal_links(VFR_CHARTS_URL)
    vfr_dir = os.path.join(DOWNLOAD_DIR, 'sectional')
    os.makedirs(vfr_dir, exist_ok=True)
    to_download = []
    for url in vfr_links:
        if check_current and is_vfr_chart_current(metadata, url):
            logger.info(f"⏩ Skipping current VFR chart: {os.path.basename(url)}")
            continue
        to_download.append(url)
    max_workers = min(4, os.cpu_count() or 1)
    def vfr_task(url):
        success, err = download_and_extract_single_vfr(url, metadata)
        fname = os.path.basename(url)
        if not success:
            logger.error(f"❌ [VFR] Failed: {fname}: {err}")
        return success
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(tqdm(executor.map(vfr_task, to_download), total=len(to_download), desc="VFR Charts", unit="file"))
    backup_and_save_metadata(metadata, METADATA_PATH)
    return metadata

def process_ifr_charts(metadata: Dict[str, Any], chart_type: str, allowed_prefixes, check_current=False) -> Dict[str, Any]:
    """
    Download and extract IFR Low or High charts with progress bar and parallel downloads.
    Skips if current if check_current is True.
    """
    logger.info(f"🚩 Starting {chart_type.upper()} chart download...")
    links = fetch_ifr_low_high_links(IFR_CHARTS_URL, allowed_prefixes)
    out_dir = os.path.join(DOWNLOAD_DIR, chart_type)
    os.makedirs(out_dir, exist_ok=True)
    to_download = []
    for entry in links:
        if check_current and is_ifr_chart_current(metadata, entry, chart_type):
            logger.info(f"⏩ Skipping current {chart_type} chart: {entry['chart_code']}_{entry['published_date']}")
            continue
        to_download.append(entry)
    max_workers = min(4, os.cpu_count() or 1)
    def ifr_task(entry):
        success, err = download_and_extract_single_ifr(entry, chart_type, metadata)
        key = f"{entry['chart_code']}_{entry['published_date']}"
        if not success:
            logger.error(f"❌ [{chart_type.upper()}] Failed: {key}: {err}")
        return success
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(tqdm(executor.map(ifr_task, to_download), total=len(to_download), desc=f"{chart_type.upper()} Charts", unit="file"))
    backup_and_save_metadata(metadata, METADATA_PATH)
    return metadata

def print_summary(metadata):
    """Print a summary of processed charts."""
    vfr_count = len(metadata.get('vfr', {}))
    ifr_low_count = len(metadata.get('ifr_low', {}))
    ifr_high_count = len(metadata.get('ifr_high', {}))
    logger.info("\n🎉✅ Download and extraction complete.")
    logger.info(f"  VFR charts processed: {vfr_count}")
    logger.info(f"  IFR Low charts processed: {ifr_low_count}")
    logger.info(f"  IFR High charts processed: {ifr_high_count}")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download and extract FAA charts.")
    parser.add_argument('--chart-type', type=str, default=None, choices=['sectional', 'ifr_low', 'ifr_high'], help='Only process this chart type (for matrix jobs)')
    parser.add_argument('--check-current', action='store_true', help='Skip download if chart is already current')
    return parser.parse_args()

def main():
    """
    Orchestrate the download and extraction workflow for all chart types or a single chart type.
    """
    args = parse_args()
    metadata = load_metadata()
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    check_current = getattr(args, 'check_current', False)
    if args.chart_type:
        if args.chart_type == 'sectional':
            metadata = process_vfr_charts(metadata, check_current=check_current)
        elif args.chart_type == 'ifr_low':
            metadata = process_ifr_charts(metadata, 'ifr_low', IFR_LOW_PREFIXES, check_current=check_current)
        elif args.chart_type == 'ifr_high':
            metadata = process_ifr_charts(metadata, 'ifr_high', IFR_HIGH_PREFIXES, check_current=check_current)
    else:
        metadata = process_vfr_charts(metadata, check_current=check_current)
        metadata = process_ifr_charts(metadata, 'ifr_low', IFR_LOW_PREFIXES, check_current=check_current)
        metadata = process_ifr_charts(metadata, 'ifr_high', IFR_HIGH_PREFIXES, check_current=check_current)
    print_summary(metadata)

def download_and_extract_single_vfr(url, metadata=None):
    """Download and extract a single VFR chart zip file."""
    vfr_dir = os.path.join(DOWNLOAD_DIR, 'sectional')
    fname = os.path.basename(url)
    extract_path = os.path.join(vfr_dir, fname.replace('.zip', ''))
    success, err = download_and_extract_zip(url, vfr_dir, extract_path, download_file, unzip_file)
    if metadata is not None and success:
        metadata.setdefault('vfr', {})[fname] = {
            'downloaded': True,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        backup_and_save_metadata(metadata, METADATA_PATH)
    return success, err

def download_and_extract_single_ifr(entry, chart_type, metadata=None):
    """Download and extract a single IFR chart zip file (entry from fetch_ifr_low_high_links)."""
    out_dir = os.path.join(DOWNLOAD_DIR, chart_type)
    key = f"{entry['chart_code']}_{entry['published_date']}"
    fname = os.path.basename(entry['url'])
    extract_path = os.path.join(out_dir, key)
    success, err = download_and_extract_zip(entry['url'], out_dir, extract_path, download_file, unzip_file)
    if metadata is not None and success:
        metadata.setdefault(chart_type, {})[key] = {
            'downloaded': True,
            'published_date': entry['published_date'],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        backup_and_save_metadata(metadata, METADATA_PATH)
    return success, err

def get_first_vfr_url():
    """Get the first VFR chart .zip URL for testing."""
    links = fetch_vfr_sectional_and_terminal_links(VFR_CHARTS_URL)
    return links[0] if links else None

def get_first_ifr_entry(chart_type):
    """Get the first IFR chart entry for the given type ('ifr_low' or 'ifr_high')."""
    prefixes = IFR_LOW_PREFIXES if chart_type == 'ifr_low' else IFR_HIGH_PREFIXES
    entries = fetch_ifr_low_high_links(IFR_CHARTS_URL, prefixes)
    return entries[0] if entries else None

if __name__ == "__main__":
    main()
