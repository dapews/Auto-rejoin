#!/data/data/com.termux/files/usr/bin/bash
# ╔══════════════════════════════════════════════════════════╗
# ║       🍪 Roblox Auto-Rejoin YURXZ — Setup Wizard        ║
# ║                                                          ║
# ║  Cara pakai:                                             ║
# ║  1. Taruh file ini di /sdcard/                           ║
# ║  2. Buka Termux                                          ║
# ║  3. Ketik: bash /sdcard/setup.sh                         ║
# ║  4. Ikuti instruksi di layar                             ║
# ╚══════════════════════════════════════════════════════════╝

REPO="https://raw.githubusercontent.com/DEWM0404/AUTO-REJOIN-YURXZ/main"
DIR="/sdcard/Auto-Rejoin"
GREEN="\033[32m"; YELLOW="\033[33m"; RED="\033[31m"; CYA="\033[36m"; RESET="\033[0m"; BOLD="\033[1m"

clear
echo ""
echo -e "${CYA}${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CYA}${BOLD}║   🍪 Roblox Auto-Rejoin Setup Wizard    ║${RESET}"
echo -e "${CYA}${BOLD}║           by YURXZ                      ║${RESET}"
echo -e "${CYA}${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo ""

# ─── STEP 1: Storage permission ──────────────────────────────
echo -e "${YELLOW}[1/6] Setup storage permission...${RESET}"
if [ ! -d "/sdcard/Download" ]; then
    termux-setup-storage
    echo "    Izinkan akses storage, lalu tunggu 5 detik..."
    sleep 5
else
    echo -e "${GREEN}    ✓ Storage sudah OK${RESET}"
fi

# ─── STEP 2: Install packages ─────────────────────────────────
echo ""
echo -e "${YELLOW}[2/6] Install dependencies...${RESET}"
pkg update -y -q 2>/dev/null
pkg install -y python git wget -q 2>/dev/null
pip install requests discord.py -q 2>/dev/null
echo -e "${GREEN}    ✓ Python, requests, discord.py siap${RESET}"

# ─── STEP 3: Download files dari GitHub ──────────────────────
echo ""
echo -e "${YELLOW}[3/6] Download files dari GitHub...${RESET}"
mkdir -p "$DIR/docs" "$DIR/cookies"

# Download semua file utama
for FILE in main.py bot.py start.sh update.sh cookie_import.py; do
    echo -e "    Downloading $FILE..."
    wget -q -O "$DIR/$FILE" "$REPO/$FILE"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}    ✓ $FILE${RESET}"
    else
        echo -e "${RED}    ✗ Gagal download $FILE${RESET}"
    fi
done

# Download docs
for DOC in BOT.md COOKIE.md TROUBLESHOOTING.md; do
    wget -q -O "$DIR/docs/$DOC" "$REPO/docs/$DOC" 2>/dev/null
done

chmod +x "$DIR/start.sh" "$DIR/update.sh" 2>/dev/null
echo -e "${GREEN}    ✓ Semua file siap${RESET}"

# ─── STEP 4: Konfigurasi ─────────────────────────────────────
echo ""
echo -e "${CYA}${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CYA}${BOLD}║            ⚙️  KONFIGURASI               ║${RESET}"
echo -e "${CYA}${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo ""
echo -e "${YELLOW}  Isi data berikut. Boleh kosong, bisa diisi nanti.${RESET}"
echo ""

# Bot Token
echo -e "${BOLD}🤖 Discord Bot Token${RESET}"
echo "   Buat di: discord.com/developers/applications"
echo -e "   (kosong = skip, isi nanti di bot.py)\n"
echo -n "   Bot Token: "
read BOT_TOKEN

# Discord User ID
echo ""
echo -e "${BOLD}🔐 Discord User ID kamu${RESET}"
echo "   Settings > Tampilan > Mode Developer ON > klik kanan nama kamu"
echo -n "   Discord User ID: "
read DISCORD_ID

