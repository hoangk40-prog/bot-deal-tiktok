# -*- coding: utf-8 -*-
"""Kiem thu tu dong cho auto_deals.py (khong can mang, khong can token). Chay:  python test_auto_deals.py"""
import datetime, json, os, sys, tempfile
import auto_deals as A

VN = A.VN
fails = []


def check(name, cond, extra=""):
    print(("  OK   " if cond else "  LOI  ") + name + (f"   {extra}" if extra and not cond else ""))
    if not cond:
        fails.append(name)


def at(day=8, hour=10, month=10):
    return datetime.datetime(2026, month, day, hour, 0, tzinfo=VN)


def offer(i, shop, desc, end="2026-10-30", code="", link=True):
    o = {"id": f"id{i}", "name": f"[{shop}] - {desc}", "end_time": end,
         "coupons": [{"coupon_code": code, "coupon_desc": desc}]}
    if link:
        o["aff_link"] = f"https://aff/{i}"
    return o


print("1) Doc gia tri voucher")
cases = [
    ("Giảm 50.000đ cho đơn tối thiểu 200.000đ", 50000, 200000),
    ("Giảm 10% tối đa 100.000đ cho đơn tối thiểu 500.000đ", 100000, 500000),
    ("Giảm 10% tối đa 100K cho đơn tối thiểu 500K", 100000, 500000),
    ("Giảm 30k đơn từ 199k", 30000, 199000),
    ("Giam 50.000d don toi thieu 200.000d", 50000, 200000),
    ("Giảm 15% tối đa 30.000₫", 30000, 0),
    ("Giảm 1,5tr cho đơn từ 10tr", 1500000, 10000000),
    ("Giảm 10% đơn tối thiểu 300.000đ", 30000, 300000),
    ("Giảm 5 sản phẩm khi mua combo", 0, 0),
    ("Giảm 10%", 0, 0),
    ("Giảm 5% Giảm 50k cho đơn từ 100k", 50000, 100000),
]
for t, v, m in cases:
    p = A.parse_text(t)
    check(f"{t[:48]:<48} -> {v}/{m}", (p["value"], p["minorder"]) == (v, m), f"ra {p['value']}/{p['minorder']}")

print("2) Nho trang thai dung thoi gian")
cfg = A.load_config()
n = at(8, 10)
old = (n - datetime.timedelta(hours=80)).isoformat()
st = A.migrate_state({"offers": {"a": old, "b": {"t": old, "exp": "2026-10-30"}, "c": {"t": old, "exp": "2026-10-05"}},
                      "shops": {"S": old}, "links": {"https://x/1": old, "https://x/2": old}})
A.cleanup_state(st, {"https://x/1"}, cfg, n)
check("voucher con han van duoc nho sau 80 gio", "b" in st["offers"])
check("voucher het han tu lau thi bo", "c" not in st["offers"])
check("ban cu (chi co gio gui) van duoc doc", "a" in st["offers"])
check("link con trong my_links.txt khong bi quen", "https://x/1" in st["links"])
check("link da xoa khoi file van nho them 30 ngay", "https://x/2" in st["links"])
check("shop het thoi gian nghi thi bo", "S" not in st["shops"])
very_old = (n - datetime.timedelta(days=40)).isoformat()
st2 = A.migrate_state({"links": {"https://x/3": very_old}})
A.cleanup_state(st2, set(), cfg, n)
check("link da xoa khoi file qua 30 ngay thi bo", "https://x/3" not in st2["links"])

print("3) Chon voucher")
offers = [offer(1, "ShopA", "Giảm 50.000đ cho đơn tối thiểu 200.000đ"),
          offer(2, "ShopA", "Giảm 30.000đ cho đơn tối thiểu 100.000đ"),
          offer(3, "ShopB", "Giảm 10% tối đa 100K cho đơn tối thiểu 500K"),
          offer(4, "ShopC", "Giảm 5.000đ cho đơn tối thiểu 0đ"),
          offer(5, "ShopD", "Giảm 80.000đ", end="2026-10-01"),
          offer(6, "ShopE", "Giảm 80.000đ", link=False),
          offer(7, "ShopF", "Giảm 40.000đ"),
          offer(8, "ShopG", "Mua 1 tặng 1")]
