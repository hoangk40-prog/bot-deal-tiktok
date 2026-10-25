"""Deal SHOPEE qua tai khoan Shopee Affiliate RIENG cua anh (25/10, anh duyet: "doc thua moi ngay 1 lan").

Accesstrade ngung duyet Shopee, Open API chua co quyen -> bot dung Chrome rieng TREN MAY (da dang nhap affiliate.shopee.vn):
  1. Moi ngay 1 lan doc THUA vai nhom hang (nghi 30-60s giua 2 lan; 25/10 doc ~15 lan trong vai phut la Shopee bat captcha).
  2. Chon hang giup NGUOI MUA (nguyen tac anh dan 23/10): sao cao that, nhieu danh gia, ban chay, dang giam gia that,
     Shopee Mall, CO MA GIAM CUA SHOP (ma tren the san pham + ma Shopee cua Accesstrade ghep theo ten shop). Khong bia.
  3. Tao link rut gon s.shopee.vn qua trang Custom Link (bam nhu nguoi; goi API tay bi chong bot chan).
  4. Ghi shopee_hang.json (o may: %LOCALAPPDATA%/shopee_bot, cho bot Zalo) + day len GitHub (bot GitHub moi lan dang lay 1 mon).
Gap captcha / bi dang xuat -> DUNG ngay, nhan Telegram cho anh (khong co gang doc tiep).

Lenh:  python shopee_bot.py dang_nhap   (mo Chrome cua bot, anh dang nhap Shopee 1 lan)
       python shopee_bot.py lay         (lay hang hom nay - lich Windows goi moi sang)
       python shopee_bot.py xem         (in hang da chon)
Bien:  DRY_RUN=1 khong day GitHub, khong tao link (chi chon hang) ; HIEN=1 hien cua so ; SO_TU=6 so nhom hang/ngay
"""
import base64
import datetime
import json
import math
import os
import random
import re
import subprocess
import sys
import time

import auto_deals as ad

OUT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ad.HERE), "shopee_bot")
PROFILE = os.path.join(OUT_DIR, "chrome")                      # o may, KHONG de tren Drive
HANG = os.path.join(OUT_DIR, "shopee_hang.json")
REPO = "hoangk40-prog/bot-deal-tiktok"
AFF = "https://affiliate.shopee.vn"
IMG = "https://down-vn.img.susercontent.com/file/"

# Moi ngay lay SO_TU tu, xoay vong -> ~1 tuan quet het. Uu tien hang dung hang ngay, gia vua (de co nguoi mua).
SHOPEE_KEYWORDS = [
    "nồi chiên không dầu", "kem chống nắng", "bình giữ nhiệt", "áo thun nữ", "sạc dự phòng", "tã quần",
    "hộp đựng thực phẩm", "sữa rửa mặt", "dép nữ", "tai nghe bluetooth", "khăn giấy", "đồ chơi trẻ em",
    "chảo chống dính", "son kem", "túi xách nữ", "cáp sạc", "nước giặt", "bỉm",
    "máy xay sinh tố", "serum", "quần jean nữ", "đèn ngủ", "dầu gội", "bình sữa",
    "cây lau nhà", "tẩy trang", "giày thể thao", "ốp lưng điện thoại", "kem đánh răng", "balo",
    "kệ để đồ", "mặt nạ", "váy nữ", "quạt mini", "bàn chải điện", "đồ ăn vặt",
]

SP_DEFAULTS = {
    "sp_so_tu": 6,             # so nhom hang doc moi ngay
    "sp_per_day": 18,          # so mon chon moi ngay (bot GitHub 16 lan/ngay x 1 mon + du phong)
    "sp_min_rating": 4.8,      # sao toi thieu (sao THAT cua Shopee)
    "sp_min_reviews": 30,      # so luot danh gia toi thieu (it qua thi sao khong dang tin)
    "sp_max_per_keyword": 4,   # moi nhom hang toi da bao nhieu mon (cho da dang)
    "sp_repick_days": 7,       # mon da chon: nghi bao nhieu ngay moi chon lai
}


