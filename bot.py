import discord
from discord.ext import commands, tasks
import subprocess
import os
import json
import sys
import time
import signal
import asyncio
import re

BOT_TOKEN    = "ISI_TOKEN_BOT_DISCORD_KAMU"
PREFIX       = "!"
ALLOWED_IDS  = []
MAIN_PY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
STATUS_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "status.json")
CONFIG_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LOG_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "activity.log")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

rejoin_process = None
schedule_hours = 2
schedule_on    = False
preventive_on  = False

# ══════════════════════════════════════════════════════════════
#  HELPER
# ══════════════════════════════════════════════════════════════

def is_allowed(uid):
    return True if not ALLOWED_IDS else uid in ALLOWED_IDS

def run_cmd(cmd):
    try:
        r = subprocess.run(['su','-c',cmd], capture_output=True, text=True, timeout=10)
        return r.returncode==0, (r.stdout or '')+(r.stderr or '')
    except Exception as e:
        return False, str(e)

def read_status():
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE) as f: return json.load(f)
    except: pass
    return []

def read_config():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f: return json.load(f)
    except: pass
    return {}

def get_memory_info():
    try:
        with open("/proc/meminfo") as f: c = f.read()
        tot = re.search(r"MemTotal:\s+(\d+)", c)
        av  = re.search(r"MemAvailable:\s+(\d+)", c)
        if tot and av:
            t,a = int(tot.group(1)), int(av.group(1))
            return f"{a//1024}MB free", f"{(t-a)//1024}MB used ({int((t-a)/t*100)}%)"
    except: pass
    return "N/A","N/A"

def get_cpu_info():
    try:
        ok,out = run_cmd("cat /proc/loadavg")
        if ok: return f"Load: {' '.join(out.strip().split()[:3])}"
    except: pass
    return "N/A"

def get_screenshot():
    tmp="/data/local/tmp/bot_sc.png"; local="/sdcard/bot_screen.png"
    ok,_ = run_cmd(f"screencap -p {tmp} && cp {tmp} {local} && chmod 666 {local}")
    return local if ok and os.path.exists(local) else None

def is_running():
    return rejoin_process is not None and rejoin_process.poll() is None

# ══════════════════════════════════════════════════════════════
#  EMBED & PANEL
# ══════════════════════════════════════════════════════════════

def build_status_embed():
    accounts = read_status()
    running  = is_running()
    embed    = discord.Embed(
        title="🍪 Roblox Auto-Rejoin",
        color=discord.Color.green() if running else discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )
    _, mem_used = get_memory_info()
    sched_txt = f"⏰ Tiap {schedule_hours}j ✅" if schedule_on else "⏰ Off"
    prev_txt  = "🛡️ ON ✅" if preventive_on else "🛡️ Off"

    embed.add_field(name="💾 RAM",     value=f"`{mem_used}`",    inline=True)
    embed.add_field(name="⚙️ CPU",     value=f"`{get_cpu_info()}`", inline=True)
    embed.add_field(name="📊 Mode",    value=f"`{sched_txt}` `{prev_txt}`", inline=True)
    embed.add_field(name="\u200b",     value="─"*28, inline=False)

    if not accounts:
        embed.description = "Tidak ada data. Tekan **▶️ Start** untuk mulai."
    else:
        for acc in accounts:
            st = acc.get("status","?")
            if any(x in st for x in ["In Game","✅"]):                       icon="🟢"
            elif any(x in st for x in ["Rejoin","Waiting","Opening","Tunggu"]): icon="🟡"
            elif any(x in st for x in ["Gagal","❌","Offline"]):               icon="🔴"
            else:                                                               icon="⚪"
            embed.add_field(name=f"{icon} {acc.get('name','?')}", value=f"`{st}`", inline=True)

    embed.set_footer(text=f"{'🟢 Berjalan' if running else '🔴 Berhenti'} | {sched_txt} | {prev_txt}")
    return embed

