use anyhow::Result;
use async_trait::async_trait;
use aws_sdk_s3::{
    Client,
    config::{Builder, Region},
};
use bytes::Bytes;

use super::StorageProvider;

pub struct AwsS3Provider {
    client: Client,
}

impl AwsS3Provider {
    pub fn new(region: &str) -> Result<Self> {
        let region = Region::new(region.to_string());
        let config = Builder::new().region(region).behavior_version_latest().build();
        let client = Client::from_conf(config);
        
        Ok(AwsS3Provider { client })
    }
}

#[async_trait]
impl StorageProvider for AwsS3Provider {
    async fn list_objects(&self, bucket: &str, prefix: Option<&str>) -> Result<Vec<String>> {
        let mut request = self.client.list_objects_v2().bucket(bucket);
        
        if let Some(prefix) = prefix {
            request = request.prefix(prefix);
        }
        
        let response = request.send().await?;
        let objects = response.contents
            .unwrap_or_default()
            .into_iter()
            .filter_map(|obj| obj.key)
            .collect();
            
        Ok(objects)
    }

    async fn get_object(&self, bucket: &str, key: &str) -> Result<Bytes> {
        let response = self.client
            .get_object()
            .bucket(bucket)
            .key(key)
            .send()
            .await?;
            
        let bytes = response.body.collect().await?.into_bytes();
        Ok(bytes)
    }

    fn provider_name(&self) -> &'static str {
        "AWS S3"
    }
}