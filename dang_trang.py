# -*- coding: utf-8 -*-
"""Dang video / anh hai len Trang Facebook, lay tu Google Drive (thay kich ban Make 8074072).

Drive (dulieuhoangsythb3): thu muc "Trang Facebook" chia se cho service account (GOOGLE_SA_JSON), ben trong:
  Video Trang Facebook/{Video chờ đăng, Video đã đăng, tieu_de.txt}
  Ảnh Trang Facebook/{Ảnh chờ đăng, Ảnh đã đăng, tieu_de_anh.txt}
Moi lan chay dang 1 file SO NHO NHAT co dong tieu de `so | tieu de` -> chuyen sang thu muc "da dang".
Video doc (cao > rong) <= 90 giay -> Reels, con lai -> video thuong. Anh -> /photos.

27/10 TU DAT SO: anh bo file ten gi cung duoc vao thu muc cho -> bot (`tu_dat_so`) dat so tiep sau so lon nhat, Gemini xem
video/anh viet tieu de, ghi them dong vao tieu_de*.txt. Ten trung file bot da dang / 2 file cung so -> doi so moi;
giong HET file da dang (md5) -> bo qua.

Bien moi truong: KIEU=video|anh, GOOGLE_SA_JSON, FB_PAGE_ID, FB_PAGE_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GEMINI_API_KEY,
  DRY_RUN=1 (chi in ra se dang gi), AN=1 (dang bai an roi xoa ngay, khong chuyen file, khong ghi trang thai).
"""
import base64
import json
import os
import re
import sys
import tempfile
import time
import unicodedata

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

FB_API = "https://graph.facebook.com/v21.0"
FB_VIDEO_API = "https://graph-video.facebook.com/v21.0"
DRIVE = "https://www.googleapis.com/drive/v3/files"
FOLDER = "application/vnd.google-apps.folder"
FOOTER = "👉 Theo dõi Trang để giải trí mỗi ngày nhé!"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dang_trang.json")
KIEU = {
    "video": {"goc": "Video Trang Facebook", "cho": "Video chờ đăng", "xong": "Video đã đăng", "tieu_de": "tieu_de.txt"},
    "anh": {"goc": "Ảnh Trang Facebook", "cho": "Ảnh chờ đăng", "xong": "Ảnh đã đăng", "tieu_de": "tieu_de_anh.txt"},
}


def nfc(s):
    """Ten tieng Viet tren Drive co the la dang dung san hoac to hop -> chuan hoa truoc khi so."""
    return unicodedata.normalize("NFC", s or "").strip().lower()


