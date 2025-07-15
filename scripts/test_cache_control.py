import os
import subprocess
import sys

def get_sample_tile_path(tile_dir):
    """Return the path to a sample PNG tile in the given directory."""
    for root, dirs, files in os.walk(tile_dir):
        for f in files:
            if f.endswith('.png'):
                return os.path.join(root, f)
    return None

def check_s3_cache_control(bucket, s3_prefix, local_tile_path):
    """Check the Cache-Control header of a sample tile uploaded to S3."""
    import boto3
    s3 = boto3.client('s3')
    key = os.path.join(s3_prefix, os.path.basename(local_tile_path))
    key = key.replace('\\', '/').replace('//', '/')
    resp = s3.head_object(Bucket=bucket, Key=key)
    cache_control = resp.get('CacheControl')
    print(f"S3 object: s3://{bucket}/{key}")
    print(f"Cache-Control: {cache_control}")
    assert cache_control == "public, max-age=31536000, immutable", f"Cache-Control header is incorrect: {cache_control}"
    print("✅ Cache-Control header is correct.")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python test_cache_control.py <bucket> <s3_prefix> <local_tile_dir>")
        sys.exit(1)
    bucket = sys.argv[1]
    s3_prefix = sys.argv[2]
    tile_dir = sys.argv[3]
    tile_path = get_sample_tile_path(tile_dir)
    if not tile_path:
        print(f"No PNG tile found in {tile_dir}")
        sys.exit(1)
    check_s3_cache_control(bucket, s3_prefix, tile_path)
