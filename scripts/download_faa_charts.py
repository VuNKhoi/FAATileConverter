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
    Fetch IFR chart links from tables on the FAA IFR page, including only allowed prefixes and skipping unwanted regions.
    Returns a list of dicts: [{chart_code, published_date, url}]
    """
    import re
    resp = requests.get(base_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    results = []
    # Find all tables with IFR charts
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
            # Extract published date from the second cell
            published_date = None
            date_match = re.search(r'([A-Z][a-z]{2} \d{1,2} \d{4})', cells[1].get_text())
            if date_match:
                try:
                    published_date = datetime.strptime(date_match.group(1), '%b %d %Y').strftime('%Y-%m-%d')
                except Exception:
                    published_date = None
            # Find GEO-TIFF .zip link in the second cell
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

def download_file(url, dest_folder):
    os.makedirs(dest_folder, exist_ok=True)
    local_filename = os.path.join(dest_folder, url.split('/')[-1])
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print(f"Downloaded: {os.path.basename(local_filename)}")
    return local_filename

def unzip_file(zip_path, extract_to):
    print(f"Unzipped: {os.path.basename(zip_path)}")
    os.makedirs(extract_to, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def process_chart_group(chart_type, url, allowed_prefixes, metadata):
    chart_dir = os.path.join(DOWNLOAD_DIR, chart_type)
    if chart_type == 'sectional':
        links = fetch_vfr_sectional_and_terminal_links(url)
        link_tuples = [(None, None, l) for l in links]
    elif chart_type in ('ifr_low', 'ifr_high'):
        link_dicts = fetch_ifr_low_high_links(url, allowed_prefixes)
        link_tuples = [(d['chart_code'], d['published_date'], d['url']) for d in link_dicts]
    else:
        links = fetch_chart_links(url, allowed_prefixes)
        link_tuples = [(None, None, l) for l in links]
    print(f"Found {len(link_tuples)} links for {chart_type}.")
    # Pre-check: filter out already-processed charts before any download/convert
    filtered_tuples = []
    for chart_code, published_date, link in link_tuples:
        key = f"{chart_type}:{chart_code or ''}:{published_date or ''}:{link}"
        if key in metadata and metadata[key].get("converted"):
            print(f"Skipping {os.path.basename(link)} — already processed.")
            continue
        filtered_tuples.append((chart_code, published_date, link))
    print(f"To process for {chart_type}: {len(filtered_tuples)} charts.")
    for chart_code, published_date, link in filtered_tuples:
        print(f"Processing {os.path.basename(link)}...")
        zip_path = download_file(link, chart_dir)
        unzip_file(zip_path, chart_dir)
        metadata[f"{chart_type}:{chart_code or ''}:{published_date or ''}:{link}"] = {
            "chart_type": chart_type,
            "chart_code": chart_code,
            "published_date": published_date,
            "url": link,
            "zip_file": os.path.basename(zip_path),
            "unzip_dir": chart_dir,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "converted": True
        }
    print("\n\n")  # Two empty lines after each category
