import sys
import os
import io
# Clean up test results before running tests
test_results_dir = os.path.join(os.path.dirname(__file__), 'test_results')
for fname in os.listdir(test_results_dir):
    if fname.endswith('.txt') or fname.endswith('.html'):
        try:
            os.remove(os.path.join(test_results_dir, fname))
        except Exception:
            pass

from download_faa_charts import (
    VFR_CHARTS_URL, IFR_CHARTS_URL,
    IFR_LOW_PREFIXES, IFR_HIGH_PREFIXES,
    fetch_vfr_sectional_and_terminal_links, fetch_ifr_low_high_links
)

def test_vfr():
    output = io.StringIO()
    output.write("Testing VFR link extraction...\n")
    links = fetch_vfr_sectional_and_terminal_links(VFR_CHARTS_URL)
    for l in links:
        output.write(f"{l}\n")
    output.write(f"Found {len(links)} VFR links.\n")
    with open(os.path.join(test_results_dir, 'vfr_test_output.txt'), 'w') as f:
        f.write(output.getvalue())
    print(output.getvalue(), end='')

def test_ifr():
    output = io.StringIO()
    output.write("Testing IFR link extraction...\n")
    links = fetch_ifr_low_high_links(IFR_CHARTS_URL, IFR_LOW_PREFIXES + IFR_HIGH_PREFIXES)
    for d in links:
        output.write(f"{d}\n")
    output.write(f"Found {len(links)} IFR links.\n")
    with open(os.path.join(test_results_dir, 'ifr_test_output.txt'), 'w') as f:
        f.write(output.getvalue())
    print(output.getvalue(), end='')

def main():
    if '--vfr' in sys.argv:
        test_vfr()
    if '--ifr' in sys.argv:
        test_ifr()
    if len(sys.argv) == 1:
        print("Usage: python test_faa_chart_extraction.py [--vfr] [--ifr]")

if __name__ == "__main__":
    main()
