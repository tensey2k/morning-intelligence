#!/bin/bash
# ============================================================
# DEPLOY TO VPS - Morning Intelligence Assistant
# Run this ON YOUR VPS as root: bash deploy-to-vps.sh
# ============================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  MORNING INTELLIGENCE - VPS DEPLOY${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ============================================================
# STEP 0: Check running as root
# ============================================================
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   echo "Run: sudo bash $0"
   exit 1
fi

# ============================================================
# STEP 1: Get the project files onto the VPS
# ============================================================
echo -e "${YELLOW}STEP 1: Copying project files to VPS...${NC}"

# The project files should already be on the VPS at /opt/morning-intel/app
# If not, we'll create the directory structure
mkdir -p /opt/morning-intel/{app,data,logs,backups,config}

# If running locally and want to sync to VPS, use:
# rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.pytest_cache' \
#   /local/path/morning-intelligence/ user@your-vps:/opt/morning-intel/app/

# For now, assume files are already at /opt/morning-intel/app
# If not, you need to copy them there first (see below)

# ============================================================
# STEP 2: System dependencies
# ============================================================
echo -e "${YELLOW}STEP 2: Installing system dependencies...${NC}"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3.11 python3.11-venv python3.11-dev \
    git curl nginx certbot python3-certbot-nginx \
    ufw fail2ban postgresql postgresql-contrib redis-server \
    build-essential libpq-dev 2>/dev/null

# ============================================================
# STEP 2b: PostgreSQL setup (optional - only if using PostgreSQL)
# ============================================================
echo -e "${YELLOW}Setting up PostgreSQL (optional)...${NC}"
# The app works with SQLite by default. Uncomment below if you want PostgreSQL:
# sudo -u postgres psql -c "CREATE USER morning_intel WITH PASSWORD 'changeme123';" 2>/dev/null || true
# sudo -u postgres psql -c "CREATE DATABASE morning_intel OWNER morning_intel;" 2>/dev/null || true
# sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE morning_intel TO morning_intel;" 2>/dev/null || true

# ============================================================
# STEP 3: Service user
# ============================================================
echo -e "${YELLOW}Creating service user...${NC}"
id -u morning-intel &>/dev/null || useradd -r -s /bin/bash -d /opt/morning-intel morning-intel

# ============================================================
# STEP 4: Directory structure and permissions
# ============================================================
echo -e "${YELLOW}Setting up directories...${NC}"
mkdir -p /opt/morning-intel/{app,data,logs,backups,config}
chown -R morning-intel:morning-intel /opt/morning-intel

# ============================================================
# STEP 4b: Ensure project files exist at /opt/morning-intel/app
# ============================================================
if [ ! -d "/opt/morning-intel/app/src" ]; then
    echo -e "${RED}ERROR: Project files not found at /opt/morning-intel/app${NC}"
    echo ""
    echo "You need to copy your project files to the VPS first."
    echo ""
    echo "FROM YOUR LOCAL MACHINE, run:"
    echo "  rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.pytest_cache' \\"
    echo "    /path/to/local/morning-intelligence/ \\"
    echo "    root@YOUR_VPS_IP:/opt/morning-intel/app/"
    echo ""
    echo "OR if using git:"
    echo "  cd /opt/morning-intel && git clone https://github.com/your-repo/morning-intelligence.git app"
    echo ""
    exit 1
fi

# ============================================================
# STEP 5: Virtual environment & dependencies
# ============================================================
echo -e "${YELLOW}Setting up Python virtual environment...${NC}"
sudo -u morning-intel python3.11 -m venv /opt/morning-intel/venv
/opt/morning-intel/venv/bin/pip install --upgrade pip -q
/opt/morning-intel/venv/bin/pip install -r /opt/morning-intel/app/requirements.txt -q

# ============================================================
# STEP 6: Configuration
# ============================================================
echo -e "${YELLOW}Setting up configuration...${NC}"
if [ ! -f /opt/morning-intel/config/.env ]; then
    if [ -f /opt/morning-intel/app/config/.env.example ]; then
        sudo -u morning-intel cp /opt/morning-intel/app/config/.env.example /opt/morning-intel/config/.env
        echo "Created .env from template. YOU MUST EDIT IT:"
        echo "  nano /opt/morning-intel/config/.env"
    else
        echo "WARNING: No .env.example found. Creating empty .env"
        touch /opt/morning-intel/config/.env
        chown morning-intel:morning-intel /opt/morning-intel/config/.env
    fi
else
    echo ".env already exists"
fi

# ============================================================
# STEP 7: Database initialization
# ============================================================
echo -e "${YELLOW}Initializing database...${NC}"
cd /opt/morning-intel/app && sudo -u morning-intel /opt/morning-intel/venv/bin/python -c "
import asyncio
import sys
sys.path.insert(0, '.')
from src.storage.database import init_db
import asyncio
asyncio.run(init_db())
print('Database initialized successfully')
"

