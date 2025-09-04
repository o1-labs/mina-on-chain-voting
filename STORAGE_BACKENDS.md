# Storage Backend Support

This document explains how multiple storage backends were added to support both AWS S3 and Google Cloud Storage (GCS) for staking ledger retrieval.

## What Was Done

A storage abstraction layer was implemented to support multiple cloud storage providers while maintaining backward compatibility with the existing AWS S3 setup.

**Key Changes:**
- Created a `StorageProvider` trait for unified storage operations
- Implemented AWS S3 and GCS providers behind this interface
- Added configuration options to switch between providers
- Refactored ledger download logic to use the abstraction

## How It Works

### Storage Provider Selection
The system selects storage providers based on configuration:
- **Default**: AWS S3 (maintains backward compatibility)
- **GCS**: Set `--storage-provider gcs` flag or `STORAGE_PROVIDER=gcs` environment variable

### Provider Features
- **AWS S3**: Downloads compressed `.tar.gz` archives containing JSON files
- **GCS**: Downloads direct `.json` files (no compression) with anonymous public bucket access
- Both providers handle authentication, pagination, and error scenarios

### Authentication
- **AWS S3**: Uses AWS SDK default credential chain
- **GCS**: Uses Google Application Default Credentials with fallback to anonymous access for public buckets

## Configuration

### GCS Backend
```bash
# Required
GCS_PROJECT_ID=your-project-id
--storage-provider gcs
--bucket-name your-gcs-bucket

# For private buckets (via ADC only)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### AWS S3 Backend (Default)
```bash
# Optional (has defaults)
--storage-provider aws
--aws-region us-west-2
--bucket-name your-s3-bucket
```

## Running with GCS Backend

### Mainnet with Public GCS Bucket
```bash
#!/usr/bin/env bash

podman run --platform linux/amd64 \
  --entrypoint /bin/bash \
  --replace \
  -d \
  --name mainnet-ocv-server \
  -e GCS_PROJECT_ID=o1labs-192920 \
  -e RUST_LOG=debug \
  -p 8081:8080 \
  asia-northeast3-docker.pkg.dev/o1labs-192920/gitops-images/on-chain-voting-server:latest -c \
    "./mina_ocv --network mainnet \
        --release-stage production \
        --archive-database-url 'postgres://user:pass@host:port/db' \
        --bucket-name 'mina-staking-ledgers' \
        --port 8080 \
        --storage-provider gcs"
```

### Devnet with Public GCS Bucket
```bash
#!/usr/bin/env bash

podman run --platform linux/amd64 \
  --entrypoint /bin/bash \
  --replace \
  -d \
  --name devnet-ocv-server \
  -e GCS_PROJECT_ID=o1labs-192920 \
  -e RUST_LOG=debug \
  -p 8080:8080 \
  your-image -c \
    "./mina_ocv --network devnet \
        --release-stage development \
        --archive-database-url 'postgres://user:pass@host:port/db' \
        --bucket-name 'mina-staking-ledgers-devnet' \
        --port 8080 \
        --storage-provider gcs"
```

### With Authentication (Private Buckets - ADC Only)
```bash
#!/usr/bin/env bash

podman run --platform linux/amd64 \
  --entrypoint /bin/bash \
  --replace \
  -d \
  --name ocv-server \
  -e GCS_PROJECT_ID=your-project-id \
  -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keyfiles \
  -v "$(pwd)/service-account.json":/tmp/keyfiles \
  -p 8080:8080 \
  your-image -c \
    "./mina_ocv --network mainnet \
        --bucket-name 'your-private-bucket' \
        --storage-provider gcs"
```

## Current Limitations

**⚠️ Important**: The following features are **NOT YET IMPLEMENTED**:

- **Service Account Key File Loading**: The `GCS_SERVICE_ACCOUNT_KEY_PATH` configuration field exists but is currently ignored. The code always uses Google Application Default Credentials (ADC) even when a key file path is provided.

- **Private Bucket Access**: Limited to environments where Google ADC works (GCP instances with workload identity, gcloud-authenticated environments). Direct service account key file authentication is not implemented.

**What Works:**
- ✅ Public GCS bucket access (anonymous)
- ✅ Private bucket access via ADC (when available in environment)
- ✅ Full AWS S3 functionality (unchanged)

**What Doesn't Work:**
- ❌ Direct service account key file authentication for GCS private buckets

## Testing

**Unit Tests:**
- Mock HTTP responses for GCS operations
- Test authentication fallback scenarios
- Validate bucket name format checking
- Error handling (404, 401, 403 responses)

**Run Storage Tests:**
```bash
cd server && cargo test storage::gcs::tests
cd server && cargo test storage::factory::tests
```

**Integration Testing:**
- Provider factory configuration validation  
- Real bucket connectivity (tested with `mina-staking-ledgers` public bucket)
- Cross-provider compatibility

## Files Modified

**New Files:**
- `server/src/storage/mod.rs` - Storage trait definition
- `server/src/storage/aws_s3.rs` - AWS S3 provider
- `server/src/storage/gcs.rs` - GCS provider  
- `server/src/storage/factory.rs` - Provider factory

**Modified Files:**
- `server/src/config.rs` - Added storage provider configuration
- `server/src/ledger.rs` - Replaced direct S3 calls with storage abstraction
- `server/src/ocv.rs` - Integrated storage provider
- `server/Cargo.toml` - Added GCS dependencies

**Dependencies Added:**
- `google-cloud-storage = "0.22.0"`
- `google-cloud-auth = "0.16.0"`
- `async-trait = "0.1.80"`