def build_panel():
    running = is_running()
    v = discord.ui.View(timeout=None)

    # ── Row 0: Kontrol utama ──────────────────────────────────
    v.add_item(discord.ui.Button(label="Start",    emoji="▶️", style=discord.ButtonStyle.success,   custom_id="btn_start",    disabled=running,     row=0))
    v.add_item(discord.ui.Button(label="Stop",     emoji="⏹️", style=discord.ButtonStyle.danger,    custom_id="btn_stop",     disabled=not running,  row=0))
    v.add_item(discord.ui.Button(label="Restart",  emoji="🔄", style=discord.ButtonStyle.primary,   custom_id="btn_restart",                         row=0))
    v.add_item(discord.ui.Button(label="Refresh",  emoji="📊", style=discord.ButtonStyle.secondary, custom_id="btn_status",                          row=0))

    # ── Row 1: Info & tools ───────────────────────────────────
    v.add_item(discord.ui.Button(label="Screenshot", emoji="📸", style=discord.ButtonStyle.secondary, custom_id="btn_ss",      row=1))
    v.add_item(discord.ui.Button(label="Log",         emoji="📋", style=discord.ButtonStyle.secondary, custom_id="btn_log",     row=1))
    v.add_item(discord.ui.Button(label="RAM/CPU",     emoji="💻", style=discord.ButtonStyle.secondary, custom_id="btn_sysinfo", row=1))
    v.add_item(discord.ui.Button(label="Config",      emoji="⚙️", style=discord.ButtonStyle.secondary, custom_id="btn_config",  row=1))

    # ── Row 2: Fitur jadwal & preventif ──────────────────────
    jadwal_label = f"Jadwal: {schedule_hours}j ✅" if schedule_on else "Jadwal: OFF"
    jadwal_style = discord.ButtonStyle.success if schedule_on else discord.ButtonStyle.secondary
    v.add_item(discord.ui.Button(label=jadwal_label,  emoji="⏰", style=jadwal_style,                  custom_id="btn_jadwal",     row=2))

    prev_label = "Preventif: ON ✅" if preventive_on else "Preventif: OFF"
    prev_style = discord.ButtonStyle.success if preventive_on else discord.ButtonStyle.secondary
    v.add_item(discord.ui.Button(label=prev_label,    emoji="🛡️", style=prev_style,                   custom_id="btn_preventif",  row=2))

    v.add_item(discord.ui.Button(label="Set Jam",     emoji="✏️", style=discord.ButtonStyle.primary,   custom_id="btn_set_jadwal", row=2))

    return v

# ══════════════════════════════════════════════════════════════
#  MODAL — popup input atur jam jadwal
# ══════════════════════════════════════════════════════════════

