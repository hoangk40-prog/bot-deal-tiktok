# -*- coding: utf-8 -*-
"""Nick Zalo PHU dang deal vao nhom Zalo (qua Zalo Web, chay tren may, lich Windows).

  python zalo_bot.py dang_nhap   -> mo Chrome rieng cua bot, anh quet ma QR bang dien thoai cam NICK PHU (1 lan)
  python zalo_bot.py dang        -> chon 4 deal + anh ghep + tin gop -> dang vao nhom (lich Windows goi 4 lan/ngay)
  python zalo_bot.py xem         -> mo Zalo Web cua bot de xem / kiem tra (khong dang gi)

Bien moi truong: DRY_RUN=1 (chi tao anh + chu, mo nhom nhung KHONG gui), ZALO_NHOM="ten nhom" (dang vao nhom khac, vd nhom thu),
  NGAY=1 (khong cho ngau nhien vai phut truoc khi dang).
Cai dat: config.local.json "zalo_nhom" (ten nhom Zalo that). config.json "zalo_items" (so mon/lan, mac dinh 4).
Quy tac chong khoa nick: chi dang vao 1 nhom cua anh, 3-4 lan/ngay, 1 anh + 1 tin, gio lech ngau nhien, go nhu nguoi.
Da dang mon nao: zalo_da_dang.json (khong dua len GitHub). Bi dang xuat -> nhan Telegram chat rieng.
"""
import datetime
import os
import random
import sys
import time

import auto_deals as ad

sys.stdout.reconfigure(encoding="utf-8")
PROFILE = os.path.join(os.environ.get("LOCALAPPDATA", ad.HERE), "zalo_bot", "chrome")   # o may, KHONG de tren Drive
STATE = "zalo_da_dang.json"
OUT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ad.HERE), "zalo_bot")
ZALO = "https://chat.zalo.me/"
LOGGED_IN = "#contact-search-input"          # o tim kiem chi co khi da dang nhap
INPUT = "#richInput"                          # o soan tin
PHOTO_BTN = "[data-translate-title='STR_SEND_PHOTO']"   # nut "Gui hinh anh" tren thanh cong cu khung chat


