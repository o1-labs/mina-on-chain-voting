"""
MIP Vote Verification Script (Database Version)
Verifies votes by querying the archive database directly

Usage:
    python3 verify_mip_db.py \
        --db-url "postgresql://user:password@host:port/database" \
        --mip-key "MIP6" \
        --start-time 1733598000000 \
        --end-time 1734289199000 \
        --ledger-hash "jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve"

Or with individual connection parameters:
    python3 verify_mip_db.py \
        --db-host "localhost" \
        --db-port "5432" \
        --db-name "archive" \
        --db-user "postgres" \
        --db-password "password" \
        --mip-key "MIP6" \
        --start-time 1733598000000 \
        --end-time 1734289199000 \
        --ledger-hash "jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve"
"""

import argparse
import base58
import psycopg2
import json
from collections import defaultdict
from decimal import Decimal


def parse_args():
    parser = argparse.ArgumentParser(description='Verify MIP votes from archive database')

    # Database connection options
    db_group = parser.add_mutually_exclusive_group(required=True)
    db_group.add_argument('--db-url', help='PostgreSQL connection URL')
    db_group.add_argument('--db-params', action='store_true', help='Use individual DB parameters')

    parser.add_argument('--db-host', help='Database host')
    parser.add_argument('--db-port', default='5432', help='Database port')
    parser.add_argument('--db-name', help='Database name')
    parser.add_argument('--db-user', help='Database user')
    parser.add_argument('--db-password', help='Database password')

    # MIP parameters
    parser.add_argument('--mip-key', required=True, help='MIP key (e.g., MIP6, MIP7)')
    parser.add_argument('--start-time', required=True, type=int, help='Start timestamp in milliseconds')
    parser.add_argument('--end-time', required=True, type=int, help='End timestamp in milliseconds')
    parser.add_argument('--ledger-hash', required=True, help='Ledger hash for stake calculations')
    parser.add_argument('--ledger-file', help='Path to local ledger JSON file (optional, will download from GCS if not provided)')
    parser.add_argument('--export-voters', help='Export voter list to file for comparison')
    parser.add_argument('--debug-account', help='Debug a specific account to see why it was included/excluded')

    return parser.parse_args()


def get_connection(args):
    """Create database connection from arguments"""
    if args.db_url:
        return psycopg2.connect(args.db_url)
    else:
        return psycopg2.connect(
            host=args.db_host,
            port=args.db_port,
            database=args.db_name,
            user=args.db_user,
            password=args.db_password
        )