st = A.migrate_state({"shops": {"ShopF": {"t": (n - datetime.timedelta(hours=3)).isoformat()}}})
ch, stats, samples = A.pick_new(offers, st, cfg, n)
ids = sorted(o["id"] for o in ch)
check("moi shop chi 1 voucher, lay cai tot nhat (ShopA chon id1)", ids == ["id1", "id3"], str(ids))
check("ghi nhan ly do loai", stats["het han"] == 1 and stats["khong co link"] == 1 and stats["shop dang nghi"] == 1
      and stats["gia tri thap"] == 1 and stats["khong doc duoc gia tri"] == 1, str(dict(stats)))
st["offers"]["id1"] = {"t": n.isoformat(), "exp": "2026-10-30"}
ch2, _, _ = A.pick_new(offers, st, cfg, n)
check("voucher da gui khong gui lai", "id1" not in [o["id"] for o in ch2])
check("het han trong hom nay sau 20h thi bo", not A.not_expired(offer(9, "X", "x", end="2026-10-08"), at(8, 21)))

print("4) Chia tin nhan dai")
big = "\n\n".join(f"{i}. " + "x" * 700 for i in range(30))
parts = A.split_chunks(big)
check("moi tin <= 3800 ky tu", all(len(p) <= 3800 for p in parts))
check("khong mat noi dung", "".join(parts).replace("\n", "") == big.replace("\n", ""))
one = "y" * 9000
check("mot khoi qua dai van duoc cat", all(len(p) <= 3800 for p in A.split_chunks(one)))

print("5) Chay main() tu dau den cuoi (gia lap mang)")
tmp = tempfile.mkdtemp()
A.HERE = tmp
json.dump({"shopee": True, "tiktok": False, "max_items": 5}, open(os.path.join(tmp, "config.json"), "w"))
open(os.path.join(tmp, "my_links.txt"), "w").write("# ghi chu\nhttps://vt.tiktok.com/abc\nkhong phai link\nhttps://vt.tiktok.com/abc\n")
os.environ.update(ACCESSTRADE_TOKEN="t", TELEGRAM_BOT_TOKEN="b", TELEGRAM_CHAT_ID="c")
os.environ.pop("FORCE", None); os.environ.pop("DRY_RUN", None)
sent, clock = [], {"t": at(8, 10)}
A.now = lambda: clock["t"]
A.send_telegram = lambda b, c, t: sent.append(t) or 1
mode = {"fail": False, "data": offers}
def fake_fetch(token, m, limit=50, pages=4):
    if mode["fail"]:
        raise RuntimeError("API sap")
    return mode["data"]
A.fetch_offers = fake_fetch
A.make_link = lambda *a, **k: None      # khong goi mang: link TikTok khong doi duoc -> bao trong tin chu
def run():
    try:
        A.main(); return 0
    except SystemExit as e:
        return 1 if e.code not in (None, 0) else 0
state_path = os.path.join(tmp, "sent.json")

run()
check("lan 1 gui 1 tin co voucher va link TikTok", len(sent) == 1 and "https://vt.tiktok.com/abc" in sent[0] and "ShopB" in sent[0])
check("link bi lap trong file chi xuat hien 1 lan", sent[0].count("https://vt.tiktok.com/abc") == 1)
sent.clear(); clock["t"] = at(8, 12); run()
check("2 gio sau khong gui lai gi", sent == [])
sent.clear(); clock["t"] = at(11, 12); run()
txt = " ".join(sent)
check("3 ngay sau: voucher da gui (aff/1, aff/3, aff/7) KHONG bi gui lai",
      not any(f"https://aff/{i}\n" in txt + "\n" for i in (1, 3, 7)), txt[:120])
check("3 ngay sau: voucher thu 2 cua ShopA (chua gui lan nao) duoc gui dung 1 lan",
      txt.count("https://aff/2\n") + txt.count("https://aff/2") >= 1 and "ShopA" in txt and "https://vt.tiktok.com/abc" not in txt)
