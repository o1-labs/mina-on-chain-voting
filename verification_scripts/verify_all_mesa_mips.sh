#!/bin/bash

# Helper script to verify all MESA MIPs at once
# Usage: ./verify_all_mesa_mips.sh --db-url "postgresql://user:password@host:port/database" [--ledger-file path/to/ledger.json]

# MESA MIPs voting period (from proposals.json)
START_TIME=1765152000000  # December 7, 2025, 18:00 UTC
END_TIME=1765843199000    # December 15, 2025, 17:59:59 UTC
LEDGER_HASH="jw6vWbTAx69iRb3ynYK9tMCN9w1DjK4YwHu19dYWKfZ9q9Qbkve"

# Parse ledger file argument if provided
LEDGER_ARG=""
for arg in "$@"; do
    if [[ "$arg" == "--ledger-file" ]]; then
        LEDGER_FLAG=1
    elif [[ "$LEDGER_FLAG" == "1" ]]; then
        LEDGER_ARG="--ledger-file $arg"
        LEDGER_FLAG=0
    fi
done

# Check if db credentials provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 --db-url \"postgresql://user:password@host:port/database\" [--ledger-file path/to/ledger.json]"
    echo "   or: $0 --db-host HOST --db-port PORT --db-name NAME --db-user USER --db-password PASS [--ledger-file path/to/ledger.json]"
    exit 1
fi

echo "==================================================================="
echo "Verifying all MESA MIPs"
echo "==================================================================="
echo ""

# Verify MIP6
echo "1. Verifying MIP-0006 (Reduce slot time to 90s)..."
python3 verify_mip_db.py "$@" \
    --mip-key "MIP6" \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --ledger-hash $LEDGER_HASH

echo ""
echo "-------------------------------------------------------------------"
echo ""

# Verify MIP7
echo "2. Verifying MIP-0007 (Increase On-Chain State Size Limit)..."
python3 verify_mip_db.py "$@" \
    --mip-key "MIP7" \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --ledger-hash $LEDGER_HASH

echo ""
echo "-------------------------------------------------------------------"
echo ""

# Verify MIP8
echo "3. Verifying MIP-0008 (Increase Events & Actions Limit)..."
python3 verify_mip_db.py "$@" \
    --mip-key "MIP8" \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --ledger-hash $LEDGER_HASH

echo ""
echo "-------------------------------------------------------------------"
echo ""

# Verify MIP9
echo "4. Verifying MIP-0009 (Increase zkApp Account Update Limit)..."
python3 verify_mip_db.py "$@" \
    --mip-key "MIP9" \
    --start-time $START_TIME \
    --end-time $END_TIME \
    --ledger-hash $LEDGER_HASH

echo ""
echo "==================================================================="
echo "All MESA MIPs verified!"
echo "==================================================================="