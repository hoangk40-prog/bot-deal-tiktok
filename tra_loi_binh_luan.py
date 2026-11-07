# -*- coding: utf-8 -*-
"""Tra loi binh luan tren cac Trang Facebook bang mau co san (khong spam, co gioi han). Chay moi gio.

Moi lan chay: quet vai bai gan nhat cua Trang -> binh luan CHUA AI TRA LOI, da dang >= CHO_PHUT phut
-> tra loi bang 1 mau ngau nhien DUNG GIONG TRANG + DUNG KIEU BINH LUAN (co ten nguoi binh luan) + tha tim.
Binh luan co tu nhay cam (khieu nai, lua dao...) hoac co link -> KHONG tra loi, bao Telegram de anh tu xu ly.

07/11 (anh duyet): moi Trang 1 bo mau rieng (truoc day ca 2 Trang dung chung mau "cung cuoi nhe 😄" tu thoi truyen cuoi):
  Trang 1 "Ngam Doi Ma Song" + Trang 2 "Song Cham Nghi Sau": thong diep cuoc song -> tram, am, dong cam, khong emoji cuoi dua
  Trang 3 "Bep Nha Meo Hay", Trang 4 do gia dung/meo don dep: vui vua phai; hoi mua -> link o binh luan cua Trang (dang_trang.py tu dang)
  Trang 5 "Suc khoe La Tat ca": KHONG noi chua benh; hoi ve benh/dau -> khuyen hoi bac si
Kieu binh luan: tim (chi tha tim/bieu tuong), khen (dong tinh), tam_su (buon, ke chuyen), hoi, hoi_mua, hoi_benh (Trang 5).

Bien moi truong (hoac config.local.json: fb_page<N>_id, fb_page<N>_token, telegram_bot_token, telegram_chat_id, kenh_link):
  TRANG=1..5       Trang nao (ma: FB_PAGE<N>_ID / FB_PAGE<N>_TOKEN, Trang 1 = FB_PAGE_ID; Trang 3+ doc ca SECRETS_JSON)
  DRY_RUN=1        chi in ra se tra loi gi, KHONG gui, KHONG luu trang thai
  KENH_LINK        link kenh Telegram deal (Trang 1, 2: nguoi hoi mua)
  MAX=8            toi da bao nhieu tra loi moi lan chay          SO_BAI=25     quet bao nhieu bai gan nhat
  TRAN_NGAY=40     toi da bao nhieu tra loi moi ngay moi Trang    CHO_PHUT=10   binh luan phai du bao nhieu phut tuoi
  NGAY=1           bo gioi han gio (mac dinh chi tra loi tu 7h den 23h)
Quyen token can: pages_read_engagement, pages_manage_engagement, pages_read_user_content
  (chay lai nhap_facebook_nhieu_trang.bat, luc tao ma o Graph API Explorer tick them 3 quyen nay).
"""
import datetime
import json
import os
import random
import re
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "tra_loi_binh_luan.json")
CONFIG_FILE = os.path.join(HERE, "config.local.json")
FB_API = "https://graph.facebook.com/" + (os.environ.get("FB_API_VERSION") or "v23.0")
VN = datetime.timezone(datetime.timedelta(hours=7))

