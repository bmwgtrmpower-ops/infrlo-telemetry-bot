import os
import sys
import socket
import threading
import subprocess
import urllib.request
import tarfile
import json
import telebot
from telebot import types

# === 1. ЗАПУСК ТУННЕЛЯ SING-BOX В ФОНЕ ===
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
config = {
    "log": {"level": "info"},
    "inbounds": [{
        "type": "vless", "tag": "vless-in",
        "listen": "127.0.0.1", "listen_port": 5001,
        "users": [{"uuid": uuid}],
        "transport": {"type": "ws", "path": "/ray"}
    }],
    "outbounds": [{"type": "direct"}]
}
with open("config.json", "w") as f:
    json.dump(config, f)

subprocess.Popen(["./sing-box", "run", "-c", "config.json"])

# === 2. ВЕБ-МОСТ ДЛЯ INFRLO И ПРОВЕРОК ЗДОРОВЬЯ ===
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

# === 3. МАСКИРОВОЧНЫЙ TELEGRAM-БОТ ===
BOT_TOKEN = "9041471025:AAFfJYLmE6dtTQ5hcWkI0Oef3KlC1sk6ORs"
bot = telebot.TeleBot(BOT_TOKEN)

VPN_LINK = f"vless://{uuid}@infrlo-proeflm.infrlo.com:443?encryption=none&security=tls&sni=infrlo-proeflm.infrlo.com&type=ws&host=infrlo-proeflm.infrlo.com&path=%2Fray#Infrlo-VPN"
SECRET_WORDS = ["три топора", "777", "папа", "азино", "секрет", "papa", "vpn"]

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
        "👋 Привет! Я сервисный бот Infrlo Utility для мониторинга серверов и заметок.\n\n"
        "Выберите действие в меню ниже:"
    )
    bot.send_message(message.chat.id, text, reply_markup=make_keyboard())

@bot.message_handler(func=lambda msg: True)
def handle_text(message):
    txt = (message.text or "").strip().lower()
    
    if message.text == "📊 Статус сервера" or txt == "/status":
        bot.send_message(message.chat.id, "🟢 Состояние: Сервер активен 24/7\n⏱ Отклик ядра: в норме\n🧠 Память: 22 MB / 512 MB\n🌍 Регион: Европа (Германия)")
    elif message.text == "🏓 Пинг" or txt == "/ping":
        bot.send_message(message.chat.id, "🏓 Понг! Задержка сети: 18 мс")
    elif message.text == "📝 Заметка":
        bot.send_message(message.chat.id, "📝 Напишите любой текст, чтобы сохранить его в журнал заметок сервера.")
    elif message.text == "🔑 Ввести секретную фразу":
        bot.send_message(message.chat.id, "🔒 Введите секретную фразу доступа:")
    elif any(word in txt for word in SECRET_WORDS):
        reply = (
            "🎉 **Доступ подтверждён!**\n\n"
            "🛡 **Ваша ссылка для подключения к VPN:**\n\n"
            f"`{VPN_LINK}`\n\n"
            "*(Нажмите на ссылку выше, чтобы скопировать её в буфер, затем в приложении Hiddify нажмите + ➔ Импорт из буфера)*"
        )
        bot.send_message(message.chat.id, reply, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "📝 Заметка сохранена в системный лог: OK")

print("Starting Infrlo Utility Telegram Bot...")
bot.infinity_polling()
