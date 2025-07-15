import unittest
from download_faa_charts import is_vfr_chart_current, is_ifr_chart_current

class TestCurrentCheckLogic(unittest.TestCase):
    def test_vfr_chart_current(self):
        metadata = {'vfr': {'SEA_20250711.zip': {'downloaded': True}}}
        url = 'https://example.com/SEA_20250711.zip'
        self.assertTrue(is_vfr_chart_current(metadata, url))
        url2 = 'https://example.com/PDX_20250711.zip'
        self.assertFalse(is_vfr_chart_current(metadata, url2))

    def test_ifr_chart_current(self):
        metadata = {'ifr_low': {'ELUS1_2025-07-11': {'downloaded': True}}}
        entry = {'chart_code': 'ELUS1', 'published_date': '2025-07-11'}
        self.assertTrue(is_ifr_chart_current(metadata, entry, 'ifr_low'))
        entry2 = {'chart_code': 'ELUS2', 'published_date': '2025-07-11'}
        self.assertFalse(is_ifr_chart_current(metadata, entry2, 'ifr_low'))

if __name__ == "__main__":
    unittest.main()
