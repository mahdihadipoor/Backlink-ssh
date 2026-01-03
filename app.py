import socket
import threading
import select
import time
import sys
import random
import argparse
import json
import os
import uuid

# --- CONFIGURATION ---
CONTROL_PORT = 8000
BUFFER_SIZE = 4096
APP_DIR = "/usr/local/backlink"
STATUS_FILE = os.path.join(APP_DIR, "status.json")
PORTS_FILE = os.path.join(APP_DIR, "ports.json")   # DB for Server (UUID -> Port)
CLIENT_ID_FILE = os.path.join(APP_DIR, "client_id.txt") # ID for Client

# --- GLOBAL STATE ---
server_sessions = {}  # Active sessions in memory
client_info = {}      # Client side state
persistent_ports = {} # Loaded from PORTS_FILE

# --- HELPERS ---

def print_banner():
    print("""
    ======================================
       BACKLINK-SSH | Persistent Tunnel
    ======================================
    """)

def load_persistent_ports():
    """Loads the UUID-to-Port mapping from disk."""
    global persistent_ports
    if os.path.exists(PORTS_FILE):
        try:
            with open(PORTS_FILE, 'r') as f:
                persistent_ports = json.load(f)
        except: persistent_ports = {}
    else:
        persistent_ports = {}

def save_persistent_ports():
    """Saves the UUID-to-Port mapping to disk."""
    try:
        with open(PORTS_FILE, 'w') as f:
            json.dump(persistent_ports, f)
    except Exception as e:
        print(f"[!] Failed to save ports DB: {e}")

def save_status(mode):
    data = {"mode": mode, "timestamp": time.time()}
    if mode == 'server':
        active_list = []
        for uid, info in server_sessions.items():
            active_list.append(info)
        data["sessions"] = active_list
    elif mode == 'client':
        data["vps_ip"] = client_info.get("vps_ip", "N/A")
        data["assigned_port"] = client_info.get("assigned_port", "Pending")
        data["connected"] = client_info.get("connected", False)
        data["uuid"] = client_info.get("uuid", "Unknown")

    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f)
    except: pass

def get_free_port():
    while True:
        port = random.randint(10000, 60000)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result != 0: return port

def bridge_traffic(admin_sock, agent_sock):
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
    client_uuid = "unknown"
    assigned_port = 0
    
    try:
        # 1. Wait for Client to Identify itself (Handshake)
        # Client sends: "ID:550e8400-e29b..."
        agent_sock.settimeout(5)
        initial_data = agent_sock.recv(1024).decode('utf-8').strip()
        agent_sock.settimeout(None)

        if not initial_data.startswith("ID:"):
            print(f"[!] Invalid handshake from {agent_addr}")
            return

        client_uuid = initial_data.split(":")[1]
        
        # 2. Determine Port (Persistence Logic)
        if client_uuid in persistent_ports:
            # Reuse existing port
            assigned_port = persistent_ports[client_uuid]
            print(f"[+] Known Agent {client_uuid[:8]}... reconnected. reusing Port: {assigned_port}", flush=True)
        else:
            # Assign new port
            assigned_port = get_free_port()
            persistent_ports[client_uuid] = assigned_port
            save_persistent_ports()
            print(f"[+] New Agent {client_uuid[:8]}... connected. Assigned Port: {assigned_port}", flush=True)

        # 3. Update Live Session State
        server_sessions[client_uuid] = {"ip": agent_addr[0], "port": assigned_port, "uuid": client_uuid}
        save_status('server')
        
        # 4. Tell Client the port
        agent_sock.sendall(f"PORT:{assigned_port}".encode('utf-8'))
        
        # 5. Listen for Admin
        admin_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        admin_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            admin_server.bind(('0.0.0.0', assigned_port))
            admin_server.listen(1)
        except Exception as bind_err:
            print(f"[!] Port {assigned_port} busy or error: {bind_err}")
            # If port is busy (maybe zombie process), we might need to fail or pick new one.
            # For now, we abort to keep DB consistent.
            return

        # Blocking wait for admin
        admin_sock, _ = admin_server.accept()
        print(f"[+] Admin connected to port {assigned_port}. Tunnel Active!", flush=True)
        admin_server.close()
        
        # 6. Bridge
        bridge_traffic(admin_sock, agent_sock)
        
    except Exception as e:
        print(f"[!] Session Error: {e}", flush=True)
    finally:
        agent_sock.close()
        if client_uuid in server_sessions:
            del server_sessions[client_uuid]
            save_status('server')
        print(f"[-] Session {client_uuid[:8]}... closed.", flush=True)

def run_server_mode():
    if not os.path.exists(APP_DIR): os.makedirs(APP_DIR)
    load_persistent_ports()
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

def get_client_uuid():
    """Reads or generates a unique ID for this client machine."""
    if os.path.exists(CLIENT_ID_FILE):
        with open(CLIENT_ID_FILE, 'r') as f:
            return f.read().strip()
    else:
        new_id = str(uuid.uuid4())
        if not os.path.exists(APP_DIR): os.makedirs(APP_DIR)
        with open(CLIENT_ID_FILE, 'w') as f:
            f.write(new_id)
        return new_id

def run_client_mode(server_ip):
    if not os.path.exists(APP_DIR): os.makedirs(APP_DIR)
    my_uuid = get_client_uuid()
    
    client_info['vps_ip'] = server_ip
    client_info['uuid'] = my_uuid
    client_info['connected'] = False
    save_status('client')
    
    print_banner()
    print(f"[*] Client UUID: {my_uuid}")

    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((server_ip, CONTROL_PORT))
            s.settimeout(None)
            
            # 1. Send Identity
            s.sendall(f"ID:{my_uuid}".encode('utf-8'))
            
            # 2. Receive Assigned Port
            data = s.recv(1024).decode('utf-8')
            if data.startswith("PORT:"):
                assigned_port = data.split(":")[1]
                
                client_info['assigned_port'] = assigned_port
                client_info['connected'] = True
                save_status('client')
                
                print(f"[+] Tunnel Established. Remote Port: {assigned_port}", flush=True)
                
                local_ssh = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                local_ssh.connect(('127.0.0.1', 22))
                bridge_traffic(s, local_ssh)
                
                print("[!] Tunnel closed. Reconnecting...", flush=True)
            else:
                print(f"[!] Unexpected response: {data}")
                s.close()
            
        except Exception as e: 
            # print(f"[!] Connection failed: {e}")
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
