"""Bao cao tong hop moi ngay -> nhom Telegram "BAO CAO KIEM TIEN".

  python bao_cao_ngay.py tu_dong         -> gom so lieu + viet bao cao + gui nhom (GitHub Actions chay 22h30, xem bao_cao.yml)
  python bao_cao_ngay.py thu_thap        -> chi gom so lieu, luu lich su, in JSON
  python bao_cao_ngay.py gui <file.txt>  -> gui noi dung file vao nhom bao cao (KHONG gui vao kenh)

Bien moi truong (GitHub): ACCESSTRADE_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID, TELEGRAM_REPORT_CHAT_ID
  (thieu thi gui TELEGRAM_CHAT_ID), GOOGLE_SA_JSON (dem anh/video Trang FB tren Drive khi may khong co o Drive),
  DRY_RUN=1 (in bao cao, khong gui, khong luu lich su).
Tren may: lay ma trong config.local.json. Khong co so lieu Metricool (FB/TikTok/YouTube) - phan do Claude lay khi chay tay.
Lich su tung ngay: bao_cao/lich_su.json (de so sanh xu huong).
"""
import datetime
import json
import os
import string
import sys
import urllib.parse
import urllib.request

import auto_deals as ad

sys.stdout.reconfigure(encoding="utf-8")
HISTORY = os.path.join(ad.HERE, "bao_cao", "lich_su.json")
AT_API = "https://api.accesstrade.vn/v1"
RUT_TIEN = 200000


def find_drive_dir(name):
    """Thu muc Drive dulieuhoangsythb3 mang chu o khac nhau tren moi may (co the nam trong thu muc cha 'Trang Facebook')."""
    for d in string.ascii_uppercase:
        for p in (f"{d}:\\My Drive\\Trang Facebook\\{name}", f"{d}:\\My Drive\\{name}"):
            if os.path.isdir(p):
                return p
    return ""


def count_files(path, today=None):
    if not path or not os.path.isdir(path):
        return None, None
    files = [f for f in os.scandir(path) if f.is_file() and not f.name.startswith(".")]
    if today is None:
        return len(files), None
    moved = sum(1 for f in files if datetime.datetime.fromtimestamp(f.stat().st_mtime, ad.VN).date() == today)
    return len(files), moved


def money(x):
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def at_orders(token, since, until):
    """Don hang Accesstrade (moi trang 100 don)."""
    out, page = [], 1
    while True:
        q = urllib.parse.urlencode({"since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "until": until.strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": 100, "page": page})
        d = ad.api_get(token, f"{AT_API}/order-list?{q}")
        rows = d.get("data") or []
        out += rows
        if len(rows) < 100 or page >= 20:
            return out
        page += 1


def sum_orders(rows):
    s = {"don": len(rows), "doanh_so": 0.0, "hoa_hong": 0.0, "cho_duyet": 0, "da_duyet": 0, "huy": 0, "san": {}}
    for r in rows:
        s["doanh_so"] += money(r.get("billing"))
        s["hoa_hong"] += money(r.get("pub_commission") or r.get("commission"))
        s["cho_duyet"] += int(r.get("order_pending") or 0)
        s["da_duyet"] += int(r.get("order_approved") or 0)
        s["huy"] += int(r.get("order_reject") or 0)
        m = str(r.get("merchant") or "khac")
        s["san"][m] = s["san"].get(m, 0) + 1
    return s


def secret(env, key):
    """Ma lay tu bien moi truong (GitHub) hoac config.local.json (may)."""
    return (os.environ.get(env, "") or str(ad.load_json("config.local.json", {}).get(key, ""))).strip()


def fb_queue_local(today):
    anh, video = find_drive_dir("Ảnh Trang Facebook"), find_drive_dir("Video Trang Facebook")
    if not anh and not video:
        return None
    a_cho, _ = count_files(os.path.join(anh, "Ảnh chờ đăng") if anh else "")
    a_da, a_hom_nay = count_files(os.path.join(anh, "Ảnh đã đăng") if anh else "", today)
    v_cho, _ = count_files(os.path.join(video, "Video chờ đăng") if video else "")
    v_da, v_hom_nay = count_files(os.path.join(video, "Video đã đăng") if video else "", today)
    return {"anh_cho": a_cho, "anh_da_dang": a_da, "anh_dang_hom_nay": a_hom_nay,
            "video_cho": v_cho, "video_da_dang": v_da, "video_dang_hom_nay": v_hom_nay}