# ============================================================
# STEP 8: Systemd service
# ============================================================
echo -e "${YELLOW}Creating systemd service...${NC}"
cat > /etc/systemd/system/morning-intel.service << 'SVC'
[Unit]
Description=Morning Intelligence Assistant
After=network.target
Wants=network.target

[Service]
Type=simple
User=morning-intel
Group=morning-intel
WorkingDirectory=/opt/morning-intel/app
Environment=PYTHONPATH=/opt/morning-intel/app
EnvironmentFile=/opt/morning-intel/config/.env
ExecStart=/opt/morning-intel/venv/bin/python -m src.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=morning-intel

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/morning-intel/data /opt/morning-intel/logs /opt/morning-intel/backups /opt/morning-intel/config

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable morning-intel

# ============================================================
# STEP 9: Nginx (optional - for health checks)
# ============================================================
echo -e "${YELLOW}Configuring Nginx (optional)...${NC}"
cat > /etc/nginx/sites-available/morning-intel << 'NGX'
server {
    listen 80;
    server_name _;

    location /health {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        return 403;
    }
}
NGX

ln -sf /etc/nginx/sites-available/morning-intel /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx 2>/dev/null || true

# ============================================================
# STEP 10: Firewall
# ============================================================
echo -e "${YELLOW}Configuring firewall...${NC}"
ufw --force enable
ufw allow ssh
ufw allow 'Nginx Full'

# ============================================================
# STEP 11: Fail2Ban
# ============================================================
echo -e "${YELLOW}Configuring Fail2Ban...${NC}"
cat > /etc/fail2ban/jail.local << 'F2B'
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
F2B

systemctl enable fail2ban
systemctl restart fail2ban

# ============================================================
# STEP 12: Cron backup
# ============================================================
echo -e "${YELLOW}Setting up backup cron...${NC}"
cat > /opt/morning-intel/app/scripts/backup.sh << 'BCK'
#!/bin/bash
# Backup script for Morning Intelligence
BACKUP_DIR="/opt/morning-intel/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

# Backup database (SQLite)
if [ -f /opt/morning-intel/data/morning_intelligence.db ]; then
    cp /opt/morning-intel/data/morning_intelligence.db "$BACKUP_DIR/morning_intelligence_$DATE.db"
fi

# Backup config
cp /opt/morning-intel/config/.env "$BACKUP_DIR/.env_$DATE" 2>/dev/null || true

# Keep only last 30 days
find "$BACKUP_DIR" -name "*.db" -mtime +30 -delete
find "$BACKUP_DIR" -name ".env_*" -mtime +30 -delete

echo "Backup completed: $DATE"
BCK

chmod +x /opt/morning-intel/app/scripts/backup.sh
chown morning-intel:morning-intel /opt/morning-intel/app/scripts/backup.sh

(crontab -u morning-intel -l 2>/dev/null; echo "0 2 * * * /opt/morning-intel/app/scripts/backup.sh >> /opt/morning-intel/logs/backup.log 2>&1") | crontab -u morning-intel -

# ============================================================
# DONE
# ============================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}REQUIRED NEXT STEPS:${NC}"
echo ""
echo "1. EDIT CONFIGURATION (REQUIRED):"
echo "   nano /opt/morning-intel/config/.env"
echo ""
echo "   REQUIRED KEYS TO SET:"
echo "     TELEGRAM_BOT_TOKEN=9031414114:AAHreb1bj7EMDRmkd6aXp-4lYwKG1-_njBs"
echo "     TELEGRAM_ALLOWED_USER_ID=YOUR_TELEGRAM_USER_ID"
echo "     GROQ_API_KEY=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"
echo "     GEMINI_API_KEY=AQ.Ab8RN6KhO0NN6HdB5hGOL2FmPtKIyCAKUIKGXctUbWBh7UrgiA"
echo "     ALPHA_VANTAGE_API_KEY=IVZESP215TRMK0OX"
echo "     FRED_API_KEY=f303b830b0b359decb9a48ef185b23a6"
echo "     EIA_API_KEY=TGJLtHTBrLKGwnCHMRqdjGdQrDTz6jh6NP6GrcPf"
echo "     MARKETAUX_API_KEY=u4lF47mlvHuHtv31cgclMAnYwiZylxZHBmNo9cxz"
echo ""
echo "2. START THE SERVICE:"
echo "   systemctl start morning-intel"
echo ""
echo "3. CHECK LOGS:"
echo "   journalctl -u morning-intel -f"
echo ""
echo "4. TEST HEALTH ENDPOINT:"
echo "   curl http://localhost:8080/health"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  DEPLOYMENT SCRIPT COMPLETE${NC}"
echo -e "${GREEN}========================================${NC}"