use anyhow::Result;
use async_trait::async_trait;
use bytes::Bytes;
use google_cloud_storage::client::{Client, ClientConfig};
use google_cloud_storage::http::objects::download::Range;
use google_cloud_storage::http::objects::get::GetObjectRequest;
use google_cloud_storage::http::objects::list::ListObjectsRequest;

use super::StorageProvider;

pub struct GcsProvider {
    client: Client,
    project_id: String,
}

impl GcsProvider {
    pub async fn new(project_id: &str, service_account_key_path: Option<&str>) -> Result<Self> {
        let config = if let Some(_path) = service_account_key_path {
            // For now, we'll use default auth even if a path is provided
            // This can be enhanced later to support service account files
            ClientConfig::default().with_auth().await?
        } else {
            ClientConfig::default().with_auth().await?
        };
        
        let client = Client::new(config);
        
        Ok(GcsProvider {
            client,
            project_id: project_id.to_string(),
        })
    }
}

#[async_trait]
impl StorageProvider for GcsProvider {
    async fn list_objects(&self, bucket: &str, prefix: Option<&str>) -> Result<Vec<String>> {
        let mut request = ListObjectsRequest {
            bucket: bucket.to_string(),
            ..Default::default()
        };
        
        if let Some(prefix) = prefix {
            request.prefix = Some(prefix.to_string());
        }
        
        let response = self.client.list_objects(&request).await?;
        let objects = response.items
            .unwrap_or_default()
            .into_iter()
            .map(|obj| obj.name)
            .collect();
            
        Ok(objects)
    }

    async fn get_object(&self, bucket: &str, key: &str) -> Result<Bytes> {
        let request = GetObjectRequest {
            bucket: bucket.to_string(),
            object: key.to_string(),
            ..Default::default()
        };
        
        let response = self.client.download_object(&request, &Range::default()).await?;
        Ok(Bytes::from(response))
    }

    fn provider_name(&self) -> &'static str {
        "Google Cloud Storage"
    }
}