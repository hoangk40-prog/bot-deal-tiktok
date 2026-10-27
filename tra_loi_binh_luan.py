# -*- coding: utf-8 -*-
"""Tra loi binh luan tren Trang Facebook bang mau co san (khong spam, co gioi han). Chay moi gio.

Moi lan chay: quet vai bai gan nhat cua Trang -> binh luan CHUA AI TRA LOI, da dang >= CHO_PHUT phut
-> tra loi bang 1 mau ngau nhien (co ten nguoi binh luan) + tha tim. Binh luan hoi mua/link -> mau moi vao kenh.
Binh luan co tu nhay cam (khieu nai, lua dao...) hoac co link -> KHONG tra loi, bao Telegram de anh tu xu ly.

Bien moi truong (hoac config.local.json: fb_page_id, fb_page_token, fb_page2_id, fb_page2_token,
  telegram_bot_token, telegram_chat_id, kenh_link):
  TRANG=1|2        Trang 1 (mac dinh) hoac Trang 2 (dung FB_PAGE2_ID / FB_PAGE2_TOKEN)
  DRY_RUN=1        chi in ra se tra loi gi, KHONG gui, KHONG luu trang thai
  KENH_LINK        link kenh Telegram / nhom Zalo de moi nguoi hoi mua (de trong thi bo mau nay)
  MAX=8            toi da bao nhieu tra loi moi lan chay          SO_BAI=5      quet bao nhieu bai gan nhat
  TRAN_NGAY=40     toi da bao nhieu tra loi moi ngay moi Trang    CHO_PHUT=10   binh luan phai du bao nhieu phut tuoi
  NGAY=1           bo gioi han gio (mac dinh chi tra loi tu 7h den 23h)
Quyen token can: pages_read_engagement, pages_manage_engagement, pages_read_user_content
  (chay lai nhap_facebook.bat, luc tao ma o Graph API Explorer tick them 3 quyen nay).
"""
import datetime
import json
import os
import random
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "tra_loi_binh_luan.json")
CONFIG_FILE = os.path.join(HERE, "config.local.json")
FB_API = "https://graph.facebook.com/" + (os.environ.get("FB_API_VERSION") or "v23.0")
VN = datetime.timezone(datetime.timedelta(hours=7))

# ----- Mau tra loi: anh sua thoai mai. {ten} = ten goi cua nguoi binh luan, {link} = KENH_LINK
MAU_CHUNG = [
    "Cảm ơn {ten} đã ghé xem nhé! 😊 Nhớ theo dõi Trang để xem video mới mỗi ngày.",
    "Hihi cảm ơn {ten} nhiều ạ ❤️",
    "Vui quá, cảm ơn {ten} đã bình luận! Chia sẻ cho bạn bè cùng cười nhé 😄",
    "Cảm ơn {ten} ủng hộ Trang nha 🙌",
    "{ten} thấy vui thì ghé Trang thường xuyên nhé, mỗi ngày có video mới 😆",
]
MAU_HOI_MUA = [
    "Chào {ten}, deal hot mỗi ngày bên mình đăng ở đây nhé: {link} 👈",
    "{ten} vào kênh này xem link và giá mới nhất nha: {link} 🛒",
]
TU_HOI_MUA = ["link", "giá", "gia bao", "bao nhiêu", "bao nhieu", "mua ở", "mua o", "ở đâu", "o dau", "shop", "đặt hàng", "dat hang", "ship"]
TU_NHAY_CAM = ["lừa đảo", "lua dao", "scam", "khiếu nại", "khieu nai", "hoàn tiền", "hoan tien", "bom hàng", "bom hang",
               "tố cáo", "to cao", "hàng giả", "hang gia", "không nhận được", "khong nhan duoc", "báo cáo", "bao cao"]


# ---------------------------------------------------------------- cau hinh / trang thai
def _local():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


LOCAL = _local()


def secret(env, key):
    """Ma lay tu bien moi truong (GitHub) hoac config.local.json (may)."""
    return (os.environ.get(env, "") or str(LOCAL.get(key, ""))).strip()


def num(name, default):
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(st):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE_FILE)