# Webhook
echo ""
echo -e "${BOLD}📢 Discord Webhook URL ${YELLOW}(opsional)${RESET}"
echo -n "   Webhook URL: "
read WEBHOOK_URL

# ─── STEP 5: Inject config ke bot.py ─────────────────────────
echo ""
echo -e "${YELLOW}[4/6] Menyimpan konfigurasi...${RESET}"

if [ -n "$BOT_TOKEN" ]; then
    sed -i "s/ISI_TOKEN_BOT_DISCORD_KAMU/$BOT_TOKEN/" "$DIR/bot.py"
    echo -e "${GREEN}    ✓ Bot Token disimpan${RESET}"
else
    echo -e "${YELLOW}    ⚠️  Bot Token belum diisi — edit manual di bot.py nanti${RESET}"
fi

if [ -n "$DISCORD_ID" ]; then
    sed -i "s/ALLOWED_IDS  = \[\]/ALLOWED_IDS  = [$DISCORD_ID]/" "$DIR/bot.py"
    echo -e "${GREEN}    ✓ Discord ID disimpan${RESET}"
fi

# Buat config.json dasar
cat > "$DIR/config.json" << CONFIGEOF
{
  "check_interval": 35,
  "load_wait": 30,
  "launch_delay": 12,
  "webhook_url": "${WEBHOOK_URL}",
  "webhook_interval": 600,
  "accounts": []
}
CONFIGEOF
echo -e "${GREEN}    ✓ config.json dibuat${RESET}"
echo -e "${YELLOW}    ➜  Jalankan 'python main.py' → pilih 1 untuk tambah akun${RESET}"

# ─── STEP 6: Termux:Boot ──────────────────────────────────────
echo ""
echo -e "${YELLOW}[5/6] Setup auto-start saat boot...${RESET}"
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/autostart.sh << BOOTEOF
#!/data/data/com.termux/files/usr/bin/bash
# Auto-start Roblox Auto-Rejoin saat HP boot
sleep 15
cd $DIR
bash "$DIR/start.sh" >> "$DIR/boot.log" 2>&1
BOOTEOF
chmod +x ~/.termux/boot/autostart.sh
echo -e "${GREEN}    ✓ Auto-start saat boot aktif${RESET}"
echo -e "${YELLOW}    ⚠️  Pastikan Termux:Boot sudah diinstall dari F-Droid!${RESET}"

# ─── STEP 7: Langsung jalankan ────────────────────────────────
echo ""
echo -e "${YELLOW}[6/6] Setup selesai!${RESET}"
echo ""

# Tanya mau langsung jalankan atau tidak
echo -n "   Langsung jalankan sekarang? (y/n): "
read RUN_NOW
if [ "$RUN_NOW" = "y" ] || [ "$RUN_NOW" = "Y" ]; then
    cd "$DIR"
    bash "$DIR/start.sh"
fi

# ─── DONE ────────────────────────────────────────────────────
echo ""
echo -e "${CYA}${BOLD}╔══════════════════════════════════════════╗${RESET}"
echo -e "${CYA}${BOLD}║            ✅ SETUP SELESAI!             ║${RESET}"
echo -e "${CYA}${BOLD}╚══════════════════════════════════════════╝${RESET}"
echo ""
echo -e "  📁 Folder    : ${BOLD}$DIR${RESET}"
echo -e "  📝 Tambah akun: ${BOLD}cd $DIR && python main.py${RESET}"
echo -e "  🚀 Jalankan  : ${BOLD}bash $DIR/start.sh${RESET}"
echo -e "  🔄 Update    : ${BOLD}bash $DIR/update.sh${RESET}"
echo ""
echo -e "  ${YELLOW}⚠️  Kalau belum tambah akun, jalankan dulu:${RESET}"
echo -e "  ${BOLD}cd $DIR && python main.py${RESET} → pilih 1"
echo ""