# ----- Mau tra loi: anh sua thoai mai. {ten} = ten goi cua nguoi binh luan, {link} = KENH_LINK
MAU_THONG_DIEP = {                     # Trang 1, 2: tram, am, ngan, khong emoji cuoi dua
    "tim": [
        "Cảm ơn {ten} đã ghé lại. Chúc bạn một ngày bình yên 🌿",
        "Cảm ơn {ten} đã đồng cảm. Mong lòng bạn luôn nhẹ nhõm.",
        "Trân trọng {ten} đã dừng lại nghe hết câu chuyện 🙏",
        "Cảm ơn {ten}. Mong điều bạn đang mang trong lòng sẽ sớm nhẹ đi.",
        "Cảm ơn {ten} đã ở lại cùng Trang. Chúc bạn bình an.",
    ],
    "khen": [
        "Cảm ơn {ten}. Hiểu được là một chuyện, sống được mới khó. Mình cùng cố gắng nhé.",
        "Cảm ơn {ten} đã đồng cảm. Có những điều phải trải qua rồi mới thấm, phải không bạn?",
        "{ten} nói đúng lắm. Ngẫm một lần, nhớ một đời. Cảm ơn bạn đã chia sẻ 🌿",
        "Cảm ơn {ten}. Mong bài học nhỏ này giúp được bạn phần nào.",
        "Cảm ơn {ten} đã ghé xem và để lại lời. Chúc bạn sống chậm mà vững vàng.",
    ],
    "tam_su": [
        "Đọc mà thương {ten}. Chuyện gì rồi cũng qua, bạn cứ đi chậm thôi, đừng bỏ cuộc 🙏",
        "Cảm ơn {ten} đã tin mà chia sẻ. Ai cũng có lúc mệt, nghỉ một chút rồi lại bước tiếp nhé.",
        "{ten} ơi, bạn đã cố gắng nhiều rồi. Hãy thương bản thân mình thêm một chút.",
        "Những ngày khó rồi sẽ qua, {ten} ạ. Mong bạn sớm tìm lại được bình yên 🌿",
        "Trang hiểu cảm giác của {ten}. Cứ từ từ thôi, mọi chuyện sẽ ổn dần.",
    ],
    "hoi": [
        "Cảm ơn {ten} đã hỏi. Mỗi người một hoàn cảnh, mong video cho bạn thêm một góc nhìn 🌿",
        "Câu hỏi hay lắm {ten}. Có những điều phải tự sống mới trả lời được, mình cùng ngẫm thêm nhé.",
        "Cảm ơn {ten}. Mọi người có suy nghĩ gì thì cùng chia sẻ với {ten} nhé.",
    ],
    "hoi_mua": [
        "Chào {ten}, các món hay giá tốt bên mình đăng mỗi ngày ở đây nhé: {link}",
        "{ten} xem link và giá mới nhất ở kênh này nha: {link}",
    ],
}


def _do_dung(chu):                     # Trang 3, 4: vui vua phai, gan gui
    return {
        "khen": [
            f"Cảm ơn {{ten}} nha! Mai còn {chu} hay nữa, nhớ ghé Trang 😊",
            "{ten} thấy hữu ích thì lưu lại dùng dần nhé 👍",
            "Cảm ơn {ten} đã xem! Mỗi ngày một món đồ hay cùng Trang nha 😊",
            f"Cảm ơn {{ten}} ủng hộ ạ. Nhà mình có {chu} nào hay thì chia sẻ cùng mọi người nhé!",
        ],
        "tam_su": [
            "Cảm ơn {ten} đã chia sẻ. Chúc bạn mọi chuyện nhẹ nhàng hơn nhé 🌿",
            "Thương {ten}. Mong bạn sớm qua những ngày mệt này 🙏",
        ],
        "hoi": [
            "Câu hỏi hay quá {ten}! Ai biết thì chia sẻ giúp bạn ấy với nhé 😊",
            "Cảm ơn {ten} đã hỏi. Mọi người dùng rồi thấy sao thì góp ý cho {ten} nha 😊",
        ],
        "hoi_mua": [
            "Chào {ten}, link các món trong video Trang để ở bình luận phía dưới nhé 👇",
            "{ten} kéo xem bình luận của Trang, có link và giá mới nhất nha 👇",
        ],
    }


MAU_SUC_KHOE = {                       # Trang 5: nhe nhang, KHONG noi chua benh
    "khen": [
        "Cảm ơn {ten}. Mỗi ngày giãn cơ vài phút, cơ thể sẽ nhẹ hơn nhiều 🌿",
        "Cảm ơn {ten} đã xem. Nhớ tập nhẹ nhàng, vừa sức mình thôi nhé.",
        "{ten} lưu lại tập dần nha. Đều đặn mỗi ngày mới thấy khác 🌿",
        "Cảm ơn {ten}. Chúc bạn và gia đình luôn khoẻ 🙏",
    ],
    "tam_su": [
        "Cảm ơn {ten} đã chia sẻ. Mong bạn sớm khoẻ lại, nhớ nghỉ ngơi đầy đủ nhé 🙏",
        "Thương {ten}. Chăm mình một chút mỗi ngày, rồi mọi thứ sẽ nhẹ dần 🌿",
    ],
    "hoi_benh": [
        "{ten} có bệnh nền hay đau nhiều thì nên hỏi bác sĩ trước khi tập nhé. Chúc bạn mau khoẻ 🙏",
        "Mỗi người một thể trạng, {ten} nên hỏi bác sĩ xem có hợp với mình không nhé. Tập thấy đau thì dừng lại ngay ạ.",
        "Đau nhức kéo dài thì {ten} nên đi khám để bác sĩ xem kỹ nhé. Video chỉ là động tác thư giãn nhẹ thôi ạ 🙏",
    ],
    "hoi_mua": [
        "Chào {ten}, link dụng cụ trong video Trang để ở bình luận phía dưới nhé 👇",
        "{ten} kéo xem bình luận của Trang, có link và giá mới nhất nha 👇",
    ],
}

