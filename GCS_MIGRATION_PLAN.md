# Google Cloud Storage Migration Plan
## Mina On-Chain Voting Project

### Executive Summary

This document outlines a plan to add Google Cloud Storage (GCS) support to the Mina On-Chain Voting project, which currently relies exclusively on AWS S3 for fetching staking ledger data. The goal is to enable the system to work with Google Cloud buckets while maintaining compatibility with the existing AWS infrastructure.

---

## Current State Analysis

### AWS S3 Dependencies Identified

The project currently has the following AWS-specific coupling:

#### 1. **Hard Dependencies in `Cargo.toml`**
- **Package**: `aws-sdk-s3 = "1.51.0"`
- **Location**: `/server/Cargo.toml`
- **Usage**: Core dependency for S3 operations

#### 2. **AWS S3 Client Implementation**
- **File**: `/server/src/util/s3.rs`
- **Functionality**: 
  - Creates a singleton AWS S3 client
  - Hard-coded to `us-west-2` region
  - Uses AWS SDK configuration
- **Code**:
```rust
use aws_sdk_s3::{
  Client,
  config::{Builder, Region},
};

pub fn s3_client() -> &'static Client {
  static HASHMAP: OnceLock<Client> = OnceLock::new();
  HASHMAP.get_or_init(|| {
    let region = Region::new("us-west-2");
    let config = Builder::new().region(region).behavior_version_latest().build();
    Client::from_conf(config)
  })
}
```

#### 3. **S3 API Usage in Ledger Module**
- **File**: `/server/src/ledger.rs`
- **Functions Used**:
  - `list_objects_v2()` - Lists objects in bucket
  - `get_object()` - Downloads object content
- **Operations**:
  - Downloads compressed tar.gz ledger files
  - Searches for files by hash pattern
  - Extracts and stores ledger data locally

#### 4. **Configuration**
- **Environment Variable**: `BUCKET_NAME`
- **Example Value**: `"673156464838-mina-staking-ledgers"` (clearly an AWS bucket)
- **File**: `.env.example`

#### 5. **Current Workflow**
1. System receives a ledger hash request
2. Checks local cache (`/tmp/ledgers` by default)
3. If not cached, calls `Ledger::download()`
4. Uses AWS S3 client to list bucket objects
5. Finds object with matching hash
6. Downloads tar.gz file from S3
7. Extracts specific ledger JSON file
8. Caches locally for future use

---

## AWS Download Testing (Pre-Migration Validation)

Before proceeding with the GCS migration, we need to validate that the current AWS S3 ledger download functionality is working properly. This serves as a baseline test to ensure we can always fall back to the current implementation.

### Current AWS Implementation Overview

The system currently downloads staking ledger files from AWS S3 using:
- **File**: `server/src/ledger.rs:24` - `download()` function
- **S3 Client**: `server/src/util/s3.rs:8` - Singleton client hardcoded to `us-west-2`
- **Trigger Points**: Ledger download is only triggered when:
  - `/api/proposal/:id/results` is called AND the proposal has a `ledger_hash` field
  - `/api/mef_proposal_consideration` is called WITH a `ledger_hash` query parameter
- **Process**:
  1. Lists objects in bucket using `list_objects_v2()`
  2. Finds object key containing the requested hash
  3. Downloads tar.gz file using `get_object()`
  4. Extracts specific ledger JSON file from archive
  5. Saves to local cache

### Pre-Migration Test Plan

#### Test Environment Setup

1. **Environment Variables Required**:
   ```bash
   # Copy from your working .env file
   NETWORK=mainnet  # or devnet/berkeley
   RELEASE_STAGE=development
   ARCHIVE_DATABASE_URL=postgresql://localhost:5432/your_db
   BUCKET_NAME=673156464838-mina-staking-ledgers  # AWS bucket
   LEDGER_STORAGE_PATH=/tmp/ledgers
   ```

2. **Docker Compose Setup**:
   ```bash
   # Ensure your .env file has the correct AWS bucket name
   echo "BUCKET_NAME=673156464838-mina-staking-ledgers" >> .env
   
   # Start services
   docker-compose up --build
   ```

#### Test Cases

##### Test 1: Verify AWS S3 Connection
**Objective**: Confirm the application can connect to AWS S3 and list bucket contents.

**Steps**:
1. Start the server: `docker-compose up server`
2. Check server logs for any AWS connection errors
3. Monitor for successful startup without S3-related failures

**Expected Result**: Server starts without AWS/S3 connection errors.

##### Test 2: Test Ledger Download Functionality
**Objective**: Verify end-to-end ledger download from AWS S3.

