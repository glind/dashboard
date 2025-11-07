# Operations Guide

## Deployment Targets

Personal Dashboard supports multiple deployment options. Choose what fits your needs.

---

## 1. Docker (Recommended)

### Quick Start

```bash
# Using docker-compose (easiest)
cd personal-dashboard
docker-compose -f ops/docker-compose.yml up -d

# Access at http://localhost:8008
```

### Environment Configuration

Create `.env` file:

```bash
# Required
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_secret
GITHUB_TOKEN=your_token

# Optional
TICKTICK_CLIENT_ID=your_client_id
TICKTICK_CLIENT_SECRET=your_secret
OPENWEATHER_API_KEY=your_key
NEWSAPI_KEY=your_key
OLLAMA_HOST=http://host.docker.internal:11434
OPENAI_API_KEY=your_key
GEMINI_API_KEY=your_key
```

### With Local Ollama

```bash
# Start dashboard + Ollama
docker-compose --profile with-ollama up -d

# Pull Ollama models
docker exec -it personal-dashboard_ollama_1 ollama pull llama2
```

### Custom Build

```bash
# Build image
docker build -f ops/Dockerfile -t personal-dashboard:latest .

# Run container
docker run -d \
  --name dashboard \
  -p 8008:8008 \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  personal-dashboard:latest
```

### Health Check

```bash
# Check status
docker ps | grep dashboard

# View logs
docker logs -f dashboard

# Test health endpoint
curl http://localhost:8008/health
```

---

## 2. Kubernetes (Helm)

### Prerequisites

- Kubernetes cluster (1.20+)
- Helm 3.x installed
- kubectl configured

### Install Chart

```bash
# Add Buildly repo (when published)
helm repo add buildly https://charts.buildly.io
helm repo update

# Install
helm install dashboard buildly/personal-dashboard \
  --namespace personal \
  --create-namespace \
  --set env.GOOGLE_CLIENT_ID=your_id \
  --set env.GOOGLE_CLIENT_SECRET=your_secret \
  --set env.GITHUB_TOKEN=your_token

# Or use values file
helm install dashboard buildly/personal-dashboard \
  -f ops/helm/values-production.yaml
```

### Local Development (Helm)

```bash
# Install from local chart
cd ops/helm/personal-dashboard
helm install dashboard . \
  --values values.yaml \
  --namespace personal \
  --create-namespace

# Upgrade
helm upgrade dashboard . --values values.yaml

# Uninstall
helm uninstall dashboard --namespace personal
```

### Port Forward for Testing

```bash
kubectl port-forward -n personal svc/dashboard 8008:8008
```

### Check Status

```bash
# Pods
kubectl get pods -n personal

# Logs
kubectl logs -n personal -l app=dashboard -f

# Service
kubectl get svc -n personal
```

---

## 3. GitHub Pages (Static Docs Only)

The repository includes a GitHub Pages workflow for hosting documentation.

### Enable GitHub Pages

1. Go to repository **Settings > Pages**
2. Source: **GitHub Actions**
3. The `.github/workflows/pages.yml` workflow will automatically deploy

### Workflow File

Already included at `.github/workflows/pages.yml`:

```yaml
name: Deploy Docs to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build docs
        run: |
          mkdir -p public
          cp -r devdocs/* public/
      - name: Deploy
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./public
```

Docs will be available at: `https://[username].github.io/personal-dashboard/`

---

## 4. Desktop (Local Production)

### Systemd Service (Linux)

Create `/etc/systemd/system/dashboard.service`:

```ini
[Unit]
Description=Personal Dashboard
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/personal-dashboard
Environment="PATH=/home/youruser/personal-dashboard/.venv/bin"
ExecStart=/home/youruser/personal-dashboard/.venv/bin/python src/main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable dashboard
sudo systemctl start dashboard
sudo systemctl status dashboard
```

### LaunchAgent (macOS)

Create `~/Library/LaunchAgents/io.buildly.dashboard.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>io.buildly.dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/dashboard/.venv/bin/python</string>
        <string>/path/to/dashboard/src/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/dashboard</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/dashboard.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/dashboard.error.log</string>
</dict>
</plist>
```

Load and start:

```bash
launchctl load ~/Library/LaunchAgents/io.buildly.dashboard.plist
launchctl start io.buildly.dashboard
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# HTTP health endpoint
curl http://localhost:8008/health

# Expected response
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-11-05T..."
}
```

### Logs

**Docker:**
```bash
docker logs -f dashboard --tail=100
```

**Kubernetes:**
```bash
kubectl logs -n personal -l app=dashboard -f
```

**Systemd:**
```bash
journalctl -u dashboard -f
```

### Backups

**Database:**
```bash
# Backup
cp data/dashboard.db data/dashboard.db.backup-$(date +%Y%m%d)

# Restore
cp data/dashboard.db.backup-YYYYMMDD data/dashboard.db
```

**Configuration:**
```bash
# Backup
tar -czf config-backup-$(date +%Y%m%d).tar.gz config/ .env

# Restore
tar -xzf config-backup-YYYYMMDD.tar.gz
```

### Updates

**Docker:**
```bash
# Pull latest image
docker pull buildly/personal-dashboard:latest

# Restart with new image
docker-compose down
docker-compose up -d
```

**Helm:**
```bash
helm upgrade dashboard buildly/personal-dashboard --reuse-values
```

**Local:**
```bash
git pull origin main
source .venv/bin/activate
pip install -r requirements.txt --upgrade
./ops/startup.sh
```

---

## Performance Tuning

### Adjust Auto-Refresh

In the UI: **Settings > Auto-Refresh Interval** (default: 5 minutes)

### Disable Collectors

Edit `config/config.yaml`:

```yaml
collectors:
  enabled:
    - gmail
    - calendar
    - tasks
    # Comment out collectors you don't need
    # - github
    # - news
    # - weather
```

### Database Optimization

```bash
# Vacuum database (reduces size)
sqlite3 data/dashboard.db "VACUUM;"

# Analyze (optimizes queries)
sqlite3 data/dashboard.db "ANALYZE;"
```

---

## Security Considerations

- **Never commit** `.env` or `credentials.yaml`
- Use **secrets management** in production (Vault, AWS Secrets Manager)
- Enable **HTTPS** with reverse proxy (nginx, Traefik, Caddy)
- Restrict **port 8008** to localhost or internal network
- Rotate **API keys** periodically
- Review **SECURITY.md** for known risks

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs dashboard

# Common issues:
# - Missing environment variables
# - Port 8008 already in use
# - Volume permissions
```

### High Memory Usage

```bash
# Reduce collector frequency
# Disable unused collectors
# Limit AI model size (use smaller Ollama models)
```

### Slow Response

```bash
# Check API quotas (Google, GitHub, etc.)
# Optimize database: VACUUM and ANALYZE
# Reduce auto-refresh frequency
# Use caching (Redis) for large deployments
```

---

## Support

For deployment assistance during the 30-day support window, see `SUPPORT.md`.
