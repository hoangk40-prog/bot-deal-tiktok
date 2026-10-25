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


def qr_qua_telegram(ctx, phut=10):
    """24/10: nick phu bi da ra (lich 15h/18h/20h deu loi) -> chup MA QR gui Telegram chat rieng cua anh; anh mo Zalo NICK PHU
    tren dien thoai > Quet ma > chon anh. Ma het han thi lay ma moi, gui lai (toi da 6 anh). Quet xong tra ve page da dang nhap."""
    import re
    local = ad.load_json("config.local.json", {})
    bot, chat = str(local.get("telegram_bot_token", "")).strip(), str(local.get("telegram_chat_id", "")).strip()
    if not (bot and chat):
        return None
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    het, gui, lan = time.time() + phut * 60, 0, 0
    while time.time() < het:
        moi = page.get_by_text(re.compile("Lấy mã mới|hết hạn", re.I)).locator("visible=true")
        if moi.count():                                # ma QR het han -> bam lay ma moi
            try:
                moi.first.click()
                page.wait_for_timeout(2500)
            except Exception:
                pass
            lan = 0
        if lan == 0 and gui < 6:
            try:
                jpg = page.screenshot(type="jpeg", quality=90)
                ad.tg_upload_photo(bot, chat, jpg, "🔐 Bot Zalo bị đăng xuất. Anh LƯU ảnh này → mở Zalo NICK PHỤ trên điện thoại → "
                                   "Quét mã QR → chọn ảnh này. Quét xong bot tự đăng tiếp lượt này (chờ tối đa 10 phút).")
                gui += 1
                log(f"Da gui ma QR qua Telegram (lan {gui})")
            except Exception as e:
                log("Gui ma QR loi:", str(e)[:120])
        lan = (lan + 1) % 20                           # ~1 phut gui lai anh moi (ma QR Zalo doi lien tuc)
        try:
            page.wait_for_selector(LOGGED_IN, timeout=3000)
            return page
        except Exception:
            pass
    log("Het 10 phut chua quet ma QR")
    return None


def alert(text):
    local = ad.load_json("config.local.json", {})
    bot, chat = str(local.get("telegram_bot_token", "")).strip(), str(local.get("telegram_chat_id", "")).strip()
    if bot and chat and os.environ.get("DRY_RUN") != "1":
        try:
            ad.send_telegram(bot, chat, text)
        except Exception as e:
            log("Khong gui duoc canh bao Telegram:", e)


def browser(p, headless=False, an=False):
    """an=True (24/10 anh muon): cua so Chrome mo NGOAI man hinh -> khong bat len, anh khong bam nham. Van la Chrome that
    (khong headless, de Zalo khong nghi). Dang nhap QR / xem thi van hien."""
    os.makedirs(PROFILE, exist_ok=True)
    args = ["--disable-blink-features=AutomationControlled"]
    if an:
        args += ["--window-position=-32000,-32000"]
    return p.chromium.launch_persistent_context(
        PROFILE, channel="chrome", headless=headless, viewport={"width": 1280, "height": 860},
        locale="vi-VN", args=args)


