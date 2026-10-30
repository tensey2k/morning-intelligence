# Morning Intelligence Assistant

A production-ready, Telegram-only personal morning briefing assistant for a Moroccan-Canadian financial analyst. Delivers daily intelligence at 9 AM Montreal time covering markets, news, weather, mortgage analysis, savings, and economic calendar.

## Features

- **🤖 Telegram Bot** - All interaction via Telegram with 10 commands
- **⏰ Automated Daily Delivery** - 9 AM America/Toronto (DST-aware) via APScheduler
- **📊 Market Data** - Oil (WTI/Brent), Crypto (BTC/ETH), Bonds (CA/US), Stock Indices, FX
- **📰 Financial News** - RSS + MarketAux (Canada, US, Morocco, Energy, Central Banks)
- **🌤️ Weather** - Montreal + Casablanca via Open-Meteo
- **📅 Economic Calendar** - FinanceCalendar (BoC, Fed, CPI, Employment, GDP, OPEC+)
- **🏠 Mortgage Intelligence** - Bond yield analysis, BoC expectations, affordability
- **💰 Savings & Finance** - TFSA/RRSP/FHSA, GIC rates, tax changes, fraud alerts
- **🔒 Secure** - Authorized user only, environment-based secrets, idempotent delivery
- **🐳 Dockerized** - Ready for Oracle Free Tier VPS deployment

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Oracle Free Tier VPS                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐     │
│  │   App       │  │ PostgreSQL  │  │ Redis (optional)    │     │
│  │ (Python)    │◄──│ (settings,  │  │ (caching, locks)    │     │
│  │             │  │  history)   │  │                     │     │
│  └──────┬──────┘  └─────────────┘  └─────────────────────┘     │
│         │                                                         │
│  ┌──────▼────────────────────────────────────────────────────┐  │
│  │              MORNING INTELLIGENCE SERVICE                   │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐  │  │
│  │  │  Scheduler  │ │  Telegram   │ │   Briefing Engine   │  │  │
│  │  │  (APScheduler)     Bot     │ │  (Validation, LLM)  │  │  │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │           DATA SOURCE PROVIDERS                      │  │  │
│  │  │  Weather │ Crypto │ Stocks │ Bonds │ Oil │ News     │  │  │
│  │  │  Calendar│ FX     │ Morocco│ Alerts│                  │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Sources (All Free)

| Data | Source | Free Tier | Auth |
|------|--------|-----------|------|
| Weather | Open-Meteo | Unlimited, no key | ❌ |
| Crypto | CoinGecko | 50 req/min | ❌ |
| Stocks/Indices/FX | Alpha Vantage | 5/min, 500/day | ✅ API Key |
| CA Bonds/FX/Policy | Bank of Canada Valet | Unlimited | ❌ |
| US Bonds/Fed/Inflation | FRED | 120/min | ✅ API Key |
| Oil Prices | EIA | Unlimited | ✅ API Key |
| Financial News | MarketAux + RSS | 100/mo + Unlimited | ✅ API Key |
| Economic Calendar | FinanceCalendar | 2000/day | ❌ |

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (for production)
- Telegram Bot Token (from @BotFather)
- Your Telegram User ID

### 1. Clone and Setup
```bash
git clone <repository-url>
cd morning-intelligence

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp config/.env.example config/.env
# Edit config/.env with your API keys and settings
```

Required `.env` values:
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_ALLOWED_USER_ID=your_numeric_telegram_user_id
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
FRED_API_KEY=your_fred_key
EIA_API_KEY=your_eia_key
MARKETAUX_API_KEY=your_marketaux_key
```

### 3. Run Locally
```bash
# Initialize database
python -m src.storage.database