# Tu hoi mua: Trang 1, 2 chi tu RO (tranh "gia tri", "hanh phuc o dau" bi hieu la hoi mua)
MUA_CHAT = ["link", "mua ở", "mua o", "mua ở đâu", "giá bao", "gia bao", "bao nhiêu tiền", "bao nhieu tien", "shop",
            "đặt hàng", "dat hang", "ship", "chốt đơn", "inbox giá", "ib giá"]
MUA_RONG = MUA_CHAT + ["giá", "bao nhiêu", "bao nhieu", "ở đâu", "o dau", "mua", "tên gì", "ten gi", "tên sản phẩm",
                       "xin tên", "xin link", "đặt", "order"]

CAU_HINH = {
    "1": {"ten": "Ngẫm Đời Mà Sống", "mau": MAU_THONG_DIEP, "tu_mua": MUA_CHAT, "can_link": True},
    "2": {"ten": "Sống Chậm Nghĩ Sâu", "mau": MAU_THONG_DIEP, "tu_mua": MUA_CHAT, "can_link": True},
    "3": {"ten": "Bếp Nhà Mẹo Hay", "mau": _do_dung("mẹo bếp"), "tu_mua": MUA_RONG},
    "4": {"ten": "Đồ Gia dụng và các mẹo hay", "mau": _do_dung("mẹo gọn nhà"), "tu_mua": MUA_RONG},
    "5": {"ten": "Sức khỏe Là Tất cả", "mau": MAU_SUC_KHOE, "tu_mua": MUA_RONG, "benh": True},
}

TU_NHAY_CAM = ["lừa đảo", "lua dao", "scam", "khiếu nại", "khieu nai", "hoàn tiền", "hoan tien", "bom hàng", "bom hang",
               "tố cáo", "to cao", "hàng giả", "hang gia", "không nhận được", "khong nhan duoc", "báo cáo", "bao cao"]
TU_TAM_SU = ["buồn", "khóc", "mệt", "cô đơn", "tủi", "áp lực", "chán", "bế tắc", "thất bại", "nợ nần", "mất việc",
             "ly hôn", "đau lòng", "tổn thương", "một mình", "tâm trạng", "tâm sự", "giống mình", "giống em", "như mình",
             "hoàn cảnh", "nhớ mẹ", "nhớ bố", "nhớ nhà", "xa quê", "vất vả", "khổ"]
TU_HOI = ["?", "tại sao", "vì sao", "làm sao", "thế nào", "như nào", "được không", "có nên", "không ạ", "ko ạ", "là gì"]
TU_BENH = ["đau", "bệnh", "thoát vị", "thoái hóa", "thoái hoá", "huyết áp", "tiểu đường", "chữa", "khỏi", "bác sĩ",
           "uống thuốc", "tê", "nhức", "viêm", "gai cột sống", "bầu", "mang thai", "mổ", "chấn thương"]


# ---------------------------------------------------------------- cau hinh / trang thai
def _local():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


LOCAL = _local()


def secret(env, key):
    """Ma lay tu bien moi truong (GitHub), SECRETS_JSON (moi secret, Trang 3+) hoac config.local.json (may)."""
    v = os.environ.get(env, "")
    if not v:
        try:
            v = json.loads(os.environ.get("SECRETS_JSON") or "{}").get(env, "")
        except ValueError:
            v = ""
    return (v or str(LOCAL.get(key, ""))).strip()


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
            hint = " (ma Trang het han/sai -> chay lai nhap_facebook_nhieu_trang.bat)"
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


def _co(m, tu):
    """Co tu nao trong danh sach khong (tu 1 chu thi phai dung nguyen chu, tranh 'mua' khop 'mùa')."""
    for t in tu:
        if " " in t or not t.isalpha():
            if t in m:
                return True
        elif re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", m):
            return True
    return False


