#!/bin/bash
set -e

REPO_URL="https://github.com/DennyBeus/tg-channel-parser.git"
INSTALL_DIR="tg-channel-parser"

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
 ██████╗ ██████╗ ███████╗███╗   ██╗    ██████╗  █████╗ ██████╗ ███████╗███████╗██████╗
██╔═══██╗██╔══██╗██╔════╝████╗  ██║    ██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝██╔══██╗
██║   ██║██████╔╝█████╗  ██╔██╗ ██║    ██████╔╝███████║██████╔╝███████╗█████╗  ██████╔╝
██║   ██║██╔═══╝ ██╔══╝  ██║╚██╗██║    ██╔═══╝ ██╔══██║██╔══██╗╚════██║██╔══╝  ██╔══██╗
╚██████╔╝██║     ███████╗██║ ╚████║    ██║     ██║  ██║██║  ██║███████║███████╗██║  ██║
 ╚═════╝ ╚═╝     ╚══════╝╚═╝  ╚═══╝   ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝
EOF
echo -e "\033[0;90m                   Telegram Channel Parser - developed by DennyBeus\033[0m"
echo ""

# ── 1. Проверка ОС ───────────────────────────────────
if [ -f /etc/os-release ]; then
    . /etc/os-release
    if [[ "$ID" != "ubuntu" && "$ID" != "debian" && "$ID_LIKE" != *"debian"* ]]; then
        warn "Этот скрипт оптимизирован для Ubuntu/Debian. Продолжаем на свой страх и риск."
    fi
else
    warn "Не удалось определить ОС. Продолжаем..."
fi

# ── 2. Установка Docker ───────────────────────────────
if command -v docker &>/dev/null; then
    success "Docker уже установлен: $(docker --version)"
else
    info "Устанавливаю Docker..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg lsb-release
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    success "Docker установлен."
fi

# ── 3. Клонирование репозитория ───────────────────────
if [ -f "parser.py" ] && [ -f "docker-compose.yml" ]; then
    info "Уже в папке проекта, пропускаю клонирование."
elif [ -d "$INSTALL_DIR" ]; then
    info "Папка $INSTALL_DIR уже существует, пропускаю клонирование."
    cd "$INSTALL_DIR"
else
    info "Клонирую репозиторий..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    success "Репозиторий клонирован."
fi

# ── 4. Настройка .env ─────────────────────────────────
if [ -f ".env" ]; then
    echo ""
    read -r -p "Файл .env уже существует. Перезаписать? [y/N]: " overwrite
    if [[ "$overwrite" != "y" && "$overwrite" != "Y" ]]; then
        info "Оставляю существующий .env."
    else
        rm .env
    fi
fi