def fetch_votes(conn, mip_key, start_time, end_time, debug_account=None):
    """
    Fetch all voting transactions from the archive database.
    Similar to the query in server/src/archive.rs:37-57
    """
    # The archive database stores timestamps in MILLISECONDS (not seconds)
    # So we use the millisecond values directly

    # Encode the memo strings to base58 for comparison
    mip_memo = base58.b58encode(mip_key.encode()).decode()
    no_mip_memo = base58.b58encode(f"no {mip_key}".encode()).decode()

    print(f"Searching for memos: {mip_key} ({mip_memo}), no {mip_key} ({no_mip_memo})")
    print(f"Time range: {start_time} to {end_time} (milliseconds)")

    if debug_account:
        print(f"\n🔍 DEBUG MODE: Tracking account {debug_account}")

    # First, let's check what timestamps exist in the database
    check_query = """
        SELECT MIN(b.timestamp::bigint) as min_ts, MAX(b.timestamp::bigint) as max_ts, COUNT(*) as total
        FROM blocks b
        WHERE NOT b.chain_status = 'orphaned'
    """

    cursor = conn.cursor()
    cursor.execute(check_query)
    min_ts, max_ts, total = cursor.fetchone()
    print(f"Database timestamp range: {min_ts} to {max_ts} ({total} non-orphaned blocks)")

    # NOTE: Removed DISTINCT to match potential difference with OCV server
    # The Rust code has DISTINCT, but we'll deduplicate in Python anyway
    query = """
        SELECT
            pk.value as account,
            uc.memo as memo,
            uc.nonce as nonce,
            uc.hash as hash,
            b.height as height,
            b.chain_status as status,
            b.timestamp::bigint as timestamp
        FROM user_commands AS uc
        JOIN blocks_user_commands AS buc ON uc.id = buc.user_command_id
        JOIN blocks AS b ON buc.block_id = b.id
        JOIN public_keys AS pk ON uc.source_id = pk.id
        WHERE uc.command_type = 'payment'
          AND uc.source_id = uc.receiver_id
          AND NOT b.chain_status = 'orphaned'
          AND buc.status = 'applied'
          AND b.timestamp::bigint BETWEEN %s AND %s
    """

    cursor.execute(query, (start_time, end_time))

    all_transactions = cursor.fetchall()
    print(f"Total self-payment transactions in period: {len(all_transactions)}")

    # Filter for MIP-related memos
    votes = []
    memo_samples = set()  # Track unique memo values for debugging
    debug_found_in_all = False

    for row in all_transactions:
        account, memo, nonce, tx_hash, height, status, timestamp = row

        # Debug: Check if this is our debug account
        if debug_account and account == debug_account:
            debug_found_in_all = True
            print(f"\n[DEBUG] Found {debug_account} in all transactions:")
            print(f"   Memo (base58): {memo}")
            print(f"   Nonce: {nonce}, Hash: {tx_hash}")
            print(f"   Height: {height}, Status: {status}, Timestamp: {timestamp}")

        # Decode the memo using Mina's memo format
        # Format: first 3 bytes are metadata, byte[2] is length, bytes[3:] is the message
        try:
            decoded_bytes = base58.b58decode(memo)
            if len(decoded_bytes) < 3:
                if debug_account and account == debug_account:
                    print(f"   [DEBUG] ❌ Skipped: decoded_bytes too short ({len(decoded_bytes)} < 3)")
                continue

            # Byte 2 contains the length of the message
            msg_length = decoded_bytes[2]

            if debug_account and account == debug_account:
                print(f"   [DEBUG] Decoded bytes length: {len(decoded_bytes)}, msg_length from byte[2]: {msg_length}")

            # Extract the message from bytes 3 onwards
            if len(decoded_bytes) < 3 + msg_length:
                if debug_account and account == debug_account:
                    print(f"   [DEBUG] ❌ Skipped: not enough bytes for message ({len(decoded_bytes)} < {3 + msg_length})")
                continue

            message_bytes = decoded_bytes[3:3 + msg_length]
            decoded_memo = message_bytes.decode('utf-8', errors='ignore').strip()

            if debug_account and account == debug_account:
                print(f"   [DEBUG] Decoded memo text: '{decoded_memo}'")
                print(f"   [DEBUG] Comparing with MIP key: '{mip_key}' (case-sensitive)")

            # Check if it matches our MIP key (CASE-SENSITIVE)
            # ONLY exact matches: "MIP6" or "no MIP6"
            if decoded_memo == mip_key:
                votes.append({
                    'account': account,
                    'memo': memo,
                    'vote': mip_key,
                    'nonce': nonce,
                    'hash': tx_hash,
                    'height': height,
                    'timestamp': timestamp
                })
                memo_samples.add(f'"{decoded_memo}"')
                if debug_account and account == debug_account:
                    print(f"   [DEBUG] ✅ MATCHED as '{mip_key}' vote!")
            elif decoded_memo == f"no {mip_key}":
                votes.append({
                    'account': account,
                    'memo': memo,
                    'vote': f"no{mip_key}",
                    'nonce': nonce,
                    'hash': tx_hash,
                    'height': height,
                    'timestamp': timestamp
                })
                memo_samples.add(f'"{decoded_memo}"')
                if debug_account and account == debug_account:
                    print(f"   [DEBUG] ✅ MATCHED as 'no {mip_key}' vote!")
            else:
                if debug_account and account == debug_account:
                    print(f"   [DEBUG] ❌ No match: '{decoded_memo}' != '{mip_key}' and '{decoded_memo}' != 'no {mip_key}'")
        except Exception as e:
            # Silently skip memos that can't be decoded
            if debug_account and account == debug_account:
                print(f"   [DEBUG] ❌ Exception decoding memo: {e}")
            continue

    if debug_account and not debug_found_in_all:
        print(f"\n[DEBUG] ⚠️  Account {debug_account} NOT found in any self-payment transactions in this period")

    cursor.close()

    print(f"Valid {mip_key} voting transactions: {len(votes)}")
    if memo_samples:
        print(f"Unique decoded memo values matched: {', '.join(sorted(memo_samples))}")

    # Check for votes exactly at boundaries
    boundary_votes = [v for v in votes if v['timestamp'] == start_time or v['timestamp'] == end_time]
    if boundary_votes:
        print(f"⚠️  Votes exactly at time boundaries: {len(boundary_votes)}")
        for v in boundary_votes[:3]:
            print(f"    {v['timestamp']} ({v['account'][:20]}...)")

    return votes