os.environ["DRY_RUN"] = "1"; mode["data"] = offers + [offer(20, "ShopZ", "Giảm 90.000đ")]
before = open(state_path).read(); sent.clear(); run()
check("chay thu (DRY_RUN) khong gui va khong doi sent.json", sent == [] and open(state_path).read() == before)
os.environ.pop("DRY_RUN"); run()
check("voucher moi xuat hien thi duoc gui", len(sent) == 1 and "ShopZ" in sent[0])
sent.clear(); clock["t"] = at(11, 23); run()
check("ngoai gio 7h-22h thi khong gui", sent == [])

print("6) Canh bao khi loi lien tiep")
sent.clear(); mode["fail"] = True
codes = []
for h in (8, 10, 12, 14):
    clock["t"] = at(12, h); codes.append(run())
alerts = [s for s in sent if "đang lỗi" in s]
check("moi lan loi deu bao 'that bai' (exit != 0)", codes == [1, 1, 1, 1])
check("canh bao Telegram dung 1 lan, o lan loi thu 3", len(alerts) == 1 and "3 lần" in alerts[0], str(sent))
mode["fail"] = False; sent.clear(); clock["t"] = at(12, 16); run()
check("het loi thi bao 'hoat dong lai' dung 1 lan", len([s for s in sent if "hoạt động lại" in s]) == 1)
sent.clear(); clock["t"] = at(12, 18); run()
check("khong bao lai lan nua", not [s for s in sent if "hoạt động lại" in s])

print("7) Gui Telegram loi giua chung")
mode["data"] = [offer(30, "ShopY", "Giảm 70.000đ")]
def half_fail(b, c, t):
    raise A.SendError("Telegram loi 400", 0)
A.send_telegram = half_fail
clock["t"] = at(12, 20); code = run()
st = json.load(open(state_path))
check("gui that bai hoan toan thi khong danh dau da gui (lan sau gui lai)", code == 1 and "id30" not in st["offers"])
def partial(b, c, t):
    raise A.SendError("Telegram loi 429", 1)
A.send_telegram = partial; run()
st = json.load(open(state_path))
check("gui duoc mot phan thi danh dau da gui (tranh gui trung)", "id30" in st["offers"])

print("8) San pham TikTok: doc so lieu, loc, xep hang")
def tt(i, price, sold=500, rate=0.06, shop=None, cat="c%d", stock=True, orig=None, url=True, amount=None):
    return {"id": f"{i}", "title": f"San pham {i}", "shop": {"name": shop or f"Shop{i}"},
            "sales_price": {"minimum_amount": str(price)}, "original_price": {"minimum_amount": str(orig or price)},
            "commission": {"rate": rate, "amount": amount if amount is not None else price * rate},
            "units_sold": sold, "has_inventory": stock, "main_image_url": f"https://img/{i}.jpg",
            "detail_link": f"https://shop.tiktok.com/view/product/{i}" if url else "",
            "category_chains": [{"local_name": cat % i if "%d" in cat else cat}]}

check("so '3.000' (dau cham hang nghin) doc thanh 3000", A.num("3.000") == 3000 and A.num(34979.57) == 34979.57)
check("hoa hong dang 0.05185 = 5,19%", abs(A.tt_info(tt(1, 100000, rate=0.05185))["pct"] - 5.185) < 0.001)
check("hoa hong dang 3587 = 35,87%", round(A.tt_info(tt(1, 100000, rate=3587))["pct"], 2) == 35.87)
check("gia goc = gia ban thi khong ghi 'giam'", A.tt_info(tt(1, 100000))["orig"] == 0)
check("gia goc cao hon thi ghi gia goc", A.tt_info(tt(1, 100000, orig=150000))["orig"] == 150000)

cfg8 = dict(A.DEFAULTS)
n8 = at(12, 11)
st8 = A.migrate_state({})
cases = [tt(1, 300000), tt(2, 10000), tt(3, 2000000), tt(4, 300000, sold=5), tt(5, 300000, rate=0.01),
         tt(6, 300000, stock=False), tt(7, 300000, url=False), tt(1, 300000)]
