# Morning Intelligence Assistant - Ubuntu VPS Deployment Guide

This guide provides step-by-step instructions to deploy the Morning Intelligence Assistant on an Ubuntu VPS. The bot is a lightweight Python Telegram bot that sends daily morning intelligence briefings at 9:00 AM Toronto time.

## Prerequisites

- Ubuntu 22.04 LTS or 24.04 LTS VPS
- Root or sudo access
- Domain name (optional, for SSL)
- Telegram Bot Token (from @BotFather)
- Your Telegram User ID

---

## Step 1: Initial Server Setup

### 1.1 Connect to Your VPS
```bash
ssh root@your-vps-ip
```

### 1.2 Update System Packages
```bash
apt update && apt upgrade -y
```

### 1.3 Install Required System Packages
```bash
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    ufw \
    fail2ban \
    htop \
    vim \
    python3-dev \
    build-essential \
    libpq-dev \
    pkg-config
```

### 1.4 Create Application User
```bash
adduser --disabled-password --gecos "" morningbot
usermod -aG sudo morningbot
```

### 1.4 Configure Firewall
```bash
ufw allow ssh
ufw allow 8080/tcp  # Health check endpoint
ufw enable
```

### 1.5 Configure Fail2Ban
```bash
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF

systemctl enable fail2ban
systemctl restart fail2ban
```

---

## Step 2: Application Setup

### 2.1 Switch to Application User
```bash
su - morningbot
```

### 2.2 Clone the Repository
```bash
cd /home/morningbot
git clone https://github.com/yourusername/morning-intelligence.git
cd morning-intelligence
```

> **Note**: Replace the GitHub URL with your actual repository URL. If deploying from local files, use `scp` to copy the project instead.

### 2.3 Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.4 Configure Environment Variables

Copy the example environment file and edit it:
```bash
cp config/.env.example config/.env
vim config/.env
```

Fill in all required values:

```env
# =============================================================================
# TELEGRAM (Required)
# =============================================================================
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ALLOWED_USER_ID=your_numeric_telegram_user_id

# =============================================================================
# LLM PROVIDERS (At least one required)
# =============================================================================
# Groq (PRIMARY - Recommended: fast, generous free tier)
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODEL=llama-3.1-8b-instant
GROQ_BASE_URL=https://api.groq.com/openai/v1

# Google Gemini (FALLBACK)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-1.5-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta

# OpenRouter (BACKUP)
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MAX_TOKENS=8000
OPENROUTER_TEMPERATURE=0.3

# Cloudflare Workers AI (BACKUP)
CLOUDFLARE_ACCOUNT_ID=your_cloudflare_account_id
CLOUDFLARE_API_TOKEN=your_cloudflare_api_token
CLOUDFLARE_MODEL=@cf/meta/llama-3.1-8b-instruct

# LLM Selection
LLM_PRIMARY=groq
LLM_FALLBACK=gemini

# =============================================================================
# MARKET DATA APIs
# =============================================================================
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
ALPHA_VANTAGE_BASE_URL=https://www.alphavantage.co/query

FRED_API_KEY=your_fred_key
FRED_BASE_URL=https://api.stlouisfed.org/fred

EIA_API_KEY=your_eia_key
EIA_BASE_URL=https://api.eia.gov/v2

MARKETAUX_API_KEY=your_marketaux_key
MARKETAUX_BASE_URL=https://api.marketaux.com/v1

BANK_AL_MAGHRIB_API_KEY=your_bam_key
BANK_AL_MAGHRIB_BASE_URL=https://apihelpdesk.centralbankofmorocco.ma

# =============================================================================
# SCHEDULING & TIMEZONE
# =============================================================================
TIMEZONE=America/Toronto
BRIEFING_HOUR=9
BRIEFING_MINUTE=0
SCHEDULE_WEEKDAYS_ONLY=false

# =============================================================================
# LOCATION SETTINGS
# =============================================================================
WEATHER_CITY=Montreal
WEATHER_COUNTRY=Canada
WEATHER_LATITUDE=45.5017
WEATHER_LONGITUDE=-73.5673
MOROCCO_WEATHER_CITY=Casablanca
MOROCCO_WEATHER_COUNTRY=Morocco
MOROCCO_WEATHER_LATITUDE=33.5731
MOROCCO_WEATHER_LONGITUDE=-7.5898

# =============================================================================
# LANGUAGE & OUTPUT
# =============================================================================
DEFAULT_LANGUAGE=en
ENABLED_LANGUAGES=en,fr,ar
BRIEFING_MODE=full

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL=INFO
```

### 2.5 Get Your Telegram User ID
1. Open Telegram and search for `@userinfobot`
2. Start the bot and it will reply with your numeric User ID
2. Add this ID to `TELEGRAM_ALLOWED_USER_ID` in `.env`

### 2.6 Set Correct Permissions
```bash
chmod 600 config/.env
```

---

## Step 3: Systemd Service Setup

### 3.1 Create Systemd Service File
```bash
sudo tee /etc/systemd/system/morning-intelligence.service << 'EOF'
[Unit]
Description=Morning Intelligence Assistant
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=morningbot
Group=morningbot
WorkingDirectory=/home/morningbot/morning-intelligence
Environment=PATH=/home/morningbot/morning-intelligence/venv/bin
ExecStart=/home/morningbot/morning-intelligence/venv/bin/python -m src.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/home/morningbot/morning-intelligence

# Resource limits
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF
```

