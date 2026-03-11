# Docker Deployment Guide

This guide explains how to deploy the Accessibility Auditor using Docker.

## Prerequisites

- Docker Engine 20.10 or later
- Docker Compose V2 or later

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/marshalmiller/acessiblity-auditor.git
cd acessiblity-auditor
```

### 2. Set up environment variables (optional)

```bash
cp .env.example .env
# Edit .env and set a secure SECRET_KEY
```

### 3. Build and run with Docker Compose

```bash
docker-compose up -d
```

This will:
- Build the Docker image
- Start the application on http://localhost:5000
- Create a volume for database persistence

### 4. Access the application

Open your browser and navigate to:
```
http://localhost:5000
```

## Using Pre-built Images

Instead of building locally, you can use pre-built images from GitHub Container Registry:

### 1. Pull the latest image

```bash
docker pull ghcr.io/marshalmiller/acessiblity-auditor:latest
```

### 2. Run with Docker

```bash
docker run -d \
  --name accessibility-auditor \
  -p 5000:5000 \
  -v $(pwd)/instance:/app/instance \
  -e SECRET_KEY="your-secret-key-here" \
  ghcr.io/marshalmiller/acessiblity-auditor:latest
```

### 3. Or use with Docker Compose

Use the pre-configured compose file:
```bash
docker-compose -f docker-compose.ghcr.yml up -d
```

Alternatively, update your `docker-compose.yml` by replacing the `build: .` line with:
```yaml
image: ghcr.io/marshalmiller/acessiblity-auditor:latest
```

Available tags:
- `latest` - Latest build from main branch
- `v1.0.0`, `v1.0`, `v1` - Semantic version tags
- `main-<sha>` - Specific commit from main branch

## Management Commands

### Start the application
```bash
docker-compose up -d
```

### Stop the application
```bash
docker-compose down
```

### View logs
```bash
docker-compose logs -f
```

### Restart the application
```bash
docker-compose restart
```

### Rebuild after code changes
```bash
docker-compose up -d --build
```

### Stop and remove all data (including database)
```bash
docker-compose down -v
```

## Customization

### Change the Port

Edit `docker-compose.yml` and modify the ports section:
```yaml
ports:
  - "8080:5000"  # Change 8080 to your desired port
```

### Generate a Secure Secret Key

Run this command to generate a secure secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Add it to your `.env` file:
```
SECRET_KEY=your-generated-key-here
```

## Database Persistence

The SQLite database is stored in the `./instance` folder on your host machine, which is mounted as a volume. This ensures your audit data persists across container restarts.

## Production Deployment

For production:

1. **Always set a secure SECRET_KEY** in your `.env` file
2. **Use a reverse proxy** (nginx, Caddy, Traefik) for HTTPS
3. **Increase workers** in Dockerfile if needed:
   ```dockerfile
   CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "app:app"]
   ```
4. **Set up monitoring** and logging
5. **Regular backups** of the `instance/` folder

## Troubleshooting

### Container fails to start

Check logs:
```bash
docker-compose logs
```

### Port already in use

Change the port in `docker-compose.yml` or stop the service using port 5000.

### Chromium browser issues

The Dockerfile installs Chromium and its dependencies. If issues occur:
```bash
docker-compose exec web playwright install chromium
docker-compose restart
```

### Database migration

If you need to run database migrations:
```bash
docker-compose exec web python migrate_db.py
```

## Architecture

- **Base Image**: Python 3.13-slim
- **Web Server**: Gunicorn with 2 workers (configurable)
- **Browser**: Chromium via Playwright
- **Database**: SQLite (upgradeable to PostgreSQL)
- **Port**: 5000 (internal), mapped to host

## Support

For issues or questions, please open an issue on the GitHub repository.