pk, ps = A.pick_tiktok(cases, st8, cfg8, n8)
check("chi lay san pham dat nguong, trung id chi tinh 1 lan", [it["id"] for it in pk] == ["1"], str([it["id"] for it in pk]))
check("loai dung ly do", ps["gia qua re"] == 1 and ps["gia cao"] == 1 and ps["it luot ban"] == 1 and ps["hoa hong thap"] == 1
      and ps["het hang"] == 1 and ps["khong co link"] == 1, str(dict(ps)))
st8b = A.migrate_state({"products": {"tt|1": {"t": n8.isoformat()}}})
check("san pham vua gui thi nghi", A.pick_tiktok([tt(1, 300000)], st8b, cfg8, n8)[0] == [])
pk, _ = A.pick_tiktok([tt(10, 300000, sold=100, amount=10000), tt(11, 300000, sold=5000, amount=30000)], st8, cfg8, n8)
check("ban chay + hoa hong cao xep truoc", [it["id"] for it in pk] == ["11", "10"])
pk, ps = A.pick_tiktok([tt(i, 300000, shop="CungShop") for i in range(20, 24)], st8, cfg8, n8)
check("moi shop 1 san pham/dot", len(pk) == 1 and ps["trung shop"] == 3, str(dict(ps)))
pk, ps = A.pick_tiktok([tt(i, 300000, cat="ao") for i in range(30, 36)], st8, cfg8, n8)
check("moi nhom hang toi da 2", len(pk) == 2 and ps["trung nhom hang"] == 4, str(dict(ps)))
nosold = tt(40, 300000); nosold.pop("units_sold")
pk, ps = A.pick_tiktok([nosold], st8, cfg8, n8)
check("API khong tra 'da ban' thi KHONG loai san pham", [it["id"] for it in pk] == ["40"], str(dict(ps)))
check("khong biet 'da ban' thi chu thich khong ghi dong da ban",
      "Đã bán" not in A.caption(dict(A.tt_info(nosold), aff="https://shorten.asia/y")))

print("8b) Goi API TikTok: tu khoa du phong, API tu choi, loi")
cfgt = dict(A.DEFAULTS, tiktok_pages=2)
calls_ = []
real_sleep = A.time.sleep; A.time.sleep = lambda s: None
def fake_get(token, p):
    calls_.append(dict(p))
    if "title_keywords" not in p:
        return {"status": False, "message": "title_keywords is required"}
    return {"status": True, "data": {"products": [tt(len(calls_), 300000)], "next_page_token": ""}}
A.tt_get = fake_get
got = A.fetch_tiktok("x", cfgt)
check("'goi y' bi tu choi -> tu tim theo tu khoa mac dinh", len(got) == len(A.DEFAULT_KEYWORDS)
      and all("title_keywords" in c for c in calls_[1:]), str(len(got)))
calls_.clear()
def fake_get2(token, p):
    calls_.append(dict(p))
    return {"status": True, "data": {"products": [tt(len(calls_), 300000)], "next_page_token": "t2" if len(calls_) < 2 else ""}}
A.tt_get = fake_get2
got = A.fetch_tiktok("x", dict(cfgt, tiktok_keywords=["nồi chiên"]))
check("'goi y' co hang: lay 2 trang + tu khoa cua anh, khong dung tu khoa mac dinh",
      len(got) == 3 and calls_[1].get("page_token") == "t2" and calls_[2]["title_keywords"] == "nồi chiên", str(calls_))
def fake_get3(token, p):
    raise A.urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
A.tt_get = fake_get3
try:
    A.fetch_tiktok("x", cfgt); raised = False
except Exception:
    raised = True
check("moi lan goi deu loi thi bao loi (de dem canh bao)", raised)
A.time.sleep = real_sleep

it = dict(A.tt_info(tt(1, 299000, sold=11780, orig=399000)), aff="https://shorten.asia/x")
cap = A.caption(it)
check("chu thich co gia, gia goc, da ban, shop, link", "299.000đ" in cap and "399.000đ" in cap and "11.780+" in cap
      and "Shop1" in cap and "https://shorten.asia/x" in cap, cap)
