import unittest
from scripts.download_faa_charts import is_vfr_chart_current, is_ifr_chart_current

class TestCurrentCheck(unittest.TestCase):
    def test_vfr_chart_current(self):
        metadata = {'vfr': {'chart1.zip': {'downloaded': True}}}
        url = 'http://example.com/chart1.zip'
        self.assertTrue(is_vfr_chart_current(metadata, url))

    def test_ifr_chart_current(self):
        metadata = {'ifr_low': {'ELUS01_2025-07-15': {'downloaded': True}}}
        entry = {'chart_code': 'ELUS01', 'published_date': '2025-07-15'}
        self.assertTrue(is_ifr_chart_current(metadata, entry, 'ifr_low'))

if __name__ == "__main__":
    unittest.main()
