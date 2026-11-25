#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lay SAN PHAM HOT TikTok Shop (API TikTok cua Accesstrade, tao link rut gon co hoa hong)
+ voucher Shopee (khi chien dich Shopee duoc duyet), gui ve Telegram theo khung gio (vd 11h va 19h).
Moi san pham 1 tin co anh + chu thich san de chuyen tiep / dan vao nhom Zalo.
Chay tren GitHub Actions moi 2 tieng (xem deals.yml). Khong tu dang len Zalo (tranh bi khoa nick).
KHONG theo doi lich su gia: Shopee cam cong cu xem lich su gia (phat 10 trieu/lan).

Bien moi truong:  ACCESSTRADE_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
                  FORCE=true  -> bo qua khung gio gui (chay tay)
                  DRY_RUN=1   -> chi in tin nhan, KHONG gui, KHONG luu trang thai
                  WIN=1       -> gui 'San pham win hom nay' ngay (khong doi gio)
                  CHI_RIENG=1 -> chi gui chat rieng, khong dang kenh / Trang Facebook (nut 'Chay ngay')
Cai dat: config.json (khong chua token). Token chay tren may: config.local.json (khong dua len GitHub).
"""
import datetime
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
OFFERS_API = "https://api.accesstrade.vn/v1/offers_informations"
TIKTOK_API = "https://api.accesstrade.vn/v2/tiktokshop_product_feeds"
VN = datetime.timezone(datetime.timedelta(hours=7))
STATE_FILE = "sent.json"

DEFAULTS = {
    "shopee": False,               # voucher Shopee: bat khi chien dich Shopee tren Accesstrade da duoc duyet
    "tiktok": True,                # san pham hot TikTok Shop
    "max_items": 8,                # so voucher toi da moi tin nhan
    "min_value": 20000,            # gia tri voucher toi thieu (dong) moi duoc gui
    "shop_cooldown_hours": 24,     # moi shop nghi bao lau giua 2 lan gui
    "active_from": 7,              # chi gui trong khung gio nay (gio Viet Nam, tu 7h den truoc 22h)
    "active_to": 22,
    "fetch_pages": 4,              # moi san lay toi da bao nhieu trang (50 khuyen mai/trang)
    "keep_days_no_end": 30,        # voucher khong co ngay het han: nho da gui trong bao nhieu ngay
    "alert_after_failures": 3,     # loi lien tiep bao nhieu lan thi nhan canh bao Telegram
    "alert_cooldown_hours": 12,    # nhac lai canh bao toi da moi bao nhieu gio
    # ---- san pham hot TikTok Shop
    "send_hours": [],              # gio gui tin (gio VN), vd [11, 19]. De trong = gui ngay khi co hang moi
    "max_products": 4,             # so san pham moi dot gui (moi san pham 1 tin co anh)
    "max_vouchers": 2,             # khi dot gui co san pham: so voucher Shopee kem theo
    "tiktok_pages": 3,             # so trang 'goi y' lay ve (20 san pham/trang)
    "tiktok_keywords": [],         # tim them theo tu khoa, vd ["áo chống nắng", "sạc dự phòng"] (1 trang/tu khoa)
    "min_price": 30000,            # gia ban toi thieu (dong): bo hang qua re, hoa hong khong dang
    "max_price": 1000000,          # gia ban toi da (dong)
    "min_sold": 100,               # da ban toi thieu (hang co nguoi mua that)
    "min_commission": 3,           # % hoa hong toi thieu
    "product_cooldown_days": 7,    # san pham da gui: nghi bao nhieu ngay
    "max_per_category": 2,         # moi nhom hang toi da bao nhieu san pham/dot (cho da dang)
    "fb_max_per_day": 6,           # Trang Facebook qua Make.com: toi da bao nhieu bai/ngay (anh chon 6 ngay 21/10 de danh credits Make cho video + anh)
    "fb_gap_hours": 2.5,           # 2 bai Facebook cach nhau it nhat bao nhieu gio (~3 gio: 7h,10h,13h,16h,19h,22h; de 2.5 vi GitHub chay lech gio vai phut)
    "shopee_per_run": 1,           # 25/10: moi lan dang lay may mon Shopee (shopee_hang.json do shopee_bot.py tren may chon), 0 = tat
    "zalo_combo": False,          # true: moi dot gui 1 ANH GHEP (danh so, co gia) + 1 TIN CHU GOP -> chi 2 lan copy sang Zalo
    # ---- san pham win: moi ngay 1 lan gui 10 san pham hoa hong cao ve chat rieng
    "nganh_win": "gia_dung",       # doi nganh: gia_dung / my_pham / thoi_trang / me_va_be (xem WIN_KEYWORDS). De "" = tat
    "win_hour": 8,                 # gui luc may gio (gio VN), moi ngay 1 lan
    "win_count": 10,               # so san pham win
    "win_min_price": 100000,
    "win_max_price": 300000,
    "win_min_commission": 5,       # % hoa hong toi thieu cho san pham win (deal thuong van dung min_commission)
    "win_keywords_per_day": 10,    # moi ngay quet bao nhieu tu khoa (xoay vong trong WIN_KEYWORDS)
}


# ---------------------------------------------------------------- tien ich chung
def now():
    return datetime.datetime.now(VN)


def load_json(name, default):
    try:
        with open(os.path.join(HERE, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(name, data):
    """Ghi qua file tam roi doi ten, de dang ghi do ma bi tat thi khong hong file cu."""
    path = os.path.join(HERE, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_config():
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in load_json("config.json", {}).items() if k != "token"})
    if not cfg.get("merchants"):
        cfg["merchants"] = ["shopee"] if cfg["shopee"] else []    # TikTok khong co voucher qua API nay
    return cfg


def get_token():
    t = os.environ.get("ACCESSTRADE_TOKEN", "").strip()
    if t:
        return t
    t = str(load_json("config.local.json", {}).get("token", "")).strip()
    if t:
        return t
    t = str(load_json("config.json", {}).get("token", "")).strip()   # kieu cu
    if t:
        print("CANH BAO: token dang nam trong config.json. Hay mo deals_gui.pyw bam 'Luu cai dat' de chuyen sang config.local.json.")
    return t


# ---------------------------------------------------------------- goi API (co thu lai khi loi tam thoi)
def http_json(req, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise
        except urllib.error.URLError:
            if i < tries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise


def api_get(token, url):
    return http_json(urllib.request.Request(url, headers={"Authorization": f"Token {token}",
                                                          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Safari/537.36"}))


def fetch_offers(token, merchant, limit=50, pages=4):
    out = []
    for page in range(1, pages + 1):
        qs = urllib.parse.urlencode({"merchant": merchant, "status": 1, "limit": limit, "page": page})
        got = api_get(token, f"{OFFERS_API}?{qs}").get("data", [])
        if not isinstance(got, list):
            got = []
        out += got
        if len(got) < limit:
            break
    return out


def describe_error(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            body = e.read().decode("utf-8", "ignore")[:150]
        except Exception:
            body = ""
        hint = " (token sai/het han hoac chua duoc duyet chien dich)" if e.code in (401, 403) else ""
        return f"HTTP {e.code}{hint} {body}".strip()
    if isinstance(e, urllib.error.URLError):
        return f"loi mang ({e.reason})"
    return str(e)[:150]


# ---------------------------------------------------------------- doc gia tri voucher tu mo ta
def fold(t):
    """Chu thuong, bo dau tieng Viet: 'Giảm tối đa' -> 'giam toi da'."""
    t = unicodedata.normalize("NFD", str(t or "").lower().replace("đ", "d"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


NUM = r"(\d+(?:[.,]\d+)*)(?!\d)"
UNIT = r"\s*(trieu|tr|nghin|ngan|vnd|k|d|₫)?(?![a-z])"


def to_vnd(num, unit):
    """'50.000'->50000, '30'+'k'->30000, '1,5'+'tr'->1500000, '100'+'K'->100000."""
    mult = 1000 if unit in ("k", "nghin", "ngan") else 1_000_000 if unit in ("tr", "trieu") else 1
    if mult > 1 and re.fullmatch(r"\d+[.,]\d{1,2}", num):
        return int(round(float(num.replace(",", ".")) * mult))
    return int(re.sub(r"[.,]", "", num)) * mult


def parse_text(desc):
    """Tra ve dict(value, minorder, pct). value = so tien uoc tinh khach duoc giam (dong), 0 neu khong doc duoc."""
    t = fold(desc)
    pct = re.search(r"giam\s*(?:den\s*)?(\d{1,3})\s*%", t)
    cap = re.search(r"toi da\s*" + NUM + UNIT, t)
    mn = re.search(r"(?:toi thieu|don tu)\s*" + NUM + UNIT, t)
    minorder = to_vnd(mn.group(1), mn.group(2)) if mn else 0
    flat = 0
    for m in re.finditer(r"giam\s*(?:toi da\s*)?" + NUM + UNIT + r"(?!\s*%)", t):
        v = to_vnd(m.group(1), m.group(2))
        if m.group(2) or v >= 1000:                 # 'giam 5 san pham' khong phai tien
            flat = v
            break
    pc = int(pct.group(1)) if pct else 0
    if pc and cap:
        value = to_vnd(cap.group(1), cap.group(2))
    elif flat:
        value = flat
    elif pc and minorder:
        value = int(pc / 100 * minorder)
    else:
        value = 0
    return {"value": value, "minorder": minorder, "pct": pc, "pct_cap": bool(pc and cap)}


def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(s or ""))).strip()


def shop_name(o):
    name = str(o.get("name") or "")
    m = re.match(r"\s*\[(.+?)\]", name)
    if m:
        return m.group(1).strip()
    for sep in (" - ", " – ", ":", "|"):
        if sep in name:
            return name.split(sep)[0].strip()[:40]
    return name.strip()[:40] or "Khac"


def parse_offer(o):
    cs = [c for c in (o.get("coupons") or []) if isinstance(c, dict)]
    cands = [str(c.get("coupon_desc") or "") for c in cs]
    cands.append(re.sub(r"^\s*\[.*?\]\s*-?", "", str(o.get("name") or "")))
    cands.append(strip_tags(o.get("content"))[:300])
    cands = [c.strip() for c in cands if c.strip()]
    best, desc = {"value": 0, "minorder": 0, "pct": 0}, (cands[0] if cands else "")
    for c in cands:                                   # lay mo ta dau tien doc duoc gia tri
        p = parse_text(c)
        if p["value"] > 0:
            best, desc = p, c
            break
    real = best["value"]
    if best.get("pct_cap"):          # 'giam 10% toi da 550k': gio hang tham khao 300k (hoac muc toi thieu) moi la so tien that su tiet kiem duoc
        real = min(real, int(best["pct"] / 100 * max(best["minorder"], 300000)))
    shop = shop_name(o)
    score = real * (1 if best["minorder"] <= 300000 else max(300000 / best["minorder"], 0.05))
    if re.search(r"official|mall|chinh hang", fold(shop)):
        score *= 1.2                 # uu tien shop chinh hang
    return {"desc": desc, "value": real, "minorder": best["minorder"], "shop": shop, "score": score}


def offer_codes(o):
    return [c.get("coupon_code") for c in (o.get("coupons") or [])
            if isinstance(c, dict) and c.get("coupon_code")]


def fmt_date(t):
    t = str(t or "")[:10]
    try:
        return datetime.datetime.strptime(t, "%Y-%m-%d").strftime("%d/%m")
    except Exception:
        return t


def offer_key(o):
    return str(o.get("id") or "|".join(offer_codes(o)) or o.get("link") or "")


def end_date(o):
    d = str(o.get("end_time") or "")[:10]
    try:
        return datetime.date.fromisoformat(d).isoformat()
    except ValueError:
        return ""


def not_expired(o, n):
    d = end_date(o)
    if not d:
        return True
    d = datetime.date.fromisoformat(d)
    if d < n.date():
        return False
    return not (d == n.date() and n.hour >= 20)       # het han hom nay va da toi muon


def recent(ts, hours, n):
    try:
        return (n - datetime.datetime.fromisoformat(ts)).total_seconds() < hours * 3600
    except Exception:
        return False


# ---------------------------------------------------------------- trang thai da gui (sent.json)
def migrate_state(raw):
    """Doc ca ban cu (gia tri la chuoi thoi gian) lan ban moi (gia tri la {"t":..., "exp":...})."""
    st = {"offers": {}, "shops": {}, "links": {}, "products": {}, "meta": {}, "win_sold": {}}
    raw = raw if isinstance(raw, dict) else {}
    for k in ("offers", "shops", "links", "products"):
        for key, v in (raw.get(k) or {}).items():
            st[k][key] = v if isinstance(v, dict) else {"t": str(v)}
    if isinstance(raw.get("meta"), dict):
        st["meta"] = raw["meta"]
    if isinstance(raw.get("win_sold"), dict):          # so da ban moi ngay cua hang win: {id: [[ngay, da_ban], ...]}
        st["win_sold"] = raw["win_sold"]
    return st


def entry_expired(e, n, keep_days):
    exp = e.get("exp")
    if exp:
        try:
            return n.date() > datetime.date.fromisoformat(exp) + datetime.timedelta(days=1)
        except ValueError:
            pass
    return not recent(e.get("t", ""), keep_days * 24, n)


def cleanup_state(state, links_in_file, cfg, n):
    """Voucher: nho den het han + 1 ngay (khong co han thi 30 ngay).
    Link TikTok: nho chung nao con trong my_links.txt (xoa khoi file thi nho them 30 ngay).
    Shop: chi can nho trong thoi gian nghi."""
    state["offers"] = {k: e for k, e in state["offers"].items() if not entry_expired(e, n, cfg["keep_days_no_end"])}
    keep_h = max(cfg["shop_cooldown_hours"], 72)
    state["shops"] = {k: e for k, e in state["shops"].items() if recent(e.get("t", ""), keep_h, n)}
    state["links"] = {k: e for k, e in state["links"].items()
                      if k in links_in_file or recent(e.get("t", ""), 30 * 24, n)}
    state["products"] = {k: e for k, e in state["products"].items()
                         if recent(e.get("t", ""), cfg["product_cooldown_days"] * 24, n)}


def read_links():
    seen, out = set(), []
    try:
        with open(os.path.join(HERE, "my_links.txt"), encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line in seen:
                    continue
                if not line.lower().startswith(("http://", "https://")):
                    print(f"Bo qua dong khong phai link: {line[:60]}")
                    continue
                seen.add(line)
                out.append(line)
    except FileNotFoundError:
        pass
    return out


# ---------------------------------------------------------------- chon voucher
def pick_new(offers, state, cfg, n):
    """Tra ve (danh_sach_chon, thong_ke_ly_do_loai, vai_mo_ta_bi_loai_vi_gia_tri_thap)."""
    cool, minv = cfg["shop_cooldown_hours"], cfg["min_value"]
    stats, samples, best = Counter(), [], {}
    for o in offers:
        if not (o.get("aff_link") or o.get("link")):
            stats["khong co link"] += 1
            continue
        if not not_expired(o, n):
            stats["het han"] += 1
            continue
        key = offer_key(o)
        if not key:
            stats["khong co ma dinh danh"] += 1
            continue
        if key in state["offers"]:
            stats["da gui truoc do"] += 1
            continue
        p = parse_offer(o)
        if p["value"] < minv:
            stats["gia tri thap" if p["value"] else "khong doc duoc gia tri"] += 1
            if len(samples) < 5:
                samples.append(f"{p['shop']}: {p['desc'][:90] or '(trong)'} -> doc ra {p['value']}")
            continue
        shop = p["shop"]
        if shop in state["shops"] and recent(state["shops"][shop].get("t", ""), cool, n):
            stats["shop dang nghi"] += 1
            continue
        if shop in best:
            stats["cung shop, chon cai tot hon"] += 1
            if p["score"] <= best[shop][1]["score"]:
                continue
        best[shop] = (o, p)
    chosen = [o for o, _ in sorted(best.values(), key=lambda x: -x[1]["score"])][: cfg["max_items"]]
    return chosen, stats, samples


def build_message(offers, links, n):
    """Tin chu: voucher Shopee + link anh tu dan san (link da la link hoa hong)."""
    lines = []
    if offers:
        lines += [f"🎁 VOUCHER MỚI {n:%H:%M %d/%m} 🎁", ""]
        for i, o in enumerate(offers, 1):
            p = parse_offer(o)
            codes, end = offer_codes(o), fmt_date(o.get("end_time"))
            lines += [f"{i}. 🏪 {p['shop']}", f"💥 {p['desc']}"]
            tail = []
            if codes:
                tail.append("🏷 Mã: " + ", ".join(codes[:3]))
            if end:
                tail.append(f"⏰ HSD: {end}")
            if tail:
                lines.append("   ".join(tail))
            lines += [f"👉 {o.get('aff_link') or o.get('link')}", ""]
    if links:
        lines += ["⭐ Deal TikTok chọn lọc:"] + links + [""]
    return "\n".join(lines).strip()



# ---------------------------------------------------------------- san pham hot TikTok Shop
def num(x):
    """So tu API: 34979.57 / "34979.57" / "3.000" (dau cham hang nghin) -> float."""
    if isinstance(x, str):
        s = x.strip()
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
            s = s.replace(".", "")
        x = s.replace(",", "")
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def tt_get(token, params, tries=4):
    """Goi API TikTok cua Accesstrade. API gioi han rat it luot/phut -> gap 429 thi cho lau."""
    url = f"{TIKTOK_API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Token {token}", "Accept": "application/json",
                                               "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Safari/537.36"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(15 * (i + 1))
                continue
            raise
        except urllib.error.URLError:
            if i < tries - 1:
                time.sleep(5)
                continue
            raise


# Tai lieu Accesstrade ghi title_keywords la BAT BUOC -> neu goi 'goi y' khong tu khoa ra 0 / loi
# thi tu tim theo cac tu khoa hang ban chay nay (anh co the thay bang tiktok_keywords trong config.json)
DEFAULT_KEYWORDS = ["áo", "quần", "váy", "giày", "túi", "son", "kem chống nắng", "serum",
                    "sạc", "tai nghe", "nồi", "đồ gia dụng"]


def tt_call(token, params, label):
    """1 lan goi API TikTok. Tra ve (products, next_page_token, loi). In ro ket qua de doc log."""
    try:
        j = tt_get(token, params) or {}
    except urllib.error.HTTPError as e:
        msg = describe_error(e)
        print(f"  [tiktok {label}] LOI {msg}")
        return [], None, msg
    except Exception as e:
        print(f"  [tiktok {label}] LOI {str(e)[:150]}")
        return [], None, str(e)[:150]
    if j.get("status") is False:
        msg = str(j.get("message") or j)[:200]
        print(f"  [tiktok {label}] API tu choi: {msg}")
        return [], None, msg
    d = j.get("data") or {}
    prods = d.get("products") or []
    print(f"  [tiktok {label}] {len(prods)} san pham (tong {d.get('total_count', '?')})")
    return prods, d.get("next_page_token"), None


def fetch_tiktok(token, cfg):
    """San pham 'goi y' (nhieu trang) + tim them theo tu khoa. Tra ve list san pham (dict cua API).
    Chi bao loi (raise) khi MOI lan goi deu loi; mot vai lan loi van dung ket qua lay duoc."""
    out, errors, calls, page_token = [], [], 0, None
    for i in range(int(cfg["tiktok_pages"])):
        p = {"sort_field": "RECOMMENDED", "limit": 20}
        if page_token:
            p["page_token"] = page_token
        prods, page_token, err = tt_call(token, p, f"goi y trang {i + 1}")
        calls += 1
        if err:
            errors.append(err)
        out += prods
        if not page_token:
            break
        time.sleep(2)
    keywords = list(cfg.get("tiktok_keywords") or [])
    auth_err = any(("HTTP 401" in e or "HTTP 403" in e) for e in errors)   # token sai: thu tiep cung vo ich
    if not out and not keywords and not auth_err:
        print("  [tiktok] 'goi y' khong ra san pham -> tim theo tu khoa mac dinh")
        keywords = DEFAULT_KEYWORDS
    for kw in keywords:
        time.sleep(2)
        prods, _, err = tt_call(token, {"sort_field": "BEST_SELLERS", "limit": 20, "title_keywords": kw}, f"'{kw}'")
        calls += 1
        if err:
            errors.append(err)
        out += prods
    if out:
        x = out[0]
        print("  [tiktok] mau san pham dau: "
              + " | ".join(f"{k}={str(x.get(k))[:40]}" for k in ("title", "sales_price", "commission", "units_sold", "has_inventory")))
    elif errors and len(errors) == calls:
        raise RuntimeError(errors[0])
    return out


# API TikTok khong tra nhom hang -> doan loai hang tu ten san pham (de moi dot gui khong toan 1 loai)
PRODUCT_GROUPS = [
    ("sac du phong", r"(sac|pin) du phong|power ?bank"), ("cu sac", r"cu sac|bo sac|sac nhanh|cap sac|day sac"),
    ("tai nghe", r"tai nghe|earbud|headphone"), ("loa", r"\bloa\b|micro"), ("dong ho", r"dong ho|smartwatch"),
    ("ao chong nang", r"ao chong nang|ao khoac chong"), ("gang tay", r"gang tay|xo tay"),
    ("chong nang da", r"kem chong nang|sua chong nang|xit chong nang"), ("trang diem", r"son |phan |ke mat|mascara|cushion"),
    ("cham soc da", r"serum|sua rua mat|toner|kem duong|mat na|tay trang"), ("toc", r"dau goi|dau xa|duong toc"),
    ("ao", r"\bao\b"), ("quan", r"\bquan\b"), ("vay dam", r"\bvay\b|\bdam\b"), ("giay dep", r"giay|dep|sandal"),
    ("tui vi", r"\btui\b|\bvi\b|balo"), ("massage", r"massage|mat xa"), ("ghe", r"\bghe\b"),
    ("bep", r"noi |chao |bep |may xay|noi chien"), ("do an", r"banh|keo|snack|tra |ca phe|hat "),
]


def guess_group(title):
    t = fold(title)
    for name, pat in PRODUCT_GROUPS:
        if re.search(pat, t):
            return name
    return ""


def tt_info(x):
    """Rut gon 1 san pham API thanh dict de chon va viet tin."""
    sp, op, c = x.get("sales_price") or {}, x.get("original_price") or {}, x.get("commission") or {}
    sale = num(sp.get("minimum_amount"))
    orig = num(op.get("minimum_amount"))
    r = num(c.get("rate"))
    pct = r * 100 if r <= 1 else r / 100          # API tra 0.05185 (=5,19%) hoac 3587 (=35,87%)
    amount = num(c.get("amount")) or sale * pct / 100
    cats = x.get("category_chains") or []
    # API hien tra original_price = sales_price; min/max la khoang gia giua cac phan loai (mau, size), KHONG phai giam gia
    smax = num(sp.get("maximum_amount"))
    return {"id": str(x.get("id") or ""), "title": str(x.get("title") or "").strip(), "shop": str((x.get("shop") or {}).get("name") or ""),
            "price": sale, "orig": orig if orig > sale * 1.03 else 0, "price_max": smax if smax > sale * 1.03 else 0,
            "rating": num(x.get("rating_star")), "sold": int(num(x.get("units_sold"))),
            "sold_known": x.get("units_sold") is not None,   # API bo truong nay neu shop khong chia se so lieu
            "pct": pct, "commission": amount, "image": x.get("main_image_url") or "", "url": x.get("detail_link") or "",
            "stock": x.get("has_inventory", True) is not False, "cat": str((cats[0] if cats else {}).get("local_name") or "") or guess_group(x.get("title") or "")}


OFFICIAL_WORDS = ("chinh hang", "official", "mall", "authentic", "flagship", "store chinh")


def is_official(it):
    """Hang/shop chinh hang: ten san pham hoac ten shop ghi ro chinh hang / Official / Mall, hoac shop mang dung ten thuong
    hieu co trong ten san pham (vd shop 'BONNE VN' ban 'Sac du phong Bonne'). Chi dua tren chu co that, khong doan."""
    t, s = fold(it.get("title", "")), fold(it.get("shop", ""))
    if any(w in t or w in s for w in OFFICIAL_WORDS):
        return True
    brand = s.replace(" vietnam", "").replace(" viet nam", "").replace(" vn", "").strip()
    return len(brand) >= 4 and re.search(r"\b" + re.escape(brand) + r"\b", t) is not None


def sold_text(n):
    """41.953 -> 'trên 40.000' ; 226.317 -> 'trên 200.000' ; 7.003 -> 'trên 7.000' ; <100 -> None (lam tron XUONG, khong noi qua)."""
    n = int(n or 0)
    if n < 100:
        return None
    d = len(str(n))
    step = 10 ** (d - 1) if (n < 10000 or n >= 100000) else 10 ** (d - 2) * 10
    return "trên " + f"{n // step * step:,}".replace(",", ".")


def pick_tiktok(items, state, cfg, n):
    """Tra ve (danh_sach_info_xep_hang, thong_ke_ly_do_loai). Lay du phong gap doi (tao link co the loi)."""
    stats, cands, seen = Counter(), [], set()
    for x in items:
        it = tt_info(x)
        if not it["id"] or it["id"] in seen:
            continue
        seen.add(it["id"])
        if not it["url"]:
            stats["khong co link"] += 1
        elif not it["stock"]:
            stats["het hang"] += 1
        elif it["price"] < cfg["min_price"]:
            stats["gia qua re"] += 1
        elif it["price"] > cfg["max_price"]:
            stats["gia cao"] += 1
        elif it["sold_known"] and it["sold"] < cfg["min_sold"]:
            stats["it luot ban"] += 1
        elif it["pct"] < cfg["min_commission"]:
            stats["hoa hong thap"] += 1
        elif recent((state["products"].get("tt|" + it["id"]) or {}).get("t", ""), cfg["product_cooldown_days"] * 24, n):
            stats["da gui gan day"] += 1
        else:
            # 23/10 anh muon giup NGUOI MUA: uu tien ban chay + hang chinh hang / shop chinh hang, khong uu tien hang dat
            # (truoc dung tien hoa hong -> hay chon mon gia cao). Hoa hong % van tinh nhe.
            it["official"] = is_official(it)
            score = math.log10(it["sold"] + 10) * math.sqrt(max(it["pct"], 1)) * (1.5 if it["official"] else 1)
            if it["orig"]:
                score *= 1 + min(1 - it["price"] / it["orig"], 0.6)            # dang giam gia that: uu tien (giam 30% -> x1,3)
            # 28/10 anh thay bot toan lay hang hoi dat -> uu tien hang re (de chot don, nguoi mua de bam mua)
            score *= 1.4 if it["price"] < 100_000 else 1.2 if it["price"] < 150_000 else 1
            cands.append((score, it))
    cands.sort(key=lambda c: -c[0])
    out, per_cat, shops = [], Counter(), set()
    for _, it in cands:
        if it["shop"] and it["shop"] in shops:
            stats["trung shop"] += 1
            continue
        if it["cat"] and per_cat[it["cat"]] >= cfg["max_per_category"]:
            stats["trung nhom hang"] += 1
            continue
        shops.add(it["shop"])
        per_cat[it["cat"]] += 1
        out.append(it)
        if len(out) >= cfg["max_products"] * 2:
            break
    return out, stats


def pick_shopee(state, cfg, n, data=None):
    """25/10: hang Shopee do shopee_bot.py (MAY anh, Shopee Affiliate rieng) chon moi sang, day len GitHub = shopee_hang.json.
    Moi lan chay lay `shopee_per_run` mon chua dang. Chi dung hang lay HOM NAY (gia/flash sale doi nhanh, khong ghi gia cu)."""
    want = int(cfg.get("shopee_per_run", 1))
    d = data if data is not None else load_json("shopee_hang.json", {})
    if want <= 0 or d.get("ngay") != n.date().isoformat():
        return []
    out = []
    for it in d.get("items") or []:
        if len(out) >= want:
            break
        if it.get("aff") and not recent((state["products"].get(it.get("key", "")) or {}).get("t", ""),
                                         cfg["product_cooldown_days"] * 24, n):
            out.append(dict(it))
    return out


def make_link(token, product_url, product_id="", full=False, utm="zalo"):
    """Tao link hoa hong rut gon. Tra ve data cua API (co aff_short_url; full=True co them ten/anh/gia), None neu loi.
    utm: nguon de xem don tu dau tren Accesstrade (tool Live AI dung "youtube_live")."""
    body = {"product_url": product_url, "utm_source": utm}
    if product_id:
        body["product_id"] = product_id
    url = f"{TIKTOK_API}/create_link" + ("" if full else "?minify=true")
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": f"Token {token}", "Content-Type": "application/json",
                                          "Accept": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0 Safari/537.36"})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                j = json.loads(r.read().decode("utf-8"))
            d = j.get("data") or {}
            if j.get("status") and (d.get("aff_short_url") or d.get("aff_url")):
                return d
            print(f"  Khong tao duoc link: {j.get('message') or j}"[:200])
            return None
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < 2:
                time.sleep(15 * (i + 1))
                continue
            print(f"  Tao link loi: {describe_error(e)}")
            return None
        except urllib.error.URLError as e:
            if i < 2:
                time.sleep(5)
                continue
            print(f"  Tao link loi mang: {e.reason}")
            return None


AFF_HOSTS = ("isclix.com", "shorten.asia", "accesstrade", "atid.me")


def is_tiktok_raw(link):
    """Link san pham TikTok chua phai link hoa hong -> can doi."""
    l = link.lower()
    return "tiktok.com" in l and not any(h in l for h in AFF_HOSTS)


def from_link_data(d, link):
    """Ket qua create_link (ban day du) -> dict san pham de viet tin."""
    pp = d.get("product_price") or {}
    return {"id": str(d.get("product_id") or link), "title": str(d.get("product_name") or "").strip(), "shop": "",
            "price": num(pp.get("minimum_amount") or pp.get("amount")), "orig": 0, "sold": 0,
            "image": d.get("product_image") or "", "aff": d.get("aff_short_url") or d.get("aff_url"), "cat": ""}


# ---------------------------------------------------------------- loi chao hang do AI viet (Gemini, mien phi)
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-3.7-flash", "gemini-flash-lite-latest"]   # 3.7 hay cham qua 90s
HOOK_SCHEMA = {"type": "OBJECT", "properties": {"items": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "so": {"type": "INTEGER"}, "mo_dau": {"type": "STRING"}, "noi_bat": {"type": "ARRAY", "items": {"type": "STRING"}}},
    "required": ["so", "mo_dau", "noi_bat"]}}}, "required": ["items"]}


def gemini_key():
    """GitHub: secret GEMINI_API_KEY. May: config.local.json 'gemini_key', khong co thi lay khoa cua Xuong Video (cung Drive)."""
    k = os.environ.get("GEMINI_API_KEY", "").strip() or str(load_json("config.local.json", {}).get("gemini_key", "")).strip()
    if k:
        return k
    try:
        with open(os.path.join(os.path.dirname(HERE), "xuong_video", "tai_render_data", "cai_dat.json"), encoding="utf-8") as f:
            return str(json.load(f).get("gemini_key") or "").strip()
    except Exception:
        return ""


def _nums(s):
    return {re.sub(r"[.,]", "", x) for x in re.findall(r"\d[\d.,]*\d|\d", s)}


def add_hooks(items, cfg):
    """Gan it['hook'] = 2-3 cau chao hang kieu 'Troi oi ca nha oi...' cho tung mon. AI loi / het luot / bia so -> bo qua
    (tin gui nhu cu). CHI dung so lieu that: cau nao co con so khong co trong du lieu thi bo cau chao hang mon do."""
    if not items or not cfg.get("ai_hook", True):
        return
    key = gemini_key()
    if not key:
        print("  [AI chao hang] chua co khoa Gemini -> gui tin nhu cu")
        return
    facts = [{"so": i + 1, "ten": it["title"], "shop": it.get("shop", ""), "chinh_hang": bool(it.get("official"))}
             for i, it in enumerate(items)]
    prompt = ("Bạn là người bán hàng online Việt Nam tận tâm, giúp NGƯỜI MUA chọn được hàng tốt giá rẻ. Với mỗi sản phẩm viết:\n"
              "1) mo_dau: 2 câu chào deal thân mật, hào hứng (\"Trời ơi cả nhà ơi\", \"ce ơi\", \"khẩn cầu\", \"đừng bỏ qua\"), 1-2 "
              "emoji, mỗi món một kiểu khác nhau; nói lợi ích thật cho người dùng; kết bằng ý mời bấm link xem giá sale trong app. "
              "KHÔNG nhắc giá tiền, KHÔNG nhắc số người mua.\n"
              "2) noi_bat: 4-6 điểm nổi bật NGẮN (3-10 chữ mỗi điểm) giúp người mua thấy chất lượng: chất liệu, công dụng, kích cỡ, "
              "dung lượng, đối tượng dùng, quà kèm... Nếu chinh_hang = true được viết 1 điểm về hàng chính hãng của shop.\n"
              "LUẬT BẮT BUỘC: CHỈ dùng thông tin CÓ TRONG TÊN sản phẩm / tên shop. KHÔNG bịa đánh giá, số sao, bảo hành, xuất xứ, "
              "nhập khẩu, cam kết, hoàn tiền, % giảm, freeship, quà không có trong tên. Không viết link, không nhắc Shopee.\n"
              "Trả JSON {\"items\": [{\"so\": 1, \"mo_dau\": \"...\", \"noi_bat\": [\"...\"]}]}\nDỮ LIỆU: "
              + json.dumps(facts, ensure_ascii=False))
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {
        "temperature": 0.9, "responseMimeType": "application/json", "responseSchema": HOOK_SCHEMA}}).encode()
    for model in GEMINI_MODELS:
        try:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                                         data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as r:      # model nao cham thi sang model ke (tong toi da ~3 phut)
                j = json.loads(r.read().decode("utf-8"))
            out = json.loads(j["candidates"][0]["content"]["parts"][0]["text"]).get("items") or []
        except Exception as e:
            print(f"  [AI chao hang] {model} loi: {describe_error(e) if isinstance(e, urllib.error.HTTPError) else str(e)[:80]}")
            continue
        ok = 0
        for x in out:
            i = int(x.get("so", 0)) - 1
            if not (0 <= i < len(items)):
                continue
            it = items[i]
            hook = str(x.get("mo_dau") or "").strip()
            if hook and claim_ok(hook, it):
                it["hook"] = hook[:300]
                ok += 1
            it["noi_bat"] = [p.strip(" •-") for p in (x.get("noi_bat") or []) if p.strip() and claim_ok(p, it)][:6]
        print(f"  [AI chao hang] {model}: viet duoc {ok}/{len(items)} mon")
        return


RISKY = ("bao hanh", "chinh hang", "uy tin", "xuat xu", "nhap khau", "cam ket", "hoan tien", "doi tra", "freeship", "mien phi van",
         "giam gia", "%", "5 sao", "danh gia", "review", "tot nhat", "re nhat", "so 1", "top 1")


def claim_ok(text, it):
    """Cau AI viet co hop le khong: so trong cau phai co trong ten san pham; tu ngu 'cam ket' (bao hanh, chinh hang, uy tin,
    giam gia, danh gia...) chi duoc dung khi ten san pham / shop CO chu do (chinh hang: khi bot da xac nhan it['official'])."""
    t = fold(it.get("title", "") + " " + it.get("shop", ""))
    if _nums(text) - _nums(it.get("title", "")):
        return False
    f = fold(text)
    for w in RISKY:
        if w in f and w not in t and not (w in ("chinh hang", "uy tin") and it.get("official")):
            return False
    return True


ZALO_LINK = ""          # 11/11 anh duyet: link moi vao nhom Zalo (config.json "zalo_link"), gan cuoi tin kenh Telegram + Trang FB


def loi_moi_nhom():
    """Dong moi vao nhom Zalo; chua co link thi rong. KHONG gan vao tin dang trong chinh nhom Zalo."""
    link = (ZALO_LINK or str(load_config().get("zalo_link") or "")).strip()
    return f"👥 Vào nhóm Zalo SĂN DEAL HỜI MỖI NGÀY để nhận deal sớm nhất: {link}" if link else ""


def caption(it, moi=False):
    """moi=True (kenh Telegram, Trang FB): them dong moi vao nhom Zalo o cuoi.
    Chu thich 1 san pham (Telegram / Zalo / Trang FB). 23/10 theo y anh, giup NGUOI MUA: loi chao AI, 'da ban tren X',
    hang chinh hang (chi khi co that), diem noi bat (AI, da loc bia), GIA NIEM YET (Accesstrade chi co gia nay; trong app
    co khuyen mai nen re hon) + meo mua re nhat."""
    title = it["title"] if len(it["title"]) <= 120 else it["title"][:117].rstrip() + "..."
    sold = it.get("sold") or 0
    lines = ([it["hook"], ""] if it.get("hook") else []) + [f"🔥 {title}" if title else "🔥 Deal hot hôm nay", ""]
    # 24/10 anh duyet: GIA len ngay duoi ten, 'hang ban chay' xuong cho gia cu (sau diem noi bat)
    if it.get("price"):
        if it.get("orig"):         # chi khi API tra gia goc that su cao hon
            save = it["orig"] - it["price"]
            lines += [f"❌ Giá gốc: {vnd(it['orig'])}",
                      f"✅ GIÁ SALE: {vnd(it['price'])}  (-{round(save / it['orig'] * 100)}%, tiết kiệm {vnd(save)})"]
        elif it.get("gia_that"):   # Shopee Affiliate tra GIA BAN THAT (da tru khuyen mai shop)
            lines.append(f"💰 Giá đang bán: {vnd(it['price'])}")
        else:                      # 23/10 anh duyet: khong ghi dung gia niem yet (nhin dat), ghi "duoi X" lam tron LEN -> luon dung
            gia = ("từ " if it.get("price_max") else "") + "dưới " + gia_tron(it["price"])
            lines.append(f"💰 Giá chỉ {gia} – bấm link đang sale còn rẻ hơn")
        if it.get("flash"):
            lines.append("⚡ Đang Flash Sale – giá có thể đổi nhanh, vào sớm kẻo lỡ")
    if it.get("rating") and it.get("reviews", 0) >= 20:     # sao THAT cua Shopee (TikTok/Accesstrade khong co -> khong ghi)
        lines.append(f"⭐ {it['rating']:.1f}/5 – {it['reviews']:,} lượt đánh giá".replace(",", "#").replace(".", ",").replace("#", "."))
    if it.get("mall"):
        lines.append(f"✅ Shopee Mall (hàng chính hãng) – shop {it['shop']}")
    elif it.get("official"):
        lines.append(f"✅ Hàng chính hãng – shop {it['shop']}" if it.get("shop") else "✅ Hàng chính hãng")
    elif it.get("shop"):
        lines.append(f"🏪 Shop: {it['shop']}" + (" (Yêu thích+)" if it.get("preferred") else ""))
    if it.get("vouchers"):
        lines.append("🎟 Mã giảm giá của shop (nhập lúc thanh toán):")
        lines += [f"   • {v['code']}" + (f" – {v['desc']}" if v.get("desc") else "") + (f" (HSD {v['end']})" if v.get("end") else "")
                  for v in it["vouchers"][:3]]
    if it.get("noi_bat"):
        lines.append("✨ Điểm nổi bật:")
        lines += [f"   • {p}" for p in it["noi_bat"]]
    st = sold_text(sold)
    if st:
        lines.append(f"🏆 Hàng bán chạy – đã bán {st} sản phẩm" if sold >= 10000 else f"🛒 Đã bán {st} sản phẩm")
    san = "Shopee" if it.get("san") == "shopee" else "TikTok"
    lines += [f"💡 Mẹo mua rẻ nhất: bấm “Lưu” voucher của shop + voucher {san}, chọn mã freeship rồi mới thanh toán",
              f"👉 BẤM XEM GIÁ SALE: {it['aff']}"]
    if moi and loi_moi_nhom():
        lines += ["", loi_moi_nhom()]
    return "\n".join(lines)


def vnd(x):
    return f"{int(round(x)):,}".replace(",", ".") + "đ"


def gia_tron(x):
    """Lam tron LEN (cao hon gia that) de ghi 'duoi ...': 62.779 -> '65k' ; 135.000 -> '140k' ; 294.999 -> '300k' ; 1.020.000 -> '1,1 triệu'."""
    x = int(x)
    step = 5000 if x < 100000 else 10000 if x < 1000000 else 100000
    v = (x // step + 1) * step
    return f"{v // 1000}k" if v < 1000000 else f"{v / 1000000:g}".replace(".", ",") + " triệu"


def send_due(cfg, meta, n, force):
    """Co phai luc gui tin khong? Tra ve (gui_ngay, nhan_slot). Khong dat send_hours = luon gui (kieu cu)."""
    hours = sorted(int(h) for h in cfg.get("send_hours") or [])
    if force or not hours:
        return True, None
    done = set(meta.get("slots_done", []))
    for h in reversed(hours):
        slot = f"{n.date().isoformat()}@{h}"
        if n.hour >= h and slot not in done:
            return True, slot
    return False, None


# ---------------------------------------------------------------- Telegram
class SendError(Exception):
    def __init__(self, msg, sent=0):
        super().__init__(msg)
        self.sent = sent


def split_chunks(text, limit=3800):
    chunks, cur = [], ""
    for block in text.split("\n\n"):
        while len(block) > limit:                      # khoi qua dai: cat theo dong
            cut = block.rfind("\n", 0, limit)
            cut = cut if cut > 0 else limit
            piece, block = block[:cut], block[cut:].lstrip("\n")
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(piece)
        if len(cur) + len(block) + 2 > limit and cur:
            chunks.append(cur)
            cur = ""
        cur += ("\n\n" if cur else "") + block
    if cur:
        chunks.append(cur)
    return chunks


def tg_post(bot, chat, text, tries=3, method="sendMessage", extra=None):
    fields = {"chat_id": chat, "text": text, "disable_web_page_preview": "true"} if method == "sendMessage" else {"chat_id": chat}
    fields.update(extra or {})
    data = urllib.parse.urlencode(fields).encode()
    for i in range(tries):
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"https://api.telegram.org/bot{bot}/{method}", data=data), timeout=30).read()
            return
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            if e.code == 429 and i < tries - 1:
                m = re.search(r'"retry_after"\s*:\s*(\d+)', body)
                time.sleep(min(int(m.group(1)) if m else 5, 30))
                continue
            if e.code >= 500 and i < tries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise RuntimeError(f"Telegram loi {e.code}: {body}")
        except urllib.error.URLError as e:
            if i < tries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise RuntimeError(f"Telegram loi mang: {e.reason}")


def send_telegram(bot, chat, text):
    sent = 0
    for c in split_chunks(text):
        try:
            tg_post(bot, chat, c)
        except Exception as e:
            raise SendError(str(e), sent)
        sent += 1
    return sent


def send_product(bot, chat, it, moi=False):
    """1 san pham = 1 tin co anh + chu thich (de chuyen tiep / dan sang Zalo). Anh loi thi gui chu."""
    cap = caption(it, moi)
    if it.get("image"):
        try:
            if len(cap) <= 1024:
                tg_post(bot, chat, "", method="sendPhoto", extra={"photo": it["image"], "caption": cap})
            else:                                      # Telegram gioi han chu thich anh 1024 ky tu -> anh rieng, tin chu ngay sau
                tg_post(bot, chat, "", method="sendPhoto", extra={"photo": it["image"]})
                tg_post(bot, chat, cap)
            return
        except Exception as e:
            print("  Gui anh loi, gui chu thay the:", e)
    tg_post(bot, chat, cap)


# ---------------------------------------------------------------- ban gop de dan Zalo: 1 anh ghep + 1 tin chu
NUM_ICONS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def combo_text(items):
    """1 tin chu cho ca dot, so thu tu khop voi so tren anh ghep."""
    lines = ["⚡ DEAL HOT TIKTOK SHOP HÔM NAY ⚡", "Bấm link xem voucher & giá mới nhất 👇", ""]
    for i, it in enumerate(items):
        t = it["title"] if len(it["title"]) <= 70 else it["title"][:67].rstrip() + "..."
        lines.append(f"{NUM_ICONS[i] if i < len(NUM_ICONS) else str(i + 1) + '.'} {t}")
        if it.get("orig"):
            lines.append(f"   ✅ {vnd(it['price'])} (giá gốc {vnd(it['orig'])}, -{round(100 - it['price'] / it['orig'] * 100)}%)")
        elif it.get("price"):
            lines.append(f"   💰 {'Chỉ từ ' if it.get('price_max') else ''}{vnd(it['price'])}"
                         + (f" · 🛒 {it['sold']:,}+ đã mua".replace(",", ".") if it.get("sold") else ""))
        lines += [f"   👉 {it['aff']}", ""]
    return "\n".join(lines).strip()


def make_collage(items):
    """Anh ghep 2 cot: moi o = anh san pham + so thu tu + gia. Tra ve bytes JPEG, None neu loi."""
    try:
        from io import BytesIO
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  Chua co Pillow (pip install pillow), bo qua anh ghep.")
        return None

    def font(bold, size):
        for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
            try:
                return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
            except OSError:
                try:
                    return ImageFont.truetype(name, size)
                except OSError:
                    pass
        return ImageFont.load_default()

    S, BAND, cols = 540, 120, 2
    rows = (len(items) + cols - 1) // cols
    W, H = S * cols, (S + BAND) * rows
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_num, f_price, f_sub = font(True, 64), font(True, 46), font(False, 30)
    for i, it in enumerate(items):
        x, y = (i % cols) * S, (i // cols) * (S + BAND)
        try:
            req = urllib.request.Request(it["image"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                p = Image.open(BytesIO(r.read())).convert("RGB")
            p.thumbnail((S, S))
            img.paste(p, (x + (S - p.width) // 2, y + (S - p.height) // 2))
        except Exception as e:
            print("  Tai anh loi:", str(e)[:80])
            d.rectangle([x, y, x + S, y + S], fill="#eeeeee")
        d.ellipse([x + 14, y + 14, x + 114, y + 114], fill="#fe2c55", outline="white", width=5)
        d.text((x + 64, y + 66), str(i + 1), font=f_num, fill="white", anchor="mm")
        d.rectangle([x, y + S, x + S, y + S + BAND], fill="#fff1f3")
        price = ("Chỉ từ " if it.get("price_max") else "") + vnd(it["price"]) if it.get("price") else "Xem giá trong app"
        d.text((x + S // 2, y + S + 42), price, font=f_price, fill="#fe2c55", anchor="mm")
        sub = f"-{round(100 - it['price'] / it['orig'] * 100)}% · giá gốc {vnd(it['orig'])}" if it.get("orig") else \
            (f"{it['sold']:,}+ người đã mua".replace(",", ".") if it.get("sold") else "Hàng hot TikTok Shop")
        d.text((x + S // 2, y + S + 92), sub, font=f_sub, fill="#444444", anchor="mm")
        d.line([x, y, x, y + S + BAND], fill="#dddddd", width=2)
    out = BytesIO()
    img.save(out, "JPEG", quality=88)
    return out.getvalue()


def _pil_font(bold, size):
    from PIL import ImageFont
    for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
        for p in (os.path.join(FONT_DIR, name), name):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def _wrap(d, text, font, width, max_lines):
    """Ngat dong theo do rong pixel; qua max_lines thi cat va them '…'."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    lines = [ln for ln in lines if ln]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and d.textlength(lines[-1] + "…", font=font) > width:
            lines[-1] = lines[-1].rsplit(" ", 1)[0] if " " in lines[-1] else lines[-1][:-1]
        lines[-1] += "…"
    return lines