def deduplicate_votes(votes):
    """
    Keep only the latest vote per account.
    If multiple votes exist, take the one with highest block height,
    or highest nonce if same height.
    """
    latest_votes = {}
    duplicate_count = 0
    accounts_with_duplicates = []

    for vote in votes:
        account = vote['account']

        if account not in latest_votes:
            latest_votes[account] = vote
        else:
            duplicate_count += 1
            current = latest_votes[account]

            # Track accounts that voted multiple times
            if account not in accounts_with_duplicates:
                accounts_with_duplicates.append(account)

            # Compare by height first, then by nonce
            if (vote['height'] > current['height'] or
                (vote['height'] == current['height'] and vote['nonce'] > current['nonce'])):
                latest_votes[account] = vote

    print(f"\n=== Vote Deduplication ===")
    print(f"Total votes before deduplication: {len(votes)}")
    print(f"Unique voters (after deduplication): {len(latest_votes)}")
    print(f"Duplicate votes removed: {duplicate_count}")

    if accounts_with_duplicates:
        print(f"Accounts that voted multiple times: {len(accounts_with_duplicates)}")
        print(f"Sample accounts with duplicates (first 3):")
        for acc in accounts_with_duplicates[:3]:
            print(f"  {acc}")

    return latest_votes


def load_ledger(ledger_file_path):
    """
    Load ledger from JSON file.
    Expected format: [{"pk": "B62...", "balance": "1000000000", "delegate": "B62..."}]
    """
    print(f"\nLoading ledger from: {ledger_file_path}")

    try:
        with open(ledger_file_path, 'r') as f:
            ledger_data = json.load(f)

        print(f"Loaded {len(ledger_data)} accounts from ledger")

        # Show sample account to debug balance format
        if ledger_data:
            sample = ledger_data[0]
            print(f"\nSample ledger account (to verify format):")
            print(f"  Keys: {list(sample.keys())}")
            print(f"  pk: {sample.get('pk', 'N/A')[:20]}...")
            print(f"  balance: {sample.get('balance', 'N/A')}")
            print(f"  delegate: {sample.get('delegate', 'N/A')[:20] if sample.get('delegate') else 'N/A'}...")

        # Build a dictionary for quick lookups
        ledger_dict = {}
        total_balance_check = Decimal(0)

        for account in ledger_data:
            pk = account.get('pk')
            balance_raw = account.get('balance', '0')
            # Default delegate to self if None, empty, or missing (matching Rust: unwrap_or(pk))
            delegate = account.get('delegate') or pk

            # The balance is already in MINA units (not nanomina)
            # If it's a string with a decimal point, it's already in MINA
            # If it's a large integer (>1000000), it's in nanomina and needs conversion
            balance_str = str(balance_raw)
            if '.' in balance_str or (isinstance(balance_raw, (int, float)) and float(balance_raw) < 1000000):
                # Already in MINA
                balance_mina = Decimal(balance_str)
            else:
                # In nanomina, convert to MINA
                balance_mina = Decimal(balance_str) / Decimal(10**9)

            ledger_dict[pk] = {
                'balance': balance_mina,
                'delegate': delegate,
                'balance_raw': balance_raw
            }

            total_balance_check += balance_mina

        print(f"Total balance across all accounts: {total_balance_check:,.2f} MINA")
        print(f"Average balance per account: {total_balance_check / len(ledger_data):,.2f} MINA")

        return ledger_dict
    except FileNotFoundError:
        print(f"ERROR: Ledger file not found: {ledger_file_path}")
        print("Please provide a valid ledger file or download it from GCS")
        return {}
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in ledger file: {e}")
        return {}
    except Exception as e:
        print(f"ERROR loading ledger: {e}")
        return {}


def calculate_stake_weight_v2(ledger_dict, voter_pk, all_voter_pks):
    """
    Calculate stake weight for a voter using V2 logic (MESA MIPs use V2).

    Based on server/src/ledger.rs lines 132-150:
    - Start with voter's own balance
    - Add balances of all delegators (accounts that delegate to this voter)
    - SUBTRACT delegators who voted themselves (they override their delegate)
    """
    if voter_pk not in ledger_dict:
        return Decimal(0)

    voter_account = ledger_dict[voter_pk]
    stake_weight = Decimal(voter_account['balance'])

    # Find all delegators (accounts that delegate to this voter)
    delegators_total = Decimal(0)
    for pk, account in ledger_dict.items():
        # Skip self
        if pk == voter_pk:
            continue

        # Check if this account delegates to our voter
        delegate = account['delegate'] or pk  # Default delegate to self
        if delegate == voter_pk:
            # This account delegates to our voter
            # But if they voted themselves, don't count them (V2 logic)
            if pk not in all_voter_pks:
                delegators_total += account['balance']

    stake_weight += delegators_total

    return stake_weight


