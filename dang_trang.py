# -*- coding: utf-8 -*-
"""Dang video / anh hai len Trang Facebook, lay tu Google Drive (thay kich ban Make 8074072).

Drive (dulieuhoangsythb3): thu muc "Trang Facebook" chia se cho service account (GOOGLE_SA_JSON), ben trong:
  Video Trang Facebook/{Video chờ đăng, Video đã đăng, tieu_de.txt}
  Ảnh Trang Facebook/{Ảnh chờ đăng, Ảnh đã đăng, tieu_de_anh.txt}
Moi lan chay dang 1 file SO NHO NHAT co dong tieu de `so | tieu de` -> chuyen sang thu muc "da dang".
Video doc (cao > rong) <= 90 giay -> Reels, con lai -> video thuong. Anh -> /photos.

Bien moi truong: KIEU=video|anh, GOOGLE_SA_JSON, FB_PAGE_ID, FB_PAGE_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
  DRY_RUN=1 (chi in ra se dang gi), AN=1 (dang bai an roi xoa ngay, khong chuyen file, khong ghi trang thai).
"""
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
    with open(path, "rb") as fh:
        r = requests.post(f"{FB_VIDEO_API}/{page}/videos", timeout=1800, files={"source": (os.path.basename(path), fh)},
                          data={"description": caption, "published": str(published).lower(), "access_token": token})
    return fb_check(r).get("id")


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
def titles(txt):
    """Dong `so | tieu de` -> {so: tieu de}."""
    out = {}
    for line in txt.splitlines():
        m = re.match(r"\s*(\d+)\s*\|\s*(.+)", line)
        if m and m.group(2).strip():
            out[int(m.group(1))] = m.group(2).strip()
    return out


def pick(files, tieu_de, done):
    """File so nho nhat (so dau ten: 7.jpg -> 7, 1_16x9.mp4 -> 1) co dong tieu de, chua tung dang."""
    ok = []
    for f in files:
        m = re.match(r"(\d+)", f["name"])
        if m and int(m.group(1)) in tieu_de and f["name"] not in done:
            ok.append((int(m.group(1)), f))
    skipped = [f["name"] for f in files if not re.match(r"\d+", f["name"]) or int(re.match(r"\d+", f["name"]).group()) not in tieu_de]
    if skipped:
        print("  Bo qua (khong co so / chua co dong tieu de):", ", ".join(skipped[:10]))
    return min(ok, key=lambda x: x[0]) if ok else None


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
    page, token = os.environ.get("FB_PAGE_ID", ""), os.environ.get("FB_PAGE_TOKEN", "")
    sa = os.environ.get("GOOGLE_SA_JSON", "")
    if not sa or (not dry and not (page and token)):
        sys.exit("Thieu GOOGLE_SA_JSON / FB_PAGE_ID / FB_PAGE_TOKEN")
    k = KIEU[kieu]
    st = load_state()
    done = st.setdefault("da_dang", {}).setdefault(kieu, [])

    drive = Drive(sa)
    goc = drive.child(drive.root(), k["goc"], folder=True)["id"]
    cho = drive.child(goc, k["cho"], folder=True)["id"]
    xong = drive.child(goc, k["xong"], folder=True)["id"]
    tieu_de = titles(drive.text(drive.child(goc, k["tieu_de"], folder=False)["id"]))
    files = drive.ls(f"'{cho}' in parents and mimeType!='{FOLDER}'", "id,name,size,mimeType,videoMediaMetadata")
    print(f"{k['cho']}: {len(files)} file, {len(tieu_de)} dong tieu de")
    got = pick(files, tieu_de, done)
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
            st["loi_lien_tiep"] = st.get("loi_lien_tiep", 0) + 1
            if st["loi_lien_tiep"] == 3:
                tg_alert(f"⚠️ Bot dang Trang Facebook loi 3 lan lien tiep ({kieu}): {str(e)[:300]}")
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

    st["loi_lien_tiep"] = 0
    done.append(f["name"])
    try:
        drive.move(f["id"], cho, xong)
        print(f"Da chuyen sang '{k['xong']}'.")
    except Exception as e:                      # khong chuyen duoc van khong dang lai nho danh sach da_dang
        print("Chuyen file loi (van ghi nho da dang):", e)
    save_state(st)


if __name__ == "__main__":
    main()
