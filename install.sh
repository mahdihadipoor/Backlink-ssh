#!/bin/bash

# --- CONFIGURATION ---
GITHUB_USER="mahdihadipoor"
GITHUB_REPO="Backlink-ssh"
BRANCH="main"

BASE_URL="https://raw.githubusercontent.com/$GITHUB_USER/$GITHUB_REPO/$BRANCH"
INSTALL_DIR="/usr/local/backlink"
BIN_PATH="/usr/bin/backlink"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
PLAIN='\033[0m'

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run as root (sudo bash ...)${PLAIN}"
  exit 1
fi

echo -e "${GREEN}=== Backlink-SSH Installer ===${PLAIN}"

# 1. Install Dependencies
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    apt-get update && apt-get install -y python3
fi

# 2. Prepare Directory
mkdir -p $INSTALL_DIR

# 3. Download Files
echo "Downloading app.py..."
curl -s -o $INSTALL_DIR/app.py "$BASE_URL/app.py"

echo "Downloading Manager Menu..."
curl -s -o $BIN_PATH "$BASE_URL/backlink.sh"

if [ ! -s "$INSTALL_DIR/app.py" ] || [ ! -s "$BIN_PATH" ]; then
    echo -e "${RED}Failed to download files! Check your GitHub URL.${PLAIN}"
    exit 1
fi

chmod +x $INSTALL_DIR/app.py
chmod +x $BIN_PATH

echo -e "${GREEN}Installed Successfully!${PLAIN}"
echo -e "Type ${YELLOW}backlink${PLAIN} to open the panel."
sleep 1

# Launch
backlink