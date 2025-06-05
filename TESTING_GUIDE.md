# Testing Guide for Mina On-Chain Voting Project

This document provides comprehensive instructions for running all types of tests in the Mina On-Chain Voting project.

---

## Overview

The project contains several types of tests across different components:

1. **Server Unit Tests** (Rust) - Located in `server/src/`
2. **Web Unit Tests** (Jest/React Testing Library) - Located in `web/components/`
3. **Integration Tests** - Via `just` commands that test the full application
4. **Linting and Static Analysis** - Code quality checks for both server and web

---

## Prerequisites

### Required Tools

You need the following tools installed:

#### Option 1: Using Nix (Recommended)
```bash
# Install Nix (if not already installed)
curl -L https://nixos.org/nix/install | sh

# Install direnv (if not already installed)
# On macOS with Homebrew:
brew install direnv

# Add direnv hook to your shell
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc

# Enter the project directory and allow direnv
cd /Users/sanabriarusso/github/mina-on-chain-voting
direnv allow
```

#### Option 2: Manual Installation
```bash
# Install just
brew install just

# Install Rust toolchain
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install Node.js and pnpm
brew install node
npm install -g pnpm@8.5.1

# Install other dependencies
brew install libpq postgresql podman
```

### Environment Setup

1. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your specific configuration
   ```

2. **Install project dependencies**:
   ```bash
   just install
   ```

---

## Server Tests (Rust)

### Unit Tests

The server contains unit tests in the following modules:
- `server/src/ledger.rs` - Stake weight calculation tests
- `server/src/vote.rs` - Vote processing tests  
- `server/src/archive.rs` - Database archive tests
- `server/src/ranked_vote.rs` - Ranked voting algorithm tests

#### Running Server Unit Tests

```bash
# Run all server unit tests
just build-server

# Or run tests directly with cargo
cd server
cargo test

# Run tests with verbose output
cd server
cargo test -- --nocapture

# Run a specific test
cd server
cargo test test_stake_weight_v1

# Run tests in a specific module
cd server
cargo test ledger::tests
```

#### Understanding Server Test Structure

The tests follow Rust's built-in testing framework:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_function_name() {
        // Test implementation
        assert_eq!(expected, actual);
    }
}
```

**Key Test Areas:**
- **Stake Weight Calculations**: Tests for V1 and V2 proposal versions
- **Vote Processing**: Validation of memo field parsing and vote counting
- **Ledger Operations**: Account delegation and balance calculations
- **Ranked Voting**: Multi-winner election algorithms

### Linting and Static Analysis

```bash
# Run Clippy (Rust linter) with strict settings
just lint-server

# Or run directly
cd server
cargo clippy -- -D warnings -D clippy::pedantic -D clippy::unwrap_used

# Run security audit
cd server
cargo audit
```

---

## Web Tests (TypeScript/Jest)

### Unit Tests

The web application uses Jest with React Testing Library for component testing. Tests are located alongside components with `.spec.tsx` extension.

**Test files include:**
- `web/components/layout-header.spec.tsx`
- `web/components/layout-footer.spec.tsx`
- `web/components/proposal-table.spec.tsx`
- `web/components/votes-metrics-*.spec.tsx`
- And many more...

#### Running Web Unit Tests

```bash
# Run all web unit tests with coverage
just build-web

# Or run tests directly with pnpm
cd web
pnpm test

# Run tests in watch mode (for development)
cd web
pnpm test --watch

# Run tests with coverage report
cd web
pnpm test --coverage

# Run a specific test file
cd web
pnpm test layout-header.spec.tsx

# Run tests matching a pattern
cd web
pnpm test --testNamePattern="renders component"
```

#### Understanding Web Test Structure

Tests use Jest with React Testing Library:

```typescript
import { render, screen, cleanup } from 'common/test';
import { Component } from './component';

describe('Component', () => {
  beforeEach(() => {
    render(<Component />, {});
  });

  afterEach(() => {
    cleanup();
  });

  it('renders component', () => {
    const element = screen.getByRole('button');
    expect(element).toBeVisible();
  });
});
```

**Test Configuration:**
- **Jest Config**: `web/jest.config.ts`
- **Setup File**: `web/jest.setup.ts`
- **TypeScript Config**: `web/tsconfig.jest.json`
- **Custom Render Utility**: `web/common/test/render.tsx`

### Linting and Type Checking

```bash
# Run all web linting and type checking
just lint-web

# Or run individual commands
cd web

# TypeScript type checking
pnpm ts-lint

# ESLint
pnpm lint

# Fix linting issues automatically
pnpm lint:fix

# Format code with prettier
pnpm format
```

---

## Integration Tests

Integration tests verify the full application stack by launching containers and testing API endpoints.

### Running Integration Tests

