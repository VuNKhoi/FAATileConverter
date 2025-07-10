import requests
from bs4 import BeautifulSoup
import os
import zipfile
import json
from datetime import datetime

# Constants
BASE_DIR = os.path.dirname(__file__)
DOWNLOAD_DIR = os.path.join(BASE_DIR, "..", "..", "charts")
METADATA_PATH = os.path.join(BASE_DIR, "metadata", "faa_chart_log.json")

def load_metadata():
    if os.path.exists(METADATA_PATH):
        with open(METADATA_PATH, "r") as f:
            return json.load(f)
    return {}

def save_metadata(data):
    with open(METADATA_PATH, "w") as f:
        json.dump(data, f, indent=2)

def fetch_chart_links(base_url, file_pattern):
    resp = requests.get(base_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    links = []
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if file_pattern in href and href.endswith('.zip'):
            if not href.startswith('http'):
                href = base_url + href
            links.append(href)
    return links

def download_file(url, dest_folder):
    os.makedirs(dest_folder, exist_ok=True)
    local_filename = os.path.join(dest_folder, url.split('/')[-1])
    print(f"Downloading {url} to {local_filename}")
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

def process_chart_group(chart_type, url, pattern, metadata):
    chart_dir = os.path.join(DOWNLOAD_DIR, chart_type)
    links = fetch_chart_links(url, pattern)
    for link in links:
        key = f"{chart_type}:{link}"
        if key in metadata and metadata[key].get("converted"):
            print(f"Skipping {key} — already processed.")
            continue

        print(f"Processing {key}...")
        zip_path = download_file(link, chart_dir)
        unzip_file(zip_path, chart_dir)

        metadata[key] = {
            "chart_type": chart_type,
            "url": link,
            "zip_file": os.path.basename(zip_path),
            "unzip_dir": chart_dir,
            "downloaded_at": datetime.utcnow().isoformat() + "Z",
            "converted": True  # You can later break this up into stages
        }

if __name__ == "__main__":
    metadata = load_metadata()

    process_chart_group("sectional", "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/", "GeoTIFF", metadata)
    process_chart_group("ifr_low", "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/ifr/", "ELUS", metadata)
    process_chart_group("ifr_high", "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/ifr/", "DDECUS", metadata)

    save_metadata(metadata)