# Start the bot
python -m src.main
```

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with quick action buttons |
| `/help` | Show all commands and usage examples |
| `/briefing [compact\|full\|detailed]` | Get morning briefing (default: full) |
| `/markets` | Current market indicators with timestamps |
| `/news [ca\|us\|ma\|energy\|cb\|housing\|econ]` | Financial news by category |
| `/weather [montreal\|morocco]` | Weather forecast with alerts |
| `/calendar [today\|week\|cb]` | Economic calendar events |
| `/mortgage` | Mortgage analyst intelligence |
| `/savings` | Savings & personal finance updates |
| `/settings` | View current preferences |
| `/settings time HH:MM` | Set delivery time (24hr) |
| `/settings timezone IANA_TZ` | Set timezone (e.g., America/Toronto) |
| `/settings location City` | Set weather location |
| `/settings language en\|fr\|ar` | Set language |
| `/settings schedule daily\|weekdays` | Set delivery schedule |
| `/settings mode compact\|full\|detailed` | Set briefing format |
| `/status` | System health, next run, data freshness |

## Oracle Free Tier VPS Deployment

### 1. Create Oracle Cloud Account
1. Go to https://www.oracle.com/cloud/free/
2. Sign up (credit card for verification only, **no charges**)
3. Verify email and phone

### 2. Create Compute Instance
- **Shape**: Ampere A1 Flex (4 OCPU, 24 GB RAM) - Always Free
- **Image**: Canonical Ubuntu 22.04 or 24.04
- **SSH Keys**: Add your public key
- **Network**: Create VCN with public subnet

### 3. Configure Security Lists
Add ingress rules for ports: 22 (SSH), 80 (HTTP), 443 (HTTPS), 8080 (App)

### 4. Run Setup Script
```bash
ssh ubuntu@<YOUR_VPS_IP>
curl -fsSL https://raw.githubusercontent.com/yourusername/morning-intelligence/main/scripts/setup-oracle-vps.sh | bash
# Log out and back in for Docker group changes
```

### 5. Clone and Deploy
```bash
git clone git@github.com:yourusername/morning-intelligence.git ~/morning-intelligence
cd ~/morning-intelligence
./scripts/deploy.sh
```

### 6. Configure SSL (Optional but Recommended)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### 7. Automated Backups (Cron)
```bash
# Add to crontab (runs daily at 2 AM)
0 2 * * * /home/ubuntu/morning-intelligence/scripts/backup.sh >> /home/ubuntu/morning-intelligence/logs/backup.log 2>&1
```

## API Keys Setup

### Required Keys

| Service | URL | Free Tier |
|---------|-----|-----------|
| **Groq** | https://console.groq.com/keys | 14,400 req/day |
| **Gemini** | https://aistudio.google.com/apikey | 1,500 req/day |
| **Alpha Vantage** | https://www.alphavantage.co/support/#api-key | 5/min, 500/day |
| **FRED** | https://fred.stlouisfed.org/docs/api/api_key.html | 120/min |
| **EIA** | https://www.eia.gov/opendata/register.php | Unlimited |
| **MarketAux** | https://www.marketaux.com/ | 100/mo |

### Optional Keys
- **OpenRouter**: https://openrouter.ai/keys (backup LLM)
- **Cloudflare Workers AI**: https://dash.cloudflare.com/ (backup LLM)
- **Bank Al-Maghrib**: https://apihelpdesk.centralbankofmorocco.ma/ (Morocco data)

## Project Structure

```
morning-intelligence/
├── config/
│   ├── .env              # Environment variables (not in git)
│   └── .env.example      # Template
├── src/
│   ├── main.py                    # Entry point
│   ├── config.py                  # Pydantic settings
│   ├── models.py                  # Pydantic data models
│   ├── data_sources/              # Data providers
│   │   ├── base.py                # Base class
│   │   ├── alpha_vantage.py       # Stocks, FX, Oil, Bonds
│   │   ├── bank_of_canada.py      # CA Bonds, Policy, FX, CPI
│   │   ├── coingecko.py           # Crypto prices
│   │   ├── open_meteo.py          # Weather
│   │   ├── fred.py                # US Economic data
│   │   ├── eia.py                 # Oil market data
│   │   ├── marketaux.py           # Financial news
│   │   ├── rss_news.py            # RSS news aggregation
│   │   ├── finance_calendar.py    # Economic calendar
│   │   └── manager.py             # Unified data access
│   ├── briefing/
│   │   ├── engine.py              # Briefing orchestration
│   │   ├── llm_client.py          # Multi-LLM (Groq→Gemini→OpenRouter→Cloudflare)
│   │   └── templates.py           # Briefing structure & formatting
│   ├── telegram/
│   │   ├── bot.py                 # Telegram bot setup
│   │   ├── commands.py            # Command handlers
│   │   ├── authorization.py       # User authorization
│   │   └── formatters.py          # Telegram message formatting
│   ├── scheduler/
│   │   └── manager.py             # APScheduler with timezone support
│   └── storage/
│       ├── database.py            # SQLAlchemy async setup
│       ├── models.py              # SQLAlchemy models
│       └── repository.py          # High-level DB operations
├── tests/                         # Unit & integration tests
├── scripts/
│   ├── deploy.sh                  # Production deployment
│   ├── backup.sh                  # Automated backups
│   └── setup-oracle-vps.sh        # Oracle VPS initial setup
├── docker-compose.yml             # Production stack
├── Dockerfile                     # Container image
└── requirements.txt               # Python dependencies
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_formatters.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Cost Breakdown (Monthly, CAD)

| Configuration | Hosting | Database | APIs | LLM | Total |
|---------------|---------|----------|------|-----|-------|
| **Budget (All Free)** | $0 (Oracle) | $0 (SQLite) | $0 | $0 (Groq) | **$0** |
| Balanced | $5.50 (Hetzner) | $15 (Managed PG) | $10 (MarketAux) | $3 | ~$34 |
| Premium | $11 (Hetzner) | $30 (Managed PG) | $99 (Twelve Data) | $15 | ~$155 |

## Monitoring & Health Checks

- **Health Endpoint**: `GET /health` (port 8080)
- **Telegram `/status`**: System health, next run, data freshness
- **Logs**: `docker compose logs -f app`
- **Database**: `docker compose exec db psql -U morning_user -d morning_intel`

## Troubleshooting

### Bot not responding
1. Check logs: `docker compose logs -f app`
2. Verify token: `grep TELEGRAM_BOT_TOKEN config/.env`
3. Check user ID: `grep TELEGRAM_ALLOWED_USER_ID config/.env`
4. Test bot: `curl "https://api.telegram.org/bot<TOKEN>/getMe"`

### Briefing not delivered
1. Check scheduler: `/status` command
2. Check logs for errors
3. Verify timezone: `date` on server should match America/Toronto
4. Run manually: `/briefing` command

### Data source failures
1. Check `/status` for health checks
2. Check API rate limits in logs
3. Verify API keys in `.env`

## Security Checklist

- [ ] `.env` not committed to git
- [ ] Strong PostgreSQL password generated
- [ ] Firewall configured (UFW)
- [ ] Fail2ban active
- [ ] SSH key authentication only
- [ ] Non-root user for app
- [ ] SSL/TLS configured for webhook (if used)
- [ ] Regular backups scheduled

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest tests/`
5. Submit a PR

## Support

For issues and questions, open a GitHub issue or check the troubleshooting section above.