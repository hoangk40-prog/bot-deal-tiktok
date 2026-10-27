# -*- coding: utf-8 -*-
"""Tin "SĂN MÃ SHOPEE HÔM NAY" moi ngay (28/10, anh duyet): giup NGUOI MUA mua re nhat -> ho moi vao nhom/kenh cua minh.

Nguon: ~500 ma giam gia Shopee THAT tu Accesstrade (fetch_offers, van tra du chien dich Shopee chua duyet).
Moi ma = ma cua 1 shop + link mo thang danh sach san pham DUOC AP MA (shopee.vn/search?promotionId=...).
Chon 10 ma "loi nhat cho nguoi mua": ma giam tien voi don 0d (mon re gan nhu mien phi) > % cao + don toi thieu thap.
Moi shop 1 ma, ma da dang trong 3 ngay khong dang lai. KHONG bia: chi chep dung mo ta + ma + han cua Shopee.
Dem nguoc ngay doi (11.11, 12.12) khi con <= 14 ngay: dong dem nguoc + meo chuan bi.

Gui: kenh Telegram (anh the + tin chu) + Trang FB (`san_ma.trang_fb` trong config.json, mac dinh [1]).
Bien moi truong: ACCESSTRADE_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, FB_PAGE_ID/TOKEN, FB_PAGE2_ID/TOKEN,
  DRY_RUN=1 (in tin + luu anh the ra file, khong gui, khong luu trang thai), KIEU=chuan_bi (tin 22h30 dem truoc ngay doi).
"""
import datetime
import json
import os
import re
import sys
from io import BytesIO

import requests

import auto_deals as ad

sys.stdout.reconfigure(encoding="utf-8")
STATE_FILE = os.path.join(ad.HERE, "san_ma.json")
NGAY_DOI = [(11, 11), (12, 12)]          # cac dot giam gia lon; them (1, 1)... neu muon
SO = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


# ---------------------------------------------------------------- doc ma
def gon_tien(s):
    """'50,000 VNĐ' -> '50k', '1,000,000 VNĐ' -> '1tr'."""
    def f(m):
        v = int(m.group(1).replace(",", "").replace(".", ""))
        if v >= 1_000_000:
            return f"{v / 1_000_000:g}tr".replace(".", ",")
        return f"{v // 1000}k" if v >= 1000 and v % 1000 == 0 else ad.vnd(v)
    return re.sub(r"(\d[\d,.]*)\s*VNĐ", f, s)


def mo_ta(desc):
    """Mo ta Shopee -> cau ngan, dung y: bo 'toi da 0 VNĐ' (= khong gioi han tren), 'don toi thieu 0' -> 'moi don'."""
    d = re.sub(r"\s*-?\s*tối đa 0 VNĐ", "", desc.strip(" -"))
    d = re.sub(r"cho đơn tối thiểu 0 VNĐ", "đơn từ 0đ", d)    # KHONG ghi "moi don": ma co the chi ap 1 so mon / khach moi
    d = d.replace("cho đơn tối thiểu", "đơn từ").replace("-tối đa", " tối đa").replace("Giảm", "Giảm", 1)
    return gon_tien(re.sub(r"\s+", " ", d)).strip()


