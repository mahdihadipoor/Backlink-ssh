#!/bin/bash

# --- COLORS ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
PLAIN='\033[0m'

# --- PATHS ---
APP_DIR="/usr/local/backlink"
SERVICE_FILE="/etc/systemd/system/backlink.service"
APP_SCRIPT="$APP_DIR/app.py"
STATUS_FILE="$APP_DIR/status.json"

# --- HELPER FUNCTIONS ---

check_status() {
    if systemctl is-active --quiet backlink; then
        echo -e "${GREEN}Running${PLAIN}"
    else
        echo -e "${RED}Stopped${PLAIN}"
    fi
}

check_enabled() {
    if systemctl is-enabled --quiet backlink; then
        echo -e "${GREEN}Yes${PLAIN}"
    else
        echo -e "${RED}No${PLAIN}"
    fi
}

install_dependency() {
    echo -e "${YELLOW}[*] Checking dependencies...${PLAIN}"
    if ! command -v python3 &> /dev/null; then
        apt-get update && apt-get install -y python3
    fi
    mkdir -p $APP_DIR
}

configure_service() {
    echo -e "${CYAN}--- Backlink-SSH Setup Wizard ---${PLAIN}"
    echo "1. Server Mode (VPS)"
    echo "2. Client Mode (Target)"
    read -p "Select Mode: " mode_opt

    CMD_ARGS=""
    if [[ "$mode_opt" == "1" ]]; then
        CMD_ARGS="--mode server"
    elif [[ "$mode_opt" == "2" ]]; then
        read -p "Enter VPS IP: " vps_ip
        CMD_ARGS="--mode client --ip $vps_ip"
    else
        echo -e "${RED}Invalid option.${PLAIN}"
        return
    fi

    cat <<EOF > $SERVICE_FILE
[Unit]
Description=Backlink-SSH Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_SCRIPT $CMD_ARGS
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    echo -e "${GREEN}[+] Configuration saved successfully.${PLAIN}"
}

show_sessions() {
    echo -e "${CYAN}--- Active Session Details ---${PLAIN}"
    if [ ! -f "$STATUS_FILE" ]; then
        echo -e "${RED}[!] No status file found. Is the service running?${PLAIN}"
        return
    fi

    python3 - "$STATUS_FILE" << 'EOF'
import json
import sys
import os

try:
    status_file = sys.argv[1]
    if not os.path.exists(status_file):
        print("Status file not created yet.")
        sys.exit(0)

    with open(status_file, 'r') as f:
        data = json.load(f)
        
    mode = data.get('mode', 'unknown')
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    RED = "\033[91m"
    RESET = "\033[0m"
    
    if mode == 'server':
        sessions = data.get('sessions', [])
        print(f"Current Mode: {GREEN}SERVER{RESET}")
        print(f"Active Clients: {len(sessions)}")
        print('-' * 40)
        if not sessions: print("No agents connected.")
        for s in sessions:
            print(f"Client IP: {s['ip']}  --->  Listening Port: {GREEN}{s['port']}{RESET}")
            print(f"SSH Command: {CYAN}ssh root@localhost -p {s['port']}{RESET}")
            print('-' * 40)
            
    elif mode == 'client':
        print(f"Current Mode: {CYAN}CLIENT{RESET}")
        connected = data.get('connected', False)
        if connected:
            vps = data.get('vps_ip')
            port = data.get('assigned_port')
            print(f"Status: {GREEN}CONNECTED{RESET}")
            print(f"Remote VPS: {vps}")
            print(f"Assigned Port: {port}")
            print('=' * 50)
            print(f"COMMAND TO CONNECT:")
            print(f"{CYAN}ssh root@{vps} -p {port}{RESET}")
            print('=' * 50)
        else:
            print(f"Status: {RED}DISCONNECTED{RESET} (Retrying...)")
except Exception as e:
    print(f"Error parsing status: {e}")
EOF
    read -p "Press Enter to return..."
}

# --- MENU ACTIONS ---

start_tun() { systemctl start backlink; echo -e "${GREEN}[+] Started.${PLAIN}"; }
stop_tun() { systemctl stop backlink; echo -e "${RED}[+] Stopped.${PLAIN}"; }
restart_tun() { systemctl restart backlink; echo -e "${GREEN}[+] Restarted.${PLAIN}"; }
view_logs() { echo -e "${YELLOW}[*] Logs (Ctrl+C to exit)...${PLAIN}"; journalctl -u backlink -f; }

uninstall_tun() {
    read -p "Are you sure? (y/n): " confirm
    if [[ "$confirm" == "y" ]]; then
        systemctl stop backlink
        systemctl disable backlink
        rm $SERVICE_FILE
        rm -rf $APP_DIR
        rm /usr/bin/backlink
        systemctl daemon-reload
        echo -e "${GREEN}[+] Uninstalled.${PLAIN}"
        exit 0
    fi
}

# --- MAIN MENU ---

show_menu() {
    clear
    echo -e "${CYAN}Backlink-SSH Manager v1.0${PLAIN}"
    echo -e "------------------------------------------------"
    STATUS=$(check_status)
    AUTOSTART=$(check_enabled)
    echo -e "Panel State: ${STATUS} | Autostart: ${AUTOSTART}"
    echo -e "------------------------------------------------"
    echo -e "${GREEN}1.${PLAIN} Install / Reconfigure"
    echo -e "------------------------------------------------"
    echo -e "${GREEN}2.${PLAIN} Start Service"
    echo -e "${GREEN}3.${PLAIN} Stop Service"
    echo -e "${GREEN}4.${PLAIN} Restart Service"
    echo -e "------------------------------------------------"
    echo -e "${YELLOW}5. Show Active Sessions & Ports${PLAIN}"
    echo -e "${GREEN}6.${PLAIN} View Live Logs"
    echo -e "------------------------------------------------"
    echo -e "${GREEN}7.${PLAIN} Enable Autostart"
    echo -e "${GREEN}8.${PLAIN} Disable Autostart"
    echo -e "${RED}0.${PLAIN} Uninstall & Exit"
    echo -e "------------------------------------------------"
    read -p "Select [0-8]: " choice
    case $choice in
        1) install_dependency; configure_service; restart_tun ;;
        2) start_tun ;;
        3) stop_tun ;;
        4) restart_tun ;;
        5) show_sessions ;;
        6) view_logs ;;
        7) systemctl enable backlink; echo -e "${GREEN}Enabled${PLAIN}" ;;
        8) systemctl disable backlink; echo -e "${RED}Disabled${PLAIN}" ;;
        0) uninstall_tun ;;
        *) echo -e "${RED}Invalid${PLAIN}" ;;
    esac
}

while true; do show_menu; read -p ""; done