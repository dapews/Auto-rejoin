#!/data/data/com.termux/files/usr/bin/bash
# ============================================================
#  start.sh — Jalankan bot Discord + Auto-Rejoin sekaligus
#  Cara pakai: bash start.sh
# ============================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT="$DIR/bot.py"
MAIN="$DIR/main.py"
LOG_BOT="$DIR/bot.log"
LOG_MAIN="$DIR/rejoin.log"
LOG_ACT="$DIR/activity.log"
PID_BOT="$DIR/bot.pid"
PID_MAIN="$DIR/main.pid"
PID_WATCH="$DIR/watchdog.pid"
PYTHON="/data/data/com.termux/files/usr/bin/python3"
CONFIG="$DIR/config.json"

GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; CYA="\033[36m"; RESET="\033[0m"

echo ""
echo "=================================================="
echo "   🍪 Roblox Auto-Rejoin — Launcher"
echo "=================================================="
echo ""

# ── Cek root ─────────────────────────────────────────────────
if ! su -c "id" &>/dev/null; then
    echo -e "${RED}❌ Root tidak tersedia! Grant root ke Termux dulu.${RESET}"
    exit 1
fi
echo -e "${GREEN}✓ Root OK${RESET}"

# ── Cek config ───────────────────────────────────────────────
if [ ! -f "$CONFIG" ]; then
    echo -e "${RED}❌ config.json tidak ditemukan!${RESET}"
    echo -e "${YELLOW}   Jalankan dulu: python main.py → pilih 1 (Create Config)${RESET}"
    exit 1
fi
echo -e "${GREEN}✓ Config ditemukan${RESET}"

# ── Cek BOT_TOKEN sudah diisi ─────────────────────────────────
if grep -q "ISI_TOKEN_BOT_DISCORD_KAMU" "$BOT" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  BOT_TOKEN di bot.py belum diisi!${RESET}"
    echo -e "${YELLOW}   Bot Discord tidak akan dijalankan.${RESET}"
    SKIP_BOT=1
else
    SKIP_BOT=0
fi

# ── Install dependency kalau belum ada ───────────────────────
echo -e "${CYA}📦 Cek dependency...${RESET}"
for pkg in discord requests; do
    if ! $PYTHON -c "import $pkg" &>/dev/null; then
        echo -e "${YELLOW}   Menginstall $pkg...${RESET}"
        pip install $pkg -q
    fi
done
echo -e "${GREEN}✓ Dependency OK${RESET}"

# ── Trim log kalau sudah terlalu besar (>500KB) ───────────────
trim_log() {
    local f=$1
    if [ -f "$f" ] && [ $(wc -c < "$f") -gt 512000 ]; then
        echo -e "${YELLOW}🗑️  Trim log $(basename $f) (terlalu besar)...${RESET}"
        tail -n 300 "$f" > "${f}.tmp" && mv "${f}.tmp" "$f"
    fi
}
trim_log "$LOG_MAIN"
trim_log "$LOG_BOT"
trim_log "$LOG_ACT"

