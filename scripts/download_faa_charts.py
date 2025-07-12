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
from .utils import download_and_extract_zip, backup_and_save_metadata

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
    """Load chart processing metadata from JSON file."""
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "r") as f:
            return json.load(f)
    return {}

def save_metadata(data):
    """Save chart processing metadata to JSON file."""
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
    resp = requests.get(base_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    links = []
    for tab_id in ['sectional', 'terminalArea']:
        tab = soup.find('div', id=tab_id)
        if not tab:
            continue
        for a_tag in tab.find_all('a', href=True):
            href = a_tag['href']
            if href.endswith('.zip'):
                links.append(make_absolute_url(base_url, href))
    return links

def fetch_ifr_low_high_links(base_url, allowed_prefixes):
    """Extract IFR Low/High chart links from FAA IFR page tables, matching allowed prefixes."""
    import re
    resp = requests.get(base_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
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
                except Exception:
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
    logger.info(f"📦 Unzipping: {os.path.basename(zip_path)} to {extract_to}")
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    try:
        os.remove(zip_path)
        logger.info(f"🧹 Removed zip: {os.path.basename(zip_path)}")
    except Exception as e:
        logger.warning(f"⚠️ Could not remove zip {zip_path}: {e}")

def process_vfr_charts(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Download and extract VFR Sectional & Terminal charts with progress bar and parallel downloads."""
    logger.info("🚩 Starting VFR Sectional & Terminal chart download...")
    vfr_links = fetch_vfr_sectional_and_terminal_links(VFR_CHARTS_URL)
    vfr_dir = os.path.join(DOWNLOAD_DIR, 'sectional')
    os.makedirs(vfr_dir, exist_ok=True)
    to_download = [(url, os.path.basename(url)) for url in vfr_links if not metadata.get('vfr', {}).get(os.path.basename(url))]
    max_workers = min(4, os.cpu_count() or 1)
    def vfr_task(url, fname):
        extract_path = os.path.join(vfr_dir, fname.replace('.zip', ''))
        success, err = download_and_extract_zip(url, vfr_dir, extract_path, download_file, unzip_file)
        return (fname, success, err)
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(vfr_task, url, fname): fname for url, fname in to_download}
        for f in tqdm(as_completed(futures), total=len(futures), desc="VFR Charts", unit="file"):
            fname, success, err = f.result()
            if success:
                metadata.setdefault('vfr', {})[fname] = {
                    'downloaded': True,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            else:
                logger.error(f"❌ [VFR] Failed: {fname}: {err}")
    backup_and_save_metadata(metadata, METADATA_PATH)
    return metadata


def process_ifr_charts(metadata: Dict[str, Any], chart_type: str, allowed_prefixes) -> Dict[str, Any]:
    """
    Download and extract IFR Low or High charts with progress bar and parallel downloads.
    chart_type: 'ifr_low' or 'ifr_high'
    allowed_prefixes: list of chart code prefixes
    """
    logger.info(f"🚩 Starting {chart_type.upper()} chart download...")
    links = fetch_ifr_low_high_links(IFR_CHARTS_URL, allowed_prefixes)
    out_dir = os.path.join(DOWNLOAD_DIR, chart_type)
    os.makedirs(out_dir, exist_ok=True)
    to_download = [(entry['url'], entry['chart_code'], entry['published_date']) for entry in links if not metadata.get(chart_type, {}).get(f"{entry['chart_code']}_{entry['published_date']}")]
    max_workers = min(4, os.cpu_count() or 1)
    def ifr_task(url, chart_code, published_date):
        fname = os.path.basename(url)
        key = f"{chart_code}_{published_date}"
        extract_path = os.path.join(out_dir, key)
        success, err = download_and_extract_zip(url, out_dir, extract_path, download_file, unzip_file)
        return (key, success, err, published_date)
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ifr_task, url, chart_code, published_date): (chart_code, published_date) for url, chart_code, published_date in to_download}
        for f in tqdm(as_completed(futures), total=len(futures), desc=f"{chart_type.upper()} Charts", unit="file"):
            key, success, err, published_date = f.result()
            if success:
                metadata.setdefault(chart_type, {})[key] = {
                    'downloaded': True,
                    'published_date': published_date,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            else:
                logger.error(f"❌ [{chart_type.upper()}] Failed: {key}: {err}")
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
    return parser.parse_args()

def main():
    """
    Orchestrate the download and extraction workflow for all chart types or a single chart type.
    """
    args = parse_args()
    metadata = load_metadata()
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    if args.chart_type:
        if args.chart_type == 'sectional':
            metadata = process_vfr_charts(metadata)
        elif args.chart_type == 'ifr_low':
            metadata = process_ifr_charts(metadata, 'ifr_low', IFR_LOW_PREFIXES)
        elif args.chart_type == 'ifr_high':
            metadata = process_ifr_charts(metadata, 'ifr_high', IFR_HIGH_PREFIXES)
    else:
        # Process all chart types
        metadata = process_vfr_charts(metadata)
        metadata = process_ifr_charts(metadata, 'ifr_low', IFR_LOW_PREFIXES)
        metadata = process_ifr_charts(metadata, 'ifr_high', IFR_HIGH_PREFIXES)
    print_summary(metadata)

if __name__ == "__main__":
    main()
