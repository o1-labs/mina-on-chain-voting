# Changelog

## [Storage Backend Support] - 2024-Sep-04

### Added

- **Google Cloud Storage (GCS) Backend**: Complete GCS integration as alternative to AWS S3
  - Storage provider abstraction with pluggable backends (AWS S3, GCS)
  - Anonymous access for public GCS buckets (no credentials required)
  - Authentication fallback: tries authenticated access first, falls back to anonymous HTTP
  - Configuration via `STORAGE_PROVIDER=gcs` and `GCS_PROJECT_ID` environment variables
  - Support for direct JSON files (.json) alongside compressed archives (.tar.gz)

- **Comprehensive Unit Testing**: Full test suite for storage operations
  - Mock HTTP responses for GCS API testing
  - Authentication scenarios and error handling (404, 401, 403)  
  - Bucket validation warnings and pagination testing
  - Storage factory configuration validation

- **Enhanced Error Handling**: Improved debugging and error messages
  - Provider-specific error context and configuration guidance
  - Bucket name validation with helpful warnings
  - Enhanced logging for storage operations and hash matching

### Improvements

- **Storage Architecture Refactor**: Clean provider pattern supporting multiple backends
- **Performance**: Efficient pagination for large buckets (4,250+ objects tested)
- **Configuration**: Simplified provider switching via environment variables
- **Dependencies**: Added GCS SDK support (`google-cloud-storage`, `google-cloud-auth`)

### Backward Compatibility

- **✅ Zero Breaking Changes**: All existing AWS S3 configurations work unchanged
- **✅ Environment Variables**: AWS S3 environment variables remain functional  
- **✅ API Compatibility**: No REST API changes
- **✅ Migration Path**: Switch providers by updating environment variables only

### Current Limitations

- **Service Account Key File Loading**: `GCS_SERVICE_ACCOUNT_KEY_PATH` field exists but not implemented
- **Private GCS Buckets**: Limited to Google ADC environments only

## [o1Labs-infra] - 2025-Jun-12

### Added

- **Google Cloud Storage (GCS) Support**: Complete integration allowing the application to use GCS buckets as an alternative to AWS S3 for ledger data storage
  - New storage provider abstraction with pluggable backend support (AWS S3 and Google Cloud Storage)
  - Anonymous access support for public GCS buckets - no credentials required for public bucket access
  - Smart authentication fallback: automatically tries authenticated access first, gracefully falls back to anonymous HTTP access for public buckets
  - Full pagination support for GCS buckets with 10,000+ objects across multiple pages
  - Multi-format ledger file support: handles both compressed archives (.tar.gz from AWS) and direct JSON files (.json from GCS)
  - Enhanced debugging and logging for storage operations with detailed object listing and hash matching
  - New environment variables for storage provider configuration:
    - `STORAGE_PROVIDER` (aws|gcs) - Choose between AWS S3 and Google Cloud Storage
    - `GCS_PROJECT_ID` - Google Cloud project ID for GCS authentication
    - `GCS_SERVICE_ACCOUNT_KEY_PATH` - Optional service account key file path
    - `AWS_REGION` - AWS region for S3 operations (defaults to us-west-2)

### Improvements or Migrations

- **Storage Architecture Refactor**: Migrated from direct AWS S3 client usage to a clean provider pattern that supports multiple cloud storage backends
- **Enhanced Error Handling**: Improved error messages with provider-specific context and clear guidance for configuration issues
- **Performance Optimization**: Efficient pagination implementation that prevents memory issues when handling large bucket inventories (4,250+ objects tested)
- **Hybrid Client Architecture**: Implemented intelligent client selection between authenticated SDK access and anonymous HTTP access based on credential availability
- **File Format Detection**: Smart format detection automatically handles different ledger file formats without user intervention
- **Configuration Flexibility**: Simplified switching between storage providers via environment variable changes
- **Removed deprecated S3 utility**: Eliminated `/server/src/util/s3.rs` in favor of the new provider pattern
- **Updated dependencies**: Added Google Cloud Storage SDK (`google-cloud-storage`, `google-cloud-auth`) and URL encoding support

### Backward Compatibility & Migration Notes