def log(*a):
    msg = f"[{ad.now():%d/%m %H:%M:%S}] " + " ".join(str(x) for x in a)
    print(msg, flush=True)
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, "nhat_ky.txt"), "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def alert(text):
    local = ad.load_json("config.local.json", {})
    bot, chat = str(local.get("telegram_bot_token", "")).strip(), str(local.get("telegram_chat_id", "")).strip()
    if bot and chat and os.environ.get("DRY_RUN") != "1":
        try:
            ad.send_telegram(bot, chat, text)
        except Exception as e:
            log("Khong gui duoc canh bao Telegram:", e)


def load_cfg():
    cfg = dict(SP_DEFAULTS)
    cfg.update(ad.load_config())
    return cfg


def read_hang():
    try:
        with open(HANG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def browser(p, an=False):
    os.makedirs(PROFILE, exist_ok=True)
    args = ["--disable-blink-features=AutomationControlled"]
    if an:
        args += ["--window-position=-32000,-32000"]          # Chrome that, mo ngoai man hinh (anh khong bam nham)
    return p.chromium.launch_persistent_context(
        PROFILE, channel="chrome", headless=False, viewport={"width": 1280, "height": 860}, locale="vi-VN", args=args)


class Blocked(Exception):
    pass


def check_page(page):
    u = page.url
    if "verify/captcha" in u or "verify/traffic" in u:
        raise Blocked("Shopee bắt giải mã xác minh (captcha)")
    if "login" in u or "account.shopee" in u or "/buyer/" in u:
        raise Blocked("Chrome của bot chưa đăng nhập / bị đăng xuất Shopee Affiliate")


def open_aff(page, path="/offer/product_offer"):
    page.goto(AFF + path, wait_until="domcontentloaded", timeout=60000)
    time.sleep(random.uniform(4, 7))
    check_page(page)


JS_LIST = """async (kw) => {
  const u = `/api/v3/offer/product/list?list_type=0&sort_type=2&keyword=${encodeURIComponent(kw)}&page_offset=0&page_limit=50&client_type=1`;
  const r = await fetch(u, {credentials: 'include'});
  return await r.text();
}"""


def fetch_keyword(page, kw):
    txt = page.evaluate(JS_LIST, kw)
    try:
        j = json.loads(txt)
    except Exception:
        j = {}
    lst = (j.get("data") or {}).get("list")
    if lst is None:
        check_page(page)
        raise Blocked(f"Shopee không trả danh sách ({txt[:80]})")
    return lst


# ---------------------------------------------------------------- doc 1 san pham
def pct(s):
    try:
        return float(str(s).replace("%", "").replace(",", ".").strip() or 0)
    except ValueError:
        return 0.0


def money(x):
    try:
        return int(x) / 100000
    except (TypeError, ValueError):
        return 0


def sp_info(x, kw):
    c = x.get("batch_item_for_item_card_full") or {}
    price = money(c.get("price"))
    before = money(c.get("price_before_discount"))
    rating = c.get("item_rating") or {}
    rc = rating.get("rating_count") or [0]
    vouchers = []
    vi = c.get("voucher_info")
    if isinstance(vi, dict) and vi.get("voucher_code"):
        vouchers.append({"code": vi["voucher_code"], "desc": str(vi.get("label") or "").strip()})
    for v in x.get("promotion_vouchers") or []:
        if isinstance(v, dict) and v.get("voucher_code") and v["voucher_code"] not in {a["code"] for a in vouchers}:
            vouchers.append({"code": v["voucher_code"], "desc": str(v.get("label") or v.get("title") or "").strip()})
    shopid, itemid = str(c.get("shopid") or ""), str(c.get("itemid") or x.get("item_id") or "")
    return {
        "san": "shopee", "id": f"{shopid}_{itemid}", "key": f"sp|{shopid}_{itemid}", "kw": kw,
        "title": str(c.get("name") or "").strip(), "shop": str(c.get("shop_name") or "").strip(),
        "price": price, "orig": before if before > price * 1.03 else 0, "gia_that": True,
        "rating": round(float(rating.get("rating_star") or 0), 2), "reviews": int(rc[0] or 0),
        "sold": int(c.get("historical_sold") or 0), "sold_month": int(c.get("sold") or 0),
        "official": bool(c.get("is_official_shop")), "mall": bool(c.get("is_official_shop")),
        "preferred": bool(c.get("is_preferred_plus_seller")), "flash": bool(c.get("is_on_flash_sale")),
        "stock": int(c.get("stock") or 0), "pct": pct(x.get("default_commission_rate")),
        "image": IMG + c["image"] if c.get("image") else "", "url": x.get("product_link") or f"https://shopee.vn/product/{shopid}/{itemid}",
        "vouchers": vouchers, "cat": ad.guess_group(c.get("name") or "") or kw,
    }


# ---------------------------------------------------------------- ma giam gia Shopee tu Accesstrade (ghep theo ten shop)
def at_vouchers():
    """{ten shop da bo dau: [ {code, desc, end}, ... ]} - ma con han, gia tri doc duoc."""
    token = ad.get_token()
    out = {}
    if not token:
        return out
    try:
        offers = ad.fetch_offers(token, "shopee")
    except Exception as e:
        log("Lay ma giam Accesstrade loi:", ad.describe_error(e))
        return out
    n = ad.now()
    for o in offers:
        if not ad.not_expired(o, n):
            continue
        p = ad.parse_offer(o)
        for code in ad.offer_codes(o)[:1]:
            out.setdefault(ad.fold(p["shop"]).strip(), []).append(
                {"code": code, "desc": p["desc"][:90], "end": ad.fmt_date(o.get("end_time")), "value": p["value"]})
    for k in out:
        out[k].sort(key=lambda v: -v["value"])
    log(f"Ma giam Shopee (Accesstrade): {sum(len(v) for v in out.values())} ma, {len(out)} shop")
    return out


def add_at_vouchers(it, atv):
    for v in atv.get(ad.fold(it["shop"]).strip(), [])[:2]:
        if v["code"] not in {a["code"] for a in it["vouchers"]}:
            it["vouchers"].append({"code": v["code"], "desc": v["desc"], "end": v["end"]})


# ---------------------------------------------------------------- chon hang
def score(it):
    """Giup NGUOI MUA: ban chay x sao that x (nhieu danh gia) x Mall x dang giam that x co ma giam. Hoa hong % tinh nhe."""
    s = math.log10(it["sold"] + 10)
    s *= 1 + (it["rating"] - 4.7) * 2                       # 4,8 -> x1,2 ; 5,0 -> x1,6
    s *= min(1.0, math.log10(it["reviews"] + 1) / 3)        # 1.000 danh gia tro len = du tin
    if it["mall"]:
        s *= 1.5
    elif it["preferred"]:
        s *= 1.15
    if it["orig"]:
        s *= 1 + min(1 - it["price"] / it["orig"], 0.6)
    if it["vouchers"]:
        s *= 1.4
    return s * math.sqrt(max(it["pct"], 1)) ** 0.5


def pick(items, cfg, recent_ids):
    from collections import Counter
    stats, cands, seen = Counter(), [], set()
    for it in items:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        if not it["title"] or not it["image"]:
            stats["thieu ten/anh"] += 1
        elif it["stock"] <= 0:
            stats["het hang"] += 1
        elif not (cfg["min_price"] <= it["price"] <= cfg["max_price"]):
            stats["ngoai khoang gia"] += 1
        elif it["rating"] < cfg["sp_min_rating"]:
            stats["sao thap"] += 1
        elif it["reviews"] < cfg["sp_min_reviews"]:
            stats["it danh gia"] += 1
        elif it["sold"] < cfg["min_sold"]:
            stats["it luot ban"] += 1
        elif it["pct"] < cfg["min_commission"]:
            stats["hoa hong thap"] += 1
        elif it["id"] in recent_ids:
            stats["da chon gan day"] += 1
        else:
            cands.append((score(it), it))
    cands.sort(key=lambda c: -c[0])
    out, shops, per_kw, per_cat = [], set(), Counter(), Counter()
    for _, it in cands:
        if it["shop"] in shops:
            stats["trung shop"] += 1
        elif per_kw[it["kw"]] >= cfg["sp_max_per_keyword"] or per_cat[it["cat"]] >= cfg["sp_max_per_keyword"]:
            stats["du nhom hang"] += 1
        else:
            shops.add(it["shop"])
            per_kw[it["kw"]] += 1
            per_cat[it["cat"]] += 1
            out.append(it)
        if len(out) >= cfg["sp_per_day"]:
            break
    # xen ke nhom hang (mon tot nhat moi nhom truoc) de moi lan dang khac loai
    rr, buckets = [], {}
    for it in out:
        buckets.setdefault(it["kw"], []).append(it)
    while any(buckets.values()):
        for k in list(buckets):
            if buckets[k]:
                rr.append(buckets[k].pop(0))
    return rr, stats


# ---------------------------------------------------------------- link rut gon qua trang Custom Link (bam nhu nguoi)
def short_links(page, items):
    open_aff(page, "/offer/custom_link")
    for i in range(0, len(items), 5):
        batch = items[i:i + 5]
        if i:
            time.sleep(random.uniform(20, 35))
            open_aff(page, "/offer/custom_link")
        box = page.locator("textarea").first
        box.click()
        box.fill("\n".join(it["url"] for it in batch))
        time.sleep(random.uniform(1, 2))

        def is_link(r):
            try:
                return "/api/v3/gql" in r.url and "batchGetCustomLink" in (r.request.post_data or "")
            except Exception:
                return False
        with page.expect_response(is_link, timeout=40000) as ri:
            page.get_by_role("button", name=re.compile("Lấy link")).first.click()
        res = ((ri.value.json().get("data") or {}).get("batchCustomLink")) or []
        for it, r in zip(batch, res):
            if r.get("shortLink"):
                it["aff"] = r["shortLink"]
            else:
                log(f"  khong tao duoc link ({r.get('failCode')}): {it['title'][:50]}")
        log(f"  link rut gon: {sum(1 for it in batch if it.get('aff'))}/{len(batch)}")
        check_page(page)
    return [it for it in items if it.get("aff")]


# ---------------------------------------------------------------- day len GitHub (qua gh api, khong dung git o may)
def gh_exe():
    p = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "ghcli", "bin", "gh.exe")
    return p if os.path.exists(p) else "gh"


