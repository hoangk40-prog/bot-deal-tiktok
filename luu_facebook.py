#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lay ma Trang Facebook KHONG HET HAN tu ma lay o Graph API Explorer, luu vao config.local.json.
Chay bang nhap_facebook.bat. Ma chi luu tren may nay, khong dua len dau ca."""
import datetime
import json
import os
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "config.local.json")
API = "https://graph.facebook.com/v21.0"


def get(path, **params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise RuntimeError(msg or f"HTTP {e.code}")


try:
    with open(PATH, encoding="utf-8") as f:
        cfg = json.load(f)
except Exception:
    cfg = {}

print("Buoc 1/3: App ID va App Secret (trong developers.facebook.com > app cua anh > Cai dat ung dung > Thong tin co ban)")
app_id = input("  Dan APP ID: ").strip()
app_secret = input("  Dan APP SECRET (bam Hien thi roi copy): ").strip()
print("\nBuoc 2/3: Ma lay o Graph API Explorer (nut 'Generate Access Token')")
user_token = input("  Dan MA (token) roi bam Enter: ").strip()

try:
    if app_id and app_secret:                       # doi sang ma dai han (60 ngay) -> ma Trang se khong het han
        j = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id,
                client_secret=app_secret, fb_exchange_token=user_token)
        user_token = j["access_token"]
        print("  -> Da doi sang ma dai han.")
    else:
        print("  -> Bo qua doi ma dai han: ma Trang co the het han sau vai gio!")
    pages = get("me/accounts", fields="id,name,access_token,tasks", access_token=user_token).get("data", [])
except Exception as e:
    input(f"\nLOI: {e}\nKiem tra lai App ID / Secret / ma. Bam Enter de dong.")
    raise SystemExit(1)

if not pages:
    input("\nKhong thay Trang nao. Luc tao ma nho tick quyen pages_show_list, pages_manage_posts va chon Trang. Bam Enter de dong.")
    raise SystemExit(1)

print("\nBuoc 3/3: Chon Trang")
for i, p in enumerate(pages, 1):
    print(f"  {i}. {p['name']}")
pick = input("  Chon so (Enter = 1): ").strip() or "1"
page = pages[int(pick) - 1]
if "CREATE_CONTENT" not in (page.get("tasks") or []):
    print("  CANH BAO: tai khoan chua co quyen dang bai tren Trang nay.")

try:
    info = get("debug_token", input_token=page["access_token"], access_token=user_token).get("data", {})
    exp = info.get("expires_at", 0)
    print("  -> Ma Trang: " + ("KHONG HET HAN ✓" if not exp else
                               "het han luc " + datetime.datetime.fromtimestamp(exp).strftime("%H:%M %d/%m")))
except Exception:
    pass

cfg["fb_page_id"], cfg["fb_page_token"] = page["id"], page["access_token"]
with open(PATH, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=1)
input(f"\nDA LUU Trang '{page['name']}'. Bao lai de em cho dang thu. Bam Enter de dong.")