**Important**: Ledger download is only triggered by specific endpoints that require ledger data:
- `/api/proposal/:id/results` - Only if the proposal has a `ledger_hash` field
- `/api/mef_proposal_consideration/:round_id/:proposal_id/:start_time/:end_time?ledger_hash=HASH`

**Steps**:
1. Clear ledger cache: `rm -rf /tmp/ledgers/*` (or your configured path)
2. Find a proposal with a ledger hash:
   ```bash
   # Get proposals and find one with a ledger_hash
   curl -X GET "http://localhost:8080/api/proposals" | jq '.[] | select(.ledger_hash != null) | {id: .id, ledger_hash: .ledger_hash}'
   ```
3. Trigger ledger download using one of these methods:
   
   **Method A - Using proposal results endpoint:**
   ```bash
   # Replace ID with a proposal that has ledger_hash
   PROPOSAL_ID=1
   curl -X GET "http://localhost:8080/api/proposal/${PROPOSAL_ID}/results"
   ```
   
   **Method B - Using MEF proposal consideration endpoint:**
   ```bash
   # Replace with actual values from your test environment
   LEDGER_HASH="your_ledger_hash_here"
   curl -X GET "http://localhost:8080/api/mef_proposal_consideration/1/1/1234567890/1234567900?ledger_hash=${LEDGER_HASH}"
   ```

4. Monitor server logs for:
   - S3 `list_objects_v2` calls
   - S3 `get_object` calls
   - Successful tar.gz extraction
   - JSON file writing to cache
   - Log messages indicating ledger fetch operations

**Expected Result**: 
- Ledger file downloaded and cached locally
- No AWS SDK errors in logs
- Subsequent requests use cached version (no additional S3 calls)
- Server logs show successful ledger operations, not just "get_proposals"

##### Test 3: Cache Behavior Validation
**Objective**: Confirm caching works and reduces S3 calls.

**Steps**:
1. Make the same API request from Test 2 twice (using the same proposal ID or MEF endpoint)
2. First request should trigger S3 download and show ledger fetch operations in logs
3. Second request should use cached file and show no additional S3 calls
4. Check that cached ledger file exists in your configured `LEDGER_STORAGE_PATH` (default: `/tmp/ledgers/`)

**Expected Result**: 
- Only one set of S3 API calls in logs for the first request
- Second request completes faster without S3 operations
- Ledger JSON file exists in cache directory with filename `{ledger_hash}.json`

##### Test 4: Error Handling Test
**Objective**: Verify graceful handling of S3 errors.

**Steps**:
1. Temporarily set invalid bucket name: `BUCKET_NAME=invalid-bucket-name`
2. Restart server and make API request
3. Check error response and logs

**Expected Result**: Clear error message, no application crash.

#### Test Execution Checklist
- [x] Environment variables configured correctly
- [x] Docker containers start successfully  
- [x] Archive database connection working (via port forwarding)
- [x] Server responds to health checks
- [x] **Important**: Found at least one proposal with `ledger_hash` field OR have valid MEF parameters
- [x] Used correct API endpoint that triggers ledger download (not `/api/proposals`)
- [x] Ledger download completes successfully
- [x] Local cache directory contains downloaded files with correct filename format `{hash}.json`
- [x] Logs show successful S3 operations (not just "get_proposals")
- [x] Second request uses cache (no duplicate downloads)
- [ ] Error scenarios handled gracefully

#### Success Criteria

✅ **Ready for Migration** if:
- All test cases pass
- No AWS/S3 related errors in logs
- Downloaded ledger files are valid JSON
- Cache mechanism working properly
- Error handling works as expected

❌ **Not Ready** if:
- Any S3 connection failures
- Download errors or corrupted files
- Missing error handling
- Cache not functioning

### Post-Test Documentation

After successful testing, document:
1. **Working Configuration**: Copy of `.env` file that works
2. **Test Results**: Success/failure of each test case
3. **Performance Metrics**: Download times and file sizes
4. **Log Samples**: Key success/error log entries showing actual ledger operations
5. **API Endpoints Used**: Which specific endpoints triggered ledger downloads
6. **Proposal Data**: Which proposals had `ledger_hash` fields available for testing

This baseline test ensures we have a working reference implementation before introducing GCS complexity.

**Note**: If you only see "get_proposals" in your server logs without any S3 operations, you're using the wrong endpoint - the `/api/proposals` endpoint does not trigger ledger downloads.

---

## Migration Strategy

### Phase 1: Abstraction Layer Creation ✅ **COMPLETED**

#### 1.1 Create Storage Trait ✅ **COMPLETED**
**Objective**: Abstract storage operations behind a common interface