def fb_queue_drive(sa_json):
    """Tren GitHub: dem file qua Google Drive API bang service account cua bot dang Trang."""
    import dang_trang as dt                      # can requests + google-auth (chi cai tren GitHub)
    drive = dt.Drive(sa_json)
    root = drive.root()
    out = {}
    for kieu, k in dt.KIEU.items():
        goc = drive.child(root, k["goc"], folder=True)["id"]
        for key, name in (("cho", k["cho"]), ("da_dang", k["xong"])):
            fid = drive.child(goc, name, folder=True)["id"]
            out[f"{kieu}_{key}"] = len(drive.ls(f"'{fid}' in parents and mimeType!='{dt.FOLDER}'", "id"))
    return out


def collect(n=None):
    n = n or ad.now()
    today = n.date()
    data = {"ngay": today.isoformat(), "luc": n.strftime("%H:%M"), "loi": []}

    # --- Accesstrade: don + hoa hong hom nay va ca thang (gio UTC: VN = UTC+7)
    token = ad.get_token()
    utc = datetime.timezone.utc
    day0 = datetime.datetime.combine(today, datetime.time(), ad.VN).astimezone(utc)
    month0 = datetime.datetime.combine(today.replace(day=1), datetime.time(), ad.VN).astimezone(utc)
    until = n.astimezone(utc)
    try:
        data["accesstrade_hom_nay"] = sum_orders(at_orders(token, day0, until))
        thang = sum_orders(at_orders(token, month0, until))
        data["accesstrade_thang"] = thang
        data["con_thieu_de_rut_tien"] = max(0, RUT_TIEN - thang["hoa_hong"])
    except Exception as e:
        data["loi"].append(f"Accesstrade: {ad.describe_error(e)}")

    # --- Telegram: so nguoi theo doi kenh
    bot, channel = secret("TELEGRAM_BOT_TOKEN", "telegram_bot_token"), secret("TELEGRAM_CHANNEL_ID", "telegram_channel_id")
    if bot and channel:
        try:
            q = urllib.parse.urlencode({"chat_id": channel})
            r = json.loads(urllib.request.urlopen(
                f"https://api.telegram.org/bot{bot}/getChatMemberCount?{q}", timeout=30).read())
            data["telegram_nguoi_theo_doi"] = r.get("result")
        except Exception as e:
            data["loi"].append(f"Telegram: {e}")

    # --- Hang cho dang Trang Facebook: o Drive tren may, khong co thi qua Drive API (GitHub)
    try:
        q = fb_queue_local(today)
        if q is None and os.environ.get("GOOGLE_SA_JSON"):
            q = fb_queue_drive(os.environ["GOOGLE_SA_JSON"])
        if q is None:
            data["loi"].append("Không đếm được ảnh/video Trang FB (máy không có ổ Drive, thiếu GOOGLE_SA_JSON)")
        else:
            data["facebook_hang_cho"] = q
    except Exception as e:
        data["loi"].append(f"Drive Trang FB: {e}")

    # --- Bot deal (sent.json) + bot dang Trang (dang_trang.json); tren GitHub la ban that
    state = ad.load_json(ad.STATE_FILE, {})
    meta, d = state.get("meta") or {}, today.isoformat()
    fb = meta.get("fb_make") or {}
    trang = ad.load_json("dang_trang.json", {})
    data["bot"] = {"mon_gui_hom_nay": sum(1 for v in (state.get("products") or {}).values()
                                          if str(v.get("t", "")).startswith(d)),
                   "luot_chay_hom_nay": sum(1 for s in meta.get("slots_done", []) if s.startswith(d + "@")),
                   "bai_fb_hom_nay": fb.get("count", 0) if fb.get("date") == d else 0,
                   "loi_lien_tiep": meta.get("fail_count", 0)}
    t2 = trang.get("trang2") or {}
    data["dang_trang"] = {"video_da_dang": len((trang.get("da_dang") or {}).get("video", [])),
                          "anh_da_dang": len((trang.get("da_dang") or {}).get("anh", [])),
                          "loi_lien_tiep": trang.get("loi_lien_tiep", 0),
                          "trang2_video_da_dang": len((t2.get("da_dang") or {}).get("video", [])),
                          "trang2_anh_da_dang": len((t2.get("da_dang") or {}).get("anh", [])),
                          "trang2_loi_lien_tiep": t2.get("loi_lien_tiep", 0)}

    # --- So nguoi theo doi 2 Trang FB (27/10, thay Metricool) - ma Trang co san
    for sfx in ("", "2"):
        page, tok = secret(f"FB_PAGE{sfx}_ID", f"fb_page{sfx}_id"), secret(f"FB_PAGE{sfx}_TOKEN", f"fb_page{sfx}_token")
        if not (page and tok):
            continue
        try:
            q = urllib.parse.urlencode({"fields": "name,followers_count,fan_count", "access_token": tok})
            r = json.loads(urllib.request.urlopen(f"https://graph.facebook.com/v21.0/{page}?{q}", timeout=30).read())
            data.setdefault("trang_fb", {})[sfx or "1"] = {"ten": r.get("name"), "theo_doi": r.get("followers_count"),
                                                           "thich": r.get("fan_count")}
        except Exception as e:
            data["loi"].append(f"Trang FB {sfx or '1'}: {str(e)[:100]}")
    return data


