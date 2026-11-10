import os
import sys
import socket
import threading
import subprocess
import urllib.request
import tarfile
import json

# 1. Скачиваем бинарник sing-box
if not os.path.exists("sing-box"):
    print("Downloading sing-box...")
    url = "https://github.com/SagerNet/sing-box/releases/download/v1.11.4/sing-box-1.11.4-linux-amd64.tar.gz"
    urllib.request.urlretrieve(url, "sb.tar.gz")
    with tarfile.open("sb.tar.gz", "r:gz") as tar:
        for m in tar.getmembers():
            if m.name.endswith("sing-box"):
                m.name = "sing-box"
                tar.extract(m, ".")
    os.chmod("sing-box", 0o755)

uuid = os.environ.get("UUID", "d313e0fb-5090-4d86-bd80-5ebeaffeb78f")

# 2. Конфигурация стран в sing-box
config = {
    "log": {"level": "info"},
    "inbounds": [
        # Вход: Германия (напрямую)
        {
            "type": "vless", "tag": "in-de", "listen": "127.0.0.1", "listen_port": 5001,
            "users": [{"uuid": uuid}], "transport": {"type": "ws", "path": "/de"}
        },
        # Вход: Россия
        {
            "type": "vless", "tag": "in-ru", "listen": "127.0.0.1", "listen_port": 5003,
            "users": [{"uuid": uuid}], "transport": {"type": "ws", "path": "/ru"}
        },
        # Вход: США
        {
            "type": "vless", "tag": "in-us", "listen": "127.0.0.1", "listen_port": 5004,
            "users": [{"uuid": uuid}], "transport": {"type": "ws", "path": "/us"}
        }
    ],
    "outbounds": [
        {"type": "direct", "tag": "direct-de"},
        # Российский шлюз
        {
            "type": "socks", "tag": "out-ru",
            "server": "94.131.119.141", "server_port": 1080
        },
        # США шлюз
        {
            "type": "socks", "tag": "out-us",
            "server": "142.93.0.24", "server_port": 1080
        }
    ],
    "route": {
        "rules": [
            {"inbound": "in-de", "outbound": "direct-de"},
            {"inbound": "in-ru", "outbound": "out-ru"},
            {"inbound": "in-us", "outbound": "out-us"}
        ]
    }
}

with open("config.json", "w") as f:
    json.dump(config, f)

subprocess.Popen(["./sing-box", "run", "-c", "config.json"])

# 3. Маршрутизатор по путям (/de, /ru, /us)
port = int(os.environ.get("PORT", 5000))

def pipe(src, dst):
    try:
        while True:
            data = src.recv(4096)
            if not data: break
            dst.sendall(data)
    except: pass
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def handle_client(sock):
    try:
        header = sock.recv(4096, socket.MSG_PEEK)
        target_port = 5001 # по умолчанию Германия
        if b"/ru" in header:
            target_port = 5003 # Россия
        elif b"/us" in header:
            target_port = 5004 # США
        elif b"/de" in header or b"/ray" in header:
            target_port = 5001 # Германия

        if b"Upgrade: websocket" in header:
            backend = socket.create_connection(("127.0.0.1", target_port))
            threading.Thread(target=pipe, args=(sock, backend), daemon=True).start()
            threading.Thread(target=pipe, args=(backend, sock), daemon=True).start()
        else:
            sock.recv(4096)
            sock.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
            sock.close()
    except:
        try: sock.close()
        except: pass

srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", port))
srv.listen(128)
print(f"Multi-country gateway started on {port}...")

while True:
    s, _ = srv.accept()
    threading.Thread(target=handle_client, args=(s,), daemon=True).start()