check("nhan dang link TikTok chua phai link hoa hong", A.is_tiktok_raw("https://vt.tiktok.com/ZSabc/")
      and not A.is_tiktok_raw("https://shorten.asia/abc") and not A.is_tiktok_raw("https://go.isclix.com/deep_link/1?url=https%3A%2F%2Fwww.tiktok.com"))

cfgs = dict(A.DEFAULTS, send_hours=[11, 19])
check("7h chua den slot 11h", A.send_due(cfgs, {}, at(12, 7), False) == (False, None))
check("11h: den gio gui", A.send_due(cfgs, {}, at(12, 11), False) == (True, "2026-10-12@11"))
check("13h tre cron van gui bu slot 11h", A.send_due(cfgs, {}, at(12, 13), False)[0] is True)
check("slot da gui roi thi khong gui lai", A.send_due(cfgs, {"slots_done": ["2026-10-12@11"]}, at(12, 13), False)[0] is False)
check("20h: gui slot 19h", A.send_due(cfgs, {"slots_done": ["2026-10-12@11"]}, at(12, 20), False) == (True, "2026-10-12@19"))
check("FORCE luon gui", A.send_due(cfgs, {"slots_done": ["2026-10-12@11", "2026-10-12@19"]}, at(12, 7), True)[0] is True)

print("9) main() voi TikTok: gui anh tung san pham, doi link, khung gio")
tmp9 = tempfile.mkdtemp(); A.HERE = tmp9
json.dump({"shopee": False, "tiktok": True, "send_hours": [11], "max_products": 2, "nganh_win": ""},
          open(os.path.join(tmp9, "config.json"), "w"))
open(os.path.join(tmp9, "my_links.txt"), "w").write("https://vt.tiktok.com/mine1\nhttps://vt.tiktok.com/bad\nhttps://shorten.asia/san\n")
sent.clear(); posts = []
A.send_telegram = lambda b, c, t: sent.append(t) or 1
A.send_product = lambda b, c, it: posts.append(it)
A.time.sleep = lambda s: None
tdata = {"v": [tt(1, 300000, sold=9000), tt(2, 300000, sold=8000), tt(3, 300000, sold=7000)]}
A.fetch_tiktok = lambda token, cfg: tdata["v"]
def fake_link(token, url, pid="", full=False):
    if "bad" in url or pid == "1":
        return None                                   # san pham 1 tao link loi -> lay du phong
    d = {"aff_short_url": "https://shorten.asia/" + (pid or url[-5:])}
    if full:
        d.update(product_name="Hang anh chon", product_image="https://img/m.jpg", product_price={"minimum_amount": "150000"})
    return d
A.make_link = fake_link
clock["t"] = at(10, 9); run()
check("truoc gio gui: khong gui gi", posts == [] and sent == [])
clock["t"] = at(10, 11); run()
ids = [p.get("id") for p in posts]
check("11h: gui link anh chon + 2 san pham (san pham 1 tao link loi -> lay 3)",
      len(posts) == 3 and posts[0]["title"] == "Hang anh chon" and ids[1:] == ["2", "3"], str(ids))
check("tin chu co link hoa hong san + bao link loi", len(sent) == 1 and "https://shorten.asia/san" in sent[0]
      and "https://vt.tiktok.com/bad" in sent[0], str(sent))
st9 = json.load(open(os.path.join(tmp9, "sent.json")))
check("sent.json nho san pham, link, slot", "tt|2" in st9["products"] and "tt|1" not in st9["products"]
      and "https://vt.tiktok.com/mine1" in st9["links"] and "2026-10-10@11" in st9["meta"]["slots_done"])
posts.clear(); sent.clear(); clock["t"] = at(10, 13); run()
check("13h cung ngay: khong gui lai", posts == [] and sent == [])
posts.clear(); sent.clear(); os.environ["FORCE"] = "true"; clock["t"] = at(10, 15); run(); os.environ.pop("FORCE")
check("chay tay lan nua: chi gui san pham chua gui (1 tao link loi van loai), khong lap link",
      [p["id"] for p in posts] == [] and not any("mine1" in s for s in sent), str([p.get("id") for p in posts]))
