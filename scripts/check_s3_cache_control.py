import os
import sys

def get_sample_tile_path(tile_dir):
    """Return the path to a sample PNG tile in the given directory."""
    for root, dirs, files in os.walk(tile_dir):
        for f in files:
            if f.endswith('.png'):
                return os.path.join(root, f)
    return None

def check_s3_cache_control(bucket, s3_prefix, local_tile_path, tile_dir):
    """Check the Cache-Control header of a sample tile uploaded to S3."""
    import boto3
    import botocore
    s3 = boto3.client('s3')
    # Sanitize prefix to remove stray quotes
    s3_prefix = s3_prefix.strip('"\'')
    rel_path = os.path.relpath(local_tile_path, tile_dir)
    key = os.path.join(s3_prefix, rel_path)
    key = key.replace('\\', '/').replace('//', '/')
    try:
        resp = s3.head_object(Bucket=bucket, Key=key)
        cache_control = resp.get('CacheControl')
        print(f"S3 object: s3://{bucket}/{key}")
        print(f"Cache-Control: {cache_control}")
        if cache_control == "public, max-age=31536000, immutable":
            print("✅ Cache-Control header is correct.")
            return 0
        else:
            print(f"Cache-Control header is incorrect: {cache_control}")
            return 3
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            print(f"File {key} not found in S3. Skipping cache-control check.")
            return 4
        else:
            raise

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python check_s3_cache_control.py <bucket> <s3_prefix> <local_tile_dir>")
        sys.exit(1)
    bucket = sys.argv[1]
    s3_prefix = sys.argv[2]
    tile_dir = sys.argv[3]
    tile_path = get_sample_tile_path(tile_dir)
    if not tile_path:
        print(f"No PNG tile found in {tile_dir}")
        sys.exit(1)
    sys.exit(check_s3_cache_control(bucket, s3_prefix, tile_path, tile_dir))