# ── Ambil semua package Roblox dari config.json ───────────────
ROBLOX_PKGS=$($PYTHON -c "
import json
try:
    cfg = json.load(open('$CONFIG'))
    pkgs = list(set(a.get('package','') for a in cfg.get('accounts',[])))
    print(' '.join(p for p in pkgs if p))
except:
    print('com.roblox.client')
" 2>/dev/null)
echo -e "${GREEN}📦 Package: $ROBLOX_PKGS${RESET}"

# ── SELinux permissive ──────────────────────────────────────────
su -c "setenforce 0" 2>/dev/null
echo -e "${GREEN}✓ SELinux permissive${RESET}"

# ── Wakelock & protect ────────────────────────────────────────
echo -e "${GREEN}🔒 Wakelock & proteksi Roblox...${RESET}"
termux-wake-lock 2>/dev/null || true
su -c "dumpsys deviceidle whitelist +com.termux" 2>/dev/null
su -c "settings put global app_standby_enabled 0" 2>/dev/null
su -c "settings put global stay_on_while_plugged_in 3" 2>/dev/null
su -c "settings put system screen_off_timeout 2147483647" 2>/dev/null
su -c "dumpsys deviceidle disable" 2>/dev/null
for PKG in $ROBLOX_PKGS; do
    su -c "dumpsys deviceidle whitelist +$PKG" 2>/dev/null
    su -c "cmd appops set $PKG RUN_IN_BACKGROUND allow" 2>/dev/null
    su -c "cmd appops set $PKG RUN_ANY_IN_BACKGROUND allow" 2>/dev/null
done
echo -e "${GREEN}✓ Proteksi aktif${RESET}"

# ── Stop proses lama ──────────────────────────────────────────
is_running() {
    local pid_file=$1
    [ -f "$pid_file" ] && kill -0 "$(cat $pid_file)" 2>/dev/null
}

if is_running "$PID_BOT";   then echo -e "${YELLOW}⏹️  Stop bot lama...${RESET}";    kill -TERM "$(cat $PID_BOT)"   2>/dev/null; sleep 1; fi
if is_running "$PID_MAIN";  then echo -e "${YELLOW}⏹️  Stop rejoin lama...${RESET}"; kill -TERM "$(cat $PID_MAIN)"  2>/dev/null; sleep 1; fi
if is_running "$PID_WATCH"; then kill -TERM "$(cat $PID_WATCH)" 2>/dev/null; fi

# ── Jalankan Bot Discord ──────────────────────────────────────
if [ $SKIP_BOT -eq 0 ] && [ -f "$BOT" ]; then
    echo -e "${GREEN}🤖 Menjalankan Bot Discord...${RESET}"
    nohup $PYTHON "$BOT" > "$LOG_BOT" 2>&1 &
    BOT_PID=$!
    echo $BOT_PID > "$PID_BOT"
    sleep 2
    if kill -0 $BOT_PID 2>/dev/null; then
        echo -e "${GREEN}   ✓ Bot berjalan (PID: $BOT_PID)${RESET}"
    else
        echo -e "${RED}   ✗ Bot gagal start! Cek: tail -f $LOG_BOT${RESET}"
        tail -5 "$LOG_BOT"
    fi
else
    [ $SKIP_BOT -eq 1 ] || echo -e "${YELLOW}⚠️  bot.py tidak ditemukan, skip.${RESET}"
fi

# ── Jalankan Auto-Rejoin ──────────────────────────────────────
echo -e "${GREEN}🎮 Menjalankan Auto-Rejoin...${RESET}"
nohup $PYTHON "$MAIN" --auto > "$LOG_MAIN" 2>&1 &
MAIN_PID=$!
echo $MAIN_PID > "$PID_MAIN"
sleep 2
if kill -0 $MAIN_PID 2>/dev/null; then
    echo -e "${GREEN}   ✓ Auto-Rejoin berjalan (PID: $MAIN_PID)${RESET}"
else
    echo -e "${RED}   ✗ Auto-Rejoin gagal start! Cek log:${RESET}"
    tail -10 "$LOG_MAIN"
fi

# ── Watchdog ──────────────────────────────────────────────────
echo -e "${GREEN}👁️  Menjalankan Watchdog...${RESET}"
WATCHDOG_SCRIPT="$DIR/roblox_watchdog.sh"
cat > "$WATCHDOG_SCRIPT" << WATCHDOG
#!/data/data/com.termux/files/usr/bin/bash
PKGS="$ROBLOX_PKGS"
DIR="$DIR"
PYTHON="$PYTHON"
BOT="$BOT"
MAIN="$MAIN"
LOG_BOT="$LOG_BOT"
LOG_MAIN="$LOG_MAIN"
PID_BOT="$PID_BOT"
PID_MAIN="$PID_MAIN"

while true; do
    # ── Protect Roblox process ──
    for PKG in \$PKGS; do
        PID=\$(su -c "pidof \$PKG" 2>/dev/null)
        if [ -n "\$PID" ]; then
            for P in \$PID; do
                su -c "echo -1000 > /proc/\$P/oom_score_adj" 2>/dev/null
                su -c "renice -n -10 -p \$P" 2>/dev/null
            done
        fi
    done

    # ── Auto-restart Bot kalau mati ──
    if [ -f "\$PID_BOT" ]; then
        BOT_PID=\$(cat "\$PID_BOT")
        if ! kill -0 "\$BOT_PID" 2>/dev/null; then
            echo "[\$(date +%H:%M:%S)] Bot mati, restart..." >> "\$LOG_BOT"
            nohup \$PYTHON "\$BOT" >> "\$LOG_BOT" 2>&1 &
            echo \$! > "\$PID_BOT"
        fi
    fi

    # ── Auto-restart Auto-Rejoin kalau mati ──
    if [ -f "\$PID_MAIN" ]; then
        MAIN_PID=\$(cat "\$PID_MAIN")
        if ! kill -0 "\$MAIN_PID" 2>/dev/null; then
            echo "[\$(date +%H:%M:%S)] Auto-Rejoin mati, restart..." >> "\$LOG_MAIN"
            nohup \$PYTHON "\$MAIN" --auto >> "\$LOG_MAIN" 2>&1 &
            echo \$! > "\$PID_MAIN"
        fi
    fi

    sleep 15
done
WATCHDOG
chmod +x "$WATCHDOG_SCRIPT"
nohup bash "$WATCHDOG_SCRIPT" > /dev/null 2>&1 &
echo $! > "$PID_WATCH"
echo -e "${GREEN}   ✓ Watchdog berjalan${RESET}"

# ── Buat stop.sh otomatis ─────────────────────────────────────
cat > "$DIR/stop.sh" << STOPSCRIPT
#!/data/data/com.termux/files/usr/bin/bash
echo "🛑 Menghentikan semua proses..."
[ -f "$PID_MAIN" ]  && kill -TERM \$(cat "$PID_MAIN")  2>/dev/null && echo "   ✓ Auto-Rejoin dihentikan"
[ -f "$PID_BOT" ]   && kill -TERM \$(cat "$PID_BOT")   2>/dev/null && echo "   ✓ Bot dihentikan"
[ -f "$PID_WATCH" ] && kill -TERM \$(cat "$PID_WATCH") 2>/dev/null && echo "   ✓ Watchdog dihentikan"
termux-wake-unlock 2>/dev/null || true
echo "✅ Semua proses dihentikan."
STOPSCRIPT
chmod +x "$DIR/stop.sh"

echo ""
echo "=================================================="
echo -e "${GREEN}✅ Semua proses berjalan!${RESET}"
echo ""
echo "   📄 Log rejoin : tail -f $LOG_MAIN"
echo "   📄 Log bot    : tail -f $LOG_BOT"
echo "   🛑 Stop semua : bash stop.sh"
echo "=================================================="
echo ""
