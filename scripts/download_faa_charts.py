import requests
from bs4 import BeautifulSoup
import os
import zipfile
import json
from datetime import datetime, timezone

# TODO: Investigate and possibly support additional chart types/tabs in the future (e.g., Helicopter, Grand Canyon, Caribbean, Planning, 56-Day Sets)
# Currently only VFR Sectional, Terminal Area, and IFR Low/High charts are supported. Other types are skipped.

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
# Prefixes to skip (Alaska, Area, Hawaii, Pacific, etc)
IFR_SKIP_PREFIXES = (
    'ELAK', 'EHAA', 'ELHI', 'EHPH', 'ELPA', 'EHPA', 'AREA', 'EHAK', 'EPHI', 'EHPH'
)

def load_metadata():
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "r") as f:
            return json.load(f)
    return {}

def save_metadata(data):
    with open(METADATA_PATH, "w") as f:
        json.dump(data, f, indent=2)

def make_absolute_url(base_url, href):
    if href.startswith('http'):
        return href
    if href.startswith('/'):
        return 'https://www.faa.gov' + href
    return base_url.rstrip('/') + '/' + href

def fetch_chart_links(base_url, allowed_prefixes):
    resp = requests.get(base_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    links = []
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        # Only consider .zip files
        if href.endswith('.zip'):
            filename = href.split('/')[-1]
            # Only allow ELUS (Low) and EHUS (High) charts
            if any(filename.startswith(prefix) for prefix in allowed_prefixes):
                if not href.startswith('http'):
                    href = base_url + href
                links.append(href)
    return links

def fetch_vfr_sectional_and_terminal_links(base_url):
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
    """
    Fetch IFR chart links from the first tab (Enroute Lows, Highs, Areas),
    including only allowed prefixes and skipping unwanted regions.
    """
    resp = requests.get(base_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    links = []
    # Always select the first .ui-tabs-panel (first tab content)
    tab = soup.find('div', class_='ui-tabs-panel')
    if not tab:
        return links
    for a_tag in tab.find_all('a', href=True):
        href = a_tag['href']
        if href.endswith('.zip'):
            filename = href.split('/')[-1]
            # Skip unwanted regions
            if filename.startswith(IFR_SKIP_PREFIXES):
                continue
            # Only include allowed prefixes
            if any(filename.startswith(prefix) for prefix in allowed_prefixes):
                links.append(make_absolute_url(base_url, href))
    return links

def download_file(url, dest_folder):
    os.makedirs(dest_folder, exist_ok=True)
    local_filename = os.path.join(dest_folder, url.split('/')[-1])
    print(f"Downloading {local_filename}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return local_filename

def unzip_file(zip_path, extract_to):
    print(f"Unzipping {zip_path} to {extract_to}")
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def process_chart_group(chart_type, url, allowed_prefixes, metadata):
    chart_dir = os.path.join(DOWNLOAD_DIR, chart_type)
    if chart_type == 'sectional':
        links = fetch_vfr_sectional_and_terminal_links(url)
    elif chart_type in ('ifr_low', 'ifr_high'):
        links = fetch_ifr_low_high_links(url, allowed_prefixes)
    else:
        links = fetch_chart_links(url, allowed_prefixes)
    print(f"Found {len(links)} links for {chart_type}.")
    for link in links:
        key = f"{chart_type}:{link}"
        if key in metadata and metadata[key].get("converted"):
            print(f"Skipping {key} — already processed.")
            continue
        print(f"Processing {key}...")
        zip_path = download_file(link, chart_dir)
        print(f"Downloaded: {zip_path}")
        unzip_file(zip_path, chart_dir)
        metadata[key] = {
            "chart_type": chart_type,
            "url": link,
            "zip_file": os.path.basename(zip_path),
            "unzip_dir": chart_dir,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "converted": True
        }
    print("\n\n")  # Two empty lines after each category

if __name__ == "__main__":
    metadata = load_metadata()

    # VFR Sectional and Terminal Area charts (only those tabs)
    process_chart_group(
        "sectional",
        VFR_CHARTS_URL,
        [""],  # allowed_prefixes not used for sectional now
        metadata
    )
    # IFR Low (ELUS) and IFR High (EHUS) only
    process_chart_group("ifr_low", IFR_CHARTS_URL, IFR_LOW_PREFIXES, metadata)
    process_chart_group("ifr_high", IFR_CHARTS_URL, IFR_HIGH_PREFIXES, metadata)

    save_metadata(metadata)
