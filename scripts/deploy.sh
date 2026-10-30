#!/bin/bash
# Morning Intelligence Assistant - Deployment Script
# Run this script on your Oracle Free Tier VPS to deploy the application

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Morning Intelligence Assistant - Deploy${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please do not run this script as root${NC}"
    exit 1
fi

# Update system
echo -e "\n${YELLOW}[1/8] Updating system packages...${NC}"
sudo apt update && sudo apt upgrade -y

# Install Docker
echo -e "\n${YELLOW}[2/8] Installing Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo -e "${YELLOW}Docker installed. You may need to log out and back in for group changes.${NC}"
else
    echo -e "${GREEN}Docker already installed${NC}"
fi

# Install Docker Compose
echo -e "\n${YELLOW}[3/8] Installing Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    sudo apt install -y docker-compose-plugin
    echo -e "${GREEN}Docker Compose installed${NC}"
else
    echo -e "${GREEN}Docker Compose already available${NC}"
fi

# Create application directory
echo -e "\n${YELLOW}[4/8] Setting up application directory...${NC}"
APP_DIR="$HOME/morning-intelligence"
mkdir -p "$APP_DIR"/{data,logs,backups,config/ssl}
cd "$APP_DIR"

# Copy project files (assuming you've cloned the repo or copied files)
echo -e "\n${YELLOW}[5/8] Copying project files...${NC}"
# If using git:
# git clone https://github.com/yourusername/morning-intelligence.git .
# Or copy files manually

# Create .env file from example
echo -e "\n${YELLOW}[6/8] Creating environment configuration...${NC}"
if [ ! -f config/.env ]; then
    cp config/.env.example config/.env
    echo -e "${RED}IMPORTANT: Edit config/.env with your actual values!${NC}"
    echo -e "${YELLOW}Required values:${NC}"
    echo -e "  - TELEGRAM_BOT_TOKEN"
    echo -e "  - TELEGRAM_ALLOWED_USER_ID"
    echo -e "  - GROQ_API_KEY"
    echo -e "  - GEMINI_API_KEY"
    echo -e "  - ALPHA_VANTAGE_API_KEY"
    echo -e "  - FRED_API_KEY"
    echo -e "  - EIA_API_KEY"
    echo -e "  - MARKETAUX_API_KEY"
    echo -e "  - POSTGRES_PASSWORD (generate a secure password)"
else
    echo -e "${GREEN}.env file already exists${NC}"
fi

# Generate secure PostgreSQL password if not set
if ! grep -q "POSTGRES_PASSWORD=" config/.env || grep -q "POSTGRES_PASSWORD=$" config/.env; then
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
    sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$POSTGRES_PASSWORD/" config/.env
    echo -e "${GREEN}Generated secure PostgreSQL password${NC}"
fi

# Create necessary directories
echo -e "\n${YELLOW}[7/8] Creating data directories...${NC}"
mkdir -p data logs backups

# Build and start containers
echo -e "\n${YELLOW}[8/8] Building and starting containers...${NC}"
docker compose build
docker compose up -d

# Wait for services to be healthy
echo -e "\n${YELLOW}Waiting for services to start...${NC}"
sleep 10

# Check container status
echo -e "\n${GREEN}Container status:${NC}"
docker compose ps

# Show logs
echo -e "\n${YELLOW}Recent logs:${NC}"
docker compose logs --tail=50 app

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n${YELLOW}Next steps:${NC}"
echo -e "1. Edit config/.env with your API keys"
echo -e "2. Restart: docker compose restart app"
echo -e "3. Check logs: docker compose logs -f app"
echo -e "4. Test bot: Send /start to your bot on Telegram"
echo -e "\n${YELLOW}Useful commands:${NC}"
echo -e "  - View logs: docker compose logs -f app"
echo -e "  - Restart: docker compose restart app"
echo -e "  - Stop: docker compose down"
echo -e "  - Update: git pull && docker compose build && docker compose up -d"
echo -e "  - Backup DB: docker compose exec db pg_dump -U morning_user morning_intel > backup.sql"