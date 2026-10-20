# -*- coding: utf-8 -*-
"""Tool gom deal Shopee / TikTok Shop (qua Accesstrade) - ban co cua so.
Bam dup file nay de mo. Khong can cai them gi ngoai Python."""
import json, os, datetime, threading, traceback
import urllib.request, urllib.parse, urllib.error
import tkinter as tk
from tkinter import ttk, messagebox

try:                       # dung chung cach doc / loc / xep hang voucher voi bot tren GitHub
    import auto_deals as AD
except Exception:
    AD = None

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "config.json")             # cai dat chung voi bot (KHONG chua token)
LOCAL_PATH = os.path.join(HERE, "config.local.json")     # token (chi nam tren may nay, dung dua len GitHub)
LINKS_PATH = os.path.join(HERE, "my_links.txt")
API = "https://api.accesstrade.vn/v1/datafeeds"
OFFERS_API = "https://api.accesstrade.vn/v1/offers_informations"

DEFAULT_CFG = {"token": "", "shopee": True, "tiktok": True,
               "min_discount": 30, "max_price": 1000000, "max_items": 10}

GUIDE = """HƯỚNG DẪN SỬ DỤNG

BƯỚC 1. CÓ TÀI KHOẢN ACCESSTRADE
  - Vào accesstrade.vn, bấm Đăng ký, chọn loại tài khoản Publisher (người làm tiếp thị liên kết).
  - Điền thông tin và chờ Accesstrade duyệt tài khoản (có thể mất vài giờ đến vài ngày).

BƯỚC 2. XIN THAM GIA CHIẾN DỊCH
  - Đăng nhập, vào mục Chiến dịch (Campaigns).
  - Tìm "Shopee" và "TikTok Shop", bấm Đăng ký tham gia.
  - Chờ được duyệt. CHƯA ĐƯỢC DUYỆT = KHÔNG CÓ DEAL TRẢ VỀ.

BƯỚC 3. LẤY TOKEN (ACCESS KEY)
  - Trong tài khoản Accesstrade, tìm mục có tên gần giống: "Thông tin tài khoản",
    "API" hoặc "Cài đặt tài khoản" -> tìm dòng "Access Key" / "API Key".
  - Bấm copy rồi quay lại tab "Lấy deal", dán vào ô Token và bấm "Lưu cài đặt".
  - (Giao diện Accesstrade có thể đổi tên menu. Không thấy thì hỏi bộ phận hỗ trợ
    của Accesstrade: "Cho tôi xin Access Key để dùng API".)

BƯỚC 4. LẤY DEAL
  - Bấm "Lấy khuyến mãi / mã giảm giá". Đợi vài giây, tin nhắn hiện ở khung bên dưới.
  - (Nút "Lấy sản phẩm (thử)": dữ liệu sản phẩm Shopee của Accesstrade thiếu giá
    khuyến mãi nên hiện chưa dùng được.)
  - Bấm "Copy tin nhắn", mở nhóm Zalo, bấm Ctrl+V rồi gửi.

LINK TIKTOK CỦA ANH
  - TikTok Shop không cho tool tự lấy deal. Anh dán link affiliate TikTok tự lấy
    vào tab "Link TikTok" (mỗi link một dòng). Tool sẽ ghép vào cuối tin nhắn.

LƯU Ý QUAN TRỌNG
  - KHÔNG chia sẻ token cho ai. Ai có token là dùng được tài khoản của anh.
  - Token được lưu riêng trong file config.local.json (chỉ nằm trên máy này). KHÔNG đưa file này lên GitHub.
    File config.json chỉ chứa cài đặt chung với bot, không có token.
  - Tool không tự đăng lên Zalo. Anh dán tay để không bị Zalo khóa tài khoản.
  - Giá và khuyến mãi thay đổi liên tục, nên gửi sớm sau khi lấy.
  - Nếu ra 0 sản phẩm: kiểm tra chiến dịch đã được duyệt chưa, hoặc thử giảm
    "Giảm tối thiểu (%)" xuống thấp hơn.
  - Muốn thử giao diện trước: bấm "Chạy thử (dữ liệu giả)", không cần token.
"""


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    for path in (CFG_PATH, LOCAL_PATH):          # config.local.json (token) doc sau cung nen duoc uu tien
        try:
            with open(path, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def calc(it):
    """Tra ve (gia_sau_giam, %giam) CHI KHI du lieu dang tin cay, nguoc lai None."""
    price, sale, rate = num(it.get("price")), num(it.get("discount")), num(it.get("discount_rate"))
    if price < 1000:                      # gia goc vo ly -> bo
        return None
    if sale >= 1000 and sale < price:     # 'discount' la gia sau giam that
        r = (1 - sale / price) * 100
        return (sale, round(r)) if r <= 90 else None
    if 0 < rate < 0.9:                    # ty le dang 0-1 (vd 0.35)
        return price * (1 - rate), round(rate * 100)
    return None


def discount_rate(it):
    c = calc(it)
    return c[1] if c else 0


def sale_price(it):
    c = calc(it)
    return c[0] if c else num(it.get("price"))


def vnd(x):
    return f"{int(x):,}".replace(",", ".") + "đ"


def api_get(token, url):
    req = urllib.request.Request(url, headers={"Authorization": f"Token {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch(token, domain, limit=100, pages=3):
    out = []
    for page in range(1, pages + 1):
        qs = urllib.parse.urlencode({"domain": domain, "limit": limit, "page": page,
                                     "status_discount": 1})
        got = api_get(token, f"{API}?{qs}").get("data", [])
        out += got
        if len(got) < limit:
            break
    return out


def fetch_offers(token, merchant, limit=50, pages=2):
    out = []
    for page in range(1, pages + 1):
        qs = urllib.parse.urlencode({"merchant": merchant, "status": 1, "limit": limit, "page": page})
        got = api_get(token, f"{OFFERS_API}?{qs}").get("data", [])
        out += got
        if len(got) < limit:
            break
    return out


def offer_codes(o):
    return [c.get("coupon_code") for c in (o.get("coupons") or [])
            if isinstance(c, dict) and c.get("coupon_code")]


def build_offers_message(offers, extra):
    today = datetime.date.today().strftime("%d/%m/%Y")
    lines = [f"🎁 KHUYẾN MÃI HOT NGÀY {today} 🎁", ""]
    for i, o in enumerate(offers, 1):
        name = str(o.get("name") or o.get("title") or "Khuyến mãi")[:100]
        link = o.get("aff_link") or o.get("link") or ""
        codes, end = offer_codes(o), str(o.get("end_time") or "")[:10]
        lines.append(f"{i}. {name}")
        if codes:
            lines.append("🏷 Mã: " + ", ".join(codes[:3]))
        if end:
            lines.append(f"⏰ Hết hạn: {end}")
        lines += [f"👉 {link}", ""]
    if extra:
        lines += ["⭐ Deal TikTok chọn lọc:"] + extra + [""]
    return "\n".join(lines).strip()


def build_message(items, extra):
    today = datetime.date.today().strftime("%d/%m/%Y")
    lines = [f"🔥 DEAL HOT NGÀY {today} 🔥", ""]
    for i, it in enumerate(items, 1):
        link = it.get("aff_link") or it.get("url") or ""
        lines += [f"{i}. {str(it.get('name', ''))[:90]}",
                  f"💰 {vnd(sale_price(it))}  (giảm {discount_rate(it):.0f}%)",
                  f"👉 {link}", ""]
    if extra:
        lines += ["⭐ Deal TikTok chọn lọc:"] + extra + [""]
    return "\n".join(lines).strip()


def demo_items():
    return [{"name": f"Sản phẩm mẫu số {i}", "price": 500000 + i * 1000,
             "discount": 250000 + i * 1000, "aff_link": f"https://example.com/p{i}"}
            for i in range(1, 8)]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tool tìm deal Shopee / TikTok Shop")
        self.geometry("860x700")
        self.cfg = load_cfg()
        self.last_msg = ""
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.nb = nb
        self.tab_main = ttk.Frame(nb); self.tab_guide = ttk.Frame(nb); self.tab_links = ttk.Frame(nb)
        nb.add(self.tab_main, text="  Lấy deal  ")
        nb.add(self.tab_guide, text="  Hướng dẫn  ")
        nb.add(self.tab_links, text="  Link TikTok  ")
        self.build_main(); self.build_guide(); self.build_links()
        if not self.cfg["token"]:
            self.after(300, self.first_run)

    # ---------- giao dien ----------
    def build_main(self):
        f = self.tab_main
        top = ttk.LabelFrame(f, text="Cài đặt"); top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="Token Accesstrade:").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.v_token = tk.StringVar(value=self.cfg["token"])
        self.e_token = ttk.Entry(top, textvariable=self.v_token, width=60, show="*")
        self.e_token.grid(row=0, column=1, columnspan=3, sticky="we", padx=6)
        self.v_show = tk.BooleanVar()
        ttk.Checkbutton(top, text="Hiện token", variable=self.v_show,
                        command=lambda: self.e_token.config(show="" if self.v_show.get() else "*")
                        ).grid(row=0, column=4, padx=6)

        self.v_shopee = tk.BooleanVar(value=self.cfg["shopee"])
        self.v_tiktok = tk.BooleanVar(value=self.cfg["tiktok"])
        ttk.Checkbutton(top, text="Shopee", variable=self.v_shopee).grid(row=1, column=0, sticky="w", padx=6)
        ttk.Checkbutton(top, text="TikTok Shop", variable=self.v_tiktok).grid(row=1, column=1, sticky="w")

        self.v_min = tk.StringVar(value=str(self.cfg["min_discount"]))
        self.v_price = tk.StringVar(value=str(self.cfg["max_price"]))
        self.v_n = tk.StringVar(value=str(self.cfg["max_items"]))
        for col, (lbl, var) in enumerate([("Giảm tối thiểu (%)", self.v_min),
                                          ("Giá tối đa (đ)", self.v_price),
                                          ("Số sản phẩm", self.v_n)]):
            ttk.Label(top, text=lbl).grid(row=2, column=col, sticky="w", padx=6, pady=(6, 0))
            ttk.Entry(top, textvariable=var, width=14).grid(row=3, column=col, sticky="w", padx=6, pady=(0, 6))

        self.v_raw = tk.BooleanVar()
        ttk.Checkbutton(top, text="Hiện dữ liệu thô (để kiểm tra lỗi)", variable=self.v_raw
                        ).grid(row=3, column=3, columnspan=2, sticky="w")

        bar = ttk.Frame(f); bar.pack(fill="x", padx=8)
        self.b_off = ttk.Button(bar, text="🎁 Lấy khuyến mãi / mã giảm giá", command=self.on_offers); self.b_off.pack(side="left", padx=3)
        self.b_get = ttk.Button(bar, text="Lấy sản phẩm (thử)", command=self.on_get); self.b_get.pack(side="left", padx=3)
        ttk.Button(bar, text="Chạy thử (dữ liệu giả)", command=self.on_demo).pack(side="left", padx=3)
        ttk.Button(bar, text="📋 Copy tin nhắn", command=self.on_copy).pack(side="left", padx=3)
        ttk.Button(bar, text="Lưu cài đặt", command=self.save_cfg).pack(side="left", padx=3)
        ttk.Button(bar, text="Xem chiến dịch đã duyệt", command=self.on_campaigns).pack(side="left", padx=3)

        self.status = tk.StringVar(value="Sẵn sàng.")
        ttk.Label(f, textvariable=self.status, foreground="#1a5fb4").pack(anchor="w", padx=10, pady=4)
        box = ttk.Frame(f); box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.out = tk.Text(box, wrap="word", font=("Segoe UI", 10))
        sb = ttk.Scrollbar(box, command=self.out.yview); self.out.config(yscrollcommand=sb.set)
        self.out.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")

    def build_guide(self):
        t = tk.Text(self.tab_guide, wrap="word", font=("Segoe UI", 10), padx=10, pady=10)
        t.insert("1.0", GUIDE); t.config(state="disabled"); t.pack(fill="both", expand=True)

    def build_links(self):
        ttk.Label(self.tab_links, wrap=780, text="Dán link affiliate TikTok của anh vào đây, mỗi link một dòng. "
                  "Các link này sẽ được ghép vào cuối tin nhắn.").pack(anchor="w", padx=10, pady=8)
        self.t_links = tk.Text(self.tab_links, height=15, font=("Segoe UI", 10))
        self.t_links.pack(fill="both", expand=True, padx=10)
        if os.path.exists(LINKS_PATH):
            self.t_links.insert("1.0", open(LINKS_PATH, encoding="utf-8").read())
        ttk.Button(self.tab_links, text="Lưu link", command=self.save_links).pack(pady=8)

    # ---------- chuc nang ----------
    def first_run(self):
        messagebox.showinfo("Chào anh",
            "Đây là lần đầu anh mở tool.\n\nĐể lấy deal thật, anh cần Token của Accesstrade. "
            "Em mở sẵn tab Hướng dẫn để anh xem cách lấy.\n\nMuốn xem thử trước thì bấm "
            "'Chạy thử (dữ liệu giả)'.")
        self.nb.select(self.tab_guide)

    def save_cfg(self, quiet=False):
        try:
            token = self.v_token.get().strip()
            new = {"shopee": self.v_shopee.get(), "tiktok": self.v_tiktok.get(),
                   "min_discount": int(self.v_min.get()), "max_price": int(self.v_price.get()),
                   "max_items": int(self.v_n.get())}
        except ValueError:
            messagebox.showwarning("Sai dữ liệu", "Các ô Giảm tối thiểu, Giá tối đa, Số sản phẩm phải là số nguyên (không có dấu chấm, dấu phẩy).")
            return False
        base = {}                                    # giu nguyen cac khoa khac cua bot (min_value, active_from...)
        try:
            with open(CFG_PATH, encoding="utf-8") as f:
                base = json.load(f)
        except Exception:
            pass
        base.pop("token", None)                      # token KHONG ghi vao config.json nua
        base.update(new)
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(base, f, ensure_ascii=False, indent=2)
        with open(LOCAL_PATH, "w", encoding="utf-8") as f:
            json.dump({"token": token}, f, ensure_ascii=False, indent=2)
        self.cfg = {**DEFAULT_CFG, **base, "token": token}
        if not quiet:
            self.status.set("Đã lưu cài đặt.")
        return True

    def save_links(self):
        with open(LINKS_PATH, "w", encoding="utf-8") as f:
            f.write(self.t_links.get("1.0", "end").strip() + "\n")
        messagebox.showinfo("Đã lưu", "Đã lưu link TikTok.")

    def extra_links(self):
        return [l.strip() for l in self.t_links.get("1.0", "end").splitlines() if l.strip()]

    def show(self, text):
        self.out.delete("1.0", "end"); self.out.insert("1.0", text)

    def finish(self, items):
        c = self.cfg
        items = [i for i in items if calc(i) and discount_rate(i) >= c["min_discount"] and sale_price(i) <= c["max_price"]]
        items.sort(key=discount_rate, reverse=True)
        items = items[: c["max_items"]]
        extra = self.extra_links()
        if not items and not extra:
            self.show("Không có deal nào đạt điều kiện lọc.\n\nThử:\n- Giảm 'Giảm tối thiểu (%)' xuống (ví dụ 10)\n"
                      "- Tăng 'Giá tối đa'\n- Kiểm tra chiến dịch Shopee/TikTok Shop trên Accesstrade đã được duyệt chưa.")
            self.status.set("Không có deal phù hợp.")
        else:
            self.last_msg = build_message(items, extra)
            self.show(self.last_msg)
            self.status.set(f"Xong. {len(items)} deal. Bấm 'Copy tin nhắn' rồi dán vào Zalo.")
        self.b_get.config(state="normal")

    def on_demo(self):
        if self.save_cfg(quiet=True):
            self.finish(demo_items())

    def on_get(self):
        if not self.save_cfg(quiet=True):
            return
        if not self.cfg["token"]:
            messagebox.showwarning("Thiếu token", "Anh chưa dán Token Accesstrade.\nXem tab 'Hướng dẫn' để biết cách lấy.")
            self.nb.select(self.tab_guide); return
        domains = (["shopee.vn"] if self.cfg["shopee"] else []) + (["tiktokshop.com"] if self.cfg["tiktok"] else [])
        if not domains:
            messagebox.showwarning("Chưa chọn sàn", "Anh tick chọn ít nhất một sàn (Shopee hoặc TikTok Shop)."); return
        self.b_get.config(state="disabled"); self.status.set("Đang lấy dữ liệu, đợi vài giây..."); self.show("")
        threading.Thread(target=self.worker, args=(domains,), daemon=True).start()

    def worker(self, domains):
        items, notes, raw = [], [], ""
        for d in domains:
            try:
                got = fetch(self.cfg["token"], d)
                notes.append(f"[{d}] lấy được {len(got)} sản phẩm, trong đó {sum(1 for x in got if calc(x))} có giá giảm hợp lệ")
                if got and not raw:
                    rows = ["tên | price | discount | discount_amount | discount_rate"]
                    for x in got[:15]:
                        rows.append(f"{str(x.get('name'))[:28]} | {x.get('price')} | {x.get('discount')} | {x.get('discount_amount')} | {x.get('discount_rate')}")
                    raw = "\n".join(rows)
                items += got
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    notes.append(f"[{d}] LỖI {e.code}: Token sai, hết hạn, hoặc chưa được duyệt chiến dịch này.")
                else:
                    notes.append(f"[{d}] LỖI {e.code} từ Accesstrade. Thử lại sau ít phút.")
            except urllib.error.URLError:
                notes.append(f"[{d}] LỖI MẠNG: kiểm tra kết nối Internet.")
            except Exception as e:
                notes.append(f"[{d}] LỖI: {e}")
        self.after(0, lambda: self.done(items, notes, raw))

    def done(self, items, notes, raw):
        self.finish(items)
        head = "\n".join(notes) + "\n\n"
        if self.v_raw.get() and raw:
            head += "BẢNG SỐ LIỆU 15 SẢN PHẨM ĐẦU (để kiểm tra):\n" + raw + "\n\n"
        self.out.insert("1.0", head)
        if any("LỖI" in n for n in notes):
            self.status.set("Có lỗi, xem chi tiết ở khung bên dưới.")

    def on_offers(self):
        if not self.save_cfg(quiet=True):
            return
        if not self.cfg["token"]:
            messagebox.showwarning("Thiếu token", "Anh dán token Accesstrade trước nhé.")
            self.nb.select(self.tab_guide); return
        merchants = (["shopee"] if self.cfg["shopee"] else []) + (["tiktokshop"] if self.cfg["tiktok"] else [])
        if not merchants:
            messagebox.showwarning("Chưa chọn sàn", "Anh tick ít nhất một sàn."); return
        self.b_off.config(state="disabled"); self.status.set("Đang lấy khuyến mãi..."); self.show("")
        threading.Thread(target=self.worker_offers, args=(merchants,), daemon=True).start()

    def worker_offers(self, merchants):
        offers, notes, raw = [], [], ""
        for m in merchants:
            try:
                got = fetch_offers(self.cfg["token"], m)
                notes.append(f"[{m}] lấy được {len(got)} khuyến mãi")
                if got and not raw:
                    raw = json.dumps(got[0], ensure_ascii=False, indent=2)[:2500]
                offers += got
            except urllib.error.HTTPError as e:
                try:
                    body = e.read().decode("utf-8", "ignore")[:300]
                except Exception:
                    body = ""
                notes.append(f"[{m}] LỖI {e.code} từ Accesstrade. Lý do server trả về: {body or '(không có)'}")
            except urllib.error.URLError:
                notes.append(f"[{m}] LỖI MẠNG: kiểm tra Internet.")
            except Exception as e:
                notes.append(f"[{m}] LỖI: {e}")
        self.after(0, lambda: self.done_offers(offers, notes, raw))

    def done_offers(self, offers, notes, raw):
        offers = [o for o in offers if (o.get("aff_link") or o.get("link"))]
        skipped, minv = 0, 0
        if AD is not None:
            minv = int(self.cfg.get("min_value", AD.DEFAULTS["min_value"]))
            best = {}
            for o in offers:
                p = AD.parse_offer(o)
                if p["value"] < minv:
                    skipped += 1
                    continue
                if p["shop"] not in best or p["score"] > best[p["shop"]][1]["score"]:
                    best[p["shop"]] = (o, p)         # moi shop 1 voucher tot nhat
            offers = [o for o, _ in sorted(best.values(), key=lambda x: -x[1]["score"])]
        else:
            offers.sort(key=lambda o: 0 if offer_codes(o) else 1)   # co ma giam gia len truoc
        offers = offers[: self.cfg["max_items"]]
        extra = self.extra_links()
        head = "\n".join(notes) + "\n\n"
        if skipped:
            head += (f"(Đã bỏ {skipped} khuyến mãi có giá trị dưới {minv:,}đ hoặc không đọc được giá trị. "
                     "Muốn lấy nhiều hơn thì hạ 'min_value' trong config.json.)\n\n")
        if self.v_raw.get() and raw:
            head += "DỮ LIỆU THÔ (khuyến mãi đầu tiên):\n" + raw + "\n\n"
        if offers or extra:
            self.last_msg = (AD.build_message(offers, extra, AD.now()) if AD is not None
                             else build_offers_message(offers, extra))
            self.show(head + self.last_msg)
            self.status.set(f"Xong. {len(offers)} khuyến mãi. Bấm 'Copy tin nhắn' rồi dán vào Zalo.")
        else:
            self.show(head + "Không có khuyến mãi nào. Kiểm tra chiến dịch đã được duyệt chưa.")
            self.status.set("Không có khuyến mãi.")
        self.b_off.config(state="normal")

    def on_campaigns(self):
        if not self.save_cfg(quiet=True) or not self.cfg["token"]:
            messagebox.showwarning("Thiếu token", "Anh dán token trước nhé."); return
        self.status.set("Đang lấy danh sách chiến dịch..."); self.show("")
        def work():
            try:
                url = "https://api.accesstrade.vn/v1/campaigns?" + urllib.parse.urlencode({"approval": "successful", "limit": 50})
                data = api_get(self.cfg["token"], url).get("data", [])
                lines = [f"Có {len(data)} chiến dịch đã được duyệt:", ""]
                for c in data:
                    lines.append(f"- {c.get('name')}  | merchant: {c.get('merchant')}  | id: {c.get('id')}")
                if not data:
                    lines.append("Chưa có chiến dịch nào được duyệt. Anh vào Accesstrade đăng ký Shopee, TikTok Shop.")
                txt = "\n".join(lines)
            except Exception as e:
                txt = f"LỖI khi lấy chiến dịch: {e}"
            self.after(0, lambda: (self.show(txt), self.status.set("Xong.")))
        threading.Thread(target=work, daemon=True).start()

    def on_copy(self):
        text = self.last_msg.strip()
        if not text:
            messagebox.showinfo("Chưa có gì để copy", "Anh bấm lấy khuyến mãi trước nhé."); return
        self.clipboard_clear(); self.clipboard_append(text); self.update()
        self.status.set("✅ Đã copy. Mở nhóm Zalo và bấm Ctrl+V.")


if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        with open(os.path.join(HERE, "loi.txt"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