# ---------------------------------------------------------------- 27/10 AI nhan xet + cach kiem tien moi (Gemini, mien phi)
VE_ANH = ("Anh Hoàng ở Việt Nam, làm kiếm tiền online một mình, tận dụng bot tự động (không có nhân viên, vốn ít). Đang có: "
          "1) bot săn deal TikTok Shop tiếp thị liên kết qua Accesstrade (hoa hồng 5–8%) gửi kênh Telegram, nhóm Zalo, 2 Trang Facebook; "
          "chờ Shopee duyệt Open API. 2) 2 Trang Facebook đăng video/ảnh hài mỗi ngày (mới lập, rất ít người theo dõi). "
          "3) vài kênh YouTube kể chuyện (Nhật, Hàn) làm bằng tool tự dựng video AI. 4) bán tool làm video AI theo tháng cho người khác.")


def ai_nhan_xet(data, truoc):
    """Gemini doc so lieu hom nay + 7 ngay truoc -> nhan xet + viec nen lam + 2-3 cach kiem tien / xu huong moi.
    Co Google Search thi dung (xu huong that), loi thi bo tim kiem. Khong khoa / loi het -> '' (bao cao gui nhu cu)."""
    key = ad.gemini_key()
    if not key:
        return ""
    gon = lambda d: {k: v for k, v in d.items() if k not in ("ai", "loi")}
    cu = [d.get("ai", "")[-600:] for d in truoc[-3:] if d.get("ai")]
    prompt = (VE_ANH + "\n\nSỐ LIỆU HÔM NAY (JSON):\n" + json.dumps(gon(data), ensure_ascii=False) +
              "\n\n7 NGÀY TRƯỚC:\n" + json.dumps([gon(d) for d in truoc[-7:]], ensure_ascii=False) +
              ("\n\nGỢI Ý MẤY HÔM TRƯỚC (đừng lặp lại):\n" + "\n---\n".join(cu) if cu else "") +
              "\n\nViết bằng tiếng Việt dễ hiểu, không thuật ngữ, ngắn gọn, KHÔNG dùng markdown (không dấu *, #). Đúng 2 phần:\n"
              "🧠 Nhận xét số liệu\n- 2–3 gạch đầu dòng: xu hướng đáng chú ý (tăng/giảm, chỗ nào đang tắc) và NÊN LÀM GÌ ngay, cụ thể. "
              "Chỉ dựa trên số liệu có thật ở trên, không bịa số.\n"
              "💡 Cách kiếm tiền / xu hướng mới\n- 2–3 gạch đầu dòng, mỗi ý: tên cách + vì sao hợp với anh + bước làm đầu tiên. "
              "Ưu tiên cái tận dụng được bot/tool anh đang có, ít vốn, hợp pháp, không lách luật nền tảng, đang lên ở Việt Nam. "
              "Không hứa thu nhập. Mỗi gạch đầu dòng TỐI ĐA 2 câu ngắn, cả bài dưới 900 ký tự.")
    for tim in (True, False):
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7}}
        if tim:
            body["tools"] = [{"google_search": {}}]
        for model in ad.GEMINI_MODELS[:2] if tim else ad.GEMINI_MODELS:   # tim kiem hay het luot free (429) -> thu it
            try:
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                    data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=90) as r:
                    j = json.loads(r.read().decode("utf-8"))
                t = "".join(p.get("text", "") for p in j["candidates"][0]["content"]["parts"]).strip()
            except Exception as e:
                print(f"[AI nhan xet] {model}{' +tim' if tim else ''} loi: {str(e)[:100].replace(key, '***')}")
                continue
            t = "\n".join(ln.rstrip() for ln in t.replace("**", "").replace("##", "").splitlines() if ln.strip())
            t = t.replace("\n💡", "\n\n💡")
            if "💡" in t or len(t) > 200:
                print(f"[AI nhan xet] {model}{' +tim' if tim else ''}: {len(t)} ky tu")
                return t[:1800]
    return ""


