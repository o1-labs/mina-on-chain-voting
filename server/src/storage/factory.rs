use std::sync::Arc;

use anyhow::{Result, anyhow};

use super::{AwsS3Provider, GcsProvider, StorageProvider};
use crate::config::OcvConfig;

pub async fn create_storage_provider(config: &OcvConfig) -> Result<Arc<dyn StorageProvider + Send + Sync>> {
  match config.storage_provider.as_str() {
    "aws" => {
      tracing::info!("Initializing AWS S3 storage provider with region: {}", config.aws_region);
      Ok(Arc::new(AwsS3Provider::new(&config.aws_region)?))
    }
    "gcs" => {
      let project_id =
        config.gcs_project_id.as_ref().ok_or_else(|| anyhow!("GCS_PROJECT_ID required when using GCS provider"))?;
      tracing::info!("Initializing GCS storage provider with project: {}", project_id);
      Ok(Arc::new(GcsProvider::new(project_id, config.gcs_service_account_key_path.as_deref()).await?))
    }
    provider => Err(anyhow!("Unsupported storage provider: {}. Supported providers: aws, gcs", provider)),
  }
}