def open_zalo(ctx, wait_login=0):
    # 24/10: lich 10h bao nham "bi dang xuat" (Zalo Web tai cham > 25s, 10h15 chay tay van dang nhap) -> cho 60s, tai lai 1 lan nua
    # 24/10 toi: 15h/18h/20h bao "dang xuat" nhung 22h55 van dang nhap -> CHI coi la dang xuat khi Zalo chuyen sang
    # id.zalo.me (trang ma QR); hop hoi "dung Zalo tai day" thi bam; moi lan khong vao duoc chup man hinh de biet Zalo hien gi.
    import re
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    for lan in range(3):
        try:
            page.goto(ZALO, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector(LOGGED_IN, timeout=max(wait_login, 60) * 1000)
            return page
        except Exception:
            try:
                page.screenshot(path=os.path.join(OUT_DIR, f"khong_vao_{ad.now():%d%m_%H%M}_{lan + 1}.png"))
            except Exception:
                pass
            if wait_login or "id.zalo.me" in page.url:
                return None                   # trang ma QR = dang xuat that -> qr_qua_telegram lo
            nut = page.get_by_role("button", name=re.compile("tại đây|Dùng Zalo|Tiếp tục|Đồng ý|Thử lại", re.I))
            if nut.count():
                log(f"Zalo hien hop '{nut.first.inner_text()[:40]}' -> bam")
                try:
                    nut.first.click()
                    page.wait_for_selector(LOGGED_IN, timeout=30000)
                    return page
                except Exception:
                    pass
            log(f"Zalo Web chua vao duoc (lan {lan + 1}, {page.url[:60]}) -> tai lai")
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
    import shopee_bot                             # 25/10: 1 mon Shopee (may anh chon moi sang) + con lai TikTok
    items = ad.pick_shopee(state, cfg, n, shopee_bot.read_hang())
    ranked, stats = ad.pick_tiktok(ad.fetch_tiktok(token, cfg), state, cfg, n)
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
        state["products"][it.get("key") or "tt|" + it["id"]] = {"t": n.isoformat()}
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
    human_pause(3, 4)                         # cho Zalo dung khung xem truoc link roi tat (chi la logo TikTok Shop chung)
    close = page.locator("#linkPreview .preview-close")
    if close.count():
        close.first.click()
        human_pause(0.4, 0.8)
    box.click()                               # bam tat khung xem truoc lam roi o soan -> dua con tro ve lai, khong thi Enter khong gui
    page.keyboard.press("Control+End")
    got = box.inner_text().replace("\xa0", " ")
    if len(got.strip()) < len(text.strip()) * 0.8:
        raise RuntimeError(f"Dan tin vao Zalo bi thieu ({len(got)}/{len(text)} chu)")


TARGET = {"name": ""}


def assert_chat(page, step):
    """CHOT CHAN: khung chat dang mo phai dung nhom can dang. Sai -> xoa khay / o soan roi DUNG (khong gui nham nhom khac).
    23/10 tung thay bot nhay sang nhom 'Dau thau...' (800 nguoi) voi 1 anh nam cho trong o soan."""
    import unicodedata
    want = unicodedata.normalize("NFC", TARGET["name"]).strip()
    if not want:
        return
    try:
        got = unicodedata.normalize("NFC", page.locator(".header-title").first.inner_text().replace("\xa0", " ")).strip()
    except Exception:
        got = "?"
    if got != want:
        log(f"!!! SAI NHOM o buoc '{step}': dang mo '{got}', can '{want}' -> xoa nhap va dung")
        try:
            clear_tray(page)
            box = page.locator(INPUT).first
            if box.inner_text().strip():
                box.click(); page.keyboard.press("Control+a"); page.keyboard.press("Delete")
        except Exception:
            pass
        raise RuntimeError(f"Khung chat bi doi sang '{got}' o buoc {step} -> da dung, khong gui")


def paste_image(page, path):
    """Dan anh vao o soan (nhu Ctrl+V) -> anh nam o khay duoi o soan, chua gui."""
    import base64
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    assert_chat(page, "dan anh")
    page.locator(INPUT).first.click()
    page.evaluate("""([sel, b64]) => { const el = document.querySelector(sel); el.focus();
        const bin = atob(b64), arr = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
        const dt = new DataTransfer(); dt.items.add(new File([arr], 'deal.jpg', {type: 'image/jpeg'}));
        el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""", [INPUT, b64])
    page.locator(".input-preview-item").first.wait_for(timeout=15000)
    human_pause(1, 2)


def add_caption(page, text):
    """Bam vao anh o khay -> hop 'Nhap mo ta' -> dan chu thich -> Luu. Anh + chu thich thanh 1 tin (giong Telegram)."""
    page.locator(".input-preview-item").first.click()
    # 24/10: hop mo ta hien cham (fadeIn) -> truoc day dem ngay = 0 roi bam nham o soan bi hop che (loi Timeout o mon 2).
    # Nay CHO o mo ta trong hop .zl-modal hien ra.
    cap = page.locator(".zl-modal [contenteditable='true'], [data-placeholder*='mô tả'], [placeholder*='mô tả']") \
        .locator("visible=true").first
    cap.wait_for(timeout=15000)
    cap.click()
    human_pause(0.5, 1)
    page.evaluate("""(text) => { const el = document.activeElement;
        const dt = new DataTransfer(); dt.setData('text/plain', text);
        el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""", text)
    human_pause(1, 2)
    got = page.evaluate("() => (document.activeElement.innerText || '').length")
    if got < len(text.strip()) * 0.8:
        raise RuntimeError(f"Dan chu thich anh bi thieu ({got}/{len(text)} chu)")
    dlg_save = page.get_by_role("button", name="Lưu", exact=True)
    (dlg_save if dlg_save.count() else page.get_by_text("Lưu", exact=True).locator("visible=true")).last.click()
    human_pause(1, 2)
    assert_chat(page, "sau khi luu chu thich")


def clear_tray(page):
    x = page.get_by_text("Xoá tất cả", exact=True)
    if x.count():
        x.first.click()
        human_pause(0.5, 1)


def press_send(page):
    """Enter de gui roi KIEM TRA o soan da trong; con chu thi thu lai, van con thi bao loi (khong de tin dinh vao mon sau)."""
    box = page.locator(INPUT).first
    tray = page.locator(".input-preview-item")
    for _ in range(3):
        assert_chat(page, "truoc khi bam gui")
        box.click()
        assert_chat(page, "truoc khi bam gui")
        page.keyboard.press("Enter")
        human_pause(2, 3)
        if not box.inner_text().replace("\xa0", " ").strip() and not tray.count():
            return
    raise RuntimeError("Bam Enter nhung tin / anh van nam trong o soan (Zalo khong gui)")


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
    kieu = str(ad.load_config().get("zalo_kieu", "tung_mon"))
    jpeg = ad.make_collage(items)                 # kieu tung_mon van lam anh ghep de cua so Bot Zalo xem lai
    img_path = os.path.join(OUT_DIR, "anh_ghep.jpg")
    if jpeg:
        with open(img_path, "wb") as f:
            f.write(jpeg)
    if kieu == "gop":
        text = ad.combo_text(items)
    else:                                         # moi mon 1 anh + 1 tin chu (giong Telegram)
        ad.add_hooks(items, ad.load_config())     # AI viet loi chao hang (loi thi gui nhu cu)
        the = ad.load_config().get("zalo_the", True)   # 24/10 anh chon: THE ANH kieu B (make_card) + chu gon (card_caption)
        caps, pics = [], []
        for i, it in enumerate(items):
            p_ = os.path.join(OUT_DIR, f"mon_{i + 1}.jpg")
            card = ad.make_card(it) if the else None
            try:
                with open(p_, "wb") as f:
                    f.write(card or ad.fb_image_bytes(it["image"]))
                pics.append(p_)
            except Exception as e:
                log(f"  tai anh mon {i + 1} loi ({str(e)[:60]}) -> chi gui chu")
                pics.append(None)
            caps.append(ad.card_caption(it) if card else ad.caption(it))   # the loi -> tin day du nhu cu
        text = "\n\n――――――――\n\n".join(caps)
    with open(os.path.join(OUT_DIR, "tin_gop.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    log(f"Da tao noi dung kieu '{kieu}' ({len(items)} mon) o {OUT_DIR}")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = browser(p, an=os.environ.get("HIEN") != "1")   # HIEN=1: hien cua so de xem bot lam
        try:
            page = open_zalo(ctx)
            if not page:
                log("NICK PHU BI DANG XUAT khoi Zalo Web")
                page = None if dry else qr_qua_telegram(ctx)
                if not page:
                    alert("⚠️ Bot Zalo bị đăng xuất, lượt này KHÔNG đăng được. Anh chạy dang_nhap_zalo.bat rồi quét mã QR "
                          "bằng điện thoại cầm NICK PHỤ.")
                    sys.exit(1)
                log("Da dang nhap lai qua ma QR gui Telegram -> dang tiep luot nay")
            open_group(page, nhom)
            TARGET["name"] = nhom
            log(f"Da mo nhom '{nhom}'")
            if dry:                           # dien tin vao o soan de xem, chup man hinh, xoa di - KHONG gui
                if kieu == "gop" or not pics[0]:
                    send_text(page, text if kieu == "gop" else caps[0])
                else:                         # tung mon: dan anh + chu thich, chup hop mo ta truoc khi Luu
                    paste_image(page, pics[0])
                    add_caption(page, caps[0])
                page.screenshot(path=os.path.join(OUT_DIR, "xem_thu.png"))
                clear_tray(page)
                page.locator(INPUT).first.click()
                page.keyboard.press("Control+a")
                page.keyboard.press("Delete")
                log("DRY_RUN: khong gui. Anh chup man hinh: xem_thu.png")
                return
            if kieu == "gop":
                if jpeg:
                    send_image(page, img_path)
                send_text(page, text)
                press_send(page)
                human_pause(2, 3)
                save_done(state, items, n)
            else:
                for i, (it, cap, pic) in enumerate(zip(items, caps, pics)):
                    if i:
                        human_pause(20, 40)   # nghi giua cac mon nhu nguoi gui tay
                    if pic:                   # anh + chu thich trong 1 tin (giong Telegram)
                        paste_image(page, pic)
                        add_caption(page, cap)
                    else:
                        send_text(page, cap)
                    press_send(page)
                    human_pause(2, 3)
                    save_done(state, [it], n)  # gui toi dau ghi toi do (loi giua chung khong gui lai mon da gui)
                    log(f"  da gui mon {i + 1}/{len(items)}")
                    page.screenshot(path=os.path.join(OUT_DIR, f"sau_mon_{i + 1}.png"))   # de truy loi neu nhay nhom
                    assert_chat(page, f"sau mon {i + 1}")
            page.screenshot(path=os.path.join(OUT_DIR, "da_gui.png"))
            log(f"DA DANG {len(items)} mon vao nhom '{nhom}' (kieu {kieu})")
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


def kiem_tra():
    """In DA_DANG_NHAP / CHUA_DANG_NHAP (cua so Bot Zalo dung de hien trang thai)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = browser(p, an=True)
        ok = open_zalo(ctx) is not None
        ctx.close()
    print("DA_DANG_NHAP" if ok else "CHUA_DANG_NHAP")


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
    {"dang_nhap": dang_nhap, "dang": dang, "xem": xem, "kiem_tra": kiem_tra}.get(cmd, lambda: sys.exit(__doc__))()
