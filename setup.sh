#!/bin/bash
# ================================================
#   🤖 Social Media Downloader Bot - Setup
#   Termux ke liye
# ================================================

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════╗"
echo "║  SM Downloader Bot - Setup       ║"
echo "╚══════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}📦 System packages install ho rahe hain...${NC}"
pkg update -y && pkg upgrade -y
pkg install -y python ffmpeg git

echo -e "${YELLOW}🐍 Python packages install ho rahe hain...${NC}"
pip install python-telegram-bot==20.7 yt-dlp aiohttp aiofiles --break-system-packages

echo -e "\n${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${CYAN}══════════════════════════════${NC}"
echo -e "${YELLOW}📝 Ab config.py edit karo:${NC}"
echo ""
echo "  nano config.py"
echo ""
echo "  Yeh values change karo:"
echo "  • BOT_TOKEN  ← @BotFather se lo"
echo "  • ADMIN_IDS  ← @userinfobot se ID pata karo"
echo ""
echo -e "${CYAN}══════════════════════════════${NC}"
echo -e "${YELLOW}🚀 Bot chalane ke liye:${NC}"
echo ""
echo "  python bot.py"
echo ""
echo -e "${CYAN}══════════════════════════════${NC}"
echo -e "${YELLOW}💡 Background mein chalane ke liye:${NC}"
echo ""
echo "  pkg install screen"
echo "  screen -S mybot"
echo "  python bot.py"
echo "  # Ctrl+A phir D — detach karo"
echo ""
