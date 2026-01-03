import socket
import threading
import select
import time
import sys
import random
import argparse
import json
import os

# --- CONFIGURATION ---
CONTROL_PORT = 8000
BUFFER_SIZE = 4096
# Updated Directory
APP_DIR = "/usr/local/backlink"
STATUS_FILE = os.path.join(APP_DIR, "status.json")

# --- GLOBAL STATE ---
server_sessions = {} 
client_info = {}     

# --- HELPERS ---

def print_banner():
    print("""
    ======================================
       BACKLINK-SSH | Reverse Tunnel v1.0
    ======================================
    """)

def save_status(mode):
    data = {"mode": mode, "timestamp": time.time()}
    if mode == 'server':
        active_list = []
        for port, ip in server_sessions.items():
            active_list.append({"ip": ip, "port": port})
        data["sessions"] = active_list
    elif mode == 'client':
        data["vps_ip"] = client_info.get("vps_ip", "N/A")
        data["assigned_port"] = client_info.get("assigned_port", "Pending")
        data["connected"] = client_info.get("connected", False)

    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[!] Failed to write status file: {e}")

def get_free_port():
    while True:
        port = random.randint(10000, 60000)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result != 0: return port

def bridge_traffic(admin_sock, agent_sock, assigned_port):
    inputs = [admin_sock, agent_sock]
    try:
        while True:
            readable, _, _ = select.select(inputs, [], [], 1.0)
            if not readable: continue
            for sock in readable:
                if sock is admin_sock:
                    data = admin_sock.recv(BUFFER_SIZE)
                    if not data: return
                    agent_sock.sendall(data)
                elif sock is agent_sock:
                    data = agent_sock.recv(BUFFER_SIZE)
                    if not data: return
                    admin_sock.sendall(data)
    except: pass
    finally:
        try: admin_sock.close()
        except: pass
        try: agent_sock.close()
        except: pass

# --- SERVER LOGIC ---

def handle_client_session(agent_sock, agent_addr):
    assigned_port = 0
    try:
        assigned_port = get_free_port()
        print(f"[+] Agent {agent_addr[0]} connected. Assigned Port: {assigned_port}", flush=True)
        
        server_sessions[assigned_port] = agent_addr[0]
        save_status('server')
        
        agent_sock.sendall(f"PORT:{assigned_port}".encode('utf-8'))
        
        admin_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        admin_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        admin_server.bind(('0.0.0.0', assigned_port))
        admin_server.listen(1)
        
        admin_sock, _ = admin_server.accept()
        print(f"[+] Admin connected to port {assigned_port}. Tunnel Active!", flush=True)
        admin_server.close()
        
        bridge_traffic(admin_sock, agent_sock, assigned_port)
        
    except Exception as e:
        print(f"[!] Session Error: {e}", flush=True)
    finally:
        agent_sock.close()
        if assigned_port in server_sessions:
            del server_sessions[assigned_port]
            save_status('server')
        print(f"[-] Session on port {assigned_port} closed.", flush=True)

def run_server_mode():
    if not os.path.exists(APP_DIR): os.makedirs(APP_DIR)
    save_status('server')
    
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind(('0.0.0.0', CONTROL_PORT))
        server_socket.listen(10)
        print_banner()
        print(f"[*] Backlink Server running on port {CONTROL_PORT}", flush=True)
        while True:
            client, addr = server_socket.accept()
            t = threading.Thread(target=handle_client_session, args=(client, addr))
            t.daemon = True
            t.start()
    except Exception as e:
        print(f"[!] Server Error: {e}")
        sys.exit(1)

# --- CLIENT LOGIC ---

def run_client_mode(server_ip):
    if not os.path.exists(APP_DIR): os.makedirs(APP_DIR)
    client_info['vps_ip'] = server_ip
    client_info['connected'] = False
    save_status('client')
    print_banner()

    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((server_ip, CONTROL_PORT))
            s.settimeout(None)
            
            data = s.recv(1024).decode('utf-8')
            if data.startswith("PORT:"):
                assigned_port = data.split(":")[1]
                
                client_info['assigned_port'] = assigned_port
                client_info['connected'] = True
                save_status('client')
                
                print(f"[+] Backlink Established. Remote Port: {assigned_port}", flush=True)
                
                local_ssh = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                local_ssh.connect(('127.0.0.1', 22))
                bridge_traffic(s, local_ssh, assigned_port)
                
                print("[!] Tunnel closed. Reconnecting...", flush=True)
            else: s.close()
            
        except: 
            time.sleep(5)
        finally:
            client_info['connected'] = False
            save_status('client')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['server', 'client'], required=True)
    parser.add_argument('--ip')
    args = parser.parse_args()
    if args.mode == 'server': run_server_mode()
    elif args.mode == 'client': run_client_mode(args.ip)