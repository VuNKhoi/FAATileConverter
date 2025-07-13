import sys
from download_faa_charts import (
    get_first_vfr_url, get_first_ifr_entry, download_and_extract_single_vfr, download_and_extract_single_ifr, load_metadata,
    fetch_vfr_sectional_and_terminal_links, fetch_ifr_low_high_links, IFR_LOW_PREFIXES, IFR_HIGH_PREFIXES
)

if __name__ == "__main__":
    # 🗺️ Minimal E2E FAA chart download/extract for CI
    if len(sys.argv) < 3:
        print("Usage: python faachart_minimal_e2e.py <chart_type> <chart_code>")
        sys.exit(1)
    chart_type = sys.argv[1]
    chart_code = sys.argv[2]
    metadata = load_metadata()
    if chart_type == 'sectional':
        links = fetch_vfr_sectional_and_terminal_links(
            "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/vfr/"
        )
        # Find the link that matches the chart_code (e.g., SEA)
        url = next((u for u in links if chart_code.lower() in u.lower()), None)
        if not url:
            print(f"No VFR url found for code {chart_code}")
            sys.exit(1)
        print(f"⬇️ Downloading: {url}")
        success, err = download_and_extract_single_vfr(url, metadata)
        if not success:
            print(f"❌ Failed to download/extract VFR: {err}")
            sys.exit(1)
    elif chart_type in ['ifr_low', 'ifr_high']:
        prefixes = IFR_LOW_PREFIXES if chart_type == 'ifr_low' else IFR_HIGH_PREFIXES
        entries = fetch_ifr_low_high_links(
            "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/ifr/",
            prefixes
        )
        entry = next((e for e in entries if e['chart_code'].upper() == chart_code.upper()), None)
        if not entry:
            print(f"No IFR entry found for {chart_type} with code {chart_code}")
            sys.exit(1)
        print(f"⬇️ Downloading: {entry['url']}")
        success, err = download_and_extract_single_ifr(entry, chart_type, metadata)
        if not success:
            print(f"❌ Failed to download/extract IFR: {err}")
            sys.exit(1)
    else:
        print(f"Unknown chart type: {chart_type}")
        sys.exit(1)
    print("🎉 Download and extraction complete.")
