"""
Helper script to download ledger file from GCS for MESA MIPs verification

This script downloads the ledger file for a specific ledger hash from the public
Mina staking ledgers GCS bucket, similar to how the OCV server does it.

Usage:
    python3 download_ledger.py --ledger-hash "jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve" --output ledger.json
"""

import argparse
import json
import sys
from urllib import request, parse


def list_bucket_objects(bucket_name, prefix=None):
    """List objects in a GCS bucket using the JSON API (anonymous access) with pagination"""
    all_objects = []
    page_token = None
    page_count = 0

    print(f"Listing objects in bucket '{bucket_name}'...")

    while True:
        url = f"https://storage.googleapis.com/storage/v1/b/{bucket_name}/o?maxResults=1000"

        if prefix:
            url += f"&prefix={parse.quote(prefix)}"

        if page_token:
            url += f"&pageToken={parse.quote(page_token)}"

        try:
            with request.urlopen(url) as response:
                data = json.loads(response.read())
                items = data.get('items', [])

                if items:
                    all_objects.extend([item['name'] for item in items])
                    page_count += 1
                    print(f"  Fetched page {page_count}: {len(items)} objects (total so far: {len(all_objects)})")

                # Check for next page
                page_token = data.get('nextPageToken')
                if not page_token:
                    break

        except Exception as e:
            print(f"Error listing bucket objects: {e}")
            return all_objects if all_objects else []

    print(f"  Total objects fetched: {len(all_objects)} across {page_count} page(s)")
    return all_objects


def download_object(bucket_name, object_key, output_path):
    """Download an object from GCS using the JSON API (anonymous access)"""
    url = f"https://storage.googleapis.com/storage/v1/b/{bucket_name}/o/{parse.quote(object_key, safe='')}?alt=media"

    print(f"Downloading '{object_key}' from bucket '{bucket_name}'...")

    try:
        with request.urlopen(url) as response:
            data = response.read()

            # Parse JSON to validate it
            json_data = json.loads(data)

            # Write to file
            with open(output_path, 'w') as f:
                json.dump(json_data, f, indent=2)

            print(f"Successfully downloaded to '{output_path}'")
            print(f"Ledger contains {len(json_data)} accounts")
            return True
    except Exception as e:
        print(f"Error downloading object: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Download ledger file from GCS for MESA MIPs verification')
    parser.add_argument('--ledger-hash', required=True, help='Ledger hash to download')
    parser.add_argument('--output', default='ledger.json', help='Output file path (default: ledger.json)')
    parser.add_argument('--bucket', default='mina-staking-ledgers', help='GCS bucket name (default: mina-staking-ledgers)')

    args = parser.parse_args()

    print(f"=== Downloading Ledger for Hash: {args.ledger_hash} ===\n")

    # List objects to find the one matching the hash
    objects = list_bucket_objects(args.bucket)

    if not objects:
        print("ERROR: Could not list bucket objects")
        sys.exit(1)

    print(f"Found {len(objects)} total objects in bucket")

    # Find matching objects (hash appears anywhere in the filename, not at the start)
    matching_objects = [obj for obj in objects if args.ledger_hash in obj]

    if not matching_objects:
        print(f"\nERROR: No objects found containing hash '{args.ledger_hash}'")
        print(f"Note: The hash can appear anywhere in the filename (e.g., 'mainnet-105-{args.ledger_hash}.json')")
        print(f"\nSearching for partial matches (first 15 characters)...")
        partial_hash = args.ledger_hash[:15] if len(args.ledger_hash) >= 15 else args.ledger_hash
        partial_matches = [obj for obj in objects if partial_hash in obj]

        if partial_matches:
            print(f"Found {len(partial_matches)} partial matches:")
            for obj in partial_matches[:10]:
                print(f"  - {obj}")
        else:
            print("No partial matches found")
            print("\nSample available objects (first 20):")
            for obj in objects[:20]:
                print(f"  - {obj}")

        sys.exit(1)

    print(f"\nFound {len(matching_objects)} matching object(s):")
    for obj in matching_objects:
        print(f"  - {obj}")

    # Separate staking and next-staking files
    staking_files = [obj for obj in matching_objects if 'staking-' in obj and 'next-staking' not in obj]
    next_staking_files = [obj for obj in matching_objects if 'next-staking' in obj]

    print(f"\nStaking files: {len(staking_files)}")
    print(f"Next-staking files: {len(next_staking_files)}")

    # Download both types if they exist
    all_accounts = []
    downloaded_files = []

    if next_staking_files:
        print(f"\nDownloading next-staking ledger...")
        next_staking_key = next_staking_files[0]
        temp_output = args.output.replace('.json', '_next_staking.json')
        if download_object(args.bucket, next_staking_key, temp_output):
            with open(temp_output, 'r') as f:
                accounts = json.load(f)
                all_accounts.extend(accounts)
                downloaded_files.append(temp_output)
                print(f"  Loaded {len(accounts)} accounts from next-staking ledger")

    if staking_files:
        print(f"\nDownloading staking ledger...")
        staking_key = staking_files[0]
        temp_output = args.output.replace('.json', '_staking.json')
        if download_object(args.bucket, staking_key, temp_output):
            with open(temp_output, 'r') as f:
                accounts = json.load(f)
                all_accounts.extend(accounts)
                downloaded_files.append(temp_output)
                print(f"  Loaded {len(accounts)} accounts from staking ledger")

    if not all_accounts:
        print("\n✗ Failed to download any ledger files")
        sys.exit(1)

    # Merge accounts, removing duplicates (keep last occurrence)
    merged_accounts = {}
    for account in all_accounts:
        pk = account.get('pk')
        if pk:
            merged_accounts[pk] = account

    # Write merged ledger
    merged_list = list(merged_accounts.values())
    with open(args.output, 'w') as f:
        json.dump(merged_list, f, indent=2)

    print(f"\n✓ Merged ledger file saved to '{args.output}'")
    print(f"  Total unique accounts: {len(merged_list)}")
    print(f"  Downloaded files: {', '.join(downloaded_files)}")
    print(f"\nYou can now use it with verify_mip_db.py:")
    print(f"  python3 verify_mip_db.py --ledger-file '{args.output}' ...")


if __name__ == '__main__':
    main()