class JadwalModal(discord.ui.Modal, title="⏰ Atur Jadwal Rejoin"):
    jam_input = discord.ui.TextInput(
        label="Rejoin tiap berapa jam?",
        placeholder="Contoh: 2  (isi 0 untuk matikan jadwal)",
        min_length=1,
        max_length=2,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        global schedule_hours, schedule_on
        try:
            jam = int(self.jam_input.value.strip())
        except:
            await interaction.response.send_message("❌ Harus angka! Contoh: 2", ephemeral=True)
            return

        if jam == 0:
            schedule_on = False
            if scheduled_rejoin.is_running(): scheduled_rejoin.cancel()
            msg = "⏰ Jadwal rejoin **dimatikan**."
        elif 1 <= jam <= 24:
            schedule_hours = jam
            schedule_on    = True
            if scheduled_rejoin.is_running(): scheduled_rejoin.cancel()
            scheduled_rejoin.change_interval(hours=jam)
            scheduled_rejoin.start()
            msg = f"⏰ Jadwal rejoin diset: **tiap {jam} jam**!"
        else:
            await interaction.response.send_message("❌ Masukkan angka 1–24 (atau 0 untuk off).", ephemeral=True)
            return

        e = build_status_embed()
        e.add_field(name="Aksi", value=msg, inline=False)
        await interaction.response.edit_message(embed=e, view=build_panel())

# ══════════════════════════════════════════════════════════════
#  AKSI
# ══════════════════════════════════════════════════════════════

async def do_start():
    global rejoin_process
    if is_running(): return False,"⚠️ Sudah berjalan!"
    if not os.path.exists(MAIN_PY_PATH): return False,"❌ main.py tidak ditemukan!"
    try:
        rejoin_process = subprocess.Popen(
            ["su","-c",f"python3 {MAIN_PY_PATH} --auto"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
        await asyncio.sleep(2)
        return (True, f"✅ Dimulai! PID: `{rejoin_process.pid}`") if rejoin_process.poll() is None \
               else (False, "❌ Proses langsung berhenti. Cek config.json.")
    except Exception as e:
        return False, f"❌ Error: `{e}`"

async def do_stop():
    global rejoin_process
    if not is_running(): return False,"⚠️ Tidak sedang berjalan."
    try:
        os.killpg(os.getpgid(rejoin_process.pid), signal.SIGTERM)
        rejoin_process = None
        return True,"🛑 Dihentikan."
    except Exception as e:
        return False, f"❌ Error: `{e}`"

async def do_restart():
    global rejoin_process
    if is_running():
        try:
            os.killpg(os.getpgid(rejoin_process.pid), signal.SIGTERM)
            rejoin_process = None
            await asyncio.sleep(2)
        except: pass
    return await do_start()

# ══════════════════════════════════════════════════════════════
#  TASKS
# ══════════════════════════════════════════════════════════════

@tasks.loop(hours=2)
async def scheduled_rejoin():
    if scheduled_rejoin.current_loop > 0 and schedule_on:
        await do_restart()

@tasks.loop(minutes=18)
async def preventive_rejoin():
    if is_running() and preventive_on:
        await do_restart()

# ══════════════════════════════════════════════════════════════
#  EVENTS
# ══════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"[BOT] Login: {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="Roblox Auto-Rejoin"))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    global preventive_on, schedule_on

    if interaction.type != discord.InteractionType.component: return
    if not is_allowed(interaction.user.id):
        await interaction.response.send_message("⛔ No permission!", ephemeral=True); return

    cid = interaction.data.get("custom_id","")
    msg = ""

    # Tombol yang perlu modal — jangan defer dulu
    if cid == "btn_set_jadwal":
        await interaction.response.send_modal(JadwalModal())
        return

    await interaction.response.defer()

    if   cid == "btn_start":   _, msg = await do_start()
    elif cid == "btn_stop":    _, msg = await do_stop()
    elif cid == "btn_restart": _, msg = await do_restart(); msg = f"🔄 {msg}"
    elif cid == "btn_status":  msg = "📊 Diperbarui!"

    elif cid == "btn_jadwal":
        # Toggle jadwal on/off
        schedule_on = not schedule_on
        if schedule_on:
            if not scheduled_rejoin.is_running(): scheduled_rejoin.start()
            msg = f"⏰ Jadwal **ON** — tiap {schedule_hours} jam\nGunakan ✏️ **Set Jam** untuk ubah durasi."
        else:
            if scheduled_rejoin.is_running(): scheduled_rejoin.cancel()
            msg = "⏰ Jadwal rejoin **dimatikan**."

    elif cid == "btn_preventif":
        preventive_on = not preventive_on
        if preventive_on:
            if not preventive_rejoin.is_running(): preventive_rejoin.start()
            msg = "🛡️ Preventif rejoin **ON** — tiap 18 menit"
        else:
            if preventive_rejoin.is_running(): preventive_rejoin.cancel()
            msg = "🛡️ Preventif rejoin **OFF**"

    elif cid == "btn_ss":
        path = get_screenshot()
        if path:
            e = build_status_embed()
            e.set_image(url="attachment://screen.png")
            await interaction.edit_original_response(
                embed=e, view=build_panel(),
                attachments=[discord.File(path, filename="screen.png")]); return
        else: msg = "❌ Gagal screenshot."

    elif cid == "btn_log":
        try:
            with open(LOG_FILE) as f: lines = f.readlines()
            last = "".join(lines[-15:]) if lines else "Log kosong."
            e = discord.Embed(title="📋 Log (15 terakhir)",
                              description=f"```\n{last[:1900]}\n```",
                              color=discord.Color.blurple(),
                              timestamp=discord.utils.utcnow())
            await interaction.edit_original_response(embed=e, view=build_panel()); return
        except: msg = "❌ Gagal baca log."

    elif cid == "btn_sysinfo":
        mf, mu = get_memory_info()
        e = discord.Embed(title="💻 System Info", color=discord.Color.blurple(),
                          timestamp=discord.utils.utcnow())
        e.add_field(name="💾 RAM Free", value=f"`{mf}`", inline=True)
        e.add_field(name="💾 RAM Used", value=f"`{mu}`", inline=True)
        e.add_field(name="⚙️ CPU",      value=f"`{get_cpu_info()}`", inline=False)
        await interaction.edit_original_response(embed=e, view=build_panel()); return

    elif cid == "btn_config":
        cfg  = read_config()
        accs = cfg.get("accounts",[])
        e = discord.Embed(title="⚙️ Config", color=discord.Color.blurple(),
                          timestamp=discord.utils.utcnow())
        e.add_field(name="Check Interval", value=f"`{cfg.get('check_interval','?')}s`", inline=True)
        e.add_field(name="Load Wait",      value=f"`{cfg.get('load_wait','?')}s`",      inline=True)
        e.add_field(name="Launch Delay",   value=f"`{cfg.get('launch_delay','?')}s`",   inline=True)
        e.add_field(name="Webhook",        value=f"`{'✅ Set' if cfg.get('webhook_url') else '❌ Kosong'}`", inline=True)
        e.add_field(name="Jumlah Akun",    value=f"`{len(accs)} akun`", inline=True)
        for a in accs:
            e.add_field(name=f"👤 {a.get('name','?')}",
                        value=f"Pkg: `{a.get('package','?')}`\nUID: `{a.get('user_id','?')}`",
                        inline=True)
        await interaction.edit_original_response(embed=e, view=build_panel()); return

    e = build_status_embed()
    if msg: e.add_field(name="Aksi", value=msg, inline=False)
    await interaction.edit_original_response(embed=e, view=build_panel())

# ══════════════════════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════════════════════

@bot.command(name="panel")
async def cmd_panel(ctx):
    if not is_allowed(ctx.author.id): await ctx.send("⛔ No permission."); return
    await ctx.send(embed=build_status_embed(), view=build_panel())

@bot.command(name="start")
async def cmd_start(ctx):
    if not is_allowed(ctx.author.id): await ctx.send("⛔ No permission."); return
    _,msg = await do_start()
    e=build_status_embed(); e.add_field(name="Aksi",value=msg,inline=False)
    await ctx.send(embed=e, view=build_panel())

@bot.command(name="stop")
async def cmd_stop(ctx):
    if not is_allowed(ctx.author.id): await ctx.send("⛔ No permission."); return
    _,msg = await do_stop()
    e=build_status_embed(); e.add_field(name="Aksi",value=msg,inline=False)
    await ctx.send(embed=e, view=build_panel())

@bot.command(name="restart")
async def cmd_restart(ctx):
    if not is_allowed(ctx.author.id): await ctx.send("⛔ No permission."); return
    _,msg = await do_restart()
    e=build_status_embed(); e.add_field(name="Aksi",value=f"🔄 {msg}",inline=False)
    await ctx.send(embed=e, view=build_panel())

@bot.command(name="status")
async def cmd_status(ctx):
    if not is_allowed(ctx.author.id): await ctx.send("⛔ No permission."); return
    await ctx.send(embed=build_status_embed(), view=build_panel())

@bot.command(name="ss")
async def cmd_ss(ctx):
    if not is_allowed(ctx.author.id): await ctx.send("⛔ No permission."); return
    path = get_screenshot()
    if path:
        e=discord.Embed(title="📸 Screenshot",color=discord.Color.blurple(),timestamp=discord.utils.utcnow())
        e.set_image(url="attachment://screen.png")
        await ctx.send(embed=e, file=discord.File(path, filename="screen.png"))
    else: await ctx.send("❌ Gagal screenshot.")

@bot.command(name="log")
async def cmd_log(ctx, lines: int=20):
    if not is_allowed(ctx.author.id): await ctx.send("⛔ No permission."); return
    try:
        with open(LOG_FILE) as f: content=f.readlines()
        last="".join(content[-lines:]) if content else "Log kosong."
        e=discord.Embed(title=f"📋 Log ({lines} baris terakhir)",
                        description=f"```\n{last[:1900]}\n```",
                        color=discord.Color.blurple(),timestamp=discord.utils.utcnow())
        await ctx.send(embed=e)
    except: await ctx.send("❌ Gagal baca log.")

@bot.command(name="help")
async def cmd_help(ctx):
    e=discord.Embed(title="🍪 Roblox Auto-Rejoin Bot",
                    description="Gunakan `!panel` untuk panel tombol lengkap.",
                    color=discord.Color.blurple())
    cmds=[
        ("!panel",   "Panel kontrol lengkap dengan tombol"),
        ("!start",   "Jalankan auto rejoin"),
        ("!stop",    "Hentikan auto rejoin"),
        ("!restart", "Restart ulang"),
        ("!status",  "Status semua akun"),
        ("!ss",      "Screenshot layar sekarang"),
        ("!log [n]", "Log n baris terakhir (default 20)"),
    ]
    for n,d in cmds: e.add_field(name=f"`{n}`",value=d,inline=False)
    await ctx.send(embed=e)

if __name__=="__main__":
    if BOT_TOKEN=="ISI_TOKEN_BOT_DISCORD_KAMU":
        print("❌ Isi BOT_TOKEN dulu!"); sys.exit(1)

    # Pastikan bot reconnect otomatis kalau putus
    import signal, logging
    logging.basicConfig(level=logging.WARNING)

    async def run_bot():
        while True:
            try:
                await bot.start(BOT_TOKEN)
            except Exception as e:
                print(f"[BOT] Error: {e} — reconnect dalam 10 detik...")
                await asyncio.sleep(10)
            finally:
                if not bot.is_closed():
                    await bot.close()

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("[BOT] Dihentikan.")