if [ ! -f ".env" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "            Настройка переменных окружения            "
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo -e "${CYAN}API_ID и API_HASH${NC} — данные для доступа к Telegram API:"
    echo "  → Зайди на https://my.telegram.org"
    echo "  → Раздел «API development tools» → создай приложение"
    echo "  → Скопируй значения App api_id и App api_hash"
    echo ""
    read -r -p "  API_ID: " API_ID
    read -r -p "  API_HASH: " API_HASH
    echo ""
    echo -e "${CYAN}PHONE_NUMBER${NC} — номер телефона Telegram-аккаунта для парсинга:"
    echo "  → Формат: +79001234567 (с кодом страны)"
    echo "  → С этого аккаунта будет производиться парсинг каналов"
    echo ""
    read -r -p "  PHONE_NUMBER: " PHONE_NUMBER
    echo ""
    echo -e "${CYAN}TELEGRAM_BOT_TOKEN${NC} — токен Telegram-бота (управляющий интерфейс):"
    echo "  → Открой @BotFather в Telegram"
    echo "  → Отправь команду /newbot, следуй инструкциям"
    echo "  → Скопируй токен вида: 123456789:ABC-DEF1234ghIkl-zyx57W2v..."
    echo ""
    read -r -p "  TELEGRAM_BOT_TOKEN: " TELEGRAM_BOT_TOKEN
    echo ""
    echo -e "${CYAN}TELEGRAM_BOT_OWNER_ID${NC} — твой числовой Telegram ID:"
    echo "  → Открой @userinfobot в Telegram"
    echo "  → Отправь /start — бот покажет твой Id (числовой, без @)"
    echo ""
    read -r -p "  TELEGRAM_BOT_OWNER_ID: " TELEGRAM_BOT_OWNER_ID
    echo ""

    # Опциональный прокси
    read -r -p "Настроить прокси? (нужно если Telegram заблокирован в регионе сервера) [y/N]: " use_proxy
    PROXY_SCHEME=""
    PROXY_HOSTNAME=""
    PROXY_PORT=""
    PROXY_USERNAME=""
    PROXY_PASSWORD=""
    if [[ "$use_proxy" == "y" || "$use_proxy" == "Y" ]]; then
        read -r -p "  PROXY_SCHEME (http/socks5): " PROXY_SCHEME
        read -r -p "  PROXY_HOSTNAME: " PROXY_HOSTNAME
        read -r -p "  PROXY_PORT: " PROXY_PORT
        read -r -p "  PROXY_USERNAME (оставь пустым если без авторизации): " PROXY_USERNAME
        if [ -n "$PROXY_USERNAME" ]; then
            read -r -p "  PROXY_PASSWORD: " PROXY_PASSWORD
        fi
    fi

    printf "API_ID=%s\nAPI_HASH=%s\nPHONE_NUMBER=%s\n\nTELEGRAM_BOT_TOKEN=%s\nTELEGRAM_BOT_OWNER_ID=%s\n\nDATA_DIR=/app/data\nOUTPUT_DIR=/app/tmp\n\nPROXY_SCHEME=%s\nPROXY_HOSTNAME=%s\nPROXY_PORT=%s\nPROXY_USERNAME=%s\nPROXY_PASSWORD=%s\n" \
        "$API_ID" "$API_HASH" "$PHONE_NUMBER" \
        "$TELEGRAM_BOT_TOKEN" "$TELEGRAM_BOT_OWNER_ID" \
        "$PROXY_SCHEME" "$PROXY_HOSTNAME" "$PROXY_PORT" "$PROXY_USERNAME" "$PROXY_PASSWORD" \
        > .env
    success "Файл .env создан."
fi

mkdir -p data

# ── 5. Сборка и запуск Docker ─────────────────────────
info "Собираю Docker-образ..."
docker compose build

info "Запускаю контейнер..."
docker compose up -d

# Ожидание запуска
info "Жду запуска контейнера..."
for i in $(seq 1 15); do
    STATUS=$(docker inspect --format='{{.State.Status}}' tg-parser 2>/dev/null || echo "not_found")
    if [ "$STATUS" = "running" ]; then
        success "Контейнер запущен."
        break
    fi
    if [ "$i" -eq 15 ]; then
        error "Контейнер не запустился. Проверь: docker logs tg-parser"
    fi
    sleep 2
done

# ── 6. Первичная авторизация userbot ─────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "      Авторизация Telegram-аккаунта для парсинга      "
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Нужно авторизоваться один раз — Telegram пришлёт код"
echo "в приложение или SMS. После этого переавторизацию можно"
echo "делать прямо через бота командой /auth (без входа на сервер)."
echo ""
read -r -p "Готов? Нажми Enter для начала авторизации..."
docker exec -it tg-parser python parser.py --auth

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
success "Установка завершена!"
echo ""
echo "Бот запущен. Открой в Telegram бота, которого создал через @BotFather."
echo ""
echo "Команды:"
echo "  /start          — главное меню"
echo "  /parse <URL> [опции]  — быстрый парсинг"
echo "  /auth           — обновить сессию (если истекла)"
echo "  /cancel         — отменить текущее действие"
echo ""
echo "Пример:"
echo "  /parse https://t.me/durov -s 01.01.2024 -e 31.12.2024 -f json -k bitcoin"
echo ""
echo "Полезные команды сервера:"
echo "  docker logs tg-parser        — логи"
echo "  docker compose restart       — перезапуск"
echo "  docker compose down          — остановка"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
