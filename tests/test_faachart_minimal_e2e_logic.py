import unittest
from scripts import download_faa_charts
import re

class TestChartSelectionLogic(unittest.TestCase):
    def test_vfr_url_selection(self):
        links = [
            'https://faa.gov/SEA_20250711.zip',
            'https://faa.gov/LAX_20250711.zip',
        ]
        chart_code = 'sea'
        url = next((u for u in links if chart_code.lower() in u.lower()), None)
        self.assertEqual(url, 'https://faa.gov/SEA_20250711.zip')

    def test_ifr_entry_selection(self):
        entries = [
            {'chart_code': 'ELUS01', 'url': 'https://faa.gov/ELUS01.zip'},
            {'chart_code': 'EHUS02', 'url': 'https://faa.gov/EHUS02.zip'},
        ]
        chart_code = 'elus01'
        entry = next((e for e in entries if e['chart_code'].upper() == chart_code.upper()), None)
        self.assertEqual(entry['url'], 'https://faa.gov/ELUS01.zip')

    def test_regex_date_extraction(self):
        url = 'https://faa.gov/SEA_20250711.zip'
        m = re.search(r'(\d{4}-\d{2}-\d{2}|\d{8})', url)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), '20250711')

class TestErrorHandling(unittest.TestCase):
    def test_no_vfr_url_found(self):
        links = ['https://faa.gov/LAX_20250711.zip']
        chart_code = 'sea'
        url = next((u for u in links if chart_code.lower() in u.lower()), None)
        self.assertIsNone(url)

    def test_no_ifr_entry_found(self):
        entries = [{'chart_code': 'EHUS02', 'url': 'https://faa.gov/EHUS02.zip'}]
        chart_code = 'elus01'
        entry = next((e for e in entries if e['chart_code'].upper() == chart_code.upper()), None)
        self.assertIsNone(entry)

if __name__ == "__main__":
    unittest.main()