### 3.2 Reload and Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable morning-intelligence
sudo systemctl start morning-intelligence
```

### 3.3 Check Service Status
```bash
sudo systemctl status morning-intelligence
```

---

## Step 4: Health Check Verification

### 4.1 Test Health Endpoint
```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": 1234567890.123,
  "components": {
    "Alpha Vantage": true,
    "Bank of Canada Valet": true,
    "CoinGecko": true,
    "Open-Meteo": true,
    "FinanceCalendar": true,
    "RSS News Aggregator": true,
    "FRED": true,
    "EIA": true,
    "MarketAux": true
  }
}
```

### 4.2 Test Telegram Bot
```bash
# Send a test message from the VPS
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
  -d chat_id=<YOUR_USER_ID> \
  -d text="🧪 Morning Intelligence Bot deployed successfully!"
```

---

## Step 5: Verify Scheduled Delivery

### 5.1 Check Next Scheduled Run
```bash
# Check logs for scheduler status
journalctl -u morning-intelligence -f | grep -i "scheduled\|briefing"
```

### 5.2 Test Manual Briefing
```bash
# Trigger a manual briefing via Telegram
# Send /briefing command to your bot in Telegram
```

---

## Step 6: Monitoring & Maintenance

### 6.1 Log Rotation
```bash
sudo tee /etc/logrotate.d/morning-intelligence << 'EOF'
/home/morningbot/morning-intelligence/morning_intelligence.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 morningbot morningbot
}
EOF
```

### 6.2 Automated Backups (Optional)
```bash
# Create backup script
cat > /home/morningbot/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/morningbot/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
tar -czf $BACKUP_DIR/morning-intelligence-$DATE.tar.gz \
    -C /home/morningbot/morning-intelligence \
    --exclude=venv \
    --exclude=__pycache__ \
    --exclude=.git \
    --exclude=backups \
    .
# Keep last 30 days
find $BACKUP_DIR -name "morning-intelligence-*.tar.gz" -mtime +30 -delete
EOF
chmod +x /home/morningbot/backup.sh

# Add to crontab (run daily at 2 AM)
crontab -e
# Add: 0 2 * * * /home/morningbot/backup.sh >> /home/morningbot/logs/backup.log 2>&1
```

### 6.3 Update Procedure
```bash
# Create update script
cat > /home/morningbot/update.sh << 'EOF'
#!/bin/bash
cd /home/morningbot/morning-intelligence
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart morning-intelligence
EOF
chmod +x /home/morningbot/update.sh
```

---

## Step 7: SSL/HTTPS (Optional - for Webhook Mode)

If you want to use webhooks instead of polling:

### 7.1 Install Nginx
```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 7.2 Configure Nginx
```bash
sudo tee /etc/nginx/sites-available/morning-intelligence << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location /webhook {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://localhost:8080;
    }
}
EOF
```

### 7.3 Enable Site and Get SSL
```bash
sudo ln -s /etc/nginx/sites-available/morning-intelligence /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo certbot --nginx -d your-domain.com
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Bot doesn't respond | Check `journalctl -u morning-intelligence -f` for errors |
| API rate limits | Check logs for 429 errors; ensure API keys are valid |
| Briefing not delivered | Check `/status` command in Telegram; check logs |
| Scheduler not running | Check `journalctl -u morning-intelligence -f | grep -i scheduler` |
| Health check fails | Verify all API keys in `.env` are valid |

### Useful Commands

```bash
# View logs
journalctl -u morning-intelligence -f

# Check service status
systemctl status morning-intelligence

# Restart service
sudo systemctl restart morning-intelligence

# View environment
cat /home/morningbot/morning-intelligence/config/.env

# Manual briefing test
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d chat_id=<YOUR_ID> \
  -d text="/briefing"
```

---

## Security Checklist

- [ ] `.env` file has `600` permissions
- [ ] Firewall only allows SSH (22) and health check (8080)
- [ ] Fail2Ban is running
- [ ] Non-root user runs the service
- [ ] Systemd service has security hardening enabled
- [ ] API keys are not committed to git
- [ ] Regular updates scheduled (`apt update && apt upgrade`)
- [ ] SSH key-based authentication only (disable password auth)

---

## Quick Start Checklist

- [ ] VPS created and accessible via SSH
- [ ] System packages updated
- [ ] Application user created
- [ ] Firewall configured
- [ ] Repository cloned
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] `.env` configured with all API keys
- [ ] Systemd service created and enabled
- [ ] Health check endpoint responding
- [ ] Telegram bot responding to commands
- [ ] Scheduled delivery tested
- [ ] Logs rotating properly
- [ ] Backup strategy in place
- [ ] Monitoring alerts configured

---

## Support

For issues:
1. Check logs: `journalctl -u morning-intelligence -f`
2. Verify API keys are valid and not expired
3. Check Telegram bot token is correct
4. Ensure user ID is correctly configured
5. Check API rate limits haven't been exceeded

---

**Deployment Complete!** 🎉

Your Morning Intelligence Assistant is now running on your Ubuntu VPS, automatically delivering personalized morning intelligence briefings every day at 9:00 AM Toronto time.