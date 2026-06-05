#!/bin/bash
set -e

REPO_URL="https://github.com/DennyBeus/grabogram.git"
INSTALL_DIR="grabogram"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo ""
echo -e "\033[1;36m"
cat << 'EOF'
 ██████╗ ██████╗  █████╗ ██████╗  ██████╗  ██████╗ ██████╗  █████╗ ███╗   ███╗
██╔════╝ ██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██╔════╝ ██╔══██╗██╔══██╗████╗ ████║
██║  ███╗██████╔╝███████║██████╔╝██║   ██║██║  ███╗██████╔╝███████║██╔████╔██║
██║   ██║██╔══██╗██╔══██║██╔══██╗██║   ██║██║   ██║██╔══██╗██╔══██║██║╚██╔╝██║
╚██████╔╝██║  ██║██║  ██║██████╔╝╚██████╔╝╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
EOF
echo -e "\033[0;90m                        developed by DennyBeus\033[0m"
echo ""

# ── 1. Check dependencies ─────────────────────────────
if ! command -v curl &>/dev/null; then
    error "'curl' is required but not installed.\n  Ubuntu/Debian: apt-get install -y curl\n  CentOS/RHEL:   yum install -y curl\n  Fedora:        dnf install -y curl"
fi
success "Dependencies are in order."

# ── 2. Install Docker ─────────────────────────────────
if command -v docker &>/dev/null; then
    success "Docker is already installed: $(docker --version)"
else
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    success "Docker installed."
fi

# ── 3. Clone repository ───────────────────────────────
if [ -f "parser.py" ] && [ -f "docker-compose.yml" ]; then
    info "Already in the project folder, skipping clone."
elif [ -d "$INSTALL_DIR" ]; then
    info "Folder $INSTALL_DIR already exists, skipping clone."
    cd "$INSTALL_DIR"
else
    info "Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    success "Repository cloned."
fi

# ── 4. Configure .env ─────────────────────────────────
if [ -f ".env" ]; then
    echo ""
    read -r -p ".env file already exists. Overwrite? [y/N]: " overwrite
    if [[ "$overwrite" != "y" && "$overwrite" != "Y" ]]; then
        info "Keeping the existing .env."
    else
        rm .env
    fi
fi

if [ ! -f ".env" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "             Environment variables setup              "
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${CYAN}API_ID and API_HASH${NC} — credentials for accessing the Telegram API:"
    echo "  → Go to https://my.telegram.org"
    echo "  → Open «API development tools» → create an application"
    echo "  → Copy the App api_id and App api_hash values"
    echo ""
    read -r -p "  API_ID: " API_ID
    read -r -p "  API_HASH: " API_HASH
    echo ""
    echo -e "${CYAN}PHONE_NUMBER${NC} — phone number of the Telegram account used for parsing:"
    echo "  → Format: +79001234567 (with country code)"
    echo "  → Channels will be parsed from this account"
    echo ""
    read -r -p "  PHONE_NUMBER: " PHONE_NUMBER
    echo ""
    echo -e "${CYAN}TELEGRAM_BOT_TOKEN${NC} — Telegram bot token (control interface):"
    echo "  → Open @BotFather in Telegram"
    echo "  → Send the /newbot command and follow the instructions"
    echo "  → Copy the token, e.g.: 123456789:ABC-DEF1234ghIkl-zyx57W2v..."
    echo ""
    read -r -p "  TELEGRAM_BOT_TOKEN: " TELEGRAM_BOT_TOKEN
    echo ""
    echo -e "${CYAN}TELEGRAM_BOT_OWNER_ID${NC} — your numeric Telegram ID:"
    echo "  → Open @userinfobot in Telegram"
    echo "  → Send /start — the bot will show your Id (numeric, without @)"
    echo ""
    read -r -p "  TELEGRAM_BOT_OWNER_ID: " TELEGRAM_BOT_OWNER_ID
    echo ""

    # Optional proxy
    read -r -p "Configure a proxy? (needed if Telegram is blocked in the server's region) [y/N]: " use_proxy
    PROXY_SCHEME=""
    PROXY_HOSTNAME=""
    PROXY_PORT=""
    PROXY_USERNAME=""
    PROXY_PASSWORD=""
    if [[ "$use_proxy" == "y" || "$use_proxy" == "Y" ]]; then
        read -r -p "  PROXY_SCHEME (http/socks5): " PROXY_SCHEME
        read -r -p "  PROXY_HOSTNAME: " PROXY_HOSTNAME
        read -r -p "  PROXY_PORT: " PROXY_PORT
        read -r -p "  PROXY_USERNAME (leave empty if no authentication): " PROXY_USERNAME
        if [ -n "$PROXY_USERNAME" ]; then
            read -r -p "  PROXY_PASSWORD: " PROXY_PASSWORD
        fi
    fi

    printf "API_ID=%s\nAPI_HASH=%s\nPHONE_NUMBER=%s\n\nTELEGRAM_BOT_TOKEN=%s\nTELEGRAM_BOT_OWNER_ID=%s\n\nDATA_DIR=/app/data\nOUTPUT_DIR=/app/tmp\n\nPROXY_SCHEME=%s\nPROXY_HOSTNAME=%s\nPROXY_PORT=%s\nPROXY_USERNAME=%s\nPROXY_PASSWORD=%s\n" \
        "$API_ID" "$API_HASH" "$PHONE_NUMBER" \
        "$TELEGRAM_BOT_TOKEN" "$TELEGRAM_BOT_OWNER_ID" \
        "$PROXY_SCHEME" "$PROXY_HOSTNAME" "$PROXY_PORT" "$PROXY_USERNAME" "$PROXY_PASSWORD" \
        > .env
    success ".env file created."
fi

mkdir -p data

# ── 5. Build and run Docker ───────────────────────────
info "Building Docker image..."
docker compose build

info "Starting container..."
docker compose up -d

# Wait for startup
info "Waiting for the container to start..."
for i in $(seq 1 15); do
    STATUS=$(docker inspect --format='{{.State.Status}}' grabogram 2>/dev/null || echo "not_found")
    if [ "$STATUS" = "running" ]; then
        success "Container is running."
        break
    fi
    if [ "$i" -eq 15 ]; then
        error "Container failed to start. Check: docker logs grabogram"
    fi
    sleep 2
done

# ── 6. Initial userbot authorization ──────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "     Authorizing the Telegram account for parsing     "
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "You need to authorize once — Telegram will send a code"
echo "to the app or via SMS. After that, you can re-authorize"
echo "right through the bot with the /auth command (no server login needed)."
echo ""
read -r -p "Ready? Press Enter to start authorization..."
docker exec -it grabogram python parser.py --auth

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "\033[1;32m       ✓  Installation completed successfully!   \033[0m"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "\033[1;37mThe bot is running.\033[0m Open the bot you created via @BotFather in Telegram."
echo ""
echo -e "\033[1;33m  Commands:\033[0m"
echo "  /start                 — main menu"
echo "  /parse <URL> [options] — quick parse"
echo "  /auth                  — refresh the session (if expired)"
echo "  /cancel                — cancel the current action"
echo ""
echo -e "\033[1;33m  Example:\033[0m"
echo -e "  \033[0;36m/parse https://t.me/durov -s 01.01.2024 -e 31.12.2024 -f json -k bitcoin\033[0m"
echo ""
echo -e "\033[1;33m  Server:\033[0m"
echo "  docker logs grabogram        — logs"
echo "  docker compose restart       — restart"
echo "  docker compose down          — stop"
echo ""
