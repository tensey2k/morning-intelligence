#!/bin/bash
# NUKE & DEPLOY - Morning Intelligence Assistant
# Run on fresh Ubuntu VPS: curl -sSL https://raw.githubusercontent.com/YOUR_REPO/main/nuke-and-deploy.sh | bash

set -euo pipefail

echo "NUKE: Cleaning previous installations..."
sudo systemctl stop morning-intel 2>/dev/null || true
sudo systemctl disable morning-intel 2>/dev/null || true
sudo rm -f /etc/systemd/system/morning-intel.service
sudo rm -rf /opt/morning-intel
sudo rm -rf /var/log/morning-intel
sudo userdel morning-intel 2>/dev/null || true

echo "INSTALL: System dependencies..."
apt-get update -qq
apt-get install -y -qq python3.11 python3.11-venv python3.11-dev git curl nginx certbot python3-certbot-nginx ufw fail2ban postgresql postgresql-contrib redis-server 2>/dev/null

echo "USER: Creating service user..."
id -u morning-intel &>/dev/null || useradd -r -s /bin/bash -d /opt/morning-intel morning-intel

echo "DIRS: Creating directories..."
mkdir -p /opt/morning-intel/{data,logs,backups,config}
chown -R morning-intel:morning-intel /opt/morning-intel

echo "POSTGRES: Setting up database..."
sudo -u postgres psql -c "CREATE USER morning_intel WITH PASSWORD 'changeme123';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE morning_intel OWNER morning_intel;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE morning_intel TO morning_intel;" 2>/dev/null || true

echo "VENV: Creating virtual environment..."
sudo -u morning-intel python3.11 -m venv /opt/morning-intel/venv
/opt/morning-intel/venv/bin/pip install --upgrade pip -q

echo "CLONE: Getting code..."
cd /opt/morning-intel
sudo -u morning-intel git clone https://github.com/YOUR_REPO/morning-intelligence.git app 2>/dev/null || sudo -u morning-intel git -C app pull

echo "DEPS: Installing Python packages..."
/opt/morning-intel/venv/bin/pip install -r /opt/morning-intel/app/requirements.txt -q

echo "️CONFIG: Creating .env from template..."
sudo -u morning-intel cp /opt/morning-intel/app/config/.env.example /opt/morning-intel/config/.env

echo "SECRETS: You MUST edit /opt/morning-intel/config/.env with your API keys!"
echo "   nano /opt/morning-intel/config/.env"

echo " DB INIT: Running migrations..."
cd /opt/morning-intel/app && sudo -u morning-intel /opt/morning-intel/venv/bin/python -c "
from src.storage.database import init_db
import asyncio
asyncio.run(init_db())
print('Database initialized')
"

echo "SYSTEMD: Creating service..."
cat > /etc/systemd/system/morning-intel.service << 'SVC'
[Unit]
Description=Morning Intelligence Assistant
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

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

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/morning-intel/data /opt/morning-intel/logs /opt/morning-intel/backups

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable morning-intel

echo "🌐 NGINX: Configuring reverse proxy..."
cat > /etc/nginx/sites-available/morning-intel << 'NGX'
server {
    listen 80;
    server_name YOUR_DOMAIN.com;

    location /health {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        return 403;
    }
}
NGX

ln -sf /etc/nginx/sites-available/morning-intel /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo "UFW: Configuring firewall..."
ufw --force enable
ufw allow ssh
ufw allow 'Nginx Full'

echo "FAIL2BAN: Configuring..."
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

echo "CRON: Adding backup job..."
(crontab -u morning-intel -l 2>/dev/null; echo "0 2 * * * /opt/morning-intel/app/scripts/backup.sh >> /opt/morning-intel/logs/backup.log 2>&1") | crontab -u morning-intel -

echo ""
echo "DEPLOYMENT COMPLETE!"
echo ""
echo "NEXT STEPS (REQUIRED):"
echo "1. Edit secrets: nano /opt/morning-intel/config/.env"
echo "2. Start service: systemctl start morning-intel"
echo "3. Check logs: journalctl -u morning-intel -f"
echo "4. Test health: curl http://localhost:8080/health"
echo ""
echo "REQUIRED .env KEYS:"
echo "   TELEGRAM_BOT_TOKEN=your_bot_token"
echo "   TELEGRAM_ALLOWED_USER_ID=your_user_id"
echo "   GROQ_API_KEY=your_groq_key"
echo "   GEMINI_API_KEY=your_gemini_key"
echo "   ALPHA_VANTAGE_API_KEY=your_av_key"
echo "   FRED_API_KEY=your_fred_key"
echo "   EIA_API_KEY=your_eia_key"
echo "   MARKETAUX_API_KEY=your_marketaux_key"
echo "   POSTGRES_PASSWORD=changeme123"
echo ""
echo "For HTTPS: certbot --nginx -d YOUR_DOMAIN.com"