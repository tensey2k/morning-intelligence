#!/bin/bash
# Morning Intelligence Assistant - Oracle Free Tier VPS Setup
# Run this script on a fresh Oracle Cloud Ubuntu instance

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Oracle Free Tier VPS Setup${NC}"
echo -e "${GREEN}========================================${NC}"

# 1. System update
echo -e "\n${YELLOW}[1/10] Updating system...${NC}"
sudo apt update && sudo apt upgrade -y

# 2. Install essential packages
echo -e "\n${YELLOW}[2/10] Installing essential packages...${NC}"
sudo apt install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    ufw \
    fail2ban \
    docker.io \
    docker-compose-plugin \
    python3 \
    python3-pip \
    python3-venv \
    postgresql-client \
    redis-tools \
    jq

# 3. Configure firewall
echo -e "\n${YELLOW}[3/10] Configuring firewall...${NC}"
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8080/tcp
sudo ufw --force enable

# 4. Configure fail2ban
echo -e "\n${YELLOW}[4/10] Configuring fail2ban...${NC}"
sudo tee /etc/fail2ban/jail.local > /dev/null <<EOF
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

sudo systemctl enable fail2ban
sudo systemctl restart fail2ban

# 5. Docker setup
echo -e "\n${YELLOW}[5/10] Setting up Docker...${NC}"
sudo usermod -aG docker $USER
sudo systemctl enable docker
sudo systemctl start docker

# 6. Create swap file (important for 1GB RAM instances)
echo -e "\n${YELLOW}[6/10] Creating swap file...${NC}"
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo -e "${GREEN}2GB swap file created${NC}"
else
    echo -e "${GREEN}Swap file already exists${NC}"
fi

# 7. Set timezone
echo -e "\n${YELLOW}[7/10] Setting timezone...${NC}"
sudo timedatectl set-timezone America/Toronto

# 8. Install NVIDIA drivers (for Ampere instances - optional)
echo -e "\n${YELLOW}[8/10] Checking for NVIDIA GPU...${NC}"
if lspci | grep -i nvidia > /dev/null; then
    echo -e "${YELLOW}NVIDIA GPU detected, installing drivers...${NC}"
    sudo apt install -y nvidia-driver-535 nvidia-docker2
    sudo systemctl restart docker
else
    echo -e "${GREEN}No NVIDIA GPU detected (Ampere A1 Flex uses ARM)${NC}"
fi

# 9. Create application user and directory
echo -e "\n${YELLOW}[9/10] Creating application directory...${NC}"
APP_DIR="$HOME/morning-intelligence"
mkdir -p "$APP_DIR"/{data,logs,backups,config/ssl,scripts}

# 10. Generate SSH key for GitHub (if needed)
echo -e "\n${YELLOW}[10/10] SSH key for GitHub...${NC}"
if [ ! -f ~/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -C "morning-intel@$(hostname)" -f ~/.ssh/id_ed25519 -N ""
    echo -e "\n${GREEN}SSH key generated. Add this public key to GitHub:${NC}"
    cat ~/.ssh/id_ed25519.pub
else
    echo -e "${GREEN}SSH key already exists${NC}"
fi

# Final instructions
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Oracle VPS Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n${YELLOW}IMPORTANT NEXT STEPS:${NC}"
echo -e "1. ${RED}Log out and back in${NC} for Docker group changes"
echo -e "2. Clone the repository: ${GREEN}git clone git@github.com:yourusername/morning-intelligence.git $APP_DIR${NC}"
echo -e "3. Run the deploy script: ${GREEN}$APP_DIR/scripts/deploy.sh${NC}"
echo -e "4. Configure SSL with certbot: ${GREEN}sudo certbot --nginx -d yourdomain.com${NC}"
echo -e "\n${YELLOW}Firewall rules configured:${NC}"
sudo ufw status numbered
echo -e "\n${YELLOW}Docker version:${NC}"
docker --version
echo -e "\n${YELLOW}System info:${NC}"
echo -e "  CPU: $(nproc) cores"
echo -e "  RAM: $(free -h | awk '/^Mem:/ {print $2}')"
echo -e "  Disk: $(df -h / | awk 'NR==2 {print $4}') free"
echo -e "  Swap: $(free -h | awk '/^Swap:/ {print $2}')"