# ---------------------------------------------------------------- Google Drive
class Drive:
    def __init__(self, sa_json):
        info = json.loads(sa_json)
        self.cred = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive"])

    def _h(self):
        if not self.cred.valid:
            self.cred.refresh(Request())
        return {"Authorization": f"Bearer {self.cred.token}"}

    def ls(self, q, fields="id,name,mimeType,parents"):
        out, token = [], None
        while True:
            p = {"q": q + " and trashed=false", "fields": f"nextPageToken,files({fields})", "pageSize": 1000,
                 "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
            if token:
                p["pageToken"] = token
            r = requests.get(DRIVE, headers=self._h(), params=p, timeout=60)
            r.raise_for_status()
            j = r.json()
            out += j.get("files", [])
            token = j.get("nextPageToken")
            if not token:
                return out

    def child(self, parent, name, folder=None):
        for f in self.ls(f"'{parent}' in parents"):
            if nfc(f["name"]) == nfc(name) and (folder is None or (f["mimeType"] == FOLDER) == folder):
                return f
        raise RuntimeError(f"Khong thay '{name}' tren Drive (da chia se thu muc 'Trang Facebook' cho bot chua?)")

    def root(self):
        for f in self.ls(f"mimeType='{FOLDER}'"):
            if nfc(f["name"]) == nfc("Trang Facebook"):
                return f["id"]
        raise RuntimeError("Bot khong thay thu muc 'Trang Facebook' -> chia se thu muc nay cho email service account (Editor)")

    def text(self, fid):
        r = requests.get(f"{DRIVE}/{fid}", headers=self._h(), params={"alt": "media"}, timeout=60)
        r.raise_for_status()
        return r.content.decode("utf-8-sig", "ignore")

    def download(self, fid, path):
        with requests.get(f"{DRIVE}/{fid}", headers=self._h(), params={"alt": "media"}, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(path, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)

    def move(self, fid, old_parent, new_parent):
        r = requests.patch(f"{DRIVE}/{fid}", headers=self._h(), timeout=60,
                           params={"addParents": new_parent, "removeParents": old_parent, "supportsAllDrives": "true"})
        r.raise_for_status()

    def rename(self, fid, name):
        r = requests.patch(f"{DRIVE}/{fid}", headers=self._h(), json={"name": name}, timeout=60,
                           params={"supportsAllDrives": "true"})
        r.raise_for_status()

    def write_text(self, fid, text):
        r = requests.patch(f"https://www.googleapis.com/upload/drive/v3/files/{fid}", headers=self._h(), timeout=60,
                           params={"uploadType": "media", "supportsAllDrives": "true"}, data=text.encode("utf-8"))
        r.raise_for_status()


# ---------------------------------------------------------------- Facebook
def fb_check(r):
    if r.status_code >= 400:
        hint = " (ma Trang het han/sai)" if '"code":190' in r.text else ""
        raise RuntimeError(f"Facebook loi {r.status_code}{hint}: {r.text[:300]}")
    return r.json()


def fb_photo(page, token, path, caption, published=True):
    with open(path, "rb") as fh:
        r = requests.post(f"{FB_API}/{page}/photos", timeout=300, files={"source": (os.path.basename(path), fh)},
                          data={"caption": caption, "published": str(published).lower(), "access_token": token})
    return fb_check(r).get("id")


def fb_video(page, token, path, caption, published=True):
    """Gui tung khuc (resumable): 27/10 video 102MB gui 1 lan bi Facebook tu choi 413 -> Trang 1 ket 4 luot."""
    url, size = f"{FB_VIDEO_API}/{page}/videos", os.path.getsize(path)
    s = fb_check(requests.post(url, timeout=60, data={"upload_phase": "start", "file_size": size, "access_token": token}))
    vid, sess, start, end = s.get("video_id"), s["upload_session_id"], int(s["start_offset"]), int(s["end_offset"])
    with open(path, "rb") as fh:
        while start < end:
            fh.seek(start)
            chunk = fh.read(end - start)
            for lan in range(3):
                try:
                    s = fb_check(requests.post(url, timeout=600, files={"video_file_chunk": ("chunk", chunk)}, data={
                        "upload_phase": "transfer", "upload_session_id": sess, "start_offset": start, "access_token": token}))
                    break
                except Exception as e:
                    if lan == 2:
                        raise
                    print(f"  Gui khuc {start // 1048576}MB loi, thu lai: {str(e)[:120]}")
                    time.sleep(10)
            start, end = int(s["start_offset"]), int(s["end_offset"])
    fb_check(requests.post(url, timeout=300, data={"upload_phase": "finish", "upload_session_id": sess, "description": caption,
                                                   "published": str(published).lower(), "access_token": token}))
    return vid


def fb_reel(page, token, path, caption, published=True):
    vid = fb_check(requests.post(f"{FB_API}/{page}/video_reels", timeout=60,
                                 data={"upload_phase": "start", "access_token": token}))["video_id"]
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        r = requests.post(f"https://rupload.facebook.com/video-upload/v21.0/{vid}", data=fh, timeout=1800,
                          headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})
    fb_check(r)
    fb_check(requests.post(f"{FB_API}/{page}/video_reels", timeout=60, data={
        "upload_phase": "finish", "video_id": vid, "description": caption, "access_token": token,
        "video_state": "PUBLISHED" if published else "DRAFT"}))
    return vid


def fb_delete(oid, token):
    fb_check(requests.delete(f"{FB_API}/{oid}", params={"access_token": token}, timeout=60))


def tg_alert(text):
    bot, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if bot and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{bot}/sendMessage", data={"chat_id": chat, "text": text}, timeout=30)
        except Exception as e:
            print("Gui canh bao Telegram loi:", e)


# ---------------------------------------------------------------- chon file
SO_RE = re.compile(r"\s*(\d{1,3})(?!\d)")   # so thu tu toi da 3 chu so: ten kieu ngay `261028_1025_07_...` (tab 7), `1027 (1).mp4` KHONG phai so thu tu (30/10)


def so_dau(name):
    m = SO_RE.match(name or "")
    return int(m.group(1)) if m else None


def titles(txt):
    """Dong `so | tieu de` -> {so: tieu de}."""
    out = {}
    for line in txt.splitlines():
        m = re.match(r"\s*(\d{1,3})\s*\|\s*(.+)", line)
        if m and m.group(2).strip():
            out[int(m.group(1))] = m.group(2).strip()
    return out


def pick(files, tieu_de, done, bo=()):
    """File so nho nhat (so dau ten: 7.jpg -> 7, 1_16x9.mp4 -> 1) co dong tieu de, chua tung dang, khong nam trong `bo`."""
    ok = []
    for f in files:
        n = so_dau(f["name"])
        if n is not None and n in tieu_de and f["name"] not in done and f["name"] not in bo:
            ok.append((n, f))
    skipped = [f["name"] for f in files if so_dau(f["name"]) not in tieu_de]
    if skipped:
        print("  Bo qua (khong co so / chua co dong tieu de):", ", ".join(skipped[:10]))
    return min(ok, key=lambda x: x[0]) if ok else None


# ---------------------------------------------------------------- tu dat so + AI viet tieu de (27/10)
GEMINI = "https://generativelanguage.googleapis.com"
GEMINI_MODELS = ["gemini-3.5-flash", "gemini-flash-latest", "gemini-3.7-flash", "gemini-flash-lite-latest"]
CO_DAU = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.I)