def load_history():
    try:
        with open(HISTORY, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(data):
    hist = load_history()
    hist[data["ngay"]] = data                   # moi ngay 1 dong, chay lai thi ghi de
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    tmp = HISTORY + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)
    os.replace(tmp, HISTORY)
    return hist


def vnd(x):
    return f"{int(round(x or 0)):,}đ".replace(",", ".")


def delta(now_v, old_v):
    if now_v is None or old_v is None:
        return ""
    k = now_v - old_v
    return f" ({'+' if k >= 0 else ''}{k} so với hôm trước)" if k else " (không đổi)"


def build_text(data, prev):
    """prev = so lieu ngay truoc gan nhat (co the {})."""
    day = datetime.date.fromisoformat(data["ngay"])
    L = [f"📊 BÁO CÁO KIẾM TIỀN {day:%d/%m} (bot tự gửi {data['luc']})", ""]
    goi_y = []

    h, t = data.get("accesstrade_hom_nay"), data.get("accesstrade_thang")
    L.append("💰 Accesstrade")
    if h and t:
        L.append(f"- Hôm nay: {h['don']} đơn, hoa hồng {vnd(h['hoa_hong'])}")
        L.append(f"- Tháng {day.month}: {t['don']} đơn, hoa hồng {vnd(t['hoa_hong'])} (đã duyệt {t['da_duyet']}, chờ {t['cho_duyet']}, huỷ {t['huy']})")
        thieu = data.get("con_thieu_de_rut_tien", 0)
        L.append(f"- Còn thiếu {vnd(thieu)} mới rút được" if thieu > 0 else "- ✅ ĐÃ ĐỦ 200.000đ: anh vào Accesstrade nhập tài khoản ngân hàng")
        if t["don"] == 0:
            goi_y.append("Chưa có đơn nào trong tháng → việc gấp nhất là kéo thêm người vào kênh/nhóm (mẫu tin mời trong anh_quang_cao).")
    else:
        L.append("- Không đọc được (xem lỗi bên dưới)")
    L.append("")

    b, pb = data.get("bot", {}), prev.get("bot", {})
    L.append("🤖 Bot săn deal")
    L.append(f"- Gửi {b.get('mon_gui_hom_nay', 0)} món{delta(b.get('mon_gui_hom_nay'), pb.get('mon_gui_hom_nay'))}, "
             f"{b.get('luot_chay_hom_nay', 0)} lượt chạy, {b.get('bai_fb_hom_nay', 0)} bài deal lên Trang FB")
    if b.get("loi_lien_tiep"):
        L.append(f"- ⚠️ Đang lỗi {b['loi_lien_tiep']} lần liên tiếp")
        goi_y.append("Bot deal đang lỗi → mở tab Actions trên GitHub xem lỗi.")
    elif b.get("luot_chay_hom_nay", 0) == 0:
        goi_y.append("Hôm nay bot deal không chạy lượt nào → kiểm tra GitHub Actions.")
    tg = data.get("telegram_nguoi_theo_doi")
    if tg is not None:
        L.append(f"- Kênh Telegram: {tg} người theo dõi{delta(tg, prev.get('telegram_nguoi_theo_doi'))}")
    L.append("")

    q, pq = data.get("facebook_hang_cho"), prev.get("facebook_hang_cho") or {}
    tr, ptr = data.get("dang_trang", {}), prev.get("dang_trang") or {}
    L.append("📘 Trang Facebook (ảnh/video hài)")
    if "video_da_dang" in ptr:
        L.append(f"- Hôm nay bot đăng: {tr['video_da_dang'] - ptr['video_da_dang']} video, {tr['anh_da_dang'] - ptr['anh_da_dang']} ảnh")
    if q:
        vc, ac = q.get("video_cho"), q.get("anh_cho")
        L.append(f"- Còn chờ đăng: {vc} video, {ac} ảnh")
        for ten, so, moi_ngay in (("video", vc, 2), ("ảnh", ac, 1)):
            if so is not None and so < moi_ngay * 5:
                goi_y.append(f"Chỉ còn {so} {ten} chờ đăng (~{so // moi_ngay} ngày) → bổ sung thêm {ten} + dòng tiêu đề.")
    if "trang2_video_da_dang" in ptr:
        L.append(f"- Trang 2 hôm nay: {tr['trang2_video_da_dang'] - ptr['trang2_video_da_dang']} video, "
                 f"{tr['trang2_anh_da_dang'] - ptr['trang2_anh_da_dang']} ảnh")
    for so, tf in sorted((data.get("trang_fb") or {}).items()):
        cu = ((prev.get("trang_fb") or {}).get(so) or {}).get("theo_doi")
        L.append(f"- {tf.get('ten') or 'Trang ' + so}: {tf.get('theo_doi')} người theo dõi{delta(tf.get('theo_doi'), cu)}")
    for k, ten in (("loi_lien_tiep", "Trang 1"), ("trang2_loi_lien_tiep", "Trang 2")):
        if tr.get(k):
            L.append(f"- ⚠️ Bot đăng {ten} lỗi {tr[k]} lần liên tiếp")
    L.append("")

    if goi_y:
        L.append("👉 Việc nên làm")
        L += [f"- {g}" for g in goi_y]
        L.append("")
    if data.get("ai"):
        L += [data["ai"], ""]
    if data.get("loi"):
        L.append("⚠️ Lỗi khi lấy số liệu")
        L += [f"- {e}" for e in data["loi"]]
        L.append("")
    L.append("(Số liệu FB/TikTok/YouTube chi tiết: hỏi Claude lấy qua Metricool)")
    return "\n".join(L).strip()


