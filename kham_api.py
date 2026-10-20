# -*- coding: utf-8 -*-
"""Kham API Accesstrade lan 2: tim dung ten chien dich TikTok Shop va kiem tra trang thai Shopee. Chi doc, khong gui gi."""
import json, urllib.parse, urllib.error
import auto_deals as A

TOKEN = A.get_token()
if not TOKEN:
    raise SystemExit("Khong tim thay token (config.local.json).")
BASE = "https://api.accesstrade.vn/v1/"


def call(path, **params):
    url = BASE + path + "?" + urllib.parse.urlencode(params)
    try:
        return A.api_get(TOKEN, url)
    except urllib.error.HTTPError as e:
        print(f"   LOI HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}")
    except Exception as e:
        print(f"   LOI: {str(e)[:200]}")
    return None


def rows(r):
    d = (r or {}).get("data") if isinstance(r, dict) else None
    return d if isinstance(d, list) else []


print("=== 1. TAT CA chien dich (kem trang thai duyet), de xem Shopee dang o trang thai nao")
for label, kw in (("da duyet", {"approval": "successful"}), ("dang cho duyet", {"approval": "pending"}),
                  ("chua dang ky", {"approval": "unregistered"}), ("khong loc", {})):
    r = call("campaigns", limit=50, **kw)
    got = rows(r)
    print(f"-- {label}: {len(got)} chien dich")
    for c in got:
        print("   *", c.get("merchant"), "|", str(c.get("name"))[:45], "| status:", c.get("status"), "| approval:", c.get("approval"))

print("\n=== 2. Voucher TikTok Shop voi ten chien dich dung (tiktok_cps)")
for m in ("tiktok_cps", "tiktokshop", "tiktok"):
    r = call("offers_informations", merchant=m, status=1, limit=20)
    got = rows(r)
    print(f"-- merchant={m}: {len(got)} khuyen mai")
    for o in got[:4]:
        print("   ", str(o.get("name"))[:60], "|", str(o.get("end_time"))[:10], "|", "co link" if (o.get("aff_link") or o.get("link")) else "khong link")
    if got:
        print("    cac truong:", ", ".join(sorted(got[0].keys())))

print("\n=== 3. San pham TikTok Shop (datafeeds)")
for kw in ({"campaign": "tiktok_cps"}, {"domain": "tiktok.com"}, {"domain": "shop.tiktok.com"}, {"domain": "tiktokglobalshop.com"}):
    r = call("datafeeds", limit=50, **kw)
    got = rows(r)
    ok = [x for x in got if A.calc_price(x)]
    print(f"-- {kw}: {len(got)} san pham, {len(ok)} co gia giam hop le")
    for x in (ok[:3] or got[:2]):
        print("   ", " | ".join(str(x.get(k))[:30] for k in ("name", "price", "discount", "discount_amount", "discount_rate")))

print("\nXONG.")
