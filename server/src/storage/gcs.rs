use anyhow::{Result, anyhow};
use async_trait::async_trait;
use bytes::Bytes;
use google_cloud_storage::{
  client::{Client, ClientConfig},
  http::objects::{download::Range, get::GetObjectRequest, list::ListObjectsRequest},
};
use serde::Deserialize;

use super::StorageProvider;

enum GcsClient {
  Authenticated(Client),
  Anonymous(reqwest::Client),
}

pub struct GcsProvider {
  client: GcsClient,
  #[allow(dead_code)] // May be used for future GCS operations that require project_id
  project_id: String,
}

#[derive(Deserialize)]
struct GcsListResponse {
  items: Option<Vec<GcsObject>>,
  #[serde(rename = "nextPageToken")]
  next_page_token: Option<String>,
}

#[derive(Deserialize)]
struct GcsObject {
  name: String,
}

impl GcsProvider {
  pub async fn new(project_id: &str, service_account_key_path: Option<&str>) -> Result<Self> {
    // Try to create authenticated client first, but fall back to anonymous HTTP
    // access for public buckets
    let client = if let Some(_path) = service_account_key_path {
      // For now, we'll try default auth even if a path is provided
      // This can be enhanced later to support service account files
      match ClientConfig::default().with_auth().await {
        Ok(config) => {
          tracing::info!("GCS initialized with service account authentication");
          GcsClient::Authenticated(Client::new(config))
        }
        Err(err) => {
          tracing::warn!(
            "Failed to initialize GCS with service account authentication, using anonymous HTTP access for public buckets: {}",
            err
          );
          GcsClient::Anonymous(reqwest::Client::new())
        }
      }
    } else {
      // Try with default auth, fall back to anonymous HTTP access for public buckets
      match ClientConfig::default().with_auth().await {
        Ok(config) => {
          tracing::info!("GCS initialized with default authentication");
          GcsClient::Authenticated(Client::new(config))
        }
        Err(err) => {
          tracing::warn!("No GCS credentials found, using anonymous HTTP access for public buckets: {}", err);
          GcsClient::Anonymous(reqwest::Client::new())
        }
      }
    };

    Ok(GcsProvider { client, project_id: project_id.to_string() })
  }
}