def push_github(data):
    path = f"repos/{REPO}/contents/shopee_hang.json"
    sha = ""
    r = subprocess.run([gh_exe(), "api", path, "--jq", ".sha"], capture_output=True, text=True)
    if r.returncode == 0:
        sha = r.stdout.strip()
    body = {"message": f"hang Shopee {ad.now():%d/%m}", "branch": "main",
            "content": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")).decode()}
    if sha:
        body["sha"] = sha
    tmp = os.path.join(OUT_DIR, "gh_body.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(body, f)
    r = subprocess.run([gh_exe(), "api", "-X", "PUT", path, "--input", tmp], capture_output=True, text=True)
    os.remove(tmp)
    if r.returncode != 0:
        raise RuntimeError("Day len GitHub loi: " + (r.stderr or r.stdout)[:200])


# ---------------------------------------------------------------- lenh
def lay():
    from playwright.sync_api import sync_playwright
    dry = os.environ.get("DRY_RUN") == "1"
    cfg = load_cfg()
    n = ad.now()
    old = read_hang()
    keep = (n - datetime.timedelta(days=cfg["sp_repick_days"])).date().isoformat()
    da_chon = {k: v for k, v in (old.get("da_chon") or {}).items() if v >= keep}
    so_tu = int(os.environ.get("SO_TU") or cfg["sp_so_tu"])
    start = (n.date().toordinal() * so_tu) % len(SHOPEE_KEYWORDS)
    kws = [SHOPEE_KEYWORDS[(start + i) % len(SHOPEE_KEYWORDS)] for i in range(so_tu)]
    log(f"Lay hang Shopee: {', '.join(kws)}")
    atv = at_vouchers()
    raw = []
    with sync_playwright() as p:
        ctx = browser(p, an=os.environ.get("HIEN") != "1")
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            open_aff(page)
            for i, kw in enumerate(kws):
                if i:
                    time.sleep(random.uniform(30, 60))         # doc THUA (25/10: doc don dap -> captcha)
                lst = fetch_keyword(page, kw)
                raw += [sp_info(x, kw) for x in lst]
                log(f"  '{kw}': {len(lst)} san pham")
            for it in raw:
                add_at_vouchers(it, atv)
            chosen, stats = pick(raw, cfg, set(da_chon))
            log(f"Chon {len(chosen)}/{len(raw)} mon. Loai: " + ", ".join(f"{k} {v}" for k, v in stats.most_common()))
            if not dry and chosen:
                time.sleep(random.uniform(15, 30))
                chosen = short_links(page, chosen)
        except Blocked as e:
            log("DUNG:", e)
            try:
                page.screenshot(path=os.path.join(OUT_DIR, "bi_chan.png"))
            except Exception:
                pass
            alert(f"⚠️ Bot Shopee dừng: {e}.\nAnh mở Chrome của bot (bấm đúp dang_nhap_shopee.bat) để đăng nhập / kéo mã xác minh, "
                  "rồi chạy lay_hang_shopee.bat. Hôm nay bot vẫn đăng hàng TikTok bình thường.")
            sys.exit(1)
        finally:
            ctx.close()
    if not chosen:
        log("Khong co mon nao dat -> giu hang cu")
        return
    for it in chosen:
        da_chon[it["id"]] = n.date().isoformat()
    data = {"ngay": n.date().isoformat(), "tao_luc": n.isoformat(timespec="minutes"), "items": chosen, "da_chon": da_chon}
    if dry:
        with open(os.path.join(OUT_DIR, "shopee_hang_thu.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        log("DRY_RUN: luu shopee_hang_thu.json, khong tao link, khong day GitHub")
        return
    tmp = HANG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, HANG)
    push_github(data)
    log(f"DA XONG: {len(chosen)} mon Shopee, da day len GitHub")


def dang_nhap():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = browser(p)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(AFF + "/dashboard", wait_until="domcontentloaded", timeout=60000)
        print("Cua so Chrome cua bot Shopee da mo. Anh dang nhap Shopee (tai khoan affiliate hoangk40) trong cua so do.\n"
              "Thay trang Dashboard Shopee Affiliate la xong. Cho toi da 10 phut...")
        for _ in range(120):
            time.sleep(5)
            try:                                       # dang nhap co the mo tab moi -> xem moi tab
                if any(pg.url.startswith(AFF + "/dashboard") for pg in ctx.pages):
                    time.sleep(10)                     # cho Chrome ghi cookie xuong may
                    print("DA DANG NHAP. Cua so tu dong.", flush=True)
                    return
            except Exception:
                pass
        print("Het 10 phut chua thay dang nhap.", flush=True)


def xem():
    d = read_hang()
    for i, it in enumerate(d.get("items") or [], 1):
        print(f"{i}. {it['title'][:60]} | {ad.vnd(it['price'])} | {it['rating']}* ({it['reviews']}) | ban {it['sold']} | "
              f"{'Mall ' if it['mall'] else ''}ma {len(it['vouchers'])} | {it.get('aff', '')}")
    print(f"Ngay {d.get('ngay')}, {len(d.get('items') or [])} mon")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "lay"
    {"lay": lay, "dang_nhap": dang_nhap, "xem": xem}.get(cmd, lay)()