def report_chat():
    # nhom Telegram rieng chi nhan bao cao; chua co thi gui vao chat rieng voi bot (lan voi tin deal)
    return secret("TELEGRAM_REPORT_CHAT_ID", "telegram_report_chat_id") or secret("TELEGRAM_CHAT_ID", "telegram_chat_id")


def send(text):
    bot, chat = secret("TELEGRAM_BOT_TOKEN", "telegram_bot_token"), report_chat()
    if not (bot and chat):
        sys.exit("Thiếu mã Telegram (config.local.json hoặc secret GitHub).")
    print(f"Đã gửi {ad.send_telegram(bot, chat, text)} tin vào Telegram.")


def thu_thap():
    data = collect()
    hist = save_history(data)
    week = [hist[k] for k in sorted(hist) if k < data["ngay"]][-7:]   # 7 ngay truoc de so sanh
    print(json.dumps({"hom_nay": data, "7_ngay_truoc": week}, ensure_ascii=False, indent=1))


def tu_dong():
    dry = os.environ.get("DRY_RUN") == "1"
    data = collect()
    hist = load_history()
    older = [k for k in sorted(hist) if k < data["ngay"]]
    data["ai"] = ai_nhan_xet(data, [hist[k] for k in older])
    text = build_text(data, hist[older[-1]] if older else {})
    print(text)
    if dry:
        print("\nDRY_RUN: không gửi, không lưu lịch sử.")
        return
    save_history(data)
    send(text)


def gui(path):
    with open(path, encoding="utf-8") as f:
        send(f.read().strip())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) >= 2 else ""
    if cmd == "tu_dong":
        tu_dong()
    elif cmd == "thu_thap":
        thu_thap()
    elif cmd == "gui" and len(sys.argv) >= 3:
        gui(sys.argv[2])
    else:
        sys.exit(__doc__)
