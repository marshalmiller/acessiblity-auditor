# GitHub Actions Workflows

This directory contains automated workflows for the Accessibility Auditor project.

## docker-publish.yml

Automatically builds and publishes Docker images to GitHub Container Registry (ghcr.io).

### Triggers

- **Push to main**: Builds and pushes with `latest` and `main-<sha>` tags
- **Tagged releases**: Builds and pushes with semantic version tags (e.g., `v1.0.0`, `v1.0`, `v1`)
- **Pull requests**: Builds only (no push) for validation
- **Manual dispatch**: Can be triggered manually from GitHub Actions tab

### What it does

1. Checks out the repository code
2. Sets up Docker Buildx for efficient builds
3. Logs in to GitHub Container Registry using GITHUB_TOKEN
4. Extracts metadata and generates appropriate tags
5. Builds the Docker image with caching for faster builds
6. Pushes the image to ghcr.io/marshalmiller/acessiblity-auditor
7. Generates build attestation for supply chain security

### Image Tags

Published images are available at: `ghcr.io/marshalmiller/acessiblity-auditor`

**Available tags:**
- `latest` - Most recent build from main branch
- `main` - Latest main branch build
- `main-<sha>` - Specific commit from main (e.g., `main-abc1234`)
- `v1.0.0` - Exact semantic version (created from git tags)
- `v1.0` - Minor version (e.g., v1.0.3 → v1.0)
- `v1` - Major version (e.g., v1.2.3 → v1)
- `pr-123` - Pull request builds (not pushed to registry)

### Usage

**Pull the latest image:**
```bash
docker pull ghcr.io/marshalmiller/acessiblity-auditor:latest
```

**Pull a specific version:**
```bash
docker pull ghcr.io/marshalmiller/acessiblity-auditor:v1.0.0
```

**Run the container:**
```bash
docker run -d -p 5000:5000 ghcr.io/marshalmiller/acessiblity-auditor:latest
```

### Creating a Release

To create a versioned release:

1. Tag your commit with a semantic version:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. The workflow will automatically:
   - Build the image
   - Tag it as `v1.0.0`, `v1.0`, `v1`, and `latest`
   - Push all tags to GitHub Container Registry

### Permissions

The workflow requires these permissions (automatically granted):
- `contents: read` - Read repository code
- `packages: write` - Push images to GitHub Container Registry
- `id-token: write` - Generate attestations

### Caching

The workflow uses GitHub Actions cache to speed up builds:
- Docker layer caching reduces build time on subsequent runs
- Cache is shared between workflow runs
- Automatically cleaned up by GitHub after 7 days of inactivity

### Troubleshooting

**Build fails:**
- Check the Actions tab for detailed logs
- Verify Dockerfile syntax is correct
- Ensure all dependencies are available

**Can't pull image:**
- Make sure the repository is public, or authenticate:
  ```bash
  echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
  ```

**Old images showing:**
- Images are cached by Docker; force pull:
  ```bash
  docker pull ghcr.io/marshalmiller/acessiblity-auditor:latest --no-cache
  ```
