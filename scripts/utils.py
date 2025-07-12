import os
import shutil
import zipfile
import logging
from typing import Tuple

def download_and_extract_zip(url: str, dest_folder: str, extract_to: str, download_file_func, unzip_file_func, retries: int = 3, delay: int = 5) -> Tuple[bool, str]:
    """
    Download a zip file and extract it. Returns (success, error_message_or_None).
    download_file_func and unzip_file_func are injected for testability.
    """
    try:
        zip_path = download_file_func(url, dest_folder, retries, delay)
        try:
            unzip_file_func(zip_path, extract_to)
        except Exception as e:
            logging.error(f"Unzip failed: {zip_path}: {e}")
            # Keep zip for retry
            return False, f"Unzip failed: {e}"
        return True, None
    except Exception as e:
        return False, str(e)


def backup_and_save_metadata(metadata: dict, path) -> None:
    """
    Backup the existing metadata file and atomically save the new metadata.
    """
    if os.path.exists(path):
        shutil.copy(str(path), str(path) + '.bak')
    tmp_path = str(path) + '.tmp'
    with open(tmp_path, 'w') as f:
        import json
        json.dump(metadata, f, indent=2)
    os.replace(tmp_path, path)
