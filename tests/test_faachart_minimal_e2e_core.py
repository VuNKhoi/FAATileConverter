import unittest
from scripts.download_faa_charts import load_metadata, download_and_extract_single_vfr, download_and_extract_single_ifr
from unittest import mock
import tempfile
import os
import json

class TestMetadataLoading(unittest.TestCase):
    def test_load_metadata_valid(self):
        print("Test: load_metadata with valid file...")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'faa_chart_log.json')
            data = {'foo': 'bar'}
            with open(path, 'w') as f:
                json.dump(data, f)
            with mock.patch('scripts.download_faa_charts.METADATA_PATH', path):
                loaded = load_metadata()
                print(f"  loaded: {loaded}")
                self.assertEqual(loaded, data)

    def test_load_metadata_missing(self):
        print("Test: load_metadata with missing file...")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'faa_chart_log.json')
            if os.path.exists(path):
                os.remove(path)
            with mock.patch('scripts.download_faa_charts.METADATA_PATH', path):
                loaded = load_metadata()
                print(f"  loaded: {loaded}")
                self.assertEqual(loaded, {})

    def test_load_metadata_corrupt(self):
        print("Test: load_metadata with corrupt file...")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'faa_chart_log.json')
            with open(path, 'w') as f:
                f.write('notjson')
            with mock.patch('scripts.download_faa_charts.METADATA_PATH', path):
                loaded = load_metadata()
                print(f"  loaded: {loaded}")
                self.assertEqual(loaded, {})

class TestDownloadExtractFunctions(unittest.TestCase):
    @mock.patch('scripts.download_faa_charts.download_file')
    @mock.patch('scripts.download_faa_charts.unzip_file')
    def test_download_and_extract_single_vfr_success(self, mock_unzip, mock_download):
        print("Test: download_and_extract_single_vfr success...")
        mock_download.return_value = True
        mock_unzip.return_value = True
        url = 'https://faa.gov/SEA_20250711.zip'
        metadata = {}
        success, err = download_and_extract_single_vfr(url, metadata)
        print(f"  success: {success}, err: {err}")
        self.assertTrue(success)
        self.assertIsNone(err)

    @mock.patch('scripts.download_faa_charts.download_file')
    @mock.patch('scripts.download_faa_charts.unzip_file')
    def test_download_and_extract_single_vfr_failure(self, mock_unzip, mock_download):
        print("Test: download_and_extract_single_vfr failure...")
        mock_download.side_effect = Exception('fail')
        url = 'https://faa.gov/SEA_20250711.zip'
        metadata = {}
        success, err = download_and_extract_single_vfr(url, metadata)
        print(f"  success: {success}, err: {err}")
        self.assertFalse(success)
        self.assertIn('fail', err)

    @mock.patch('scripts.download_faa_charts.download_file')
    @mock.patch('scripts.download_faa_charts.unzip_file')
    def test_download_and_extract_single_ifr_success(self, mock_unzip, mock_download):
        print("Test: download_and_extract_single_ifr success...")
        mock_download.return_value = True
        mock_unzip.return_value = True
        entry = {'url': 'https://faa.gov/ELUS01_20250711.zip', 'chart_code': 'ELUS01', 'published_date': '2025-07-14'}
        metadata = {"ELUS01": {"published_date": "2025-07-14"}}  # Ensure published_date is present
        success, err = download_and_extract_single_ifr(entry, 'ifr_low', metadata)
        print(f"  success: {success}, err: {err}")
        self.assertTrue(success)
        self.assertIsNone(err)

    @mock.patch('scripts.download_faa_charts.download_file')
    @mock.patch('scripts.download_faa_charts.unzip_file')
    def test_download_and_extract_single_ifr_failure(self, mock_unzip, mock_download):
        print("Test: download_and_extract_single_ifr failure...")
        mock_download.side_effect = Exception('fail')
        entry = {'url': 'https://faa.gov/ELUS01_20250711.zip', 'chart_code': 'ELUS01', 'published_date': '2025-07-14'}
        metadata = {}
        success, err = download_and_extract_single_ifr(entry, 'ifr_low', metadata)
        print(f"  success: {success}, err: {err}")
        self.assertFalse(success)
        self.assertIn('fail', err)

if __name__ == "__main__":
    unittest.main()
