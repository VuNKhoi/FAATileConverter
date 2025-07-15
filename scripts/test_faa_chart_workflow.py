import unittest
from unittest import mock
import os
import shutil
import json
import tempfile
from scripts import download_faa_charts, utils

class TestErrorHandling(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    @mock.patch('scripts.download_faa_charts.download_file')
    def test_network_failure(self, mock_download):
        mock_download.side_effect = Exception('Network error')
        with self.assertRaises(Exception) as cm:
            download_faa_charts.download_file('http://example.com/file.zip', os.path.join(self.temp_dir, 'file.zip'))
        self.assertIn('Network error', str(cm.exception))

    def test_corrupt_zip_file(self):
        # Create a fake corrupt zip file
        corrupt_path = os.path.join(self.temp_dir, 'corrupt.zip')
        with open(corrupt_path, 'wb') as f:
            f.write(b'notazip')
        with self.assertRaises(Exception):
            utils.unzip_file(corrupt_path, self.temp_dir)

class TestRedundantWorkAvoidance(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.metadata_path = os.path.join(self.temp_dir, 'faa_chart_log.json')
        # Simulate a chart already downloaded
        self.chart_id = 'SEA_SECTIONAL_20250101'
        with open(self.metadata_path, 'w') as f:
            json.dump({self.chart_id: {'downloaded': True}}, f)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    @mock.patch('scripts.download_faa_charts.get_metadata_path')
    def test_skip_if_current(self, mock_get_metadata):
        mock_get_metadata.return_value = self.metadata_path
        # Should skip download since chart is current
        skipped = download_faa_charts.is_chart_current(self.chart_id, self.metadata_path)
        self.assertTrue(skipped)

class TestMetadataBackupRestore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.metadata_path = os.path.join(self.temp_dir, 'faa_chart_log.json')
        self.backup_path = os.path.join(self.temp_dir, 'faa_chart_log_backup.json')
        self.data = {'chart1': {'downloaded': True}}
        with open(self.metadata_path, 'w') as f:
            json.dump(self.data, f)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_backup_and_restore(self):
        # Backup
        utils.backup_metadata(self.metadata_path, self.backup_path)
        self.assertTrue(os.path.exists(self.backup_path))
        # Corrupt original
        with open(self.metadata_path, 'w') as f:
            f.write('corrupt')
        # Restore
        utils.restore_metadata(self.backup_path, self.metadata_path)
        with open(self.metadata_path) as f:
            restored = json.load(f)
        self.assertEqual(restored, self.data)

if __name__ == '__main__':
    unittest.main()