#[async_trait]
impl StorageProvider for GcsProvider {
  async fn list_objects(&self, bucket: &str, prefix: Option<&str>) -> Result<Vec<String>> {
    match &self.client {
      GcsClient::Authenticated(client) => {
        let mut request = ListObjectsRequest { bucket: bucket.to_string(), ..Default::default() };

        if let Some(prefix) = prefix {
          request.prefix = Some(prefix.to_string());
        }

        let response = client.list_objects(&request).await
                    .map_err(|err| {
                        if err.to_string().contains("401") || err.to_string().contains("403") {
                            anyhow!("GCS bucket '{}' requires authentication. Please set GCS_PROJECT_ID and optionally GCS_SERVICE_ACCOUNT_KEY_PATH environment variables. Error: {}", bucket, err)
                        } else {
                            anyhow!("Failed to list objects in GCS bucket '{}': {}", bucket, err)
                        }
                    })?;

        let objects = response.items.unwrap_or_default().into_iter().map(|obj| obj.name).collect::<Vec<String>>();

        tracing::info!(
          "GCS authenticated client found {} objects in bucket '{}': {:?}",
          objects.len(),
          bucket,
          objects.iter().take(5).collect::<Vec<_>>()
        );

        Ok(objects)
      }
      GcsClient::Anonymous(http_client) => {
        // Use GCS JSON API for anonymous access with pagination support
        let mut all_objects = Vec::new();
        let mut page_token: Option<String> = None;
        let mut page_count = 0;

        loop {
          let mut url = format!("https://storage.googleapis.com/storage/v1/b/{}/o?maxResults=1000", bucket);

          if let Some(prefix) = prefix {
            url.push_str(&format!("&prefix={}", urlencoding::encode(prefix)));
          }

          if let Some(token) = &page_token {
            url.push_str(&format!("&pageToken={}", urlencoding::encode(token)));
          }

          tracing::debug!("Fetching GCS page {} from: {}", page_count + 1, url);

          let response = http_client
            .get(&url)
            .send()
            .await
            .map_err(|err| anyhow!("Failed to list objects in GCS bucket '{}': {}", bucket, err))?;

          if response.status().is_client_error() {
            if response.status() == 401 || response.status() == 403 {
              return Err(anyhow!(
                "GCS bucket '{}' requires authentication. Please set GCS_PROJECT_ID and optionally GCS_SERVICE_ACCOUNT_KEY_PATH environment variables.",
                bucket
              ));
            }
            return Err(anyhow!("Failed to access GCS bucket '{}': HTTP {}", bucket, response.status()));
          }

          let list_response: GcsListResponse = response
            .json()
            .await
            .map_err(|err| anyhow!("Failed to parse GCS response for bucket '{}': {}", bucket, err))?;

          if let Some(items) = list_response.items {
            let page_objects: Vec<String> = items.into_iter().map(|obj| obj.name).collect();
            tracing::debug!("GCS page {} returned {} objects", page_count + 1, page_objects.len());
            all_objects.extend(page_objects);
          }

          page_count += 1;
          page_token = list_response.next_page_token;

          // Break if no more pages or if we've fetched a reasonable amount
          if page_token.is_none() || page_count >= 10 {
            if page_count >= 10 {
              tracing::warn!(
                "Stopped fetching GCS objects after {} pages ({} objects) to avoid excessive API calls",
                page_count,
                all_objects.len()
              );
            }
            break;
          }
        }

        tracing::info!(
          "GCS anonymous client found {} objects across {} pages in bucket '{}': {:?}",
          all_objects.len(),
          page_count,
          bucket,
          all_objects.iter().take(5).collect::<Vec<_>>()
        );

        Ok(all_objects)
      }
    }
  }

  async fn get_object(&self, bucket: &str, key: &str) -> Result<Bytes> {
    match &self.client {
      GcsClient::Authenticated(client) => {
        let request = GetObjectRequest { bucket: bucket.to_string(), object: key.to_string(), ..Default::default() };

        let response = client.download_object(&request, &Range::default()).await
                    .map_err(|err| {
                        if err.to_string().contains("401") || err.to_string().contains("403") {
                            anyhow!("GCS object '{}' in bucket '{}' requires authentication. Please set GCS_PROJECT_ID and optionally GCS_SERVICE_ACCOUNT_KEY_PATH environment variables. Error: {}", key, bucket, err)
                        } else {
                            anyhow!("Failed to download object '{}' from GCS bucket '{}': {}", key, bucket, err)
                        }
                    })?;

        Ok(Bytes::from(response))
      }
      GcsClient::Anonymous(http_client) => {
        // Use GCS JSON API for anonymous access
        let url =
          format!("https://storage.googleapis.com/storage/v1/b/{}/o/{}?alt=media", bucket, urlencoding::encode(key));

        let response = http_client
          .get(&url)
          .send()
          .await
          .map_err(|err| anyhow!("Failed to download object '{}' from GCS bucket '{}': {}", key, bucket, err))?;

        if response.status().is_client_error() {
          if response.status() == 401 || response.status() == 403 {
            return Err(anyhow!(
              "GCS object '{}' in bucket '{}' requires authentication. Please set GCS_PROJECT_ID and optionally GCS_SERVICE_ACCOUNT_KEY_PATH environment variables.",
              key,
              bucket
            ));
          }
          return Err(anyhow!(
            "Failed to access GCS object '{}' in bucket '{}': HTTP {}",
            key,
            bucket,
            response.status()
          ));
        }

        let bytes = response
          .bytes()
          .await
          .map_err(|err| anyhow!("Failed to read object '{}' from GCS bucket '{}': {}", key, bucket, err))?;

        Ok(bytes)
      }
    }
  }

  fn provider_name(&self) -> &'static str {
    "Google Cloud Storage"
  }
}
