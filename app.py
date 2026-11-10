import os
import urllib.request
import tarfile
import subprocess
import json

# 1. Скачиваем официальный бинарник sing-box
if not os.path.exists("sing-box"):
    print("Downloading sing-box binary...")
    url = "https://github.com/SagerNet/sing-box/releases/download/v1.11.4/sing-box-1.11.4-linux-amd64.tar.gz"
    urllib.request.urlretrieve(url, "sb.tar.gz")
    with tarfile.open("sb.tar.gz", "r:gz") as tar:
        for member in tar.getmembers():
            if member.name.endswith("sing-box"):
                member.name = "sing-box"
                tar.extract(member, ".")
    os.chmod("sing-box", 0o755)

# 2. Получаем порт от платформы
port = int(os.environ.get("PORT", 8080))
uuid = os.environ.get("UUID", "d313e0fb-5090-4d86-bd80-5ebeaffeb78f")

# 3. Конфиг VLESS WebSocket
config = {
    "log": {"level": "info"},
    "inbounds": [{
        "type": "vless",
        "tag": "vless-in",
        "listen": "0.0.0.0",
        "listen_port": port,
        "users": [{"uuid": uuid}],
        "transport": {"type": "ws", "path": "/ray"}
    }],
    "outbounds": [{"type": "direct"}]
}

with open("config.json", "w") as f:
    json.dump(config, f)

# 4. Запуск
print(f"Starting sing-box on port {port}...")
subprocess.run(["./sing-box", "run", "-c", "config.json"])