def tg_alert(text):
    bot, chat = secret("TELEGRAM_BOT_TOKEN", "telegram_bot_token"), secret("TELEGRAM_CHAT_ID", "telegram_chat_id")
    if bot and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{bot}/sendMessage", data={"chat_id": chat, "text": text[:4000]}, timeout=30)
        except Exception as e:
            print("Gui canh bao Telegram loi:", e)


# ---------------------------------------------------------------- Facebook
def fb_check(r):
    if r.status_code >= 400:
        t = r.text
        hint = ""
        if '"code":190' in t or '"code": 190' in t:
            hint = " (ma Trang het han/sai -> chay lai nhap_facebook.bat)"
        elif '"code":10' in t or '"code":200' in t or '"code": 200' in t or '"code": 10' in t:
            hint = " (thieu quyen -> tao lai ma, tick pages_read_engagement, pages_manage_engagement, pages_read_user_content)"
        raise RuntimeError(f"Facebook loi {r.status_code}{hint}: {t[:300]}")
    return r.json()


def lay_binh_luan(page, token, so_bai, ngay_toi_da=3):
    """[(post_id, comment), ...] cua cac bai trong ngay_toi_da ngay gan nhat."""
    fields = ("id,created_time,comments.filter(toplevel).order(reverse_chronological).limit(50)"
              "{id,message,from,created_time,comment_count}")
    j = fb_check(requests.get(f"{FB_API}/{page}/posts", timeout=60,
                              params={"fields": fields, "limit": so_bai, "access_token": token}))
    han = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=ngay_toi_da)
    out = []
    for p in j.get("data", []):
        if parse_time(p.get("created_time")) < han:
            continue
        for c in (p.get("comments") or {}).get("data", []):
            out.append((p["id"], c))
    return out