def short_title(title, n=70):
    """Ten gon: bo phan quang cao trong ngoac [..] (..), cat ~n chu."""
    t = re.sub(r"[\[【{(（].*?[\]】})）]", " ", title)
    t = " ".join(t.split()) or title
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def _short_hook(it, n=90):
    """1 cau dau cua loi chao AI, toi da ~n chu."""
    hook = (it.get("hook") or "").strip()
    if hook:
        hook = re.split(r"(?<=[.!?…])\s+", hook)[0]
        if len(hook) > n:
            hook = hook[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return hook


def make_card(it, band=False):
    """24/10 kieu B cho Zalo (anh duyet): THE ANH NGANG 1200x560 - nen la chinh anh san pham phong to lam mo + toi,
    trai: anh san pham ro net, phai: ten gon, GIA, chinh hang / da ban, 2-3 diem noi bat. Tra bytes JPEG, None neu loi.
    Chu trong anh KHONG chep duoc -> link van nam o tin chu ben duoi anh (bam duoc)."""
    try:
        from io import BytesIO
        from PIL import Image, ImageDraw, ImageFilter, ImageOps
        req = urllib.request.Request(it["image"], headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            prod = Image.open(BytesIO(r.read())).convert("RGB")
    except Exception as e:
        print("  Lam the anh loi:", str(e)[:80])
        return None
    W, H, PAD = 1200, 560, 36
    bg = ImageOps.fit(prod, (W, H)).filter(ImageFilter.GaussianBlur(26))
    shade = Image.new("L", (W, H))
    shade.putdata([int(150 + 70 * x / W) for _ in range(H) for x in range(W)])     # trai toi vua, phai toi dam (chu de doc)
    bg = Image.composite(Image.new("RGB", (W, H), (12, 12, 20)), bg, shade)
    S = H - 2 * PAD                                    # anh san pham vuong ben trai, vien trang bo goc
    pic = ImageOps.pad(prod, (S, S), color="white")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], 26, fill=255)
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([PAD + 8, PAD + 12, PAD + S + 8, PAD + S + 12], 28, fill=170)
    bg = Image.composite(Image.new("RGB", (W, H), "black"), bg, shadow.filter(ImageFilter.GaussianBlur(14)))
    bg.paste(pic, (PAD, PAD), mask)
    d = ImageDraw.Draw(bg)
    x0, tw = PAD + S + 40, W - (PAD + S + 40) - PAD

    def fit(text, bold, size, width=tw):               # chu qua dai thi nho dan cho vua cot
        f = _pil_font(bold, size)
        while size > 18 and d.textlength(text, font=f) > width:
            size -= 2
            f = _pil_font(bold, size)
        return f
    # 25/10 anh muon chu TO lap kin khung (truoc con nhieu khoang den) + gia goc / % giam to hon:
    # chu to hon, so diem noi bat tu vua cho, ca khoi canh giua theo chieu doc
    f_tag, f_title, f_pt = _pil_font(True, 28), _pil_font(True, 46), _pil_font(False, 33)
    shopee = it.get("san") == "shopee"
    tag = "DEAL HOT SHOPEE" if shopee else "DEAL HOT TIKTOK SHOP"
    title_lines = _wrap(d, short_title(it["title"], 90), f_title, tw, 2)
    old, cut, sub = "", "", ""                         # gia goc (gach ngang) + % giam (do, dam) hoac 1 dong ghi chu
    if it.get("orig"):
        price = vnd(it["price"])
        old, cut = vnd(it["orig"]), f"-{round(100 - it['price'] / it['orig'] * 100)}%"
    elif it.get("gia_that"):
        price, sub = vnd(it["price"]), "Giá đang bán trên Shopee"
    elif it.get("price"):
        price, sub = ("Từ dưới " if it.get("price_max") else "Chỉ dưới ") + gia_tron(it["price"]), "Bấm link đang sale còn rẻ hơn"
    else:
        price, sub = "Xem giá trong app", ""
    f_price = fit(price, True, 92)
    f_old, f_cut = _pil_font(True, 40), _pil_font(True, 46)
    f_sub = fit(sub, True, 34) if sub else None
    badges = []
    if it.get("mall"):
        badges.append(("SHOPEE MALL", "#d0011b"))
    elif it.get("official"):
        badges.append(("CHÍNH HÃNG", "#16a34a"))
    if it.get("rating") and it.get("reviews", 0) >= 20:
        badges.append((f"{it['rating']:.1f} SAO".replace(".", ","), "#ca8a04"))   # phong chu khong co dau sao
    if it.get("vouchers"):
        badges.append(("CÓ MÃ GIẢM", "#7c3aed"))
    st = sold_text(it.get("sold") or 0)
    if st:
        badges.append((f"ĐÃ BÁN {st.replace('trên ', '').upper()}+", "#f97316"))
    rows, bx = [[]], 0                                 # nhan xep toi da 2 hang
    for text, color in badges:
        w = d.textlength(text, font=f_tag) + 32
        if bx + w > tw:
            if len(rows) == 2:
                break
            rows.append([])
            bx = 0
        rows[-1].append((text, color, bx, w))
        bx += w + 12
    rows = [r for r in rows if r]
    # do chieu cao ca khoi -> them diem noi bat toi khi day khung -> canh giua theo chieu doc
    LT, LP, LO, LB, LN = 56, 104, 58, 56, 48
    total = 68 + LT * len(title_lines) + 12 + LP + (LO if old else 50 if sub else 0) + LB * len(rows) + (10 if rows else 0)
    pts = []
    for p in (it.get("noi_bat") or [])[:4]:            # diem noi bat (AI, da loc bia)
        if total + LN > H - 2 * PAD:
            break
        pts.append(_wrap(d, p, f_pt, tw - 34, 1)[0])
        total += LN
    y = PAD + max(0, (H - 2 * PAD - total) // 2)
    d.rounded_rectangle([x0, y, x0 + d.textlength(tag, font=f_tag) + 36, y + 48], 24, fill="#ee4d2d" if shopee else "#fe2c55")
    d.text((x0 + 18, y + 24), tag, font=f_tag, fill="white", anchor="lm")
    y += 68
    for ln in title_lines:
        d.text((x0, y), ln, font=f_title, fill="white")
        y += LT
    y += 12
    d.text((x0, y), price, font=f_price, fill="#ffd400")
    y += LP
    if old:                                            # gia goc gach ngang + % giam do dam
        d.text((x0, y + 4), old, font=f_old, fill="#d4d4d4")
        ow = d.textlength(old, font=f_old)
        d.line([x0, y + 4 + 25, x0 + ow, y + 4 + 25], fill="#d4d4d4", width=4)
        cx = x0 + ow + 22
        cw = d.textlength(cut, font=f_cut) + 28
        d.rounded_rectangle([cx, y - 2, cx + cw, y + 52], 14, fill="#ef4444")
        d.text((cx + 14, y + 25), cut, font=f_cut, fill="white", anchor="lm")
        y += LO
    elif sub:
        d.text((x0, y), sub, font=f_sub, fill="#e8e8e8")
        y += 50
    for r in rows:
        for text, color, bx, w in r:
            d.rounded_rectangle([x0 + bx, y, x0 + bx + w, y + 44], 22, fill=color)
            d.text((x0 + bx + 16, y + 22), text, font=f_tag, fill="white", anchor="lm")
        y += LB
    y += 10 if rows else 0
    for p in pts:
        d.ellipse([x0 + 2, y + 13, x0 + 16, y + 27], fill="#ffd400")
        d.text((x0 + 32, y), p, font=f_pt, fill="white")
        y += LN
    if band:                                           # dai duoi day: loi chao (1 cau) + meo mua re -> tin chu chi con link
        f_h, f_tip = _pil_font(True, 33), _pil_font(False, 26)
        probe = ImageDraw.Draw(bg)
        hook = _short_hook(it, 130) or "Deal hot hôm nay – số lượng có hạn, chốt nhanh kẻo hết!"
        hl = _wrap(probe, hook, f_h, W - 2 * PAD, 2)
        BH = 20 + 42 * len(hl) + 46
        full = Image.new("RGB", (W, H + BH), "#fe2c55")
        full.paste(bg, (0, 0))
        d = ImageDraw.Draw(full)
        for i, ln in enumerate(hl):
            d.text((PAD, H + 14 + 42 * i), ln, font=f_h, fill="white")
        d.text((PAD, H + 20 + 42 * len(hl)), "Mẹo mua rẻ nhất: lưu voucher shop + TikTok, chọn mã freeship rồi mới đặt hàng",
               font=f_tip, fill="#ffe1e8")
        bg = full
    out = BytesIO()
    bg.save(out, "JPEG", quality=90)
    return out.getvalue()


def card_caption(it, band=False):
    """Chu ngan di kem the anh (Zalo kieu B). band=True: loi chao + meo da nam trong anh -> chi con link."""
    if band:
        return f"👉 XEM GIÁ SALE: {it['aff']}"
    hook = _short_hook(it)                             # chi 1 cau dau (cho 1 man hinh dien thoai chua nhieu mon hon)
    lines = [f"🔥 {hook}"] if hook else []
    if it.get("vouchers"):                             # ma giam phai o dang chu (chep duoc), khong chi trong anh
        lines.append("🎟 Mã shop: " + ", ".join(v["code"] for v in it["vouchers"][:3]))
    lines += ["💡 Lưu voucher + chọn freeship rồi mới đặt", f"👉 XEM GIÁ SALE: {it['aff']}"]
    return "\n".join(lines)


def tg_upload_photo(bot, chat, jpeg, caption=""):
    """Gui anh tu bytes (multipart) len Telegram."""
    b = "----dealbot" + str(int(time.time() * 1000))
    parts = []
    for k, v in (("chat_id", str(chat)), ("caption", caption[:1024])):
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="photo"; filename="deal.jpg"\r\n'
                 f'Content-Type: image/jpeg\r\n\r\n'.encode() + jpeg + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request(f"https://api.telegram.org/bot{bot}/sendPhoto", data=b"".join(parts),
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    urllib.request.urlopen(req, timeout=60).read()


def send_combo(bot, chat, items):
    """Ban gop: 1 anh ghep + 1 tin chu. Raise neu tin chu khong gui duoc."""
    jpeg = make_collage(items)
    if jpeg:
        try:
            tg_upload_photo(bot, chat, jpeg, "👆 Lưu ảnh này + copy tin bên dưới, dán vào nhóm Zalo")
        except Exception as e:
            print("  Gui anh ghep loi:", e)
    tg_post(bot, chat, combo_text(items))


# ---------------------------------------------------------------- Trang Facebook (Graph API chinh thuc)
FB_API = "https://graph.facebook.com/v21.0"


def fb_image_bytes(src):
    """Tai anh san pham ve (Facebook tu tai qua link hay bao 'Missing or invalid image file'). Co Pillow thi doi sang JPEG."""
    req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    try:
        from io import BytesIO
        from PIL import Image
        out = BytesIO()
        Image.open(BytesIO(data)).convert("RGB").save(out, "JPEG", quality=90)
        return out.getvalue()
    except Exception:                                  # khong co Pillow (GitHub) -> gui nguyen anh
        return data


def fb_post(page_id, page_token, it):
    """Dang 1 san pham len Trang: anh + chu thich (link bam duoc). Khong co anh thi dang bai chu kem link."""
    photo = None
    if it.get("image"):
        url, fields = f"{FB_API}/{page_id}/photos", {"caption": caption(it, True)}
        try:
            photo = fb_image_bytes(it["image"])
        except Exception as e:
            print("  Tai anh cho Facebook loi, de Facebook tu tai qua link:", e)
            fields["url"] = it["image"]
    else:
        url, fields = f"{FB_API}/{page_id}/feed", {"message": caption(it, True), "link": it["aff"]}
    fields["access_token"] = page_token
    if photo:                                          # gui file anh kem chu thich (multipart)
        b = "----dealbot" + str(int(time.time() * 1000))
        body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items())
        body += (f'--{b}\r\nContent-Disposition: form-data; name="source"; filename="deal.jpg"\r\n'
                 f'Content-Type: image/jpeg\r\n\r\n').encode() + photo + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    else:
        req = urllib.request.Request(url, data=urllib.parse.urlencode(fields).encode())
    try:
        urllib.request.urlopen(req, timeout=60).read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:200]
        hint = " (ma Trang het han/sai: chay lai nhap_facebook.bat)" if '"code":190' in body or e.code == 401 else ""
        raise RuntimeError(f"Facebook loi {e.code}{hint}: {body}")


