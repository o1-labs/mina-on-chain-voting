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

## Migration Strategy

### Phase 1: Abstraction Layer Creation

#### 1.1 Create Storage Trait
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

#### 1.2 Implement AWS S3 Provider
**New File**: `/server/src/storage/aws_s3.rs`

Refactor existing S3 code into trait implementation:
- Move current S3 logic into `AwsS3Provider` struct
- Implement `StorageProvider` trait
- Maintain backward compatibility

#### 1.3 Implement GCS Provider
**New File**: `/server/src/storage/gcs.rs`

Create Google Cloud Storage implementation:
- Use `google-cloud-storage` crate
- Implement same interface as AWS provider
- Handle GCS-specific authentication

### Phase 2: Configuration Enhancement

#### 2.1 Update Configuration Structure
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

#### 2.2 Update Environment Configuration
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

### Phase 3: Dependency Management

#### 3.1 Update Cargo.toml
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

### Phase 4: Refactor Core Logic

#### 4.1 Update Ledger Module
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

#### 4.2 Update OCV Structure
**File**: `/server/src/ocv.rs`

Add storage provider to OCV struct:
```rust
#[derive(Clone)]
pub struct Ocv {
    // ...existing fields...
    pub storage_provider: Arc<dyn StorageProvider + Send + Sync>,
}
```

### Phase 5: Provider Factory

#### 5.1 Create Storage Factory
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