def parse_time(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
    except (TypeError, ValueError):
        return datetime.datetime.fromtimestamp(0, datetime.timezone.utc)


# ---------------------------------------------------------------- chon noi dung
def ten_goi(c):
    ten = ((c.get("from") or {}).get("name") or "").split()
    ten = ten[-1] if ten else ""
    return ten if 1 < len(ten) <= 15 and ten.isalpha() else "bạn"


def loai(msg):
    """'bo_qua' (rong/spam/link) | 'nhay_cam' | 'hoi_mua' | 'chung'"""
    m = (msg or "").strip().lower()
    if len(m) < 2 or (m.startswith("@") and len(m.split()) <= 2):
        return "bo_qua"                      # sticker/anh khong chu, hoac chi tag ban be
    if "http" in m or "www." in m or ".com" in m:
        return "bo_qua"                      # link la, nghi spam -> khong dap lai
    if any(t in m for t in TU_NHAY_CAM):
        return "nhay_cam"
    if any(t in m for t in TU_HOI_MUA):
        return "hoi_mua"
    return "chung"


def chon_mau(kieu, ten, link, truoc):
    mau = MAU_HOI_MUA if (kieu == "hoi_mua" and link) else MAU_CHUNG
    rong = [m for m in mau if m != truoc] or mau          # khong lap mau vua dung
    m = random.choice(rong)
    return m, m.format(ten=ten, link=link)


# ---------------------------------------------------------------- main
def main():
    dry = os.environ.get("DRY_RUN") == "1"
    trang = (os.environ.get("TRANG") or "1").strip()
    sfx = "2" if trang == "2" else ""
    page = secret(f"FB_PAGE{sfx}_ID", f"fb_page{sfx}_id")
    token = secret(f"FB_PAGE{sfx}_TOKEN", f"fb_page{sfx}_token")
    if not (page and token):
        sys.exit(f"Thieu FB_PAGE{sfx}_ID / FB_PAGE{sfx}_TOKEN (hoac fb_page{sfx}_id / fb_page{sfx}_token trong config.local.json)")
    link = secret("KENH_LINK", "kenh_link")
    # SO_BAI 25: moi Trang ~10 bai/ngay (deal + video + anh) -> 5 bai chi phu nua ngay, binh luan bai hom qua bi bo sot
    toi_da, so_bai, tran_ngay, cho_phut = num("MAX", 8), num("SO_BAI", 25), num("TRAN_NGAY", 40), num("CHO_PHUT", 10)

    now = datetime.datetime.now(VN)
    if os.environ.get("NGAY") != "1" and not 7 <= now.hour < 23:
        print(f"{now:%H:%M}: ngoai gio tra loi (7h-23h) -> bo qua.")
        return

    st = load_state()
    sub = st.setdefault("trang2", {}) if trang == "2" else st      # trang thai rieng moi Trang
    xong = dict.fromkeys(sub.setdefault("da_xu_ly", []))          # dict giu thu tu -> cat bot thi bo cai cu nhat
    hom_nay = now.strftime("%Y-%m-%d")
    dem = sub.get("hom_nay") or {}
    if dem.get("ngay") != hom_nay:
        dem = {"ngay": hom_nay, "so": 0}
    con_lai = min(toi_da, tran_ngay - dem["so"])
    print(f"Trang {trang}: hom nay da tra loi {dem['so']}/{tran_ngay}, luot nay toi da {max(con_lai, 0)}")

    try:
        cmts = lay_binh_luan(page, token, so_bai)
    except Exception as e:
        print("LOI doc binh luan:", e)
        loi(sub, st, trang, e, dry)
        raise

    chin = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=cho_phut)
    cho_xu_ly = []
    for pid, c in cmts:
        cid = c["id"]
        if cid in xong or c.get("comment_count", 0) > 0 or (c.get("from") or {}).get("id") == page:
            continue                                       # da tra loi / co nguoi tra loi roi / la binh luan cua Trang
        if parse_time(c.get("created_time")) > chin:
            continue                                       # con moi qua, doi vai phut cho giong nguoi that
        cho_xu_ly.append(c)
    cho_xu_ly.sort(key=lambda c: c.get("created_time", ""))
    print(f"Binh luan chua tra loi: {len(cho_xu_ly)}")

    da, truoc, that_bai = 0, sub.get("mau_truoc", ""), 0
    for c in cho_xu_ly:
        cid, msg = c["id"], c.get("message", "")
        kieu = loai(msg)
        if kieu in ("bo_qua", "nhay_cam"):
            print(f"  Khong tra loi ({kieu}): {msg[:60]!r}")
            if kieu == "nhay_cam" and not dry:
                tg_alert(f"⚠️ Binh luan can anh tu xu ly (Trang {trang}):\n{msg[:300]}\nhttps://www.facebook.com/{cid}")
            if not dry:
                xong[cid] = None
            continue
        if da >= con_lai:
            continue                                       # het suat luot nay, de lan sau
        mau, text = chon_mau(kieu, ten_goi(c), link, truoc)
        print(f"  [{kieu}] {msg[:50]!r} -> {text}")
        if dry:
            da += 1
            continue
        try:
            r = fb_check(requests.post(f"{FB_API}/{cid}/comments", timeout=60, data={"message": text, "access_token": token}))
            xong[cid] = None
            if r.get("id"):
                xong[r["id"]] = None                          # nho ca tra loi cua minh de khong tra loi chinh minh
            try:
                requests.post(f"{FB_API}/{cid}/likes", timeout=30, data={"access_token": token})
            except Exception:
                pass
            truoc = mau
            da += 1
            dem["so"] += 1
            time.sleep(random.uniform(25, 70))             # cach quang nhu nguoi that, tranh bi coi la spam
        except Exception as e:
            print("  LOI tra loi:", e)
            that_bai += 1
            last_err = e
            if that_bai >= 2:
                break                                      # loi 2 lan thi dung, khong dap lien tuc

    print(f"Xong: {da} {'se tra loi (DRY_RUN)' if dry else 'da tra loi'}.")
    if dry:
        return
    sub["da_xu_ly"] = list(xong)[-2000:]
    sub["hom_nay"], sub["mau_truoc"] = dem, truoc
    if that_bai and not da:
        loi(sub, st, trang, last_err, dry)
        raise last_err
    sub["loi_lien_tiep"] = 0
    save_state(st)


def loi(sub, st, trang, e, dry):
    if dry:
        return
    sub["loi_lien_tiep"] = sub.get("loi_lien_tiep", 0) + 1
    if sub["loi_lien_tiep"] == 3:
        tg_alert(f"⚠️ Bot tra loi binh luan Trang {trang} loi 3 lan lien tiep: {str(e)[:300]}")
    save_state(st)


if __name__ == "__main__":
    main()
