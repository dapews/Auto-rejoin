import os
import sys
import json
import subprocess
import time
import math
import re
from pathlib import Path

CONFIG_FILE = "config.json"

# ══════════════════════════════════════════════════════════════
#  ROOT HELPER
# ══════════════════════════════════════════════════════════════

def run_cmd(cmd, timeout=15):
    try:
        r = subprocess.run(['su', '-c', cmd],
                           capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or '') + '\n' + (r.stderr or '')
        return r.returncode == 0, out.strip()
    except Exception as e:
        return False, str(e)

def check_root():
    try:
        r = subprocess.run(['su', '-c', 'id'], capture_output=True, timeout=5)
        return r.returncode == 0
    except:
        return False

def log(msg, lvl="INFO"):
    try:
        with open("activity.log", "a") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] [{lvl}] {msg}\n")
    except:
        pass

# ══════════════════════════════════════════════════════════════
#  DISPLAY
# ══════════════════════════════════════════════════════════════

def clear_screen():
    print("\033[H\033[2J", end="")
    sys.stdout.flush()

def print_header():
    print("\n" + "="*52)
    print("   🍪  Roblox Auto-Rejoin  |  by DAPEWS")
    print("="*52 + "\n")

def get_memory_info():
    try:
        with open("/proc/meminfo") as f:
            c = f.read()
        tot = re.search(r"MemTotal:\s+(\d+)", c)
        av  = re.search(r"MemAvailable:\s+(\d+)", c)
        if tot and av:
            t, a = int(tot.group(1)), int(av.group(1))
            return f"{a//1024}MB", int(a/t*100)
    except:
        pass
    return "N/A", 0

def get_term_width():
    try:
        import shutil
        w = shutil.get_terminal_size(fallback=(80, 24)).columns
        return max(40, min(w, 220))
    except:
        return 80