def gemini_upload(key, path, mime):
    """Files API (video lon): tra (file_name, file_uri) khi Google xu ly xong."""
    size = os.path.getsize(path)
    r = requests.post(f"{GEMINI}/upload/v1beta/files?key={key}", timeout=60, json={"file": {"display_name": os.path.basename(path)}},
                      headers={"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
                               "X-Goog-Upload-Header-Content-Length": str(size), "X-Goog-Upload-Header-Content-Type": mime})
    r.raise_for_status()
    with open(path, "rb") as fh:
        r = requests.post(r.headers["X-Goog-Upload-URL"], data=fh, timeout=900,
                          headers={"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"})
    r.raise_for_status()
    f = r.json()["file"]
    for _ in range(60):
        if f.get("state") != "PROCESSING":
            break
        time.sleep(5)
        f = requests.get(f"{GEMINI}/v1beta/{f['name']}?key={key}", timeout=60).json()
    if f.get("state") != "ACTIVE":
        raise RuntimeError(f"Gemini khong xu ly duoc file: {f.get('state')}")
    return f["name"], f["uri"]


def ai_tieu_de(path, kieu, mau):
    """Gemini xem video / anh -> 1 dong tieu de giong kieu cac dong mau. Loi / khong khoa -> None (de lan sau)."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("  Chua co GEMINI_API_KEY -> chua viet tieu de duoc")
        return None
    ext = os.path.splitext(path)[1].lower()
    if kieu == "video":
        mime = {".mov": "video/quicktime", ".webm": "video/webm", ".avi": "video/x-msvideo"}.get(ext, "video/mp4")
        fname, uri = gemini_upload(key, path, mime)
        media = {"file_data": {"mime_type": mime, "file_uri": uri}}
    else:
        fname = None
        mime = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
        with open(path, "rb") as fh:
            media = {"inline_data": {"mime_type": mime, "data": base64.b64encode(fh.read()).decode()}}
    loai = "video hài ngắn" if kieu == "video" else "ảnh hài"
    prompt = (f"Đây là 1 {loai} sắp đăng lên Trang Facebook giải trí Việt Nam. Xem kỹ (nghe cả lời thoại nếu có) rồi viết 1 dòng "
              "tiêu đề tiếng Việt CÓ DẤU, 10–22 chữ, gây tò mò, ĐÚNG nội dung (không bịa chi tiết không có), không tục tĩu, không "
              "giật tít sai sự thật, hợp chuẩn cộng đồng Facebook; thêm 1 emoji hợp nội dung và 2–3 hashtag không dấu, cuối cùng là "
              "#haihuoc #giaitri. Không dùng dấu |. Viết theo đúng kiểu các dòng mẫu sau:\n" + "\n".join(mau) +
              '\nTrả JSON {"tieu_de": "..."}')
    body = {"contents": [{"parts": [media, {"text": prompt}]}], "generationConfig": {
        "temperature": 0.8, "responseMimeType": "application/json",
        "responseSchema": {"type": "OBJECT", "properties": {"tieu_de": {"type": "STRING"}}, "required": ["tieu_de"]}}}
    try:
        for model in GEMINI_MODELS:
            try:
                r = requests.post(f"{GEMINI}/v1beta/models/{model}:generateContent?key={key}", json=body, timeout=180)
                r.raise_for_status()
                t = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])["tieu_de"]
            except Exception as e:
                print(f"  [AI tieu de] {model} loi: {str(e)[:120].replace(key, '***')}")
                continue
            t = " ".join(str(t).replace("|", "-").split())
            t = re.sub(r"^\d+\s*[-:.]\s*", "", t)                  # AI chep ca so thu tu cua dong mau ("261034 - ...")
            if CO_DAU.search(t) and 15 <= len(t) <= 250:
                print(f"  [AI tieu de] {model}: {t}")
                return t
            print(f"  [AI tieu de] {model} viet khong dat: {t[:80]!r}")
        return None
    finally:
        if fname:
            try:
                requests.delete(f"{GEMINI}/v1beta/{fname}?key={key}", timeout=30)
            except Exception:
                pass


def tu_dat_so(drive, kieu, cho, xong, tdf, txt, done_all, dry, toi_da=3):
    """File trong thu muc cho chua dang duoc vi ten khong co so / trung so file da dang / chua co dong tieu de
    -> AI viet tieu de, ghi them dong `so | tieu de` vao tieu_de*.txt, doi ten file sang so do. Tra (so file da lo, ten file bo qua)."""
    files = drive.ls(f"'{cho}' in parents and mimeType!='{FOLDER}'", "id,name,md5Checksum,createdTime")
    da_dang = drive.ls(f"'{xong}' in parents and mimeType!='{FOLDER}'", "id,name,md5Checksum")
    tieu_de = titles(txt)
    md5_xong = {f.get("md5Checksum") for f in da_dang if f.get("md5Checksum")}
    so_xong = {so_dau(f["name"]) for f in da_dang} - {None}
    dung = set(tieu_de) | so_xong | ({so_dau(f["name"]) for f in files} - {None})
    bo, can, thay = set(), [], set()
    for f in sorted(files, key=lambda f: f.get("createdTime", "")):
        n = so_dau(f["name"])
        if f.get("md5Checksum") in md5_xong:
            bo.add(f["name"])                                  # ban chep y het video da dang -> khong dang lai
            print(f"  {f['name']}: GIONG HET 1 file da dang -> bo qua (anh xoa giup)")
            continue
        # KHONG coi trung so voi thu muc da dang: 25/10 anh thay kho moi dung lai so 1-75 (da dang con 49_16x9 cu)
        trung = n is not None and (f["name"] in done_all or n in thay)
        if n is not None and not trung and n in tieu_de:
            thay.add(n)
            continue                                           # binh thuong: co so, co tieu de
        can.append((f, None if (n is None or trung) else n))   # None = can so moi; co so = giu so, chi them tieu de
        if n is not None and not trung:
            thay.add(n)
    if not can:
        return 0, bo
    print(f"Tu dat so: {len(can)} file can lo ({', '.join(f['name'] for f, _ in can[:8])}), luot nay lam toi da {toi_da}")
    lo, mau = 0, [ln for ln in txt.splitlines() if re.match(r"\s*\d{1,3}\s*\|", ln)][-6:]
    for f, n in can[:toi_da]:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "f" + os.path.splitext(f["name"])[1].lower())
            try:
                drive.download(f["id"], path)
                t = ai_tieu_de(path, kieu, mau)
            except Exception as e:
                print(f"  {f['name']}: AI viet tieu de loi ({str(e)[:120]}) -> de lan sau")
                continue
        if not t:
            continue
        ten_moi = f["name"]
        if n is None:
            n = max(dung | {0}) + 1
            ten_moi = f"{n}{os.path.splitext(f['name'])[1].lower()}"
        dung.add(n)
        print(f"  {f['name']} -> {ten_moi} | {t}")
        if dry:
            continue
        txt = txt.rstrip("\r\n") + f"\n{n} | {t}\n"
        drive.write_text(tdf, txt)                              # ghi dong tieu de TRUOC roi moi doi ten file
        if ten_moi != f["name"]:
            drive.rename(f["id"], ten_moi)
        lo += 1
    return lo, bo


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(st):
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False, indent=1)


def main():
    kieu = (os.environ.get("KIEU") or "").strip().lower()
    if kieu not in KIEU:
        sys.exit("Thieu KIEU=video hoac KIEU=anh")
    dry, an = os.environ.get("DRY_RUN") == "1", os.environ.get("AN") == "1"
    # 25/10 Trang thu 2 "Cuoi Moi Ngay Sale Hoi" (anh muon 2 Trang noi dung KHAC nhau): chung kho Drive,
    # Trang 1 chi dang file SO LE, Trang 2 chi dang SO CHAN -> khong bao gio trung. TRANG=2 dung FB_PAGE2_*.
    trang = (os.environ.get("TRANG") or "1").strip()
    sfx = "2" if trang == "2" else ""
    page, token = os.environ.get(f"FB_PAGE{sfx}_ID", ""), os.environ.get(f"FB_PAGE{sfx}_TOKEN", "")
    sa = os.environ.get("GOOGLE_SA_JSON", "")
    if not sa or (not dry and not (page and token)):
        sys.exit(f"Thieu GOOGLE_SA_JSON / FB_PAGE{sfx}_ID / FB_PAGE{sfx}_TOKEN")
    k = KIEU[kieu]
    st = load_state()
    sub = st.setdefault("trang2", {}) if trang == "2" else st     # trang thai rieng moi Trang
    done = sub.setdefault("da_dang", {}).setdefault(kieu, [])
    chan = 0 if trang == "2" else 1                               # so du khi chia 2: Trang 2 so chan, Trang 1 so le
    print(f"Trang {trang}: chi dang file so {'chan' if chan == 0 else 'le'}")

    drive = Drive(sa)
    goc = drive.child(drive.root(), k["goc"], folder=True)["id"]
    cho = drive.child(goc, k["cho"], folder=True)["id"]
    xong = drive.child(goc, k["xong"], folder=True)["id"]
    tdf = drive.child(goc, k["tieu_de"], folder=False)["id"]
    txt = drive.text(tdf)
    bo = {ten for ten, lan in sub.get("loi_file", {}).get(kieu, {}).items() if lan >= 3}   # file loi 3 lan -> bo qua
    if not an:
        done_all = set(st.get("da_dang", {}).get(kieu, [])) | set(st.get("trang2", {}).get("da_dang", {}).get(kieu, []))
        try:
            lo, trung = tu_dat_so(drive, kieu, cho, xong, tdf, txt, done_all, dry)
            bo |= trung
            if lo:
                txt = drive.text(tdf)
        except Exception as e:                  # loi phan tu dat so khong duoc lam hong viec dang
            print("Tu dat so loi:", str(e)[:300])
    tieu_de = titles(txt)
    files = drive.ls(f"'{cho}' in parents and mimeType!='{FOLDER}'", "id,name,size,mimeType,videoMediaMetadata")
    print(f"{k['cho']}: {len(files)} file, {len(tieu_de)} dong tieu de")
    files = [f for f in files if so_dau(f["name"]) is None or so_dau(f["name"]) % 2 == chan]
    if bo:
        print("  Bo qua (trung / loi nhieu lan):", ", ".join(sorted(bo)))
    got = pick(files, tieu_de, done, bo)
    if not got:
        print("Khong co file nao du dieu kien -> bo qua lan nay.")
        return
    so, f = got
    caption = f"{tieu_de[so]}\n\n{FOOTER}"
    meta = f.get("videoMediaMetadata") or {}
    w, h, dur = int(meta.get("width", 0)), int(meta.get("height", 0)), int(meta.get("durationMillis", 0)) / 1000
    cach = "anh" if kieu == "anh" else ("reels" if h > w and 0 < dur <= 90 else "video")
    print(f"Chon: {f['name']} ({int(f.get('size', 0)) // 1048576}MB, {w}x{h}, {dur:.0f}s) -> dang {cach}")
    print("Chu thich:", caption.replace("\n", " / "))
    if dry:
        print("DRY_RUN: khong dang.")
        return

    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, f["name"])
            drive.download(f["id"], path)
            post = {"anh": fb_photo, "reels": fb_reel, "video": fb_video}[cach]
            oid = post(page, token, path, caption, published=not an)
        print("Da dang, id:", oid)
    except Exception as e:
        print("LOI:", e)
        if not an:
            sub["loi_lien_tiep"] = sub.get("loi_lien_tiep", 0) + 1
            lf = sub.setdefault("loi_file", {}).setdefault(kieu, {})
            lf[f["name"]] = lf.get(f["name"], 0) + 1
            if lf[f["name"]] == 3:                  # 1 file hong khong duoc chan ca hang cho (26-27/10 ket 4 luot vi 11.mp4)
                tg_alert(f"⚠️ Trang Facebook {trang}: file {f['name']} dang loi 3 lan -> bot BO QUA file nay, dang file khac. "
                         f"Loi: {str(e)[:200]}")
            elif sub["loi_lien_tiep"] == 3:
                tg_alert(f"⚠️ Bot dang Trang Facebook {trang} loi 3 lan lien tiep ({kieu}): {str(e)[:300]}")
            save_state(st)
        raise

    if an:
        time.sleep(5)
        try:
            fb_delete(oid, token)
            print("Bai thu an da xoa.")
        except Exception as e:
            print("Xoa bai thu loi (vao Trang xoa tay):", e)
        return

    sub["loi_lien_tiep"] = 0
    sub.get("loi_file", {}).get(kieu, {}).pop(f["name"], None)
    done.append(f["name"])
    try:
        drive.move(f["id"], cho, xong)
        print(f"Da chuyen sang '{k['xong']}'.")
    except Exception as e:                      # khong chuyen duoc van khong dang lai nho danh sach da_dang
        print("Chuyen file loi (van ghi nho da dang):", e)
    save_state(st)


if __name__ == "__main__":
    main()