def doc_ma(o):
    """1 offer Accesstrade -> dict ma, None neu khong dung duoc."""
    try:
        cps = o.get("coupons") or []
        if isinstance(cps, str):
            cps = json.loads(cps.replace("'", '"'))
        cp = cps[0] if cps else {}
    except Exception:
        cp = {}
    code = str(cp.get("coupon_code") or "").strip()
    desc = str(cp.get("coupon_desc") or "").strip()
    if not code or not desc or not o.get("link"):
        return None
    t = ad.fold(desc)
    pct = re.search(r"giam\s*(\d{1,3})\s*%", t)
    cap = re.search(r"toi da\s*([\d,.]+)", t)
    mn = re.search(r"toi thieu\s*([\d,.]+)", t)
    flat = re.search(r"giam\s*([\d,.]{4,})\s*vnd", t)
    so = lambda m: int(re.sub(r"[,.]", "", m.group(1))) if m else 0
    pct, cap, mn, flat = (int(pct.group(1)) if pct else 0), so(cap), so(mn), so(flat)
    if pct:
        giam = min(pct * max(mn, 100_000) // 100, cap) if cap else pct * max(mn, 100_000) // 100
    else:
        giam = flat
    if giam <= 0:
        return None
    # diem = phan tram duoc giam tren don toi thieu (don 0d -> tinh nhu don 50k): ma 15k don 0d = 30%, 70% don 50k = 70%
    diem = min(giam / max(mn, 50_000), 1.0) * 100
    if pct:
        diem = max(diem, pct)
    if mn == 0 and flat >= 10_000:
        diem += 30                                            # ma 0d giam tien: mon re gan nhu mien phi -> nguoi mua thich nhat
    shop = ad.shop_name(o) or "Shop"
    link = re.sub(r"&ref=[^&]*", "", o["link"])               # bo tham so ref cua nguon, link gon hon
    return {"id": o["id"], "shop": shop[:40], "code": code, "desc": mo_ta(desc), "het": str(o.get("end_time") or "")[:10],
            "bat_dau": str(o.get("start_time") or "")[:10], "link": link, "diem": round(diem, 1),
            "giam": giam, "don_tu": mn, "pct": pct}


def chon_ma(offers, st, hom_nay, n=10):
    """Ma dang hieu luc, moi shop 1 ma tot nhat, bo ma da dang 3 ngay qua, xep diem cao truoc."""
    da = {k for k, d in (st.get("da_dang") or {}).items() if (hom_nay - datetime.date.fromisoformat(d)).days < 3}
    tot = {}
    for o in offers:
        m = doc_ma(o)
        if not m or m["id"] in da or not (m["bat_dau"] <= hom_nay.isoformat() <= (m["het"] or "9999")):
            continue
        if m["het"] == hom_nay.isoformat():
            m["diem"] -= 25                                    # het han hom nay: van dung duoc nhung xep sau
        k = ad.fold(m["shop"])
        if k not in tot or m["diem"] > tot[k]["diem"]:
            tot[k] = m
    return sorted(tot.values(), key=lambda m: (-m["diem"], m["het"]))[:n]


# ---------------------------------------------------------------- ngay doi
def ngay_doi_toi(hom_nay):
    """(ngay doi gan nhat >= hom nay, so ngay con lai) neu con <= 14 ngay, khong thi (None, None)."""
    for nam in (hom_nay.year, hom_nay.year + 1):
        for th, ng in NGAY_DOI:
            d = datetime.date(nam, th, ng)
            if 0 <= (d - hom_nay).days <= 14:
                return d, (d - hom_nay).days
    return None, None


def dong_dem_nguoc(hom_nay):
    d, con = ngay_doi_toi(hom_nay)
    if d is None:
        return []
    ten = f"{d.day}.{d.month}"
    if con == 0:
        return [f"🔥 HÔM NAY LÀ {ten} – ngày giảm giá lớn nhất, săn ngay kẻo hết lượt!"]
    meo = {1: "Mai là ngày đôi: tối nay bỏ sẵn hàng vào giỏ, lưu hết mã, canh 0h đặt liền.",
           3: "Còn 3 ngày: bắt đầu bỏ hàng cần mua vào giỏ để so giá trước – sau.",
           7: "Còn 1 tuần: ghi danh sách đồ cần mua, theo dõi giá từ giờ để biết lúc nào giảm thật."}
    out = [f"⏳ Còn {con} ngày đến {ten} – đợt giảm giá lớn nhất năm"]
    for k in sorted(meo):
        if con <= k:
            out.append("📌 " + meo[k])
            break
    return out


# ---------------------------------------------------------------- noi dung
def soan_tin(mas, hom_nay, kieu=""):
    L = [f"🎟 SĂN MÃ SHOPEE HÔM NAY {hom_nay:%d/%m}"] if kieu != "chuan_bi" else \
        [f"⏰ CHUẨN BỊ 0H – {hom_nay + datetime.timedelta(days=1):%d.%m} SẮP BẮT ĐẦU"]
    L += ["🔥 0h đêm nay bắt đầu giảm giá: bỏ sẵn hàng vào giỏ, lưu mã bên dưới, canh đúng 0h đặt liền!"] \
        if kieu == "chuan_bi" else dong_dem_nguoc(hom_nay)
    L += ["Mã thật của shop, còn hạn. Bấm link = mở đúng các món được áp mã (có mã chỉ áp cho vài món / khách mới) 👇", ""]
    for i, m in enumerate(mas):
        het = datetime.date.fromisoformat(m["het"]).strftime("%d/%m") if m["het"] else ""
        if m["het"] == hom_nay.isoformat():
            het = "⚠️ HẾT HẠN HÔM NAY"
        elif het:
            het = "hạn " + het
        L += [f"{SO[i] if i < len(SO) else str(i + 1) + '.'} {m['shop']}: {m['desc']}",
              f"   🔑 Mã: {m['code']}" + (f" · {het}" if het else ""),
              f"   👉 {m['link']}", ""]
    L += ["💡 Mẹo mua rẻ nhất: dùng CÙNG LÚC mã shop + mã freeship + mã Shopee; xem 2–3 shop cùng món trước khi đặt; "
          "mã có giới hạn lượt nên lưu sớm.",
          "👉 Theo dõi kênh để nhận mã mới mỗi ngày!"]
    return "\n".join(L).strip()


def the_anh(mas, hom_nay, kieu=""):
    """Anh the 1080x1080: tieu de + dem nguoc + 3 ma tot nhat. Loi -> None."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None
    W = H = 1080
    img = Image.new("RGB", (W, H), "#ee4d2d")
    d = ImageDraw.Draw(img)
    f = ad._pil_font
    d.text((W // 2, 105), "SĂN MÃ SHOPEE" if kieu != "chuan_bi" else "CHUẨN BỊ 0H", font=f(True, 96), fill="white", anchor="mm")
    d.text((W // 2, 200), f"HÔM NAY {hom_nay:%d/%m}", font=f(True, 54), fill="#ffe14d", anchor="mm")
    dn = ["0H ĐÊM NAY BẮT ĐẦU"] if kieu == "chuan_bi" else dong_dem_nguoc(hom_nay)
    y = 270
    if dn:
        d.rounded_rectangle([90, y - 38, W - 90, y + 38], 38, fill="#ffe14d")
        d.text((W // 2, y), dn[0].split("–")[0].strip(" ⏳🔥!").replace("HÔM NAY LÀ", "HÔM NAY"),
               font=f(True, 44), fill="#c0392b", anchor="mm")
    y = 350
    for i, m in enumerate(mas[:3]):
        d.rounded_rectangle([60, y, W - 60, y + 200], 28, fill="white")
        cho = W - 260 - d.textlength(m["code"], font=f(True, 40))              # ten shop khong de len ma
        d.text((100, y + 50), ad._wrap(d, m["shop"], f(True, 40), cho, 1)[0], font=f(True, 40), fill="#333333", anchor="lm")
        lines = ad._wrap(d, m["desc"], f(True, 46), W - 200, 2)
        for j, ln in enumerate(lines):
            d.text((100, y + 108 + j * 52), ln, font=f(True, 46), fill="#ee4d2d", anchor="lm")
        d.text((W - 100, y + 50), m["code"], font=f(True, 40), fill="#0a7d32", anchor="rm")
        if m["het"]:
            d.text((W - 100, y + 160), "hạn " + datetime.date.fromisoformat(m["het"]).strftime("%d/%m"),
                   font=f(False, 32), fill="#888888", anchor="rm")
        y += 225
    d.text((W // 2, H - 50), "Mã còn hạn · link trong bài" if len(mas) <= 3 else f"+ {len(mas) - 3} mã khác · link trong bài",
           font=f(False, 38), fill="white", anchor="mm")
    out = BytesIO()
    img.save(out, "JPEG", quality=90)
    return out.getvalue()


# ---------------------------------------------------------------- gui
def gui_telegram(bot, chat, anh, text):
    if anh:
        r = requests.post(f"https://api.telegram.org/bot{bot}/sendPhoto", timeout=60,
                          data={"chat_id": chat}, files={"photo": ("san_ma.jpg", anh, "image/jpeg")})
        if r.status_code >= 400:
            print("  Telegram gui anh loi:", r.text[:200])
    ad.send_telegram(bot, chat, text)


def gui_fb(page, token, anh, text):
    if anh:
        r = requests.post(f"https://graph.facebook.com/v21.0/{page}/photos", timeout=120,
                          files={"source": ("san_ma.jpg", anh, "image/jpeg")}, data={"caption": text, "access_token": token})
    else:
        r = requests.post(f"https://graph.facebook.com/v21.0/{page}/feed", timeout=60, data={"message": text, "access_token": token})
    if r.status_code >= 400:
        raise RuntimeError(f"Facebook loi {r.status_code}: {r.text[:200]}")
    return r.json().get("post_id") or r.json().get("id")


def secret(env, key):
    """Ma lay tu bien moi truong (GitHub) hoac config.local.json (may)."""
    return (os.environ.get(env, "") or str(ad.load_json("config.local.json", {}).get(key, ""))).strip()


def load_state():
    return ad.load_json(STATE_FILE, {})


def main():
    dry, kieu = os.environ.get("DRY_RUN") == "1", (os.environ.get("KIEU") or "").strip()
    hom_nay = ad.now().date()
    cfg = (ad.load_json("config.json", {}) or {}).get("san_ma") or {}
    st = load_state()
    if not dry and kieu != "chuan_bi" and st.get("ngay_gui") == hom_nay.isoformat() and os.environ.get("FORCE") != "1":
        print("Hom nay da gui tin san ma -> bo qua.")
        return
    offers = ad.fetch_offers(ad.get_token(), "shopee", limit=50, pages=12)
    mas = chon_ma(offers, st, hom_nay, int(cfg.get("so_ma", 10)))
    print(f"{len(offers)} ma Shopee tu Accesstrade -> chon {len(mas)}")
    if len(mas) < 3:
        print("Qua it ma dung duoc -> khong gui.")
        return
    text, anh = soan_tin(mas, hom_nay, kieu), the_anh(mas, hom_nay, kieu)
    print(text)
    if dry:
        if anh:
            p = os.path.join(os.environ.get("TEMP", "/tmp"), "san_ma_thu.jpg")
            open(p, "wb").write(anh)
            print("\nDRY_RUN: anh the luu o", p)
        return

    bot, kenh = secret("TELEGRAM_BOT_TOKEN", "telegram_bot_token"), secret("TELEGRAM_CHANNEL_ID", "telegram_channel_id")
    loi = []
    if bot and kenh:
        try:
            gui_telegram(bot, kenh, anh, text)
            print("Da gui kenh Telegram.")
        except Exception as e:
            loi.append(f"Telegram: {e}")
    for so in cfg.get("trang_fb", [1]):
        sfx = "2" if str(so) == "2" else ""
        page, tok = secret(f"FB_PAGE{sfx}_ID", f"fb_page{sfx}_id"), secret(f"FB_PAGE{sfx}_TOKEN", f"fb_page{sfx}_token")
        if page and tok:
            try:
                print(f"Da dang Trang FB {so}:", gui_fb(page, tok, anh, text))
            except Exception as e:
                loi.append(f"Trang FB {so}: {e}")
    for m in mas:
        st.setdefault("da_dang", {})[m["id"]] = hom_nay.isoformat()
    st["da_dang"] = {k: v for k, v in st["da_dang"].items() if (hom_nay - datetime.date.fromisoformat(v)).days < 30}
    if kieu != "chuan_bi":
        st["ngay_gui"] = hom_nay.isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)
    if loi:
        print("LOI:", loi)
        tg = secret("TELEGRAM_CHAT_ID", "telegram_chat_id")
        if bot and tg:
            ad.send_telegram(bot, tg, "⚠️ Tin săn mã Shopee lỗi: " + "; ".join(loi)[:500])


if __name__ == "__main__":
    main()