**New File**: `/server/src/storage/mod.rs`
```rust
use anyhow::Result;
use bytes::Bytes;

#[async_trait::async_trait]
pub trait StorageProvider {
    async fn list_objects(&self, bucket: &str, prefix: Option<&str>) -> Result<Vec<String>>;
    async fn get_object(&self, bucket: &str, key: &str) -> Result<Bytes>;
    fn provider_name(&self) -> &'static str;
}
```

#### 1.2 Implement AWS S3 Provider ✅ **COMPLETED**
**New File**: `/server/src/storage/aws_s3.rs`

Refactor existing S3 code into trait implementation:
- ✅ Move current S3 logic into `AwsS3Provider` struct
- ✅ Implement `StorageProvider` trait
- ✅ Maintain backward compatibility

#### 1.3 Implement GCS Provider ✅ **COMPLETED**
**New File**: `/server/src/storage/gcs.rs`

Create Google Cloud Storage implementation:
- ✅ Use `google-cloud-storage` crate
- ✅ Implement same interface as AWS provider
- ✅ Handle GCS-specific authentication

### Phase 2: Configuration Enhancement ✅ **COMPLETED**

#### 2.1 Update Configuration Structure ✅ **COMPLETED**
**File**: `/server/src/config.rs`

Add new configuration options:
```rust
#[derive(Clone, Args)]
pub struct OcvConfig {
    // ...existing fields...
    
    /// Storage provider type: "aws" or "gcs"
    #[clap(long, env = "STORAGE_PROVIDER", default_value = "aws")]
    pub storage_provider: String,
    
    /// GCS project ID (required when using GCS)
    #[clap(long, env = "GCS_PROJECT_ID")]
    pub gcs_project_id: Option<String>,
    
    /// GCS service account key path (optional)
    #[clap(long, env = "GCS_SERVICE_ACCOUNT_KEY_PATH")]
    pub gcs_service_account_key_path: Option<String>,
    
    /// AWS region (for AWS S3)
    #[clap(long, env = "AWS_REGION", default_value = "us-west-2")]
    pub aws_region: String,
}
```

#### 2.2 Update Environment Configuration ✅ **COMPLETED**
**File**: `.env.example`

Add new environment variables:
```bash
# Storage Provider Configuration
# Valid options: "aws" | "gcs"
STORAGE_PROVIDER=aws

# AWS S3 Configuration (when STORAGE_PROVIDER=aws)
AWS_REGION=us-west-2
BUCKET_NAME=673156464838-mina-staking-ledgers

# GCS Configuration (when STORAGE_PROVIDER=gcs)
# GCS_PROJECT_ID=your-gcs-project-id
# GCS_SERVICE_ACCOUNT_KEY_PATH=/path/to/service-account.json
# BUCKET_NAME=your-gcs-bucket-name
```

### Phase 3: Dependency Management ✅ **COMPLETED**

#### 3.1 Update Cargo.toml ✅ **COMPLETED**
**File**: `/server/Cargo.toml`

Add GCS dependencies while keeping AWS:
```toml
[dependencies]
# ...existing dependencies...

# Storage providers
aws-sdk-s3 = "1.51.0"
google-cloud-storage = "0.22.0"
google-cloud-auth = "0.16.0"
async-trait = "0.1.80"

# ...rest of dependencies...
```

### Phase 4: Refactor Core Logic ✅ **COMPLETED**

#### 4.1 Update Ledger Module ✅ **COMPLETED**
**File**: `/server/src/ledger.rs`

Replace direct S3 calls with storage abstraction:
```rust
impl Ledger {
    async fn download(ocv: &Ocv, hash: &String, to: &PathBuf) -> Result<()> {
        let storage = ocv.storage_provider.as_ref();
        
        // List objects to find the one with matching hash
        let objects = storage.list_objects(&ocv.bucket_name, None).await?;
        let object_key = objects
            .into_iter()
            .find(|key| key.contains(hash))
            .ok_or(anyhow!("Could not retrieve dump corresponding to {hash}"))?;
        
        // Download object
        let bytes = storage.get_object(&ocv.bucket_name, &object_key).await?;
        
        // Process tar.gz content (existing logic)
        let tar_gz = GzDecoder::new(&bytes[..]);
        let mut archive = Archive::new(tar_gz);
        // ...existing archive processing logic...
    }
}
```

#### 4.2 Update OCV Structure ✅ **COMPLETED**
**File**: `/server/src/ocv.rs`

Add storage provider to OCV struct:
```rust
#[derive(Clone)]
pub struct Ocv {
    // ...existing fields...
    pub storage_provider: Arc<dyn StorageProvider + Send + Sync>,
}
```

