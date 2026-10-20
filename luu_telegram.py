#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nhap token bot Telegram + chat id, luu vao config.local.json (khong dua len GitHub).
Giu nguyen token Accesstrade dang co. Chay bang nhap_telegram.bat."""
import json
import os
import re
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "config.local.json")

try:
    with open(PATH, encoding="utf-8") as f:
        cfg = json.load(f)
except Exception:
    cfg = {}

print("Token bot lay tu @BotFather (dang 123456789:ABC...).")
while True:
    bot = input("Dan TOKEN BOT roi bam Enter: ").strip()
    if not re.fullmatch(r"\d{6,}:[\w-]{30,}", bot):
        print("  -> Khong phai token bot (phai co dang 123456789:AAH...). Mo @BotFather > /mybots > chon bot > API Token.\n")
        continue
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{bot}/getMe", timeout=30) as r:
            name = json.loads(r.read().decode("utf-8")).get("result", {}).get("username", "")
        print(f"  -> Token dung, bot: @{name}")
        break
    except Exception as e:
        print(f"  -> Telegram bao token sai ({e}). Copy lai tu @BotFather.\n")
print("\nChat id: so cua anh hoac cua nhom (nhom thuong bat dau bang -100...).")
print("Chua biet thi nhan 1 tin bat ky cho bot (hoac vao nhom co bot), roi de trong o duoi va bam Enter.")
chat = input("Dan CHAT ID (hoac de trong): ").strip()

if not chat and bot:
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{bot}/getUpdates", timeout=30) as r:
            ups = json.loads(r.read().decode("utf-8")).get("result", [])
        chats = {}
        for u in ups:
            m = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
            c = m.get("chat") or {}
            if c.get("id"):
                chats[c["id"]] = c.get("title") or c.get("first_name") or ""
        if chats:
            print("\nTim thay:")
            for i, (cid, name) in enumerate(chats.items(), 1):
                print(f"  {i}. {name}  ({cid})")
            pick = input("Chon so (Enter = 1): ").strip() or "1"
            chat = str(list(chats)[int(pick) - 1])
        else:
            print("Chua thay tin nhan nao toi bot. Hay nhan cho bot 1 tin roi chay lai file nay.")
    except Exception as e:
        print("Khong hoi duoc Telegram:", e)

if not (bot and chat):
    input("\nCHUA LUU (thieu token hoac chat id). Bam Enter de dong.")
    raise SystemExit(1)

cfg["telegram_bot_token"], cfg["telegram_chat_id"] = bot, chat
with open(PATH, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=1)

try:
    data = urllib.parse.urlencode({"chat_id": chat, "text": "✅ Bot deal TikTok đã kết nối với máy anh."}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{bot}/sendMessage", data=data, timeout=30).read()
    print("\nDA LUU. Telegram vua nhan tin thu, anh mo Telegram kiem tra nhe.")
except Exception as e:
    print("\nDA LUU, nhung gui tin thu loi:", e, "\n(Kiem tra lai token / chat id, bot phai duoc them vao nhom.)")
input("Bam Enter de dong.")
