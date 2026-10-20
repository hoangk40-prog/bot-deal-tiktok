#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nhap kenh Telegram de bot tu dang tung san pham, luu vao config.local.json. Chay bang nhap_kenh.bat.
Truoc do: tao kenh, them bot lam QUAN TRI VIEN (co quyen dang tin)."""
import json
import os
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "config.local.json")

try:
    with open(PATH, encoding="utf-8") as f:
        cfg = json.load(f)
except Exception:
    cfg = {}
bot = str(cfg.get("telegram_bot_token", "")).strip()
if not bot:
    input("Chua co token bot. Chay nhap_telegram.bat truoc. Bam Enter de dong.")
    raise SystemExit(1)

print("Kenh cong khai: nhap ten kenh dang @ten_kenh (lay trong link t.me/ten_kenh).")
print("Kenh rieng tu: chuyen tiep 1 tin cua kenh cho @userinfobot de lay so -100...")
while True:
    ch = input("Nhap kenh (Enter de trong = bo kenh): ").strip()
    if not ch:
        cfg.pop("telegram_channel_id", None)
        break
    if ch.lower().startswith(("https://t.me/", "t.me/")):
        ch = "@" + ch.rstrip("/").split("/")[-1]
    elif not ch.startswith(("@", "-")):
        ch = "@" + ch
    try:
        data = urllib.parse.urlencode({"chat_id": ch, "text": "✅ Kênh đã kết nối. Deal hot TikTok Shop sẽ được đăng tự động lúc 11h và 19h mỗi ngày!"}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{bot}/sendMessage", data=data, timeout=30).read()
        cfg["telegram_channel_id"] = ch
        print(f"  -> Da dang tin thu len {ch}. Mo kenh kiem tra nhe.")
        break
    except Exception as e:
        print(f"  -> Khong dang duoc len {ch} ({e}).")
        print("     Kiem tra: ten kenh dung chua, bot da la Quan tri vien co quyen 'Dang tin' chua.\n")

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=1)
input("DA LUU. Bam Enter de dong.")