def boom(b, c, it):
    raise RuntimeError("Telegram loi 400")
A.send_product = boom
tdata["v"] = [tt(40, 300000)]
clock["t"] = at(11, 11); code = run()
st9 = json.load(open(os.path.join(tmp9, "sent.json")))
check("gui anh loi: bao that bai va KHONG danh dau da gui", code == 1 and "tt|40" not in st9["products"])

print("10) Voucher Shopee: gia tri thuc te")
a1 = A.parse_offer(offer(90, "Kangaroo Official Store", "Giảm 10%-tối đa 550,000 VNĐ cho đơn tối thiểu 290,000 VNĐ"))
a2 = A.parse_offer(offer(91, "ShopNho", "Giảm 120,000 VNĐ cho đơn tối thiểu 0 VNĐ"))
check("voucher '10% toi da 550k' chi tinh gia tri thuc te (~30k), khong phai 550k", a1["value"] == 29000 or a1["value"] == 30000, str(a1["value"]))
check("voucher giam thang 120k xep cao hon '10% toi da 550k'", a2["score"] > a1["score"], f"{a2['score']} vs {a1['score']}")
k = A.parse_offer(offer(92, "Kangaroo Official Store", "Giảm 600,000 VNĐ cho đơn tối thiểu 6,390,000 VNĐ"))
j = A.parse_offer(offer(93, "Judydoll Official Store", "Giảm 236,750 VNĐ cho đơn tối thiểu 0 VNĐ"))
check("voucher 600k nhung don toi thieu 6,39 trieu xep THAP hon voucher 236k don 0d", j["score"] > k["score"], f"{j['score']} vs {k['score']}")

print("11) San pham win: loc gia 100k-300k, xep hoa hong, moi ngay 1 lan")
cfgw = dict(A.DEFAULTS)
cands = [tt(50, 90000), tt(51, 350000), tt(52, 200000, amount=5000), tt(53, 250000, amount=20000),
         tt(54, 150000, amount=30000, shop="Shop53"), tt(55, 200000, sold=5), tt(56, 200000, rate=0.01)]
pw = A.pick_win(cands, cfgw)
check("chi lay gia 100k-300k, xep theo hoa hong, moi shop 1 sp", [it["id"] for it in pw] == ["54", "52"], str([it["id"] for it in pw]))
check("den 8h va hom nay chua gui thi gui", A.win_due(cfgw, {}, at(12, 8)) and not A.win_due(cfgw, {}, at(12, 7)))
check("hom nay gui roi thi thoi", not A.win_due(cfgw, {"win_date": "2026-10-12"}, at(12, 15)))
check("nganh_win de trong = tat", not A.win_due(dict(cfgw, nganh_win=""), {}, at(12, 9)))
kw_seen = []; sent.clear()
A.tt_get = lambda token, p: kw_seen.append(p["title_keywords"]) or {"status": True, "data": {"products": [tt(60 + len(kw_seen), 200000)]}}
A.make_link = lambda token, url, pid="", full=False: {"aff_short_url": "https://shorten.asia/w" + pid}
stw = A.migrate_state({})
A.send_win("x", dict(cfgw, nganh_win="my_pham"), stw, at(12, 8), "b", "c", False)
check("doi nganh = doi tu khoa tim", kw_seen == A.WIN_KEYWORDS["my_pham"][1], str(kw_seen))
check("tin co tieu de + 10 san pham + link", len(sent) == 1 and sent[0].startswith("🏆 Sản phẩm win hôm nay – Mỹ phẩm")
      and sent[0].count("shorten.asia/w") == 10, str(sent))
check("nho da gui hom nay", stw["meta"].get("win_date") == "2026-10-12")
A.time.sleep = real_sleep

print()
print("TAT CA DAT" if not fails else f"{len(fails)} LOI: " + "; ".join(fails))
sys.exit(1 if fails else 0)
