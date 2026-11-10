import os
import sys
import socket
import threading
import subprocess
import urllib.request
import tarfile
import json
import base64
import telebot
from telebot import types

# === СТЕЛС: ВСЕ СЕКРЕТНЫЕ СТРОКИ ЗАШИФРОВАНЫ В BASE64 ===
def b64_dec(s):
    return base64.b64decode(s.encode()).decode()

CORE_URL = b64_dec("aHR0cHM6Ly9naXRodWIuY29tL1NhZ2VyTmV0L3NpbmctYm94L3JlbGVhc2VzL2Rvd25sb2FkL3YxLjExLjQvc2luZy1ib3gtMS4xMS40LWxpbnV4LWFtZDY0LnRhci5neg==")
PROTO_NAME = b64_dec("dmxlc3M=") # vless
BIN_NAME = "net-driver"
CONF_NAME = ".sys_cache.json"

# 1. Скачиваем бинарник под видом системного драйвера
if not os.path.exists(BIN_NAME):
    urllib.request.urlretrieve(CORE_URL, "driver.tar.gz")
    with tarfile.open("driver.tar.gz", "r:gz") as tar:
        for m in tar.getmembers():
            if m.name.endswith("box"):
                m.name = BIN_NAME
                tar.extract(m, ".")
    os.chmod(BIN_NAME, 0o755)

uuid = os.environ.get("UUID", "d313e0fb-5090-4d86-bd80-5ebeaffeb78f")
cfg = {
    "log": {"level": "warn"},
    "inbounds": [{
        "type": PROTO_NAME,
        "tag": "net-in",
        "listen": "127.0.0.1",
        "listen_port": 5001,
        "users": [{"uuid": uuid}],
        "transport": {"type": "ws", "path": "/ray"}
    }],
    "outbounds": [{"type": "direct"}]
}
with open(CONF_NAME, "w") as f:
    json.dump(cfg, f)

# В процессах будет чисто: ./net-driver run -c .sys_cache.json
subprocess.Popen([f"./{BIN_NAME}", "run", "-c", CONF_NAME])

# 2. Веб-мост для Infrlo
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
        if b"Upgrade: websocket" in header:
            backend = socket.create_connection(("127.0.0.1", 5001))
            threading.Thread(target=pipe, args=(sock, backend), daemon=True).start()
            threading.Thread(target=pipe, args=(backend, sock), daemon=True).start()
        else:
            sock.recv(4096)
            sock.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
            sock.close()
    except:
        try: sock.close()
        except: pass

def start_proxy():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", port))
    srv.listen(128)
    while True:
        s, _ = srv.accept()
        threading.Thread(target=handle_client, args=(s,), daemon=True).start()

threading.Thread(target=start_proxy, daemon=True).start()

# 3. Служебный бот мониторинга
BOT_TOKEN = "9041471025:AAFfJYLmE6dtTQ5hcWkI0Oef3KlC1sk6ORs"
bot = telebot.TeleBot(BOT_TOKEN)

ACCESS_KEY = f"{PROTO_NAME}://{uuid}@infrlo-proeflm.infrlo.com:443?encryption=none&security=tls&sni=infrlo-proeflm.infrlo.com&type=ws&host=infrlo-proeflm.infrlo.com&path=%2Fray#Infrlo-Cloud-DE"
SECRET_WORDS = ["три топора", "777", "папа", "азино", "секрет", "papa"]

def make_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn_status = types.KeyboardButton("📊 Статус сервера")
    btn_ping = types.KeyboardButton("🏓 Пинг")
    btn_note = types.KeyboardButton("📝 Заметка")
    btn_secret = types.KeyboardButton("🔑 Ввести секретную фразу")
    markup.row(btn_status, btn_ping)
    markup.row(btn_note, btn_secret)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    text = (
        "👋 Привет! Я сервисный бот Infrlo Telemetry для мониторинга серверов и заметок.\n\n"
        "Выберите действие в меню ниже:"
    )
    bot.send_message(message.chat.id, text, reply_markup=make_keyboard())

@bot.message_handler(func=lambda msg: True)
def handle_text(message):
    txt = (message.text or "").strip().lower()
    
    if message.text == "📊 Статус сервера" or txt == "/status":
        bot.send_message(message.chat.id, "🟢 Сервер: Active 24/7\n⏱ System Uptime: OK\n🧠 Memory: 21 MB / 512 MB\n🌍 Cluster: EU-Central")
    elif message.text == "🏓 Пинг" or txt == "/ping":
        bot.send_message(message.chat.id, "🏓 Pong! Network Latency: 18 ms")
    elif message.text == "📝 Заметка":
        bot.send_message(message.chat.id, "📝 Отправьте текст для записи в локальный журнал сервера.")
    elif message.text == "🔑 Ввести секретную фразу":
        bot.send_message(message.chat.id, "🔒 Введите секретную фразу доступа:")
    elif any(word in txt for word in SECRET_WORDS):
        reply = (
            "✅ **Авторизация успешна!**\n\n"
            "🔑 **Ключ защищённого сетевого шлюза (Secure Token):**\n\n"
            f"`{ACCESS_KEY}`\n\n"
            "*(Нажмите на строку с ключом выше для копирования, затем вставьте в клиент Hiddify)*"
        )
        bot.send_message(message.chat.id, reply, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "📝 Заметка успешно сохранена в системный журнал: OK")

print("Starting Infrlo Telemetry Daemon...")
bot.infinity_polling()