def loai(msg, ch=None):
    """'bo_qua' (rong/spam/link) | 'nhay_cam' | 'hoi_mua' | 'hoi_benh' | 'tim' | 'tam_su' | 'hoi' | 'khen'"""
    ch = ch or CAU_HINH["1"]
    m = (msg or "").strip().lower()
    if not m or (m.startswith("@") and len(m.split()) <= 2):
        return "bo_qua"                      # sticker/anh khong chu, hoac chi tag ban be
    if "http" in m or "www." in m or ".com" in m:
        return "bo_qua"                      # link la, nghi spam -> khong dap lai
    if not any(x.isalpha() for x in m):
        return "tim"                         # chi tha tim / bieu tuong / dau cham
    if len(m) < 2:
        return "bo_qua"
    if _co(m, TU_NHAY_CAM):
        return "nhay_cam"
    if _co(m.replace("giá trị", ""), ch["tu_mua"]):
        return "hoi_mua"
    if ch.get("benh") and (_co(m, TU_BENH) or _co(m, TU_HOI)):
        return "hoi_benh"                    # Trang suc khoe: hoi gi cung khuyen vua suc + hoi bac si
    if _co(m, TU_TAM_SU) or len(m.split()) >= 25:
        return "tam_su"
    if _co(m, TU_HOI):
        return "hoi"
    return "khen"


def chon_mau(kieu, ten, link, truoc, ch=None):
    ch = ch or CAU_HINH["1"]
    bo = ch["mau"]
    if kieu == "hoi_mua" and ch.get("can_link") and not link:
        kieu = "hoi"
    mau = bo.get(kieu) or (bo.get("khen") if kieu == "tim" else None) or bo.get("hoi") or bo["khen"]
    rong = [m for m in mau if m != truoc] or mau          # khong lap mau vua dung
    m = random.choice(rong)
    return m, m.format(ten=ten, link=link)


# ---------------------------------------------------------------- main
def main():
    dry = os.environ.get("DRY_RUN") == "1"
    trang = (os.environ.get("TRANG") or "1").strip()
    if trang not in CAU_HINH:
        sys.exit(f"TRANG={trang} chua co bo mau trong CAU_HINH")
    ch = CAU_HINH[trang]
    sfx = "" if trang == "1" else trang
    page = secret(f"FB_PAGE{sfx}_ID", f"fb_page{sfx}_id")
    token = secret(f"FB_PAGE{sfx}_TOKEN", f"fb_page{sfx}_token")
    if not (page and token):
        if trang in ("1", "2"):
            sys.exit(f"Thieu FB_PAGE{sfx}_ID / FB_PAGE{sfx}_TOKEN (hoac fb_page{sfx}_id / fb_page{sfx}_token trong config.local.json)")
        print(f"Trang {trang}: chua co ma FB_PAGE{sfx}_* -> bo qua.")
        return
    link = secret("KENH_LINK", "kenh_link")
    # SO_BAI 25: moi Trang ~10 bai/ngay (deal + video + anh) -> 5 bai chi phu nua ngay, binh luan bai hom qua bi bo sot
    toi_da, so_bai, tran_ngay, cho_phut = num("MAX", 8), num("SO_BAI", 25), num("TRAN_NGAY", 40), num("CHO_PHUT", 10)

    now = datetime.datetime.now(VN)
    if os.environ.get("NGAY") != "1" and not 7 <= now.hour < 23:
        print(f"{now:%H:%M}: ngoai gio tra loi (7h-23h) -> bo qua.")
        return

    st = load_state()
    sub = st if trang == "1" else st.setdefault(f"trang{trang}", {})   # trang thai rieng moi Trang
    xong = dict.fromkeys(sub.setdefault("da_xu_ly", []))          # dict giu thu tu -> cat bot thi bo cai cu nhat
    hom_nay = now.strftime("%Y-%m-%d")
    dem = sub.get("hom_nay") or {}
    if dem.get("ngay") != hom_nay:
        dem = {"ngay": hom_nay, "so": 0}
    con_lai = min(toi_da, tran_ngay - dem["so"])
    print(f"Trang {trang} ({ch['ten']}): hom nay da tra loi {dem['so']}/{tran_ngay}, luot nay toi da {max(con_lai, 0)}")

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

    da, truoc, that_bai, last_err = 0, sub.get("mau_truoc", ""), 0, None
    for c in cho_xu_ly:
        cid, msg = c["id"], c.get("message", "")
        kieu = loai(msg, ch)
        if kieu in ("bo_qua", "nhay_cam"):
            print(f"  Khong tra loi ({kieu}): {msg[:60]!r}")
            if kieu == "nhay_cam" and not dry:
                tg_alert(f"⚠️ Binh luan can anh tu xu ly (Trang {trang} - {ch['ten']}):\n{msg[:300]}\nhttps://www.facebook.com/{cid}")
            if not dry:
                xong[cid] = None
            continue
        if da >= con_lai:
            continue                                       # het suat luot nay, de lan sau
        mau, text = chon_mau(kieu, ten_goi(c), link, truoc, ch)
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
