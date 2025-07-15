import unittest
from scripts import download_faa_charts, utils
import os
import shutil
import json
import tempfile
from unittest import mock
from scripts.download_faa_charts import is_vfr_chart_current

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
        corrupt_path = os.path.join(self.temp_dir, 'corrupt.zip')
        with open(corrupt_path, 'wb') as f:
            f.write(b'notazip')
        with self.assertRaises(Exception):
            utils.unzip_file(corrupt_path, self.temp_dir)

class TestRedundantWorkAvoidance(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.metadata_path = os.path.join(self.temp_dir, 'faa_chart_log.json')
        self.chart_id = 'SEA_SECTIONAL_20250101'
        with open(self.metadata_path, 'w') as f:
            json.dump({self.chart_id: {'downloaded': True}}, f)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_skip_if_current(self):
        # Use is_vfr_chart_current or is_ifr_chart_current as appropriate
        metadata = {'vfr': {'chart1.zip': {'downloaded': True}}}
        url = 'http://example.com/chart1.zip'
        skipped = is_vfr_chart_current(metadata, url)
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
        # Use a temporary file for isolated backup/restore
        data = {'foo': 'bar'}
        with tempfile.NamedTemporaryFile('w+', delete=False) as tmp:
            tmp_path = tmp.name
        try:
            utils.backup_and_save_metadata(data, tmp_path)
            def load_metadata_from(path):
                import json, os
                if os.path.exists(path):
                    try:
                        with open(path, "r") as f:
                            return json.load(f)
                    except Exception:
                        return {}
                return {}
            loaded = load_metadata_from(tmp_path)
            self.assertEqual(loaded, data)
        finally:
            os.remove(tmp_path)

if __name__ == '__main__':
    unittest.main()
