import unittest
from scripts.download_faa_charts import (
    VFR_CHARTS_URL, IFR_CHARTS_URL,
    IFR_LOW_PREFIXES, IFR_HIGH_PREFIXES,
    fetch_vfr_sectional_and_terminal_links, fetch_ifr_low_high_links
)

class TestFAAChartExtraction(unittest.TestCase):
    def test_vfr_link_extraction(self):
        links = fetch_vfr_sectional_and_terminal_links(VFR_CHARTS_URL)
        self.assertIsInstance(links, list)
        self.assertTrue(all(isinstance(l, str) for l in links))
        # Optionally: check for expected minimum number of links
        self.assertGreater(len(links), 0)

    def test_ifr_link_extraction(self):
        links = fetch_ifr_low_high_links(IFR_CHARTS_URL, IFR_LOW_PREFIXES + IFR_HIGH_PREFIXES)
        self.assertIsInstance(links, list)
        self.assertTrue(all(isinstance(l, dict) for l in links))
        self.assertGreater(len(links), 0)

if __name__ == "__main__":
    unittest.main()
