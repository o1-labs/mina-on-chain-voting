# MESA MIPs Vote Verification Scripts

Independent verification scripts for MESA MIPs (MIP-0006 through MIP-0009) voting results. These scripts query the Mina archive database directly, mirroring exactly what the OCV server does.

## Requirements

### System Requirements
- **Python 3.7+** - Required for all scripts
- **bash** - Required for `verify_all_mesa_mips.sh` (usually pre-installed on macOS/Linux)
- **PostgreSQL database access** - Mina archive database with voting period data
- **Internet connection** - For downloading ledger files from GCS (optional)

### Python Dependencies
- **`psycopg2-binary`** (v2.9+) - PostgreSQL database adapter
- **`base58`** (v2.1+) - Base58 encoding/decoding for Mina memos

Install with:
```bash
python3 -m pip install psycopg2-binary base58
```

## Quick Start

```bash
# 1. Install dependencies
python3 -m pip install psycopg2-binary base58

# 2. Download ledger file
python3 download_ledger.py \
    --ledger-hash "jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve" \
    --output ledger.json

# 3. Verify all MESA MIPs
export DB_URL="postgresql://user:password@host:port/database"
./verify_all_mesa_mips.sh --db-url "$DB_URL" --ledger-file ledger.json
```

## MIPs Covered

- **MIP-0006**: Reduce slot time to 90s
- **MIP-0007**: Increase On-Chain State Size Limit
- **MIP-0008**: Increase Events & Actions Limit
- **MIP-0009**: Increase zkApp Account Update Limit

## Voting Period

All MESA MIPs shared the same voting period:
- **Start**: December 7, 2025, 18:00 UTC (1765152000000 ms)
- **End**: December 15, 2025, 17:59:59 UTC (1765843199000 ms)
- **Epoch**: 37
- **Ledger Hash**: `jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve`

## Setup

### 1. Install Python Dependencies

The scripts require two Python packages:

```bash
python3 -m pip install psycopg2-binary base58
```

**Dependencies:**
- **`psycopg2-binary`** (v2.9+) - PostgreSQL database adapter for Python
- **`base58`** (v2.1+) - Base58 encoding/decoding for Mina memo fields

**Note:** If you already have `psycopg2` installed (not the binary version), that works too. The binary version is easier to install as it doesn't require PostgreSQL development libraries.

### 2. Obtain Ledger File (Optional)

The ledger file is required for stake-weighted results, but optional if you only want vote counts.

**Option A: Download from GCS (Recommended)**

Use the provided helper script to download the ledger file:
```bash
python3 download_ledger.py \
    --ledger-hash "jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve" \
    --output ledger.json
```

This will download the ledger file from the public `mina-staking-ledgers` GCS bucket.

**Option B: Manual Download**

The ledger file should be in JSON format with the following structure:
```json
[
  {
    "pk": "B62qre3erTHfzQckNuibViWQGyyKwZseztqrjPZBv6SQF384Rg6ESAy",
    "balance": "66000000000",
    "delegate": "B62qre3erTHfzQckNuibViWQGyyKwZseztqrjPZBv6SQF384Rg6ESAy"
  }
]
```

You can obtain the ledger file from:
- The Mina ledger snapshots stored in GCS bucket `mina-staking-ledgers`
- The OCV server's ledger cache (if you have access to the server)
- By querying the archive database directly for the ledger hash

Note: The script will work without a ledger file but will only show vote counts, not stake-weighted results.

## Usage

### Verify a Single MIP

```bash
python3 verify_mip_db.py \
    --db-url "postgresql://user:password@host:port/database" \
    --mip-key "MIP6" \
    --start-time 1765152000000 \
    --end-time 1765843199000 \
    --ledger-hash "jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve" \
    --ledger-file "path/to/ledger.json"
```

Or with individual connection parameters:

```bash
python3 verify_mip_db.py \
    --db-host "localhost" \
    --db-port "5432" \
    --db-name "archive" \
    --db-user "postgres" \
    --db-password "your-password" \
    --mip-key "MIP6" \
    --start-time 1765152000000 \
    --end-time 1765843199000 \
    --ledger-hash "jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve" \
    --ledger-file "path/to/ledger.json"
```

### Verify All MESA MIPs at Once

```bash
./verify_all_mesa_mips.sh --db-url "postgresql://user:password@host:port/database" --ledger-file "path/to/ledger.json"
```

Or:

```bash
./verify_all_mesa_mips.sh \
    --db-host "localhost" \
    --db-port "5432" \
    --db-name "archive" \
    --db-user "postgres" \
    --db-password "your-password" \
    --ledger-file "path/to/ledger.json"
```

