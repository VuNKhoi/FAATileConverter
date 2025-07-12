import requests
from bs4 import BeautifulSoup
import os
import zipfile
import json
from datetime import datetime, timezone
import time
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

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
    'ELAK', 'EHAA', 'ELHI', 'EHPH', 'ELPA', 'EHPA', 'AREA', 'EHAK', 'EPHI', 'EHPH'
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
        logging.info(f"✅ Already exists, skipping download: {os.path.basename(local_filename)}")
        return local_filename
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            logging.info(f"⬇️ Downloaded: {os.path.basename(local_filename)}")
            return local_filename
        except Exception as e:
            logging.warning(f"⚠️ Download failed (attempt {attempt}/{retries}) for {url}: {e}")
            if attempt < retries:
                time.sleep(delay)
            else:
                raise

def unzip_file(zip_path, extract_to):
    """Unzip a .zip file to the given directory. Removes the zip after extraction."""
    logging.info(f"📦 Unzipping: {os.path.basename(zip_path)} to {extract_to}")
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    try:
        os.remove(zip_path)
        logging.info(f"🧹 Removed zip: {os.path.basename(zip_path)}")
    except Exception as e:
        logging.warning(f"⚠️ Could not remove zip {zip_path}: {e}")

def process_vfr_charts(metadata):
    """Download and extract VFR Sectional & Terminal charts."""
    logging.info("🚩 Starting VFR Sectional & Terminal chart download...")
    vfr_links = fetch_vfr_sectional_and_terminal_links(VFR_CHARTS_URL)
    vfr_dir = os.path.join(DOWNLOAD_DIR, 'sectional')
    os.makedirs(vfr_dir, exist_ok=True)
    for url in vfr_links:
        fname = os.path.basename(url)
        if metadata.get('vfr', {}).get(fname):
            logging.info(f"✅ [VFR] Already processed: {fname}")
            continue
        try:
            zip_path = download_file(url, vfr_dir)
            extract_path = os.path.join(vfr_dir, fname.replace('.zip', ''))
            unzip_file(zip_path, extract_path)
            metadata.setdefault('vfr', {})[fname] = {
                'downloaded': True,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            save_metadata(metadata)
        except Exception as e:
            logging.error(f"❌ [VFR] Failed: {fname}: {e}")
    return metadata

def process_ifr_charts(metadata, chart_type, allowed_prefixes):
    """
    Download and extract IFR Low or High charts.
    chart_type: 'ifr_low' or 'ifr_high'
    allowed_prefixes: list of chart code prefixes
    """
    logging.info(f"🚩 Starting {chart_type.upper()} chart download...")
    links = fetch_ifr_low_high_links(IFR_CHARTS_URL, allowed_prefixes)
    out_dir = os.path.join(DOWNLOAD_DIR, chart_type)
    os.makedirs(out_dir, exist_ok=True)
    for entry in links:
        fname = os.path.basename(entry['url'])
        key = f"{entry['chart_code']}_{entry['published_date']}"
        if metadata.get(chart_type, {}).get(key):
            logging.info(f"✅ [{chart_type.upper()}] Already processed: {key}")
            continue
        try:
            zip_path = download_file(entry['url'], out_dir)
            extract_path = os.path.join(out_dir, key)
            unzip_file(zip_path, extract_path)
            metadata.setdefault(chart_type, {})[key] = {
                'downloaded': True,
                'published_date': entry['published_date'],
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            save_metadata(metadata)
        except Exception as e:
            logging.error(f"❌ [{chart_type.upper()}] Failed: {key}: {e}")
    return metadata

def print_summary(metadata):
    """Print a summary of processed charts."""
    vfr_count = len(metadata.get('vfr', {}))
    ifr_low_count = len(metadata.get('ifr_low', {}))
    ifr_high_count = len(metadata.get('ifr_high', {}))
    logging.info("\n🎉✅ Download and extraction complete.")
    logging.info(f"  VFR charts processed: {vfr_count}")
    logging.info(f"  IFR Low charts processed: {ifr_low_count}")
    logging.info(f"  IFR High charts processed: {ifr_high_count}")

def main():
    """
    Orchestrate the download and extraction workflow for all chart types.
    """
    metadata = load_metadata()
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    # Process VFR charts
    metadata = process_vfr_charts(metadata)
    # Process IFR Low charts
    metadata = process_ifr_charts(metadata, 'ifr_low', IFR_LOW_PREFIXES)
    # Process IFR High charts
    metadata = process_ifr_charts(metadata, 'ifr_high', IFR_HIGH_PREFIXES)
    # Print summary
    print_summary(metadata)

if __name__ == "__main__":
    main()