def make_post(hook, it):
    """Gui 1 san pham sang Make.com (kich ban: Webhook -> Facebook Pages 'Create a Post with Photos')."""
    body = json.dumps({"image": it.get("image") or "", "message": caption(it, True), "link": it.get("aff") or ""}).encode()
    req = urllib.request.Request(hook, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()


def fb_quota_ok(meta, cfg, n):
    """Con duoc dang Facebook (qua Make) luc nay khong: chua qua so bai/ngay va da cach bai truoc du lau."""
    fb = meta.get("fb_make") or {}
    today = n.date().isoformat()
    if fb.get("date") == today and int(fb.get("count", 0)) >= int(cfg["fb_max_per_day"]):
        return False
    return not recent(fb.get("last", ""), float(cfg["fb_gap_hours"]), n)


# ---------------------------------------------------------------- san pham win (moi ngay 1 lan, chat rieng)
# API khong tra nganh hang -> moi nganh tim theo vai tu khoa ban chay. Them nganh moi: them 1 dong vao day.
# Moi ngay quet win_keywords_per_day tu, xoay vong (win_keywords) -> vai ngay quet het ma so luot goi API khong tang.
WIN_KEYWORDS = {
    "gia_dung": ("Gia dụng", ["nồi chiên không dầu", "máy xay sinh tố", "bình giữ nhiệt", "hộp đựng thực phẩm",
                              "chảo chống dính", "kệ để đồ", "nồi cơm điện", "ấm siêu tốc", "máy hút bụi", "bộ nồi",
                              "máy lọc không khí", "quạt", "đèn ngủ", "cây lau nhà", "móc treo quần áo", "giỏ đựng đồ",
                              "dao làm bếp", "thớt", "máy ép chậm", "bàn là hơi nước", "máy sấy tóc", "nồi lẩu điện",
                              "khăn tắm", "rèm cửa", "thảm lau chân"]),
    "my_pham": ("Mỹ phẩm", ["serum", "kem chống nắng", "sữa rửa mặt", "son", "kem dưỡng", "nước tẩy trang",
                            "toner", "mặt nạ", "dầu gội", "nước hoa", "sữa tắm", "kem nền", "phấn phủ", "mascara",
                            "kẻ mắt", "tẩy tế bào chết", "dưỡng thể", "dầu xả", "xịt khoáng", "kem trị mụn",
                            "son dưỡng", "tinh dầu dưỡng tóc", "kem mắt", "phấn má", "cushion"]),
    "thoi_trang": ("Thời trang", ["áo thun", "quần jean", "váy", "giày", "túi xách", "áo khoác",
                                  "áo sơ mi", "dép", "đồ bộ", "balo", "quần short", "áo len", "chân váy", "đồ ngủ",
                                  "giày thể thao", "sandal", "ví", "thắt lưng", "mũ", "kính mát", "tất",
                                  "áo polo", "quần tây", "đồ lót", "áo hoodie"]),
    "me_va_be": ("Mẹ và bé", ["bỉm", "sữa bột", "đồ chơi trẻ em", "quần áo trẻ em", "bình sữa", "khăn sữa",
                              "xe đẩy", "địu em bé", "máy hâm sữa", "ghế ăn dặm", "khăn ướt", "sữa tắm em bé",
                              "núm ti", "yếm ăn", "chăn ủ", "nhiệt kế", "máy hút sữa", "thảm chơi", "đồ chơi giáo dục",
                              "giày tập đi", "ba lô trẻ em", "bàn chải trẻ em", "kem hăm", "gối chống bẹt đầu",
                              "tã quần"]),
}


def win_keywords(key, n, cfg=None):
    """Tu khoa quet hom nay: lay win_keywords_per_day tu lien tiep, moi ngay dich sang nhom tiep theo (xoay vong)."""
    kws = WIN_KEYWORDS[key][1]
    k = min(int((cfg or DEFAULTS).get("win_keywords_per_day") or len(kws)), len(kws))
    start = (n.date().toordinal() * k) % len(kws)
    return [kws[(start + i) % len(kws)] for i in range(k)]


# Hang theo mua: (cac thang, tu trong ten san pham - viet khong dau). San pham hop mua duoc cong diem x1,5.
MUA_VU = [
    ((10, 11, 12, 1, 2), ["giu nhiet", "may suoi", "chan dien", "chan long", "chan ga", "ao len", "ao khoac", "khan quan",
                          "duong am", "son duong", "noi lau", "bep lau", "may say", "nong lanh"]),
    ((12, 1, 2), ["tet", "li xi", "hop qua", "banh keo", "mut", "trang tri", "den led", "ao dai"]),
    ((3, 4, 5, 6, 7, 8), ["quat", "chong nang", "dieu hoa", "lam mat", "do boi", "binh nuoc", "da lanh", "muoi"]),
    ((8, 9), ["balo", "cap sach", "den hoc", "ban hoc"]),
    ((9, 10, 11), ["qua tang", "hop qua"]),        # Trung thu, 20/10, 20/11
]


def hop_mua(title, month):
    t = fold(title)
    return any(re.search(r"\b" + w + r"\b", t) for months, words in MUA_VU if month in months for w in words)


def win_due(cfg, meta, n):
    """Den gio gui san pham win va hom nay chua gui."""
    return bool(cfg.get("nganh_win")) and n.hour >= int(cfg["win_hour"]) and meta.get("win_date") != n.date().isoformat()


def win_per_day(hist, pid, sold, day):
    """So don ban them moi ngay, so voi lan ghi som nhat trong 7 ngay truoc. Chua co so cu -> None."""
    old = [h for h in hist.get(pid) or [] if day - 7 <= h[0] < day]
    if not old:
        return None
    d0, s0 = old[0]
    return max(sold - s0, 0) / (day - d0)


def win_score(it):
    """Thang 100: tang nong 40 + tong da ban 30 + % hoa hong 20 + hop mua 10. Accesstrade KHONG co so sao -> khong cham sao."""
    g = it.get("per_day")
    hot = 40 * min(math.log10(g + 1) / math.log10(501), 1) if g else 0           # +500 don/ngay = du 40
    ban = 30 * min(max((math.log10(max(it["sold"], 1)) - 2) / (math.log10(50000) - 2), 0), 1)   # 100 -> 0, 50.000 -> 30
    hh = 20 * min(it["pct"] / 20, 1)                                              # 20% hoa hong = du 20
    return hot + ban + hh + (10 if it.get("mua") else 0)


def win_record(state, items, cfg, n):
    """Ghi so da ban hom nay cua moi hang trong khoang gia (de mai tinh 'ban them moi ngay'). Bo hang khong thay qua 14 ngay."""
    hist, day = state.setdefault("win_sold", {}), n.date().toordinal()
    for x in items:
        it = tt_info(x)
        if it["id"] and it["sold_known"] and cfg["win_min_price"] <= it["price"] <= cfg["win_max_price"]:
            h = [p for p in hist.get(it["id"]) or [] if p[0] != day and p[0] >= day - 7][-3:]
            hist[it["id"]] = h + [[day, it["sold"]]]
    for pid in [p for p, h in hist.items() if not h or h[-1][0] < day - 14]:
        del hist[pid]


def pick_win(items, cfg, month=None, hist=None, day=None):
    """Loc gia, con hang, da ban >= min_sold (shop giau so ban thi bo), hoa hong >= win_min_commission;
    xep theo win_score (thang 100). hist = state['win_sold'] de tinh tang nong. Moi shop 1 san pham."""
    month, hist = month or now().month, hist or {}
    day = day or now().date().toordinal()
    min_pct = cfg.get("win_min_commission", cfg["min_commission"])
    cands, seen = [], set()
    for x in items:
        it = tt_info(x)
        if not it["id"] or it["id"] in seen or not it["url"] or not it["stock"]:
            continue
        seen.add(it["id"])
        if not (cfg["win_min_price"] <= it["price"] <= cfg["win_max_price"]):
            continue
        if not it["sold_known"] or it["sold"] < cfg["min_sold"] or it["pct"] < min_pct:
            continue
        it["mua"] = hop_mua(it["title"], month)
        it["per_day"] = win_per_day(hist, it["id"], it["sold"], day)
        it["score"] = win_score(it)
        cands.append((it["score"], it))
    cands.sort(key=lambda c: -c[0])
    out, shops = [], set()
    for _, it in cands:
        if it["shop"] and it["shop"] in shops:
            continue
        shops.add(it["shop"])
        out.append(it)
    return out


def tiktok_search(title):
    """Link tim kiem TikTok theo ten san pham (bo phan quang cao trong ngoac, lay ~8 tu dau) de xem so da ban."""
    t = re.sub(r"[\[【{(（].*?[\]】})）]", " ", title)
    t = " ".join(re.sub(r"[^\w\s]", " ", t).split()[:8]) or title[:60]
    return "https://www.tiktok.com/search?q=" + urllib.parse.quote(t)


def fb_ads_search(title):
    """Link Thu vien quang cao Facebook (quang cao DANG CHAY o VN) theo ~4 tu dau ten san pham. API Facebook chi tra quang cao
    thuong mai o EU/Anh, TikTok Creative Center can dang nhap -> bot khong tu dem duoc, chi dua link de anh bam xem."""
    t = re.sub(r"[\[【{(（].*?[\]】})）]", " ", title)
    t = " ".join(re.sub(r"[^\w\s]", " ", t).split()[:4]) or title[:40]
    return ("https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=VN&media_type=all"
            "&search_type=keyword_unordered&q=" + urllib.parse.quote(t))


def win_text(items, ten_nganh, n):
    lines = [f"🏆 Sản phẩm win hôm nay – {ten_nganh} ({n:%d/%m})",
             f"Giá {vnd(items[0]['_min'])}–{vnd(items[0]['_max'])} · điểm 100 = 🔥 tăng nóng 40 + 🛒 đã bán 30 + 🎁 % hoa hồng 20 + 🍂 hợp mùa 10", ""]
    if not any(it.get("per_day") is not None for it in items):
        lines[-1:] = ["(🔥 tăng nóng cần số đã bán của hôm trước — vài ngày đầu chưa có nên mục này tạm 0 điểm)", ""]
    for i, it in enumerate(items, 1):
        t = it["title"] if len(it["title"]) <= 80 else it["title"][:77].rstrip() + "..."
        info = [f"💰 {vnd(it['price'])}", f"🎁 HH {it['pct']:.1f}% ≈ {vnd(it['commission'])}".replace(".", ",", 1)]
        if it.get("sold"):
            info.append(f"🛒 {it['sold']:,} đã bán".replace(",", "."))
        if it.get("per_day") is not None:
            info.append(f"🔥 +{round(it['per_day']):,} đơn/ngày".replace(",", "."))
        diem = f" — {round(it['score'])} điểm" if "score" in it else ""
        lines += [f"{i}. {'🍂 ' if it.get('mua') else ''}{t}{diem}", "   " + " · ".join(info), f"   👉 {it['aff']}",
                  f"   🔍 Xem trên TikTok: {tiktok_search(it['title'])}",
                  f"   📢 Ai đang chạy quảng cáo (Facebook): {fb_ads_search(it['title'])}", ""]
    return "\n".join(lines).strip()


def send_win(token, cfg, state, n, bot, chat, dry):
    """Quet san pham win theo nganh, gui 1 tin ve chat rieng. Loi o day khong lam hong phan gui deal."""
    key = str(cfg.get("nganh_win") or "").strip().lower()
    if key not in WIN_KEYWORDS:
        print(f"[win] Nganh '{key}' khong co. Chon 1 trong: {', '.join(WIN_KEYWORDS)}")
        return
    ten, kws = WIN_KEYWORDS[key][0], win_keywords(key, n, cfg)
    raw = []
    for kw in kws:                                     # moi tu khoa 2 trang (40 san pham): chi ~1/10 lot khoang gia
        p = {"sort_field": "BEST_SELLERS", "limit": 20, "title_keywords": kw}
        for _ in range(2):
            prods, page_token, _ = tt_call(token, p, f"win '{kw}'")
            raw += prods
            time.sleep(2)
            if not page_token:
                break
            p = dict(p, page_token=page_token)
    out = []
    for it in pick_win(raw, cfg, n.month, state.get("win_sold"), n.date().toordinal()):
        if len(out) >= int(cfg["win_count"]):
            break
        d = make_link(token, it["url"], it["id"])
        if d:
            it["aff"] = d.get("aff_short_url") or d.get("aff_url")
            it["_min"], it["_max"] = cfg["win_min_price"], cfg["win_max_price"]
            out.append(it)
    print(f"[win] {len(raw)} san pham quet -> chon {len(out)} ({ten})")
    if dry:
        print("\n" + (win_text(out, ten, n) if out else "[win] khong co san pham nao dat") + "\n")
        return
    if out:
        send_telegram(bot, chat, win_text(out, ten, n))
    win_record(state, raw, cfg, n)
    state["meta"]["win_date"] = n.date().isoformat()     # khong co san pham dat cung tinh la xong hom nay (do goi API moi gio)
    save_json(STATE_FILE, state)


def safe_alert(bot, chat, text, dry):
    if dry or not (bot and chat):
        print("[canh bao]", text)
        return
    try:
        send_telegram(bot, chat, text)
    except Exception as e:
        print("Khong gui duoc canh bao:", e)


# ---------------------------------------------------------------- chay chinh
def main():
    cfg = load_config()
    n = now()
    force = os.environ.get("FORCE", "").lower() == "true"
    dry = os.environ.get("DRY_RUN") == "1"
    if not force and not (cfg["active_from"] <= n.hour < cfg["active_to"]):
        print(f"Ngoai gio gui ({n.hour}h), bo qua.")
        return
    token = get_token()
    local = load_json("config.local.json", {})        # chay tren may: token Telegram luu o day (nhap_telegram.bat)
    bot = os.environ.get("TELEGRAM_BOT_TOKEN", "") or str(local.get("telegram_bot_token", "")).strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "") or str(local.get("telegram_chat_id", "")).strip()
    channel = os.environ.get("TELEGRAM_CHANNEL_ID", "") or str(local.get("telegram_channel_id", "")).strip()   # kenh: bot tu dang tung san pham
    fb_page = os.environ.get("FB_PAGE_ID", "") or str(local.get("fb_page_id", "")).strip()       # Trang Facebook dang thang (nhap_facebook.bat)
    fb_token = os.environ.get("FB_PAGE_TOKEN", "") or str(local.get("fb_page_token", "")).strip()
    fb2_page = os.environ.get("FB_PAGE2_ID", "") or str(local.get("fb_page2_id", "")).strip()   # 25/10 Trang 2 "Cuoi Moi Ngay Sale Hoi"
    fb2_token = os.environ.get("FB_PAGE2_TOKEN", "") or str(local.get("fb_page2_token", "")).strip()
    make_hook = os.environ.get("MAKE_WEBHOOK", "") or str(local.get("make_webhook", "")).strip()   # Trang Facebook qua Make.com
    win_chat = (os.environ.get("TELEGRAM_WIN_CHAT_ID", "").strip() or str(local.get("telegram_win_chat_id", "")).strip()
                or chat)                       # nhom rieng chi nhan 'San pham win'; chua co thi gui chat rieng
    if os.environ.get("CHI_RIENG") == "1":             # nut 'Chay ngay' tren may: chi gui chat rieng (sent.json tren may cu hon GitHub -> tranh dang trung kenh/Trang)
        channel = fb_page = fb_token = make_hook = fb2_page = fb2_token = ""
    if not token or (not dry and not (bot and chat)):
        sys.exit("Thieu token (ACCESSTRADE_TOKEN / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID). Tren may: bam dup nhap_telegram.bat.")
    if not cfg["merchants"] and not cfg["tiktok"]:
        sys.exit("Chua bat san nao (shopee / tiktok trong config.json).")

    state = migrate_state(load_json(STATE_FILE, {}))
    links_file = read_links()
    cleanup_state(state, set(links_file), cfg, n)
    meta, ts = state["meta"], n.isoformat()
    if cfg["tiktok"] and (win_due(cfg, meta, n) or os.environ.get("WIN") == "1"):   # WIN=1: chay thu san pham win ngay
        try:
            send_win(token, cfg, state, n, bot, win_chat, dry)
        except Exception as e:
            print("[win] LOI:", str(e)[:200])
    do_send, slot = send_due(cfg, meta, n, force)
    if not do_send:
        print(f"Chua den gio gui ({n.hour}h, khung gio gui: {cfg['send_hours']}), khong co gi de lam.")
        return

    # --- lay du lieu
    offers, raw, fails, tried = [], [], [], 0
    for m in cfg["merchants"]:
        tried += 1
        try:
            got = fetch_offers(token, m, pages=int(cfg["fetch_pages"]))
            print(f"[{m}] {len(got)} khuyen mai")
            if not got:
                print(f"[{m}] CANH BAO: 0 khuyen mai. Kiem tra chien dich da duoc duyet chua.")
            offers += got
        except Exception as e:
            fails.append(f"{m}: {describe_error(e)}")
            print(f"[{m}] LOI {describe_error(e)}")
    if cfg["tiktok"]:
        tried += 1
        try:
            raw = fetch_tiktok(token, cfg)
            print(f"[tiktok] {len(raw)} san pham")
            if not raw:
                print("[tiktok] CANH BAO: 0 san pham. Kiem tra chien dich TikTok Shop CPS tren Accesstrade.")
        except Exception as e:
            fails.append(f"tiktok: {describe_error(e)}")
            print(f"[tiktok] LOI {describe_error(e)}")

    # --- theo doi loi, canh bao khi loi lien tiep
    was_down = bool(meta.get("alerted"))
    if fails:
        meta["fail_count"] = int(meta.get("fail_count", 0)) + 1
        meta["last_error"] = "; ".join(fails)[:300]
        last = meta.get("last_alert")
        if (meta["fail_count"] >= cfg["alert_after_failures"]
                and (not last or not recent(last, cfg["alert_cooldown_hours"], n))):
            safe_alert(bot, chat, f"⚠️ Bot deal đang lỗi {meta['fail_count']} lần liên tiếp:\n{meta['last_error']}", dry)
            meta["last_alert"], meta["alerted"] = ts, True
    else:
        if was_down:
            safe_alert(bot, chat, "✅ Bot deal đã hoạt động lại bình thường.", dry)
        meta.update(fail_count=0, alerted=False)
    if len(fails) == tried:
        if not dry:
            save_json(STATE_FILE, state)
        sys.exit("Khong lay duoc du lieu tu Accesstrade: " + "; ".join(fails))

    # --- link anh tu dan trong my_links.txt: link TikTok goc -> doi sang link hoa hong (kem anh, gia)
    mine, text_links, bad_links = [], [], []
    for l in [l for l in links_file if l not in state["links"]]:
        if is_tiktok_raw(l):
            d = make_link(token, l, full=True)
            if d:
                it = from_link_data(d, l)
                it["src"] = l
                mine.append(it)
            else:
                bad_links.append(l)
        else:
            text_links.append(l)              # da la link hoa hong: gui nguyen

    # --- chon san pham TikTok, tao link hoa hong (link loi thi lay san pham du phong)
    sp_items = pick_shopee(state, cfg, n)              # hang Shopee (may anh chon moi sang) thay 1 cho hang TikTok
    picks, pstats = pick_tiktok(raw, state, cfg, n)
    products = []
    for it in picks:
        if len(products) >= cfg["max_products"] - len(sp_items):
            break
        d = make_link(token, it["url"], it["id"])
        if d:
            it["aff"] = d.get("aff_short_url") or d.get("aff_url")
            products.append(it)
        else:
            pstats["tao link loi"] += 1
    posts = mine + sp_items + products
    if sp_items:
        print(f"[shopee] {len(sp_items)} mon tu shopee_hang.json")

    # --- chon voucher Shopee
    chosen, stats, samples = pick_new(offers, state, cfg, n)
    if posts:
        chosen = chosen[: cfg["max_vouchers"]]
    if cfg["merchants"]:
        print(f"Tong {len(offers)} khuyen mai -> chon {len(chosen)} voucher. Loai: "
              + (", ".join(f"{k} {v}" for k, v in stats.most_common()) or "khong co"))
        for s_ in samples:
            print("  vi du bi loai:", s_)
    summary = (f"Tổng {len(raw)} sản phẩm TikTok -> chọn {len(products)}. Loại: "
               + (", ".join(f"{k} {v}" for k, v in pstats.most_common()) or "không có"))
    print(summary)

    msg = build_message(chosen, text_links, n)
    if bad_links:
        msg += ("\n\n" if msg else "") + "⚠️ Link không đổi được sang link hoa hồng (sản phẩm không tham gia tiếp thị liên kết):\n" + "\n".join(bad_links)

    if not posts and not msg:
        print("Khong co gi moi de gui.")
        if force and not dry:
            safe_alert(bot, chat, "✅ Bot chạy tốt. Hiện chưa có sản phẩm/voucher mới.\n" + summary, dry)
        if slot:
            meta.setdefault("slots_done", []).append(slot)
        save_json(STATE_FILE, state) if not dry else None
        return

    add_hooks(posts, cfg)                         # AI viet loi chao hang cho Telegram + Trang Facebook
    if dry:
        if cfg["zalo_combo"] and len(posts) >= 2:
            jpeg = make_collage(posts)
            if jpeg:
                with open(os.path.join(HERE, "anh_ghep_thu.jpg"), "wb") as f:
                    f.write(jpeg)
                print("\n[ANH GHEP] da luu anh_ghep_thu.jpg")
            print("\n" + combo_text(posts))
        else:
            for it in posts:
                print("\n[ANH] " + (it.get("image") or "(khong co anh)") + "\n" + caption(it))
        if msg:
            print("\n" + msg)
        print("\n(DRY_RUN: khong gui, khong luu trang thai)")
        return

    # --- gui: moi san pham 1 tin co anh, sau do 1 tin chu (voucher, link)
    errors, sent_any, sent_items = [], False, []
    combo_ok = False
    if cfg["zalo_combo"] and len(posts) >= 2:
        try:
            send_combo(bot, chat, posts)
            combo_ok = True
        except Exception as e:
            print("LOI gui ban gop, gui tung san pham:", e)
    for it in posts:
        try:
            if not combo_ok:
                send_product(bot, chat, it)
        except Exception as e:
            errors.append(str(e))
            print("LOI gui san pham:", e)
            continue
        if channel and channel != chat:
            try:
                send_product(bot, channel, it, moi=True)
            except Exception as e:                     # kenh loi khong lam hong tin gui cho anh
                print("LOI dang len kenh (bot da la admin kenh chua?):", e)
        sent_any = True
        sent_items.append(it)
        if it.get("src"):
            state["links"][it["src"]] = {"t": ts}
        else:
            state["products"][it.get("key") or "tt|" + it["id"]] = {"t": ts}
        if not combo_ok:
            time.sleep(1)
    # --- Trang Facebook: 1 bai/lan chay, gioi han so bai/ngay (khong lam hong Telegram neu loi).
    # Co ma Trang -> dang thang (khong ton credits Make); chua co -> gui qua Make nhu cu. Khong bao gio dang ca 2.
    fb_item = next((x for x in sent_items if x.get("image") and x.get("aff")), None)   # co loi chao AI nhu Telegram (anh muon 23/10)
    direct = bool(fb_page and fb_token)
    if (direct or make_hook) and fb_item and fb_quota_ok(meta, cfg, n):
        try:
            if dry:
                print("[chay thu] se dang Facebook", "thang" if direct else "qua Make", ":", fb_item.get("title", "")[:60])
            elif direct:
                fb_post(fb_page, fb_token, fb_item)
            else:
                make_post(make_hook, fb_item)
            fb = meta.get("fb_make") or {}
            cnt = int(fb.get("count", 0)) + 1 if fb.get("date") == n.date().isoformat() else 1
            meta["fb_make"] = {"date": n.date().isoformat(), "count": cnt, "last": ts}
            meta["fb_fail"] = 0
            print(f"Da dang Trang Facebook {'thang' if direct else 'qua Make'} (bai {cnt}/{cfg['fb_max_per_day']} hom nay)")
        except Exception as e:                         # Facebook loi khong lam hong Telegram
            print("LOI dang Facebook:", str(e)[:200])
            meta["fb_fail"] = meta.get("fb_fail", 0) + 1
            if meta["fb_fail"] == 3:
                safe_alert(bot, chat, f"⚠️ Đăng Trang Facebook lỗi 3 lần liên tiếp:\n{str(e)[:250]}", dry)
    # Trang 2: MON KHAC Trang 1 (mon thu 2 cua lan chay), han muc rieng (meta "fb_page2")
    fb2_item = next((x for x in sent_items if x.get("image") and x.get("aff") and x is not fb_item), None)
    if fb2_page and fb2_token and fb2_item and fb_quota_ok({"fb_make": meta.get("fb_page2")}, cfg, n):
        try:
            if dry:
                print("[chay thu] se dang Trang 2:", fb2_item.get("title", "")[:60])
            else:
                fb_post(fb2_page, fb2_token, fb2_item)
            fb = meta.get("fb_page2") or {}
            cnt = int(fb.get("count", 0)) + 1 if fb.get("date") == n.date().isoformat() else 1
            meta["fb_page2"] = {"date": n.date().isoformat(), "count": cnt, "last": ts}
            print(f"Da dang Trang 2 (bai {cnt}/{cfg['fb_max_per_day']} hom nay)")
        except Exception as e:
            print("LOI dang Trang 2:", str(e)[:200])
    if msg:
        send_err = None
        try:
            send_telegram(bot, chat, msg)
        except SendError as e:
            send_err = e
            errors.append(str(e))
            print("LOI gui Telegram:", e)
        if send_err is None or send_err.sent > 0:     # gui duoc it nhat 1 phan: danh dau da gui de khong gui trung
            sent_any = True
            for o in chosen:
                state["offers"][offer_key(o)] = {"t": ts, "exp": end_date(o)}
                state["shops"][parse_offer(o)["shop"]] = {"t": ts}
            for l in text_links + bad_links:
                state["links"][l] = {"t": ts}
    if sent_any and slot:
        meta.setdefault("slots_done", []).append(slot)
        meta["slots_done"] = meta["slots_done"][-12:]
    save_json(STATE_FILE, state)
    if errors:
        sys.exit(f"Gui Telegram loi: {errors[0]}")
    print(f"Da gui {len(posts)} san pham, {len(chosen)} voucher, {len(text_links)} link.")


if __name__ == "__main__":
    main()
