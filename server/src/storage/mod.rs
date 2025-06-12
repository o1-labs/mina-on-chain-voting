use anyhow::Result;
use bytes::Bytes;

pub mod aws_s3;
pub mod factory;
pub mod gcs;

#[async_trait::async_trait]
pub trait StorageProvider {
  async fn list_objects(&self, bucket: &str, prefix: Option<&str>) -> Result<Vec<String>>;
  async fn get_object(&self, bucket: &str, key: &str) -> Result<Bytes>;
  fn provider_name(&self) -> &'static str;
}

pub use aws_s3::AwsS3Provider;
pub use factory::create_storage_provider;
pub use gcs::GcsProvider;
