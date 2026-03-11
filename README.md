# accessibility-auditor

A Flask-based web application for auditing websites and documents for accessibility issues, compliant with **WCAG 2.2 Level AA** standards.

## Features

- **URL Auditing**: Check live websites for accessibility violations using axe-core
- **File Auditing**: Upload and analyze HTML, PDF, and Word (.docx) files
- **Markdown Conversion**: Convert any webpage to accessible Markdown format using Jina AI Reader
- **Rerun Capability**: Re-audit URLs to track improvements over time
- **Historical Trends**: View score changes and violation trends across multiple audits
- **WCAG 2.2 AA Compliance**: Tests against the latest WCAG 2.2 Level AA standards
- **Markdown Cheat Sheet**: Built-in reference guide for Markdown syntax and accessibility best practices

## Supported Formats

- **Websites**: Any publicly accessible URL
- **HTML Files**: .html, .htm
- **PDF Documents**: .pdf
- **Word Documents**: .docx

## Markdown Conversion

The Markdown converter uses Jina AI Reader API to transform web pages into clean, accessible Markdown format. This makes content:
- Easier to read and navigate
- More accessible for screen readers
- Portable and editable
- Compatible with documentation tools

The built-in cheat sheet provides quick reference for Markdown syntax and accessibility tips.

## Standards

This auditor uses:
- **axe-core** for automated web accessibility testing (WCAG 2.2 AA)
- **PyMuPDF** for PDF document analysis
- **python-docx** for Word document analysis
- **Playwright** for browser-based testing
- **Jina AI Reader** for Markdown conversion

## Deployment

### Docker (Recommended)

Pre-built images are automatically published to GitHub Container Registry on every commit.

**Quick Start with Pre-built Image:**
```bash
docker pull ghcr.io/marshalmiller/acessiblity-auditor:latest
docker-compose up -d
```

**Or build locally:**
```bash
docker-compose up -d
```

See [DOCKER.md](DOCKER.md) for complete deployment instructions, including:
- Using pre-built images from GitHub Container Registry
- Building from source
- Production configuration
- Health monitoring

### Manual Setup

1. Install Python 3.13+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Run the application:
   ```bash
   python app.py
   ```

## Branding

This application is branded for Northampton Community College with:
- NCC color scheme (Blue #004C8E, Orange #FC5000, White #FFFFFF)
- Open Innovation Office attribution

To customize for your organization, edit [static/css/style.css](static/css/style.css).

## License

See [LICENSE](LICENSE) for details.