def draw_ui(accounts, phase, detail="", extra=""):
    RES = "\033[0m"; CYA = "\033[36m"; GRE = "\033[32m"
    YEL = "\033[33m"; RED = "\033[31m"; GRY = "\033[90m"
    sys.stdout.write("\033[2J\033[H\033[?25l")

    # Lebar dinamis: responsif saat zoom in/out atau resize terminal
    TW = get_term_width()
    W  = TW - 2          # dikurangi border kiri-kanan
    C1 = max(12, W // 3) # kolom AKUN: ~1/3 lebar
    C2 = W - C1 - 3      # kolom STATUS: sisa

    def trunc(s, l):
        s = str(s).replace('\n','').replace('\r','')
        if l < 4: return s[:l]
        return s[:l-1]+"." if len(s) > l else s

    def sep(l, m, r, c='─'):
        sys.stdout.write(f"{CYA}{l}{c*(C1+1)}{m}{c*(C2+1)}{r}{RES}\n")

    def row(a, b, col=RES):
        sys.stdout.write(
            f"{CYA}│{RES} {trunc(a,C1):<{C1}}"
            f"{CYA}│{RES} {col}{trunc(b,C2):<{C2}}{RES}"
            f"{CYA}│{RES}\n"
        )

    mem, mpct = get_memory_info()

    # Judul di tengah atas tabel
    title = " 🍪 Roblox Auto-Rejoin | Dapews "
    inner = C1 + 1 + C2 + 2  # total lebar dalam tabel
    tlen  = len(title)
    if tlen <= inner:
        pl = (inner - tlen) // 2
        pr = inner - tlen - pl
        sys.stdout.write(f"{CYA}┌{'─'*pl}{title}{'─'*pr}┐{RES}\n")
    else:
        sys.stdout.write(f"{CYA}┌{'─'*inner}┐{RES}\n")

    row("AKUN", "STATUS")
    sep('├','┼','┤')

    txt = phase
    if detail: txt += f" | {detail}"
    if extra:  txt += f" | {extra}"
    row("System", txt, YEL)
    row("Memory", f"Free: {mem} ({mpct}%)", GRY)
    sep('├','┼','┤')

    for a in accounts:
        st = a.get('status','?')
        if any(x in st for x in ['In Game','Online','✅']):
            col = GRE
        elif any(x in st for x in ['Waiting','Starting','Opening','Rejoin','Tunggu','Force']):
            col = YEL
        elif any(x in st for x in ['Error','Failed','❌','Crash','Freeze','Gagal']):
            col = RED
        else:
            col = GRY
        row(f"{a['name']}", st, col)

    sep('└','┴','┘')
    sys.stdout.flush()

# ══════════════════════════════════════════════════════════════
#  ROBLOX HELPERS
# ══════════════════════════════════════════════════════════════

def is_running(pkg):
    ok, out = run_cmd(f"pidof {pkg}")
    return ok and out.strip() != ""

def protect_app(pkg):
    ok, pid = run_cmd(f"pidof {pkg}")
    if ok and pid.strip():
        p = pid.strip().split()[0]
        run_cmd(f"echo -1000 > /proc/{p}/oom_score_adj")
        run_cmd(f"renice -n -10 -p {p}")
        run_cmd(f"dumpsys deviceidle whitelist +{pkg}")
        run_cmd(f"cmd appops set {pkg} RUN_ANY_IN_BACKGROUND allow")

def set_low_performance(pkg):
    # Mute volume media
    run_cmd("media volume --stream 3 --set 0")
    run_cmd("service call audio 8 i32 3 i32 0 i32 1 2>/dev/null")
    log(f"[{pkg}] Volume dimute", "INFO")

    # TIDAK mengubah resolusi/DPI layar agar layout floating tetap beraturan
    # run_cmd("wm size 540x960")  # <-- dinonaktifkan
    # run_cmd("wm density 160")   # <-- dinonaktifkan
    log(f"[{pkg}] Low performance mode (resolusi tidak diubah)", "INFO")

    # Set grafik ke terendah
    pref_paths = [
        f"/data/data/{pkg}/shared_prefs/RobloxMobilePreferences.xml",
        f"/data/user/0/{pkg}/shared_prefs/RobloxMobilePreferences.xml",
        f"/data/user_de/0/{pkg}/shared_prefs/RobloxMobilePreferences.xml",
    ]
    xml_content = '''<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <int name="GraphicsQualityLevel" value="1" />
    <int name="SavedQualityLevel" value="1" />
    <boolean name="GraphicsAutoQuality" value="false" />
</map>'''
    run_cmd(f"echo '{xml_content}' > /data/local/tmp/rbx_pref.xml")
    for path in pref_paths:
        dir_path = "/".join(path.split("/")[:-1])
        ok_dir, _ = run_cmd(f"ls {dir_path}")
        if ok_dir:
            run_cmd(f"cp /data/local/tmp/rbx_pref.xml {path}")
            run_cmd(f"chmod 660 {path}")
            run_cmd(f"chown {pkg}:{pkg} {path} 2>/dev/null || true")
            log(f"[{pkg}] Grafik diset ke terendah via {path}", "INFO")
            break

def restore_screen():
    try:
        if os.path.exists("screen_orig.txt"):
            lines = open("screen_orig.txt").read().strip().split("\n")
            size = lines[0] if lines else "reset"
            den  = lines[1] if len(lines) > 1 else "reset"
            run_cmd(f"wm size {size}" if size != "reset" else "wm size reset")
            run_cmd(f"wm density {den}" if den != "reset" else "wm density reset")
            log("Resolusi layar di-restore", "INFO")
    except: pass

def clear_cache(pkg):
    for cmd in [
        f"rm -rf /data/data/{pkg}/cache/*",
        f"rm -rf /data/data/{pkg}/code_cache/*",
        f"rm -rf /data/user/0/{pkg}/cache/*",
    ]:
        run_cmd(cmd)
    log(f"Cache cleared: {pkg}", "INFO")

def get_screen_size():
    # Baca resolusi ASLI (sebelum dimodifikasi) agar layout floating tetap benar
    if os.path.exists("screen_orig.txt"):
        try:
            lines = open("screen_orig.txt").read().strip().split("\n")
            size = lines[0] if lines else None
            if size and size != "reset":
                m = re.search(r"(\d+)x(\d+)", size)
                if m:
                    return int(m.group(1)), int(m.group(2))
        except:
            pass
    ok, out = run_cmd("wm size")
    if ok:
        m = re.search(r"(\d+)x(\d+)", out)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            # Simpan sebagai resolusi asli jika belum ada
            if not os.path.exists("screen_orig.txt"):
                ok2, orig_den = run_cmd("wm density")
                try:
                    orig_den_val = re.search(r"(\d+)", orig_den).group(1) if ok2 else "reset"
                    with open("screen_orig.txt", "w") as f:
                        f.write(f"{w}x{h}\n{orig_den_val}\n")
                except:
                    pass
            return w, h
    return 1080, 2400

def get_float_bounds(index, total, sw, sh):
    cols = math.ceil(math.sqrt(total))
    rows = math.ceil(total / cols)
    cw   = sw // cols
    ch   = sh // rows
    idx  = index - 1
    r, c = idx // cols, idx % cols
    x1, y1 = c * cw, r * ch
    x2, y2 = x1 + cw, y1 + ch
    pad = 4
    return f"{x1+pad},{y1+pad},{x2-pad},{y2-pad}"

def open_ps_link(link, pkg, index=1, total=1):
    sw, sh = get_screen_size()
    bounds = get_float_bounds(index, total, sw, sh)
    float_flags = f"--windowingMode 1 --bounds {bounds}"

    c1 = (f'am start {float_flags} '
          f'-n {pkg}/com.roblox.client.ActivityProtocolLaunch '
          f'-a android.intent.action.VIEW -d "{link}"')
    ok, out = run_cmd(c1)
    if ok and "Error:" not in out and "does not exist" not in out:
        return True

    c2 = f'am start {float_flags} -a android.intent.action.VIEW -d "{link}" -p {pkg}'
    ok2, out2 = run_cmd(c2)
    if ok2 and "Error:" not in out2:
        return True

    # Fallback tanpa floating
    c3 = f'am start -a android.intent.action.VIEW -d "{link}" -p {pkg}'
    ok3, _ = run_cmd(c3)
    return ok3

def click_reconnect(pkg):
    sw, sh = get_screen_size()
    run_cmd(f"am start -p {pkg} --activity-brought-to-front 2>/dev/null || am start -p {pkg}")
    time.sleep(1.0)

    tap_positions = [
        (sw // 2, int(sh * 0.57)),
        (sw // 2, int(sh * 0.62)),
        (sw // 2, int(sh * 0.67)),
        (sw // 2, int(sh * 0.72)),
        (sw // 2, int(sh * 0.50)),
    ]
    for x, y in tap_positions:
        run_cmd(f"input tap {x} {y}")
        time.sleep(0.35)
    log(f"click_reconnect selesai untuk {pkg}", "INFO")

def detect_freeze(pkg):
    ok, pid_out = run_cmd(f"pidof {pkg}")
    if not ok or not pid_out.strip():
        return False

    pid = pid_out.strip().split()[0]
    zero_count = 0
    samples = 5

    for _ in range(samples):
        ok2, stat  = run_cmd(f"cat /proc/{pid}/stat 2>/dev/null")
        time.sleep(2)
        ok3, stat2 = run_cmd(f"cat /proc/{pid}/stat 2>/dev/null")
        if ok2 and ok3:
            try:
                s1 = int(stat.split()[13])  + int(stat.split()[14])
                s2 = int(stat2.split()[13]) + int(stat2.split()[14])
                if s2 - s1 == 0:
                    zero_count += 1
            except:
                pass

    is_frozen = zero_count >= 4
    if is_frozen:
        log(f"Freeze terdeteksi pada {pkg} (CPU=0 {zero_count}/{samples})", "WARN")
    return is_frozen

# ══════════════════════════════════════════════════════════════
#  MAIN REJOIN LOOP  (tanpa cookie / presence check)
# ══════════════════════════════════════════════════════════════

def safe_pause(msg="\nEnter untuk kembali..."):
    try:
        if sys.stdin.isatty():
            input(msg)
    except (EOFError, OSError):
        pass

def start_rejoin_app():
    if not os.path.exists(CONFIG_FILE):
        log("Config tidak ditemukan!", "ERROR")
        print("❌  Config tidak ditemukan! Jalankan 'Create Config' dulu.")
        safe_pause()
        return

    if not check_root():
        log("Root diperlukan!", "ERROR")
        print("❌  Root diperlukan!")
        safe_pause()
        return

    run_cmd("setenforce 0")

    with open(CONFIG_FILE) as f:
        cfg = json.load(f)

    accs_cfg = cfg.get("accounts", [])
    if not accs_cfg:
        print("❌  Tidak ada akun di config.")
        time.sleep(2)
        return

    interval     = cfg.get("check_interval", 35)
    launch_delay = cfg.get("launch_delay", 12)
    load_wait    = cfg.get("load_wait", 30)

    accounts = [{
        "index":  i + 1,
        "name":   a.get("name", f"Akun {i+1}"),
        "pkg":    a.get("package"),
        "link":   a.get("ps_link"),
        "status": "Menunggu...",
        "fail":   0,
    } for i, a in enumerate(accs_cfg)]

    tot = len(accounts)

    # ── Buka semua akun ──────────────────────────────────────
    for i, a in enumerate(accounts):
        a["status"] = "Opening..."
        draw_ui(accounts, "Launching", f"[{i+1}/{tot}]")
        clear_cache(a["pkg"])
        open_ps_link(a["link"], a["pkg"], a["index"], tot)
        protect_app(a["pkg"])
        set_low_performance(a["pkg"])
        if i < tot - 1:
            for t in range(launch_delay, 0, -1):
                draw_ui(accounts, "Launching", f"Tunggu {t}s sebelum akun berikutnya")
                time.sleep(1)

    # ── Tunggu loading ───────────────────────────────────────
    for t in range(load_wait, 0, -1):
        draw_ui(accounts, "Loading Game", f"Tunggu {t}s...")
        time.sleep(1)

    for a in accounts:
        a["status"] = "In Game ✅" if is_running(a["pkg"]) else "Tidak Terdeteksi"

    log("Monitoring dimulai (mode tanpa cookie)", "INFO")

    try:
        while True:
            for a in accounts:
                draw_ui(accounts, "Monitoring", f"Cek {a['name']}...")
                protect_app(a["pkg"])

                running = is_running(a["pkg"])

                # ── Deteksi freeze ────────────────────────────
                if running:
                    a["status"] = "Cek Freeze..."
                    draw_ui(accounts, "Monitoring", f"Freeze check {a['name']}...")
                    if detect_freeze(a["pkg"]):
                        a["status"] = "Freeze! Restart..."
                        log(f"{a['name']}: freeze terdeteksi, restart...", "WARN")
                        run_cmd(f"am force-stop {a['pkg']}")
                        time.sleep(2)
                        clear_cache(a["pkg"])
                        open_ps_link(a["link"], a["pkg"], a["index"], tot)
                        protect_app(a["pkg"])
                        set_low_performance(a["pkg"])
                        for t in range(load_wait, 0, -1):
                            a["status"] = f"Restart Freeze ({t}s)"
                            draw_ui(accounts, "Restart Freeze", a["name"])
                            time.sleep(1)
                        a["status"] = "In Game ✅" if is_running(a["pkg"]) else "Gagal Start ❌"
                        a["fail"] = 0
                        continue
                    else:
                        # App jalan normal
                        a["status"] = "In Game ✅"
                        a["fail"] = 0
                else:
                    # Roblox tidak jalan
                    a["fail"] += 1
                    if a["fail"] >= 2:
                        log(f"{a['name']}: tidak jalan {a['fail']}x → tunggu 60s lalu rejoin", "WARN")

                        # Tunggu 60 detik (1 menit) sebelum rejoin
                        for t in range(60, 0, -1):
                            a["status"] = f"Force Close! Rejoin dalam {t}s..."
                            draw_ui(accounts, "Menunggu Rejoin", a["name"])
                            time.sleep(1)

                        # Langsung rejoin tanpa klik reconnect (sudah force close)
                        a["status"] = "Rejoining... 🔄"
                        draw_ui(accounts, "Rejoining", a["name"])
                        clear_cache(a["pkg"])
                        # a["index"] tetap → menempati slot layout yang SAMA
                        open_ps_link(a["link"], a["pkg"], a["index"], tot)
                        protect_app(a["pkg"])
                        set_low_performance(a["pkg"])
                        # Tunggu 15 detik saja (cukup untuk loading awal)
                        for t in range(15, 0, -1):
                            a["status"] = f"Loading... ({t}s)"
                            draw_ui(accounts, "Rejoining", a["name"])
                            time.sleep(1)

                        a["status"] = "In Game ✅" if is_running(a["pkg"]) else "Gagal Rejoin ❌"
                        a["fail"] = 0
                        log(f"{a['name']}: rejoin → {a['status']}", "INFO")
                    else:
                        a["status"] = f"Cek ulang... ({a['fail']})"

            # Simpan status.json
            try:
                import json as _json
                with open("status.json", "w") as f:
                    _json.dump([{"name": x["name"], "status": x["status"]}
                                for x in accounts], f)
            except:
                pass

            for t in range(interval, 0, -1):
                draw_ui(accounts, "Idle", f"Cek berikutnya: {t}s")
                time.sleep(1)

    except KeyboardInterrupt:
        draw_ui(accounts, "Berhenti", "Ctrl+C ditekan")
        restore_screen()
        log("Monitoring dihentikan", "INFO")
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

# ══════════════════════════════════════════════════════════════
#  KNOWN PACKAGES
# ══════════════════════════════════════════════════════════════

KNOWN_PKGS = {
    "com.roblox.client":   "Roblox Official",
    "com.ronix.client":    "Ronix",
    "com.albert.client":   "Albert",
    "com.albert.1":        "Albert v1",
    "com.delta.client":    "Delta",
    "com.codex.client":    "Codex",
    "com.arceus.client":   "Arceus X",
    "com.arceusx.client":  "Arceus X",
    "com.fluxus.client":   "Fluxus",
    "com.trigon.client":   "Trigon Evo",
    "com.hydrogen.client": "Hydrogen",
    "com.oxygen.client":   "Oxygen",
    "com.vega.client":     "Vega X",
    "com.solara.client":   "Solara",
    "com.krnl.client":     "KRNL",
    "com.macsploit.client":"MacSploit",
    "com.getblox.client":  "GetBlox",
    "com.dansploit.client":"Dansploit",
    "com.coco.client":     "Coco Z",
}

def find_roblox_packages():
    installed = {}
    print("🔍 Mendeteksi Roblox & Executor...\n")
    _, out = run_cmd("pm list packages")
    for line in out.splitlines():
        if "package:" not in line:
            continue
        pkg = line.replace("package:", "").strip()
        if pkg in KNOWN_PKGS:
            print(f"   ✅ {KNOWN_PKGS[pkg]} ({pkg})")
            installed[KNOWN_PKGS[pkg]] = pkg
        else:
            kw = ['roblox','ronix','albert','delta','codex','arceus',
                  'fluxus','trigon','hydrogen','oxygen','krnl','vega',
                  'solara','macsploit','getblox','dansploit','coco','executor']
            if any(k in pkg.lower() for k in kw):
                label = f"Auto ({pkg})"
                print(f"   ✅ {label}")
                installed[label] = pkg
    if not installed:
        print("   ⚠️  Tidak ada yang terdeteksi!")
        manual = input("   Input manual package name: ").strip()
        if manual:
            installed["Manual"] = manual
    return installed

def clean_input(prompt):
    val = input(prompt).strip()
    val = re.sub(r'[\x00-\x1f\x7f]', '', val)
    return val

# ══════════════════════════════════════════════════════════════
#  CREATE CONFIG  (tanpa cookie, tanpa user_id)
# ══════════════════════════════════════════════════════════════

def create_config():
    clear_screen()
    print_header()
    print("  === Buat Config Baru ===\n")

    if not check_root():
        print("  ❌ Root diperlukan.")
        safe_pause()
        return

    pkgs = find_roblox_packages()
    if not pkgs:
        print("  ❌ Tidak ada package ditemukan.")
        safe_pause()
        return

    pkg_list = list(pkgs.items())
    print("\n  Package yang terinstall:")
    for i, (name, pkg) in enumerate(pkg_list):
        print(f"    {i+1}. {name}  [{pkg}]")

    accounts = []
    for idx, (label, pkg) in enumerate(pkg_list):
        print(f"\n  ── Akun {idx+1}: {label} ──")
        use = clean_input("  Gunakan akun ini? (y/n): ").lower()
        if use != 'y':
            continue

        acc_name = clean_input(f"  Nama akun [{label}]: ") or label
        ps_link  = clean_input("  Private Server Link: ").strip()

        accounts.append({
            "name":    acc_name,
            "package": pkg,
            "ps_link": ps_link,
        })
        print(f"  ✅ {acc_name} ditambahkan!")

    if not accounts:
        print("\n  Tidak ada akun. Config tidak dibuat.")
        safe_pause()
        return

    iv = clean_input("\n  Interval cek detik (default 35): ").strip()
    lw = clean_input("  Waktu tunggu loading detik (default 30): ").strip()
    ld = clean_input("  Jeda antar launch akun detik (default 12): ").strip()

    config = {
        "check_interval": int(iv) if iv.isdigit() else 35,
        "load_wait":      int(lw) if lw.isdigit() else 30,
        "launch_delay":   int(ld) if ld.isdigit() else 12,
        "accounts":       accounts,
    }

    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"\n  ✅ Config disimpan ({len(accounts)} akun)!")
    time.sleep(2)

# ══════════════════════════════════════════════════════════════
#  EDIT CONFIG
# ══════════════════════════════════════════════════════════════

def edit_config():
    if not os.path.exists(CONFIG_FILE):
        print("❌ Config tidak ada.")
        safe_pause()
        return
    os.system(f"nano {CONFIG_FILE}")

# ══════════════════════════════════════════════════════════════
#  MAIN MENU
# ══════════════════════════════════════════════════════════════

def main():
    while True:
        clear_screen()
        print_header()
        print("  1. Create Config")
        print("  2. Start Rejoin")
        print("  3. Edit Config")
        print("  4. Exit")
        print("\n" + "="*52)
        c = input("\n  Pilih: ").strip()
        if   c == '1': create_config()
        elif c == '2': start_rejoin_app()
        elif c == '3': edit_config()
        elif c == '4':
            clear_screen()
            restore_screen()
            break

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--auto" in args:
        try:
            with open("main.pid", "w") as f:
                f.write(str(os.getpid()))
        except:
            pass
        start_rejoin_app()
    else:
        main()