```bash
# Run full integration test suite
just test

# This will:
# 1. Launch the server container
# 2. Launch the web container  
# 3. Test API endpoints
# 4. Verify logging
```

**What the integration tests do:**

1. **Server Health Check**:
   ```bash
   curl http://127.0.0.1:8080/api/info | grep 'chain_tip'
   ```

2. **API Endpoint Tests**:
   ```bash
   # Test proposals endpoint
   curl http://127.0.0.1:8080/api/proposals | grep 'jw8dXuUqXVgd6NvmpryGmFLnRv1176oozHAro8gMFwj8yuvhBeS'
   
   # Test specific proposal results
   curl http://127.0.0.1:8080/api/proposal/4/results | grep 'MIP4'
   ```

3. **Log Verification**: Checks that proper logging is occurring and HTTP status codes are correct

### Manual Integration Testing Steps

If you want to run integration tests manually:

```bash
# 1. Build images
just image-build

# 2. Launch database
just launch-db

# 3. Launch server
just launch-server

# 4. Wait for startup (in another terminal)
sleep 10

# 5. Test API endpoints
curl http://127.0.0.1:8080/api/info
curl http://127.0.0.1:8080/api/proposals

# 6. Launch web interface  
just launch-web

# 7. Clean up when done
just destroy-all
```

---

## Container Testing

### Building and Testing Container Images

```bash
# Build all container images
just image-build

# Build individual images
just image-build-server
just image-build-web

# Test container functionality
just launch-server
just launch-web
```

### Container Log Analysis

Container logs are stored in a temporary directory for analysis:

```bash
# The logs are automatically created at:
# ${TMPDIR}/container-logs-XXX/server.out
# ${TMPDIR}/container-logs-XXX/server.err  
# ${TMPDIR}/container-logs-XXX/web.out
# ${TMPDIR}/container-logs-XXX/web.err

# View server logs
cat /tmp/container-logs-*/server.err

# View web logs  
cat /tmp/container-logs-*/web.out
```

---

## CI/CD Testing

The project includes Buildkite CI/CD configuration that runs tests automatically:

### CI/CD Pipeline Steps

1. **Prerequisites**: Environment setup and dependency installation
2. **Build Server**: Compiles Rust code and runs unit tests
3. **Build Web**: Builds React app and runs unit tests
4. **Build Images**: Creates Docker containers
5. **Integration Tests**: (Currently commented out) Would run full stack tests

### Running CI Tests Locally

```bash
# Run the same commands as CI
nix-shell ops/shell.nix --run "just build-server"
nix-shell ops/shell.nix --run "just build-web"
nix-shell ops/shell.nix --run "just image-build"
```

---

## Test Coverage and Reports

### Web Test Coverage

```bash
cd web
pnpm test --coverage

# Coverage report will be generated in:
# web/coverage/lcov-report/index.html
```

**Coverage Configuration** (in `web/jest.config.ts`):
- Includes: All `.ts` and `.tsx` files
- Excludes: Pages, config files, stories, generated files
- Output: HTML and text reports

### Server Test Coverage

```bash
cd server

# Install cargo-tarpaulin for coverage (one-time setup)
cargo install cargo-tarpaulin

# Generate coverage report
cargo tarpaulin --out Html

# View coverage report
open tarpaulin-report.html
```

---

## Troubleshooting

### Common Issues

1. **Port conflicts**: Ensure ports 8080 (server) and 3000 (web) are available
2. **Database connection**: Ensure PostgreSQL is running if testing database functionality
3. **Container issues**: Run `just destroy-all` to clean up containers before retesting
4. **Node version**: Ensure Node.js >= 18.0.0 and pnpm >= 8.5.1

### Debug Mode

```bash
# Run server with debug logging
RUST_LOG=debug just launch-server

# Run web in development mode
cd web
pnpm dev
```

### Cleaning Up

```bash
# Clean all build artifacts
just clean

# Clean individual components
just clean-server
just clean-web

# Destroy all containers
just destroy-all
```

---

## Test Development Guidelines

### Adding New Server Tests

1. Add tests within `#[cfg(test)]` modules in relevant `.rs` files
2. Use descriptive test names following the pattern `test_[feature]_[scenario]`
3. Include both positive and negative test cases
4. Mock external dependencies (S3, database) when appropriate

### Adding New Web Tests

1. Create `.spec.tsx` files alongside components
2. Use the custom render utility from `common/test`
3. Test user interactions, not implementation details
4. Mock external API calls and routing

### Test Data

- **Server**: Test data is created within test functions using helper functions like `get_accounts()` and `get_votes()`
- **Web**: Mock data should be defined in test files or separate mock files

---

This guide covers all testing aspects of the Mina On-Chain Voting project. For specific test implementations or debugging, refer to the existing test files as examples.