### Phase 5: Provider Factory ✅ **COMPLETED**

#### 5.1 Create Storage Factory ✅ **COMPLETED**
**New File**: `/server/src/storage/factory.rs`

```rust
use crate::config::OcvConfig;
use crate::storage::{StorageProvider, AwsS3Provider, GcsProvider};

pub fn create_storage_provider(config: &OcvConfig) -> Result<Arc<dyn StorageProvider + Send + Sync>> {
    match config.storage_provider.as_str() {
        "aws" => Ok(Arc::new(AwsS3Provider::new(&config.aws_region)?)),
        "gcs" => {
            let project_id = config.gcs_project_id.as_ref()
                .ok_or(anyhow!("GCS_PROJECT_ID required when using GCS provider"))?;
            Ok(Arc::new(GcsProvider::new(project_id, config.gcs_service_account_key_path.as_deref()).await?))
        },
        provider => Err(anyhow!("Unsupported storage provider: {}", provider))
    }
}
```

---

## Implementation Details

### Google Cloud Storage Integration

#### Authentication Options
1. **Service Account Key File**: JSON key file path via `GCS_SERVICE_ACCOUNT_KEY_PATH`
2. **Default Credentials**: Use Google Application Default Credentials (ADC)
3. **Workload Identity**: For GKE deployments

#### API Mapping
| AWS S3 Operation | GCS Equivalent | Notes |
|------------------|----------------|-------|
| `list_objects_v2()` | `list_objects()` | Similar functionality |
| `get_object()` | `download_object()` | Direct download |
| Bucket access | Bucket access | Same concept |

#### Error Handling
- Map GCS errors to common `anyhow::Error` types
- Maintain consistent error messages across providers
- Add provider-specific error context

### Testing Strategy

#### Unit Tests
- Mock both AWS and GCS providers
- Test storage factory with different configurations
- Verify error handling for each provider

#### Integration Tests
- Test against real GCS bucket (in CI/CD)
- Verify ledger download functionality
- Test failover scenarios

---

## Deployment Considerations

### Docker Image Updates
**File**: `/server/Dockerfile`

No changes required - new dependencies will be compiled into binary.

### Environment Variables
Applications will need to set:
- `STORAGE_PROVIDER=gcs`
- `GCS_PROJECT_ID=your-project`
- `BUCKET_NAME=your-gcs-bucket`
- Optionally: `GCS_SERVICE_ACCOUNT_KEY_PATH`

### Bucket Migration
We are not doing bucket migration.

---

## Files to Modify

### New Files
1. `/server/src/storage/mod.rs` - Storage trait definition
2. `/server/src/storage/aws_s3.rs` - AWS S3 provider implementation
3. `/server/src/storage/gcs.rs` - Google Cloud Storage provider implementation  
4. `/server/src/storage/factory.rs` - Provider factory

### Modified Files
1. `/server/Cargo.toml` - Add GCS dependencies
2. `/server/src/lib.rs` - Export storage module
3. `/server/src/config.rs` - Add storage configuration
4. `/server/src/ledger.rs` - Use storage abstraction
5. `/server/src/ocv.rs` - Include storage provider
6. `/server/src/util.rs` - Remove direct s3_client export
7. `.env.example` - Add GCS configuration examples

### Deprecated Files
1. `/server/src/util/s3.rs` - Logic moved to AWS provider

---

## Rollout Plan

### Phase 1: Development (Week 1)
- Implement storage trait and AWS provider
- Create basic GCS provider
- Update configuration system

### Phase 2: Testing (Week 2)
- Add comprehensive unit tests
- Set up GCS integration tests
- Validate backward compatibility

### Phase 3: Documentation (Week 3)
- Update README with GCS configuration
- Create deployment guides
- Update environment examples

### Phase 4: Deployment (Week 4)
- Deploy to staging with GCS
- Performance testing
- Production rollout with feature flag

---

## Risk Mitigation

### Backward Compatibility
- Default to AWS S3 provider
- Maintain existing environment variable support
- No breaking changes to API

### Performance Considerations
- Both providers use async operations
- Connection pooling for both AWS and GCS
- Local caching remains unchanged

### Error Handling
- Graceful degradation when provider unavailable
- Clear error messages for configuration issues
- Logging for debugging provider selection

---

## Success Metrics

1. **Functionality**: Both AWS and GCS providers work identically
2. **Performance**: No regression in ledger fetch times
3. **Reliability**: Error rates remain consistent across providers
4. **Usability**: Simple configuration switch between providers

---

This plan provides a comprehensive approach to adding Google Cloud Storage support while maintaining the existing AWS S3 functionality and ensuring a smooth transition path for users.