def calculate_results(votes, ledger_dict, mip_key):
    """Calculate vote counts and stake weights"""

    yes_votes = 0
    no_votes = 0
    yes_stake = Decimal(0)
    no_stake = Decimal(0)

    # Get all voter public keys for V2 calculation
    all_voter_pks = set(votes.keys())

    # Track voters not found in ledger for debugging
    voters_not_in_ledger = []
    voters_with_stake = []

    for account, vote_data in votes.items():
        # Calculate stake weight for this voter
        stake = calculate_stake_weight_v2(ledger_dict, account, all_voter_pks)

        if stake == 0 and account not in ledger_dict:
            voters_not_in_ledger.append(account)
        elif stake > 0:
            voters_with_stake.append((account, stake))

        if vote_data['vote'] == mip_key:
            yes_votes += 1
            yes_stake += stake
        elif vote_data['vote'] == f"no{mip_key}":
            no_votes += 1
            no_stake += stake

    # Print debugging information
    if ledger_dict:
        print(f"\n=== Ledger Matching Debug Info ===")
        print(f"Total voters: {len(votes)}")
        print(f"Voters found in ledger with stake: {len(voters_with_stake)}")
        print(f"Voters NOT found in ledger: {len(voters_not_in_ledger)}")

        if voters_not_in_ledger:
            print(f"\nSample voters not in ledger (first 5):")
            for voter in voters_not_in_ledger[:5]:
                print(f"  {voter}")

        if voters_with_stake:
            print(f"\nSample voters with stake (first 5):")
            for voter, stake in voters_with_stake[:5]:
                print(f"  {voter}: {stake:.9f} MINA")

        print(f"\nLedger contains {len(ledger_dict)} total accounts")
        print()

    return {
        'yes_votes': yes_votes,
        'no_votes': no_votes,
        'total_votes': yes_votes + no_votes,
        'yes_stake': yes_stake,
        'no_stake': no_stake,
        'total_stake': yes_stake + no_stake
    }


def main():
    args = parse_args()

    print(f"=== {args.mip_key} Vote Verification ===\n")
    print(f"Period: {args.start_time} to {args.end_time}")
    print(f"Ledger Hash: {args.ledger_hash}\n")

    # Connect to database
    print("Connecting to archive database...")
    conn = get_connection(args)

    try:
        # Fetch votes
        votes = fetch_votes(conn, args.mip_key, args.start_time, args.end_time, args.debug_account)

        # Deduplicate votes
        unique_votes = deduplicate_votes(votes)

        # Debug: Check if account made it through deduplication
        if args.debug_account:
            if args.debug_account in unique_votes:
                print(f"\n[DEBUG] ✅ Account {args.debug_account} is in FINAL vote list")
                print(f"   Final vote: {unique_votes[args.debug_account]}")
            else:
                print(f"\n[DEBUG] ❌ Account {args.debug_account} was REMOVED during deduplication or not matched")

        # Load ledger
        ledger_dict = {}
        if args.ledger_file:
            ledger_dict = load_ledger(args.ledger_file)
        else:
            print("\nWARNING: No ledger file provided (use --ledger-file)")
            print("Stake calculations will be skipped. Vote counts only.\n")

        # Calculate results
        results = calculate_results(unique_votes, ledger_dict, args.mip_key)

        # Print results
        print(f"\n=== {args.mip_key} Voting Results ===")
        print(f"Total votes: {results['total_votes']}")
        print(f"In favour: {results['yes_votes']}")
        print(f"Against: {results['no_votes']}")

        if ledger_dict:
            print(f"\nStake-weighted results:")
            print(f"Total vote stake: {results['total_stake']:.9f} MINA")
            print(f"In favour stake: {results['yes_stake']:.9f} MINA ({results['yes_stake']/results['total_stake']*100:.2f}%)")
            print(f"Against stake: {results['no_stake']:.9f} MINA ({results['no_stake']/results['total_stake']*100:.2f}%)")
        else:
            print(f"\n(Stake calculations skipped - no ledger provided)")

        # Export voter list if requested
        if args.export_voters:
            voter_list = sorted(unique_votes.keys())
            with open(args.export_voters, 'w') as f:
                for voter in voter_list:
                    f.write(f"{voter}\n")
            print(f"\n✓ Exported {len(voter_list)} voters to '{args.export_voters}'")

    finally:
        conn.close()


if __name__ == '__main__':
    main()