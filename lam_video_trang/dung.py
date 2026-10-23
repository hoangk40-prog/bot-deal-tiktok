"""Dung 1 video mau bang make_video.py cua tool nhung. Khoa Pollinations lay tu cai dat tool (khong in ra)."""
import json, os, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
TOOL = r"H:\My Drive\Tool tổng hợp Hoàng (đã nhúng)"
D = os.path.dirname(os.path.abspath(__file__))
name, extra = sys.argv[1], sys.argv[2:]
env = dict(os.environ, PYTHONIOENCODING="utf-8")
try:
    st = json.load(open(os.path.expanduser("~/.video_tool_settings.json"), encoding="utf-8"))
    k = str(st.get("gen_api_key") or "").strip()
    if ":" in k:                                  # khoa Cloudflare dang ACCOUNT_ID:TOKEN
        env["CLOUDFLARE_AI_KEY"] = k
except Exception:
    pass
try:
    env["GEMINI_API_KEY"] = json.load(open(r"H:\My Drive\xuong_video\tai_render_data\cai_dat.json",
                                           encoding="utf-8"))["gemini_key"].strip()
except Exception:
    pass
cmd = [sys.executable, "make_video.py", "--mode", "generate", "--voice", os.path.join(D, name + ".mp3"),
       "--ratio", "9:16", "--out-dir", os.path.join(D, "ra"), "--overwrite", "--sub-size", "78", "--sub-margin", "1500",
       "--sub-style", "kara_yellow", "--sub-case", "upper", "--model", "small", "--lang", "vi", "--music-vol", "0.25"] + extra
print(" ".join(cmd[1:]), flush=True)
sys.exit(subprocess.run(cmd, cwd=TOOL, env=env).returncode)
