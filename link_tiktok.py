# -*- coding: utf-8 -*-
"""Mo link cong khai (chi XEM, 'bat ky ai co link') cho video TikTok de Metricool tai ve dang.
Drive: 'Trang Facebook/TikTok sopgiadung33/Video chờ đăng' (service account GOOGLE_SA_JSON co quyen Editor).
  python link_tiktok.py mo 1.mp4 2.mp4     -> mo chia se, in link tai thang
  python link_tiktok.py dong 1.mp4         -> tat chia se cong khai (sau khi Metricool da dang)
  python link_tiktok.py ds                 -> liet ke video cho dang + dong tieu de
"""
import os
import sys

import requests

import dang_trang as dt

GOC = "TikTok sopgiadung33"


def folder(drive):
    goc = drive.child(drive.root(), GOC, folder=True)["id"]
    return goc, drive.child(goc, "Video chờ đăng", folder=True)["id"]


def main():
    cmd, names = (sys.argv[1] if len(sys.argv) > 1 else "ds"), sys.argv[2:]
    drive = dt.Drive(os.environ["GOOGLE_SA_JSON"])
    goc, cho = folder(drive)
    files = drive.ls(f"'{cho}' in parents and mimeType!='{dt.FOLDER}'", "id,name,size")
    if cmd == "ds":
        tieu_de = dt.titles(drive.text(drive.child(goc, "tieu_de_tiktok.txt", folder=False)["id"]))
        for f in sorted(files, key=lambda x: x["name"]):
            print(f["name"], int(f.get("size", 0)) // 1048576, "MB")
        print("Tieu de:", tieu_de)
        return
    for f in files:
        if f["name"] not in names:
            continue
        url = f"{dt.DRIVE}/{f['id']}/permissions"
        if cmd == "mo":
            r = requests.post(url, headers=drive._h(), params={"supportsAllDrives": "true"},
                              json={"type": "anyone", "role": "reader"}, timeout=60)
            r.raise_for_status()
            print(f"LINK {f['name']} https://drive.usercontent.google.com/download?id={f['id']}&export=download&confirm=t")
        else:
            r = requests.get(url, headers=drive._h(), params={"supportsAllDrives": "true"}, timeout=60)
            for p in r.json().get("permissions", []):
                if p.get("type") == "anyone":
                    requests.delete(f"{url}/{p['id']}", headers=drive._h(), params={"supportsAllDrives": "true"}, timeout=60)
            print("DA TAT chia se", f["name"])


if __name__ == "__main__":
    main()
