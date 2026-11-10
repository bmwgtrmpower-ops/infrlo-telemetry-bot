import os
import sys
import socket
import threading
import subprocess
import urllib.request
import tarfile
import json

# 1. Скачиваем официальный бинарник sing-box
if not os.path.exists("sing-box"):
    print("Downloading sing-box binary...")
    url = "https://github.com/SagerNet/sing-box/releases/download/v1.11.4/sing-box-1.11.4-linux-amd64.tar.gz"
    urllib.request.urlretrieve(url, "sb.tar.gz")
    with tarfile.open("sb.tar.gz", "r:gz") as tar:
        for m in tar.getmembers():
            if m.name.endswith("sing-box"):
                m.name = "sing-box"
                tar.extract(m, ".")
    os.chmod("sing-box", 0o755)

# 2. Настраиваем sing-box на внутренний порт 5001
uuid = os.environ.get("UUID", "d313e0fb-5090-4d86-bd80-5ebeaffeb78f")
config = {
    "log": {"level": "info"},
    "inbounds": [{
        "type": "vless",
        "tag": "vless-in",
        "listen": "127.0.0.1",
        "listen_port": 5001,
        "users": [{"uuid": uuid}],
        "transport": {"type": "ws", "path": "/ray"}
    }],
    "outbounds": [{"type": "direct"}]
}
with open("config.json", "w") as f:
    json.dump(config, f)

# 3. Запускаем sing-box
subprocess.Popen(["./sing-box", "run", "-c", "config.json"])

# 4. Слушаем порт 5000 для Infrlo и проверок здоровья
port = int(os.environ.get("PORT", 5000))

def pipe(src, dst):
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except:
        pass
    finally:
        try: src.close()
        except: pass
        try: dst.close()
        except: pass

def handle_client(client_sock):
    try:
        header = client_sock.recv(4096, socket.MSG_PEEK)
        if b"Upgrade: websocket" in header or b"/ray" in header:
            # VPN WebSocket-трафик -> перенаправляем в sing-box
            backend = socket.create_connection(("127.0.0.1", 5001))
            t1 = threading.Thread(target=pipe, args=(client_sock, backend))
            t2 = threading.Thread(target=pipe, args=(backend, client_sock))
            t1.start()
            t2.start()
        else:
            # Проверка здоровья от Infrlo -> возвращаем HTTP 200 OK
            client_sock.recv(4096)
            resp = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK"
            client_sock.sendall(resp)
            client_sock.close()
    except:
        try: client_sock.close()
        except: pass

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", port))
server.listen(128)
print(f"Health check & VLESS proxy listening on port {port}...")

while True:
    sock, _ = server.accept()
    threading.Thread(target=handle_client, args=(sock,), daemon=True).start()