- **✅ Zero Breaking Changes**: Existing AWS S3 configurations continue to work without any modifications
- **✅ Environment Variable Compatibility**: All existing AWS S3 (`STORAGE_PROVIDER=aws`) environment variables (`BUCKET_NAME`, etc.) remain functional
- **✅ API Compatibility**: No changes to REST API endpoints or responses
- **✅ Docker Compatibility**: No Dockerfile changes required - new dependencies compile into existing binary
- **Migration Path**: To switch to GCS, simply update environment variables:
  ```
  STORAGE_PROVIDER=gcs
  GCS_PROJECT_ID=your-project-id
  BUCKET_NAME=your-gcs-bucket-name
  ```


## [Post-MIP] as of 2023-Sep-26

### Added

- We streamlined development and deployment using Nix, Just, and Podman: for building, following
  best open-source practices and enhancements, being able to build with one command, and not reliant
  on Docker
  - Nix ensures reproducibility and isolation by defining precise dependencies
  - Just simplifies and automates common tasks with single-command actions
  - Podman offers enhanced security and flexibility for containerization
- Updated Results button to be a ternary operator with either Results or Go Vote appearing next to
  the button icon
- Adding corresponding, respective URL links and matching text with the database
- Control log level functionality from an .env file
- Added customized code and fix for the next-router-mock given lack of support from Next 13 and this
  customization fixes broken tests in CI

### Improvements or Migrations

- Clarify and improve build instructions
- Migrated to Next 13's app router with a redesigned UI
- Migrated components to Tailwind & Radix
- Migrated pages to Next 13's app router
- Migrated & extended tests to increase coverage
- Improve precision by extending to 4 decimal places from 2 and remove any unnecessary trailing
  zeros
- Improve Docker build and integration between postgres and server
- Improve .env.example file for better networking options and ports suggested
- Improve various frontend and UI changes regarding filtering and sorting on tables, title, nav bar,
  footer, coloring, MIP key to be just MIP# vs # - MIP#
- Fix graph dates display, order of dates, and overall display
- Update multiple dependencies across the repo (some advised by dependabot)
- Extend README to DEVELOPER docs and splits across the server and web directories
- Improve GitHub CI configuration

### Deprecated or Removed

- Removed unused Playwright functionality
- Remove unused features (MUI - Storybook - Typeshare)

## [Pre-MIP4] - 2023-05-20

### Added

- Database migration script to make global_slot numbers i64 in Mina Proposals
- Updated the OCV app so it supports other networks other than mainnet
- Added rustsec audit-check in github action support
- Updated TTL cache with filtering and whitelisting
- Installed and configured Storybook, Playwright, Jest configurations (and custom jest render
  utilities), and MUI base tooling
- Migrated, converted and refactored tests
- Setup Typeshare CLI to generate TypeScript bindings from Rust types
- Added zod schema validation for frontend as well as queries and store
- Update environment variables and configuration
- Added core-info endpoint for server as well as minor schema modifications
- Added extension settings [.vscode]
- Setup workspaces [pnpm cargo] and added workspace scripts
- Added and updated top-level configurations [pnpm eslint prettier] [other IDE Extensions]
- Create Dockerfile and schema using Diesel ORM

### Improvements

- Sanitize SQL query params in function fetch_transactions using bind
- Improved security with specific CORS origins and preflight
- Improve the Github actions workflows to only build projects that have changed
- Decouple frontend and backend codebases and then migrate and refactor them to NextJS and Vercel
  deployment as well as refactor and restructure server modules
- Double precision errors that occur with floating point types by using Decimal type
- Updated README.md files

### Deprecated or Removed

- Removed static page serving
- Removed dummy data and Nix build system
- Deprecated Haskell tools and scripts related to the archive node

## [Pre-MIP1] - 2023-01-04

### Added

- Created FAQs and feedback forms
- New feature and support for pagination of results
- Archive node missing blocks script and runbook to check and patch missing blocks when needed
- Create tests (unit, functional, etc.) for server and client
- Added timestamp checking to the canonical OCV query so as to avoid votes being counted that were
  cast before the start of the voting period
- Created Haskell scripts to download, clean and run archive dumps and connect to the archive node's
  PostgreSQL database
- Ability for users explore a tx hash instead of copying and manually going to verify the
  transaction with a third-party
- Updated the SQL query, sqlx uses github workflows to determine query validity, and LedgerAccount
  changed to an array from a vector and begins empty rather than zero
- Created a progress bar to display the progress of the voting time period
- Memo all lowercase to avoid case sensitivity
- Delegating stake is clearly expressed in browser
- Maintain certain version of tokio and axum to avoid security issue
- Created tooltips, such as for total votes calculations

### Deprecated or Removed

- Deprecated feature to count valid signals from accounts not on the Staking Ledger in the total
  number of signals, but not for the total stake
