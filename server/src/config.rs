use std::{fs, path::PathBuf, str::FromStr};

use anyhow::Result;
use bytes::Bytes;
use clap::{Args, Parser, ValueEnum};
use derive_more::Display;
use serde::{Deserialize, Serialize};

use crate::{Archive, Ocv, Proposal, ProposalsManifest, storage::create_storage_provider};

#[derive(Clone, Args)]
pub struct OcvConfig {
  /// The Mina network to connect to.
  #[clap(long, env = "NETWORK")]
  pub network: Network,
  /// The environment stage.
  #[clap(long, env = "RELEASE_STAGE")]
  pub release_stage: ReleaseStage,
  /// The URL from which the `proposals.json` should be fetched.
  #[clap(long, env = "PROPOSALS_URL")]
  pub maybe_proposals_url: Option<String>,
  /// The connection URL for the archive database.
  #[clap(long, env)]
  pub archive_database_url: String,
  /// Set the name of the bucket containing the ledgers
  #[clap(long, env)]
  pub bucket_name: String,
  /// Path to store the ledgers
  #[clap(long, env, default_value = "/tmp/ledgers")]
  pub ledger_storage_path: String,
  /// Storage provider type: "aws" or "gcs"
  #[clap(long, env = "STORAGE_PROVIDER", default_value = "gcs")]
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

impl OcvConfig {
  pub async fn to_ocv(&self) -> Result<Ocv> {
    fs::create_dir_all(&self.ledger_storage_path)?;
    let storage_provider = create_storage_provider(self).await?;
    Ok(Ocv {
      archive: Archive::new(&self.archive_database_url),
      network: self.network,
      release_stage: self.release_stage,
      ledger_storage_path: PathBuf::from_str(&self.ledger_storage_path)?,
      bucket_name: self.bucket_name.clone(),
      storage_provider,
      proposals: self.load_proposals().await?,
    })
  }

  async fn load_proposals(&self) -> Result<Vec<Proposal>> {
    let manifest_bytes = match self.release_stage {
      ReleaseStage::Development | ReleaseStage::Staging => {
        // Use embedded proposals.json for non-production env
        Bytes::from_static(include_bytes!("../proposals/proposals.json"))
      }
      _ => {
        // Fetch from github for all other networks
        let url = self.maybe_proposals_url.as_deref().unwrap_or(PROPOSALS_MANIFEST_GITHUB_URL);
        reqwest::Client::new().get(url).send().await?.bytes().await?
      }
    };

    let manifest: ProposalsManifest = serde_json::from_slice(manifest_bytes.as_ref())?;
    let filtered_by_network =
      manifest.proposals.into_iter().filter(|proposal| proposal.network == self.network).collect();
    Ok(filtered_by_network)
  }
}

static PROPOSALS_MANIFEST_GITHUB_URL: &str =
  "https://raw.githubusercontent.com/o1-labs/mina-on-chain-voting/main/server/proposals/proposals.json";

#[derive(Clone, Copy, Parser, ValueEnum, Debug, Display, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum Network {
  #[display("mainnet")]
  Mainnet,
  #[display("devnet")]
  Devnet,
}

#[derive(Clone, Copy, Parser, ValueEnum, Debug, Display, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum ReleaseStage {
  #[display("development")]
  Development,
  #[display("staging")]
  Staging,
  #[display("production")]
  Production,
}
