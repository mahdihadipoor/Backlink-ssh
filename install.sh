#!/bin/bash

# --- CONFIGURATION ---
# !!! CHANGE THIS TO YOUR GITHUB DETAILS !!!
GITHUB_USER="mahdihadipoor"
GITHUB_REPO="Backlink-ssh"
BRANCH="main"

# Construct the Raw URL
BASE_URL="https://raw.githubusercontent.com/$GITHUB_USER/$GITHUB_REPO/$BRANCH"

INSTALL_DIR="/usr/local/tunpro"
BIN_PATH="/usr/bin/tunpro"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
PLAIN='\033[0m'

# Check Root
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}Please run as root (sudo bash ...)${PLAIN}"
  exit 1
fi

echo -e "${GREEN}=== SSH Tunnel Pro Installer ===${PLAIN}"
echo -e "${YELLOW}Fetching files from GitHub...${PLAIN}"

# 1. Install Dependencies
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    apt-get update && apt-get install -y python3
fi

# 2. Prepare Directory
mkdir -p $INSTALL_DIR

# 3. Download app.py (The Engine)
echo "Downloading app.py..."
curl -s -o $INSTALL_DIR/app.py "$BASE_URL/app.py"

if [ ! -s "$INSTALL_DIR/app.py" ]; then
    echo -e "${RED}Failed to download app.py! Check your repository URL.${PLAIN}"
    exit 1
fi

# 4. Download tunpro.sh (The Manager Menu) and set as binary
echo "Downloading Manager Menu..."
curl -s -o $BIN_PATH "$BASE_URL/tunpro.sh"

if [ ! -s "$BIN_PATH" ]; then
    echo -e "${RED}Failed to download tunpro.sh! Check your repository URL.${PLAIN}"
    exit 1
fi

chmod +x $INSTALL_DIR/app.py
chmod +x $BIN_PATH

# 5. Run the Manager to Configure
echo -e "${GREEN}Files installed successfully!${PLAIN}"
echo -e "Launching configuration wizard..."
sleep 1

# Launch the menu directly (it will handle service creation)
tunpro