def log(*a):
    line = f"[{ad.now():%d/%m %H:%M:%S}] " + " ".join(str(x) for x in a)
    print(line)
    try:
        with open(os.path.join(OUT_DIR, "nhat_ky_zalo.txt"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def alert(text):
    local = ad.load_json("config.local.json", {})
    bot, chat = str(local.get("telegram_bot_token", "")).strip(), str(local.get("telegram_chat_id", "")).strip()
    if bot and chat and os.environ.get("DRY_RUN") != "1":
        try:
            ad.send_telegram(bot, chat, text)
        except Exception as e:
            log("Khong gui duoc canh bao Telegram:", e)


def browser(p, headless=False):
    os.makedirs(PROFILE, exist_ok=True)
    return p.chromium.launch_persistent_context(
        PROFILE, channel="chrome", headless=headless, viewport={"width": 1280, "height": 860},
        locale="vi-VN", args=["--disable-blink-features=AutomationControlled"])


def open_zalo(ctx, wait_login=0):
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(ZALO, wait_until="domcontentloaded")
    try:
        page.wait_for_selector(LOGGED_IN, timeout=max(wait_login, 25) * 1000)
        return page
    except Exception:
        return None


# ---------------------------------------------------------------- chon deal
def pick_deals():
    cfg = ad.load_config()
    n = ad.now()
    token = ad.get_token()
    if not token:
        sys.exit("Thieu token Accesstrade trong config.local.json")
    state = ad.load_json(STATE, {})
    state.setdefault("products", {})
    want = int(cfg.get("zalo_items", 4))
    ranked, stats = ad.pick_tiktok(ad.fetch_tiktok(token, cfg), state, cfg, n)
    items = []
    for it in ranked:
        if len(items) >= want:
            break
        d = ad.make_link(token, it["url"], it["id"])
        if d:
            it["aff"] = d.get("aff_short_url") or d.get("aff_url")
            items.append(it)
    log(f"Chon {len(items)} mon (loai: {dict(stats)})")
    return items, state, n


def save_done(state, items, n):
    for it in items:
        state["products"]["tt|" + it["id"]] = {"t": n.isoformat()}
    keep = (n - datetime.timedelta(days=30)).isoformat()
    state["products"] = {k: v for k, v in state["products"].items() if v.get("t", "") >= keep}
    ad.save_json(STATE, state)


# ---------------------------------------------------------------- thao tac Zalo Web
def human_pause(a=0.6, b=1.6):
    time.sleep(random.uniform(a, b))


def open_group(page, name):
    box = page.locator(LOGGED_IN)
    box.click()
    human_pause()
    box.fill("")
    for ch in name:                           # go tung chu nhu nguoi
        page.keyboard.type(ch, delay=random.randint(60, 160))
    human_pause(1.5, 2.5)
    hit = page.get_by_text(name, exact=True).locator("visible=true").first   # ban an cung ten nam san trong trang
    hit.wait_for(timeout=15000)
    hit.click()
    page.wait_for_selector(INPUT, timeout=15000)
    human_pause()
    # kiem tra dung nhom: ten nhom hien o dau khung chat
    title = page.locator(".header-title").first.inner_text().replace("\xa0", " ").strip()
    if title != name:
        raise RuntimeError(f"Mo nham khung chat '{title}' (can '{name}')")


def send_image(page, path):
    btn = page.locator(PHOTO_BTN).first
    if btn.count() == 0:
        raise RuntimeError("Khong thay nut 'Gui hinh anh' tren Zalo Web (giao dien doi?)")
    with page.expect_file_chooser(timeout=15000) as fc:
        btn.click()
    fc.value.set_files(path)
    human_pause(4, 6)                         # cho anh tai len + gui


def send_text(page, text):
    """Dan ca tin 1 lan (go tung dong lam Zalo nuot mat dong co emoji so 1️⃣ 2️⃣)."""
    box = page.locator(INPUT)
    box.click()
    human_pause(0.5, 1)
    page.evaluate("""([sel, text]) => { const el = document.querySelector(sel); el.focus();
        const dt = new DataTransfer(); dt.setData('text/plain', text);
        el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""",
                  [INPUT, text])
    human_pause(1.5, 2.5)
    got = box.inner_text().replace("\xa0", " ")
    if len(got.strip()) < len(text.strip()) * 0.8:
        raise RuntimeError(f"Dan tin vao Zalo bi thieu ({len(got)}/{len(text)} chu)")


def dang():
    dry = os.environ.get("DRY_RUN") == "1"
    local = ad.load_json("config.local.json", {})
    nhom = (os.environ.get("ZALO_NHOM") or str(local.get("zalo_nhom", ""))).strip()
    if not nhom:
        sys.exit('Chua co ten nhom: them "zalo_nhom": "Ten nhom Zalo" vao config.local.json')
    if not dry and os.environ.get("NGAY") != "1":
        wait = random.randint(0, 8 * 60)      # lech gio ngau nhien 0-8 phut
        log(f"Cho {wait // 60} phut {wait % 60} giay cho giong nguoi...")
        time.sleep(wait)

    items, state, n = pick_deals()
    if not items:
        log("Khong co deal moi -> bo qua lan nay.")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    jpeg = ad.make_collage(items)
    img_path = os.path.join(OUT_DIR, "anh_ghep.jpg")
    if jpeg:
        with open(img_path, "wb") as f:
            f.write(jpeg)
    text = ad.combo_text(items)
    with open(os.path.join(OUT_DIR, "tin_gop.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    log(f"Da tao anh ghep + tin gop ({len(text)} chu) o {OUT_DIR}")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = browser(p)
        try:
            page = open_zalo(ctx)
            if not page:
                log("NICK PHU BI DANG XUAT khoi Zalo Web")
                alert("⚠️ Bot Zalo bị đăng xuất. Anh chạy dang_nhap_zalo.bat rồi quét mã QR bằng điện thoại cầm NICK PHỤ.")
                sys.exit(1)
            open_group(page, nhom)
            log(f"Da mo nhom '{nhom}'")
            if dry:                           # dien tin vao o soan de xem, chup man hinh, xoa di - KHONG gui
                send_text(page, text)
                page.screenshot(path=os.path.join(OUT_DIR, "xem_thu.png"))
                page.locator(INPUT).click()
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                log("DRY_RUN: khong gui. Anh chup man hinh: xem_thu.png")
                return
            if jpeg:
                send_image(page, img_path)
            send_text(page, text)
            page.keyboard.press("Enter")
            human_pause(3, 5)
            page.screenshot(path=os.path.join(OUT_DIR, "da_gui.png"))
            save_done(state, items, n)
            log(f"DA DANG {len(items)} mon vao nhom '{nhom}'")
        except Exception as e:
            log("LOI:", e)
            try:
                ctx.pages[0].screenshot(path=os.path.join(OUT_DIR, "loi.png"))
            except Exception:
                pass
            alert(f"⚠️ Bot Zalo đăng lỗi: {str(e)[:300]}")
            raise
        finally:
            ctx.close()


def dang_nhap():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = browser(p)
        print("Cua so Chrome cua bot da mo. Dung dien thoai cam NICK PHU -> Zalo -> quet ma QR. Cho toi da 5 phut...")
        page = open_zalo(ctx, wait_login=300)
        if page:
            human_pause(5, 6)
            print("DA DANG NHAP. Tu nay bot dung dang nhap nay (luu o", PROFILE, ")")
        else:
            print("Chua dang nhap duoc. Chay lai dang_nhap_zalo.bat.")
        ctx.close()


def xem():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = browser(p)
        page = open_zalo(ctx)
        print("Da dang nhap" if page else "CHUA dang nhap")
        input("Xem xong bam Enter de dong...")
        ctx.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"dang_nhap": dang_nhap, "dang": dang, "xem": xem}.get(cmd, lambda: sys.exit(__doc__))()