Note: The `--ledger-file` parameter is optional. Without it, the scripts will only show vote counts.

### Using Environment Variables

For better security, you can use environment variables:

```bash
export DB_URL="postgresql://user:password@host:port/database"
python3 verify_mip_db.py \
    --db-url "$DB_URL" \
    --mip-key "MIP6" \
    --start-time 1765152000000 \
    --end-time 1765843199000 \
    --ledger-hash "jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve" \
    --ledger-file "path/to/ledger.json"
```

## Files

- **`verify_mip_db.py`** - Main verification script for individual MIPs
- **`verify_all_mesa_mips.sh`** - Batch script to verify all 4 MESA MIPs at once
- **`download_ledger.py`** - Helper to download ledger files from GCS
- **`ledger.json`** - Downloaded ledger file (merged from staking + next-staking)

## Output

Each script will output:
- Total number of self-payment transactions found in the period
- Number of valid voting transactions for the specific MIP
- Number of unique voters (after removing duplicates)
- Vote counts (for and against)
- Stake weights (for and against) - if ledger data is available

Example output:
```
=== MIP6 Voting Results ===
Total votes: 227
In favour: 227
Against: 0

Stake-weighted results:
Total vote stake: 246,874,259.24 MINA
In favour stake: 246,874,259.24 MINA (100.00%)
Against stake: 0.00 MINA (0.00%)
```

## Advanced Options

### Debug a Specific Account

To understand why a specific account was included or excluded:

```bash
python3 verify_mip_db.py \
    --db-url "$DB_URL" \
    --mip-key "MIP6" \
    --start-time 1765152000000 \
    --end-time 1765843199000 \
    --ledger-hash "jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve" \
    --ledger-file ledger.json \
    --debug-account "B62q..."
```

### Export Voter List

To export the list of voters for comparison:

```bash
python3 verify_mip_db.py \
    --db-url "$DB_URL" \
    --mip-key "MIP6" \
    --start-time 1765152000000 \
    --end-time 1765843199000 \
    --ledger-hash "jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve" \
    --ledger-file ledger.json \
    --export-voters voters_mip6.txt
```

## Verification

Compare the results from these scripts with:
1. The OCV Dashboard results at https://ocv.minaprotocol.com/
2. The API endpoint results: `GET /api/proposal/{id}/results` where id is 41-44

### Known Differences

**Minor vote count differences (±1 vote)** may occur due to:
- **Block finality timing**: OCV applies a 10-block finality rule. Votes near the end of the voting period that haven't reached 10 blocks deep at the time OCV calculated results will be excluded by OCV but included by this script (which calculates with full finality).
- This is expected and correct behavior - both implementations are valid depending on when results are calculated.

**Stake weight differences (<1%)** may occur due to:
- Decimal precision differences between Rust's `Decimal` and Python's `Decimal`
- Rounding when summing many small balances

If differences are larger than this, investigate using the `--debug-account` option.

## How It Works

The verification script:
1. Connects to the PostgreSQL archive database
2. Queries for all self-payment transactions in the voting period (similar to `archive.rs:37-57`)
3. Filters transactions by decoding memo fields to match MIP keys
4. Removes duplicate votes (keeps latest per voter based on block height and nonce)
5. Fetches stake information from the ledger (using the provided ledger hash)
6. Calculates aggregated stake weights
7. Adjusts for delegating voters who override their delegate's vote
8. Outputs final vote counts and stake totals

## Database Requirements

You need access to a Mina archive database that contains:
- `user_commands` table with payment transactions
- `blocks` table with block data
- `public_keys` table with account addresses
- Ledger data for the specified ledger hash

The archive database schema is documented in the Mina documentation.

## Security Notes

- Never commit database credentials to version control
- Use environment variables or pass credentials via command-line arguments
- Consider using `.pgpass` file for PostgreSQL password management
- Ensure your database connection is encrypted (use SSL/TLS)

## Troubleshooting

### Connection Errors

If you get connection errors, verify:
- Database host and port are accessible
- Credentials are correct
- Database exists and contains archive data
- Firewall allows connections

### Missing Ledger Data

If ledger stake calculations fail:
- Verify the ledger hash is correct
- Check that the archive database has ledger data for that hash
- The implementation may need adjustment based on your archive DB schema version

## References

- OCV server implementation: `server/src/archive.rs`
- Original GraphQL verification scripts: [MIP3](https://gist.github.com/trevorbernard/ec11db89bb9079dd0a01332ef32c0284) and [MIP4](https://gist.github.com/trevorbernard/928be21e8e1d9464c3a9b2453d9fd886)
- Vote calculation process: See `OCV_PROCESS.md` in the repository root