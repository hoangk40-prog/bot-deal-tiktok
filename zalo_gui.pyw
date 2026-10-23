# -*- coding: utf-8 -*-
"""Cua so BOT ZALO (nick phu dang deal vao nhom Zalo). Bam dup file nay de mo.
Moi viec that van do zalo_bot.py lam; cua so nay chi de xem trang thai, sua cai dat va bam nut."""
import json, os, sys, subprocess, threading, traceback
import tkinter as tk
from tkinter import ttk, messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "config.json")
LOCAL_PATH = os.path.join(HERE, "config.local.json")
OUT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", HERE), "zalo_bot")
LOG = os.path.join(OUT_DIR, "nhat_ky_zalo.txt")
TASK = "Bot Zalo dang deal"
PY = sys.executable.replace("pythonw.exe", "python.exe")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
KIEU_LABEL = {"tung_mon": "Từng món (mỗi món 1 ảnh + 1 tin, nghỉ 20–40 giây)", "gop": "Gộp (1 ảnh ghép + 1 tin)"}


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", creationflags=NOWIN)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bot Zalo – nick phụ đăng deal vào nhóm")
        self.geometry("980x720")
        self.busy = False
        cfg, local = read_json(CFG_PATH), read_json(LOCAL_PATH)
        self.v_nhom = tk.StringVar(value=str(local.get("zalo_nhom", "")))
        self.v_gio = tk.StringVar(value=", ".join(str(h) for h in cfg.get("zalo_hours", [9, 12, 17, 20])))
        self.v_items = tk.StringVar(value=str(cfg.get("zalo_items", 3)))
        self.v_kieu = tk.StringVar(value=KIEU_LABEL.get(cfg.get("zalo_kieu", "tung_mon"), KIEU_LABEL["tung_mon"]))
        self.v_login = tk.StringVar(value="Chưa kiểm tra (bấm 'Kiểm tra')")
        self.v_lich = tk.StringVar(value="đang xem...")
        self.v_status = tk.StringVar(value="Sẵn sàng.")
        self.img = None
        self.build()
        self.refresh_task()
        self.refresh_log()
        self.refresh_preview()

    # ------------------------------------------------------------ giao dien
    def build(self):
        top = ttk.LabelFrame(self, text="Trạng thái")
        top.pack(fill="x", padx=8, pady=6)
        ttk.Label(top, text="Nick phụ trên Zalo Web:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Label(top, textvariable=self.v_login, foreground="#1a5fb4").grid(row=0, column=1, sticky="w")
        self.b_check = ttk.Button(top, text="Kiểm tra", command=self.on_check)
        self.b_check.grid(row=0, column=2, padx=4)
        self.b_login = ttk.Button(top, text="🔑 Đăng nhập Zalo (quét QR)", command=self.on_login)
        self.b_login.grid(row=0, column=3, padx=4)
        ttk.Label(top, text="Lịch tự đăng:").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        ttk.Label(top, textvariable=self.v_lich, foreground="#1a5fb4").grid(row=1, column=1, sticky="w")
        ttk.Button(top, text="▶ Bật lịch", command=self.on_task_on).grid(row=1, column=2, padx=4)
        ttk.Button(top, text="⏸ Tắt lịch", command=self.on_task_off).grid(row=1, column=3, padx=4, sticky="w")

        st = ttk.LabelFrame(self, text="Cài đặt")
        st.pack(fill="x", padx=8, pady=6)
        ttk.Label(st, text="Tên nhóm Zalo (đúng từng chữ, có dấu):").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(st, textvariable=self.v_nhom, width=45).grid(row=0, column=1, columnspan=2, sticky="w")
        ttk.Label(st, text="Giờ đăng (cách nhau dấu phẩy):").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(st, textvariable=self.v_gio, width=20).grid(row=1, column=1, sticky="w")
        ttk.Label(st, text="Số món mỗi lần:").grid(row=2, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(st, textvariable=self.v_items, width=6).grid(row=2, column=1, sticky="w")
        ttk.Button(st, text="💾 Lưu cài đặt", command=self.save).grid(row=2, column=2, sticky="w", padx=4)
        ttk.Label(st, text="Kiểu gửi:").grid(row=3, column=0, sticky="w", padx=6, pady=3)
        ttk.Combobox(st, textvariable=self.v_kieu, values=list(KIEU_LABEL.values()), state="readonly",
                     width=48).grid(row=3, column=1, columnspan=2, sticky="w")
        ttk.Label(st, foreground="#666", text="Chống khoá nick: chỉ 1 nhóm của anh, 3–4 lần/ngày, bot tự lệch giờ 0–8 phút; kiểu 'Từng món' "
                  "nên để 3 món/lần. Đổi giờ xong bấm 'Bật lịch' lại để áp dụng.").grid(row=4, column=0, columnspan=4, sticky="w", padx=6, pady=(2, 4))

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8)
        self.b_try = ttk.Button(bar, text="👀 Xem thử (điền tin, KHÔNG gửi)", command=lambda: self.on_post(dry=True))
        self.b_try.pack(side="left", padx=3)
        self.b_post = ttk.Button(bar, text="📤 Đăng ngay 1 lần", command=lambda: self.on_post(dry=False))
        self.b_post.pack(side="left", padx=3)
        ttk.Button(bar, text="📁 Mở thư mục ảnh / nhật ký", command=lambda: os.startfile(OUT_DIR)).pack(side="left", padx=3)
        ttk.Button(bar, text="↻ Làm mới", command=self.refresh_all).pack(side="left", padx=3)
        ttk.Label(self, textvariable=self.v_status, foreground="#1a5fb4").pack(anchor="w", padx=10, pady=4)

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        left = ttk.LabelFrame(body, text="Lần đăng gần nhất (ảnh ghép các món + nội dung tin)")
        right = ttk.LabelFrame(body, text="Nhật ký")
        body.add(left, weight=1)
        body.add(right, weight=1)
        self.lbl_img = ttk.Label(left)
        self.lbl_img.pack(anchor="n", pady=4)
        self.t_msg = tk.Text(left, height=10, wrap="word", font=("Segoe UI", 9))
        self.t_msg.pack(fill="both", expand=True, padx=4, pady=4)
        self.t_log = tk.Text(right, wrap="none", font=("Consolas", 9))
        sb = ttk.Scrollbar(right, command=self.t_log.yview)
        self.t_log.config(yscrollcommand=sb.set)
        self.t_log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    # ------------------------------------------------------------ doc trang thai
    def refresh_all(self):
        self.refresh_task(); self.refresh_log(); self.refresh_preview()

    def refresh_task(self):
        def work():
            code, out = ps(f"$t = Get-ScheduledTask -TaskName '{TASK}' -ErrorAction SilentlyContinue; "
                           "if ($t) { $i = $t | Get-ScheduledTaskInfo; $t.State.ToString() + '|' + $i.LastRunTime + '|' + $i.NextRunTime } else { 'NONE' }")
            out = out.strip()
            if out == "NONE" or not out:
                txt = "❌ CHƯA BẬT"
            else:
                parts = out.split("|")
                state = {"Ready": "✅ ĐANG BẬT", "Running": "✅ ĐANG CHẠY", "Disabled": "⏸ ĐANG TẮT"}.get(parts[0], parts[0])
                nxt = parts[2] if len(parts) > 2 and parts[0] != "Disabled" else ""
                txt = state + (f"  ·  lần tới: {nxt}" if nxt else "")
            self.after(0, lambda: self.v_lich.set(txt))
        threading.Thread(target=work, daemon=True).start()

    def refresh_log(self):
        try:
            with open(LOG, encoding="utf-8") as f:
                lines = f.readlines()[-200:]
        except OSError:
            lines = ["(chưa có nhật ký)\n"]
        self.t_log.delete("1.0", "end")
        self.t_log.insert("1.0", "".join(lines))
        self.t_log.see("end")

    def refresh_preview(self):
        try:
            from PIL import Image, ImageTk
            im = Image.open(os.path.join(OUT_DIR, "anh_ghep.jpg"))
            im.thumbnail((380, 380))
            self.img = ImageTk.PhotoImage(im)
            self.lbl_img.config(image=self.img, text="")
        except Exception:
            self.lbl_img.config(image="", text="(chưa có ảnh ghép)")
        try:
            with open(os.path.join(OUT_DIR, "tin_gop.txt"), encoding="utf-8") as f:
                msg = f.read()
        except OSError:
            msg = ""
        self.t_msg.delete("1.0", "end")
        self.t_msg.insert("1.0", msg)

    # ------------------------------------------------------------ cai dat
    def hours(self):
        hs = sorted({int(x) for x in self.v_gio.get().replace(";", ",").split(",") if x.strip()})
        if not hs or any(h < 6 or h > 22 for h in hs):
            raise ValueError
        return hs

    def save(self, quiet=False):
        try:
            hs, n = self.hours(), int(self.v_items.get())
            if not 1 <= n <= 8:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Sai cài đặt", "Giờ đăng: các số từ 6 đến 22, ví dụ 9, 12, 17, 20.\nSố món: từ 1 đến 8.")
            return False
        cfg = read_json(CFG_PATH)
        kieu = next((k for k, v in KIEU_LABEL.items() if v == self.v_kieu.get()), "tung_mon")
        cfg.update(zalo_hours=hs, zalo_items=n, zalo_kieu=kieu)
        write_json(CFG_PATH, cfg)
        local = read_json(LOCAL_PATH)                 # giu nguyen token / ma Telegram / Facebook
        local["zalo_nhom"] = self.v_nhom.get().strip()
        write_json(LOCAL_PATH, local)
        if len(hs) > 4:
            messagebox.showinfo("Lưu ý", "Đăng hơn 4 lần/ngày dễ bị Zalo khoá nick phụ hơn.")
        if not quiet:
            self.v_status.set("✅ Đã lưu cài đặt.")
        return True

    # ------------------------------------------------------------ nut
    def run_bot(self, args, env_extra, label, after=None, timeout=900):
        if self.busy:
            messagebox.showinfo("Đang bận", "Bot đang làm việc khác, đợi xong đã nhé.")
            return
        self.busy = True
        self.v_status.set(label)

        def work():
            env = dict(os.environ, PYTHONIOENCODING="utf-8", **env_extra)
            try:
                r = subprocess.run([PY, os.path.join(HERE, "zalo_bot.py")] + args, cwd=HERE, env=env, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=timeout, creationflags=NOWIN)
                out, ok = (r.stdout or "") + (r.stderr or ""), r.returncode == 0
            except Exception as e:
                out, ok = f"LỖI: {e}", False

            def done():
                self.busy = False
                self.refresh_all()
                if after:
                    after(out, ok)
            self.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def on_check(self):
        self.v_login.set("đang kiểm tra (Chrome của bot mở ~20 giây)...")
        self.run_bot(["kiem_tra"], {}, "Đang kiểm tra đăng nhập...", after=lambda out, ok: (
            self.v_login.set("✅ ĐÃ ĐĂNG NHẬP" if "DA_DANG_NHAP" in out else "❌ CHƯA ĐĂNG NHẬP – bấm 'Đăng nhập Zalo'"),
            self.v_status.set("Xong.")), timeout=120)

    def on_login(self):
        messagebox.showinfo("Đăng nhập Zalo", "Cửa sổ Chrome của bot sẽ mở trang Zalo có MÃ QR.\n\n"
                            "Dùng điện thoại cầm NICK PHỤ: Zalo -> biểu tượng quét QR -> quét -> bấm Đăng nhập.\n"
                            "Bot chờ tối đa 5 phút.")
        self.run_bot(["dang_nhap"], {}, "Đang chờ anh quét mã QR...", after=lambda out, ok: (
            self.v_login.set("✅ ĐÃ ĐĂNG NHẬP" if "DA DANG NHAP" in out else "❌ CHƯA ĐĂNG NHẬP"),
            self.v_status.set("Đăng nhập xong." if "DA DANG NHAP" in out else "Chưa đăng nhập được, bấm lại.")), timeout=400)

    def on_post(self, dry):
        if not self.save(quiet=True):
            return
        if not self.v_nhom.get().strip():
            messagebox.showwarning("Thiếu tên nhóm", "Gõ tên nhóm Zalo (đúng từng chữ, có dấu) rồi bấm lại.")
            return
        if not dry and not messagebox.askyesno("Đăng ngay", f"Đăng ngay {self.v_items.get()} deal vào nhóm "
                                               f"'{self.v_nhom.get().strip()}'?"):
            return

        def after(out, ok):
            if dry and ok:
                self.v_status.set("👀 Đã điền thử rồi xoá (không gửi). Ảnh chụp màn hình đang mở.")
                try:
                    os.startfile(os.path.join(OUT_DIR, "xem_thu.png"))
                except Exception:
                    pass
            elif ok:
                self.v_status.set("✅ Đã đăng vào nhóm.")
            else:
                self.v_status.set("❌ Lỗi, xem nhật ký bên phải.")
        env = {"NGAY": "1"}
        if dry:
            env["DRY_RUN"] = "1"
        self.run_bot(["dang"], env, "Đang chọn deal + mở Zalo (1–2 phút)...", after=after)

    def on_task_on(self):
        if not self.save(quiet=True):
            return
        if not self.v_nhom.get().strip():
            messagebox.showwarning("Thiếu tên nhóm", "Gõ tên nhóm Zalo trước khi bật lịch.")
            return
        hs = self.hours()
        if not messagebox.askyesno("Bật lịch", "Bật lịch Windows: bot tự đăng lúc " + ", ".join(f"{h}h" for h in hs)
                                   + " mỗi ngày (máy phải bật).\n\nNick phụ MỚI LẬP thì nên nuôi 1–2 tuần rồi mới bật. Bật ngay?"):
            return
        vbs = os.path.join(HERE, "zalo_an.vbs")
        trig = ", ".join(f"(New-ScheduledTaskTrigger -Daily -At '{h:02d}:00')" for h in hs)
        code, out = ps(f"$a = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument '\"{vbs}\"'; "
                       f"$s = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew; "
                       f"Register-ScheduledTask -TaskName '{TASK}' -Action $a -Trigger @({trig}) -Settings $s "
                       f"-Description 'Nick Zalo phu dang deal vao nhom (zalo_bot.py)' -Force | Out-Null")
        self.v_status.set("✅ Đã bật lịch." if code == 0 else "❌ Không bật được lịch: " + out[-200:])
        self.refresh_task()

    def on_task_off(self):
        code, out = ps(f"Disable-ScheduledTask -TaskName '{TASK}' -ErrorAction Stop | Out-Null")
        self.v_status.set("⏸ Đã tắt lịch (bot không tự đăng nữa)." if code == 0 else "Chưa có lịch nào để tắt.")
        self.refresh_task()


if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        with open(os.path.join(HERE, "loi.txt"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
