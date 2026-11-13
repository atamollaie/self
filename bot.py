import asyncio
import os
import json
import time
import random
import string
import psutil
from datetime import datetime
from zoneinfo import ZoneInfo
from pyrogram import Client, filters, idle
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from pyrogram.errors import (
    SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired,
    PasswordHashInvalid, FloodWait
)

# ================= تنظیمات هسته =================
API_ID = 21721898
API_HASH = "41ed1de839c40c637c337c096039e334"
BOT_TOKEN = "9155660838:AAFJNF0wZqM9NhGAhk7puRGiCpbYpXWFM40"
HELPER_BOT_TOKEN = "9155660838:AAFJNF0wZqM9NhGAhk7puRGiCpbYpXWFM40"
ROOT_ADMIN = 5878935442
# =================================================

SESSIONS_DIR = "sessions"
DATA_FILE = "users_data.json"
SYS_FILE = "system_config.json"
os.makedirs(SESSIONS_DIR, exist_ok=True)

ACTIVE_CLIENTS = {}  # {user_id: Client}
USER_STATES = {}     # {user_id: dict}
TIME_TASKS = {}      # {user_id: asyncio.Task}
GROUP_BETS = {}      # {bet_id: dict}
HELPER_USERNAME = ""

# ================= پیکربندی سیستم (مدیریت) =================
def load_sys() -> dict:
    default_sys = {
        "hourly_cost": 2,
        "welcome_bonus": 0,
        "min_bet": 1,
        "max_bet": 10000,
        "maintenance": False,
        "gift_codes": {},
        "banned_users": [],
        "total_games": 0,
        "total_volume": 0
    }
    if os.path.exists(SYS_FILE):
        try:
            with open(SYS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in default_sys.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            return default_sys
    return default_sys

def save_sys(data: dict):
    with open(SYS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

SYS_CFG = load_sys()

# ================= دیتابیس کاربران =================
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

USERS_DB = load_data()

def get_user(uid: int) -> dict:
    key = str(uid)
    defaults = {
        "diamonds": SYS_CFG.get("welcome_bonus", 0),
        "last_charge": 0.0,
        "rig_mode": "normal",  # normal | win | lose
        "wins": 0,
        "losses": 0,
        "time_name": False,
        "time_bio": False,
        "font_style": 1,
        "orig_name": "",
        "orig_bio": "",
        "away_mode": False,
        "away_text": "در حال حاضر پاسخگو نیستم؛ پیام شما دریافت شد.",
        "pv_lock": False,
        "anti_flood": False,
        "auto_read": False,
        "typing_mode": False,
        "bold_mode": False,
        "italic_mode": False,
        "spoiler_mode": False,
        "no_forward": False,
        "approved_users": [],
        "muted_users": [],
        "enemies": [],
        "enemy_text": "پیام شما در لیست فیلتر قرار دارد."
    }
    if key not in USERS_DB:
        USERS_DB[key] = defaults.copy()
        save_data(USERS_DB)
    else:
        changed = False
        for k, v in defaults.items():
            if k not in USERS_DB[key]:
                USERS_DB[key][k] = v
                changed = True
        if changed:
            save_data(USERS_DB)
    return USERS_DB[key]

# ================= استایل‌های ساعت =================
FONT_STYLES = {
    1: ("𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗:", "Bold 𝟎𝟏:𝟐𝟑"),
    2: ("𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡:", "Outline 𝟘𝟙:𝟚𝟛"),
    3: ("⓪①②③④⑤⑥⑦⑧⑨:", "Circle ⓪①:②③"),
    4: ("⁰¹²³⁴⁵⁶⁷⁸⁹:", "Mini ⁰¹:²³"),
    5: ("０１２３４５６７８９:", "Wide ０１:２３"),
    6: ("0123456789:", "Clean 01:23")
}

def format_clock(t_str: str, style_id: int) -> str:
    normal = "0123456789:"
    target = FONT_STYLES.get(style_id, FONT_STYLES[1])[0]
    return t_str.translate(str.maketrans(normal, target))

manager_bot = Client(
    "manager_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ================= پنل اینلاین هلپر (دسته‌بندی شده و مدرن) =================
def build_self_panel_ui(uid: int, page: str = "main"):
    cfg = get_user(uid)
    st = lambda k: "🟢" if cfg.get(k) else "🔴"
    style_name = FONT_STYLES.get(cfg.get("font_style", 1))[1]

    if page == "main":
        text = (
            f"**کنترل پنل پیشرفته سلف‌بات**\n\n"
            f"> **موجودی حساب:** `{cfg['diamonds']}` الماس\n"
            f"> **تعرفه ساعتی:** `{SYS_CFG['hourly_cost']}` الماس\n"
            f"> **استایل ساعت:** `{style_name}`\n\n"
            f"لطفاً یکی از بخش‌های زیر را انتخاب کنید:"
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⏱ زمان و استایل ساعت", callback_data=f"hlp_cat_time_{uid}"),
                InlineKeyboardButton("🛡 امنیت و پی‌وی", callback_data=f"hlp_cat_sec_{uid}")
            ],
            [
                InlineKeyboardButton("🤖 دستیار و واکنش", callback_data=f"hlp_cat_asst_{uid}"),
                InlineKeyboardButton("✨ استایل متن", callback_data=f"hlp_cat_txt_{uid}")
            ],
            [
                InlineKeyboardButton("📖 راهنمای دستورات", callback_data=f"hlp_cmds_{uid}"),
                InlineKeyboardButton("✖️ بستن پنل", callback_data=f"hlp_close_{uid}")
            ]
        ])
        return text, kb

    elif page == "cat_time":
        text = (
            f"**بخش زمان و استایل ساعت**\n\n"
            f"> تنظیمات ساعت زنده و فونت نمایشی."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"ساعت نام: {st('time_name')}", callback_data=f"hlp_tname_{uid}"),
                InlineKeyboardButton(f"ساعت بیو: {st('time_bio')}", callback_data=f"hlp_tbio_{uid}")
            ],
            [
                InlineKeyboardButton(f"تغییر فونت ◂ {style_name}", callback_data=f"hlp_font_{uid}")
            ],
            [
                InlineKeyboardButton("❮ بازگشت به منوی اصلی", callback_data=f"hlp_back_{uid}")
            ]
        ])
        return text, kb

    elif page == "cat_sec":
        text = (
            f"**بخش امنیت و پی‌وی**\n\n"
            f"> مدیریت قفل پی‌وی، آنتی‌اسپم و فیلتر فوروارد."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"قفل پی‌وی: {st('pv_lock')}", callback_data=f"hlp_pv_{uid}"),
                InlineKeyboardButton(f"آنتی‌اسپم: {st('anti_flood')}", callback_data=f"hlp_flood_{uid}")
            ],
            [
                InlineKeyboardButton(f"حذف فوروارد: {st('no_forward')}", callback_data=f"hlp_nofwd_{uid}")
            ],
            [
                InlineKeyboardButton("❮ بازگشت به منوی اصلی", callback_data=f"hlp_back_{uid}")
            ]
        ])
        return text, kb

    elif page == "cat_asst":
        text = (
            f"**بخش دستیار و واکنش**\n\n"
            f"> تنظیمات منشی خودکار و واکنش به لیست دشمن."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"منشی خودکار: {st('away_mode')}", callback_data=f"hlp_away_{uid}")
            ],
            [
                InlineKeyboardButton("❮ بازگشت به منوی اصلی", callback_data=f"hlp_back_{uid}")
            ]
        ])
        return text, kb

    elif page == "cat_txt":
        text = (
            f"**بخش استایل متن و رفتار**\n\n"
            f"> تایپینگ، سین خودکار و فرمت خودکار پیام‌ها."
        )
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"تایپینگ: {st('typing_mode')}", callback_data=f"hlp_type_{uid}"),
                InlineKeyboardButton(f"سین خودکار: {st('auto_read')}", callback_data=f"hlp_read_{uid}")
            ],
            [
                InlineKeyboardButton(f"متن ضخیم: {st('bold_mode')}", callback_data=f"hlp_bold_{uid}"),
                InlineKeyboardButton(f"متن کج: {st('italic_mode')}", callback_data=f"hlp_ital_{uid}")
            ],
            [
                InlineKeyboardButton(f"اسپویلر: {st('spoiler_mode')}", callback_data=f"hlp_spoil_{uid}")
            ],
            [
                InlineKeyboardButton("❮ بازگشت به منوی اصلی", callback_data=f"hlp_back_{uid}")
            ]
        ])
        return text, kb

    elif page == "cmds":
        text = (
            "**دستورات سریع سلف‌بات**\n\n"
            "> **مدیریت و حساب**\n"
            "> • `پنل` یا `.panel` — باز کردن پنل\n"
            "> • `.bal` یا `موجودی` — موجودی و آمار\n"
            "> • `.ping` — سرعت اتصال\n"
            "> • `.info` — مشخصات کاربر (با ریپلای)\n"
            "> • `.save` — ذخیره پیام یا مدیای تایمردار (با ریپلای)\n\n"
            "> **کنترل دسترسی (با ریپلای)**\n"
            "> • `.ok` / `.unok` — تایید یا لغو عبور از قفل پی‌وی\n"
            "> • `.mute` / `.unmute` — حذف خودکار پیام‌های کاربر\n"
            "> • `.enemy` / `.unenemy` — واکنش خودکار به کاربر\n"
            "> • `.block` / `.unblock` — مسدود یا آزاد کردن کاربر\n\n"
            "> **ابزارها**\n"
            "> • `.setaway متن` — متن پاسخ منشی\n"
            "> • `.setenemy متن` — متن واکنش خودکار\n"
            "> • `.purge 10` — حذف پیام‌های ارسالی اخیر\n"
            "> • `.calc 15*4` — محاسبه‌گر\n"
            "> • `.font متن` — فونت انگلیسی\n"
            "> • `.spam 5 متن` — ارسال متوالی"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("❮ بازگشت به منوی اصلی", callback_data=f"hlp_back_{uid}")]
        ])
        return text, kb

@manager_bot.on_inline_query()
async def helper_inline_handler(client: Client, inline_query: InlineQuery):
    uid = inline_query.from_user.id
    q = inline_query.query.strip().lower()

    if q.startswith("panel"):
        if uid not in ACTIVE_CLIENTS:
            await inline_query.answer([
                InlineQueryResultArticle(
                    title="سلف‌بات خاموش است",
                    description="ابتدا در ربات مدیریت سلف خود را روشن کنید.",
                    input_message_content=InputTextMessageContent("> **سلف‌بات شما در حال حاضر غیرفعال است.**")
                )
            ], cache_time=1)
            return

        text, kb = build_self_panel_ui(uid, "main")
        await inline_query.answer([
            InlineQueryResultArticle(
                title="کنترل پنل پیشرفته سلف‌بات",
                description="مدیریت دسته‌بندی‌شده ساعت، امنیت، منشی و تنظیمات",
                input_message_content=InputTextMessageContent(text),
                reply_markup=kb
            )
        ], cache_time=1)

# ================= توقف سلف کاربر =================
async def disconnect_user_self(target_uid: int, remove_session: bool = False):
    if target_uid in TIME_TASKS:
        TIME_TASKS[target_uid].cancel()
        del TIME_TASKS[target_uid]
    if target_uid in ACTIVE_CLIENTS:
        try:
            await ACTIVE_CLIENTS[target_uid].stop()
        except Exception:
            pass
        del ACTIVE_CLIENTS[target_uid]
    if remove_session:
        session_file = os.path.join(SESSIONS_DIR, f"user_{target_uid}.session")
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except Exception:
                pass

# ================= موتور کسر الماس ساعتی =================
async def billing_worker():
    while True:
        await asyncio.sleep(60)
        now = time.time()
        cost = SYS_CFG.get("hourly_cost", 2)
        for uid in list(ACTIVE_CLIENTS.keys()):
            u_data = get_user(uid)
            last_charge = u_data.get("last_charge", 0.0)
            if now - last_charge >= 3600:
                if u_data["diamonds"] >= cost:
                    u_data["diamonds"] -= cost
                    u_data["last_charge"] = now
                    save_data(USERS_DB)
                    try:
                        await manager_bot.send_message(
                            uid,
                            f"**تمدید ساعتی سلف‌بات**\n\n"
                            f"> **کسر شده:** `{cost}` الماس\n"
                            f"> **موجودی باقیمانده:** `{u_data['diamonds']}` الماس"
                        )
                    except Exception:
                        pass
                else:
                    await disconnect_user_self(uid, remove_session=False)
                    try:
                        await manager_bot.send_message(
                            uid,
                            f"**پایان موجودی سلف‌بات**\n\n"
                            f"> موجودی شما برای تمدید ساعتی (`{cost}` الماس) کافی نیست. سلف‌بات متوقف شد."
                        )
                    except Exception:
                        pass

# ================= تسک ساعت زنده =================
async def clock_worker(uid: int, app: Client):
    last_stamp = ""
    while uid in ACTIVE_CLIENTS:
        try:
            cfg = get_user(uid)
            if cfg.get("time_name") or cfg.get("time_bio"):
                now = datetime.now(ZoneInfo("Asia/Tehran"))
                current_minute = now.strftime("%H:%M")
                style_id = cfg.get("font_style", 1)
                stamp = f"{current_minute}_{style_id}"
                if stamp != last_stamp:
                    last_stamp = stamp
                    styled = format_clock(current_minute, style_id)
                    if cfg.get("time_name"):
                        base = cfg.get("orig_name") or "User"
                        await app.update_profile(first_name=f"{base} | {styled}")
                    if cfg.get("time_bio"):
                        base_bio = cfg.get("orig_bio") or ""
                        new_bio = f"{base_bio} | {styled}".strip()[:70]
                        await app.update_profile(bio=new_bio)
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 2)
        except Exception:
            pass
        await asyncio.sleep(10)

# ================= هسته دستورات و قابلیت‌های سلف‌بات =================
PV_FLOOD_TRACKER = {}

def register_self_handlers(app: Client, owner_id: int):
    @app.on_message(~filters.me & ~filters.bot, group=1)
    async def incoming_guard(client: Client, message: Message):
        cfg = get_user(owner_id)
        sender = message.from_user
        if not sender:
            return

        if cfg.get("auto_read"):
            try:
                await client.read_chat_history(message.chat.id)
            except Exception:
                pass

        if sender.id in cfg.get("enemies", []):
            try:
                await message.reply_text(cfg.get("enemy_text", "پیام شما در لیست فیلتر قرار دارد."))
            except Exception:
                pass

        if message.chat.type.value == "private":
            if sender.id in cfg.get("muted_users", []):
                try:
                    await message.delete()
                except Exception:
                    pass
                return

            if cfg.get("no_forward") and (message.forward_date or message.forward_from or message.forward_from_chat):
                if sender.id not in cfg.get("approved_users", []):
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    return

            if cfg.get("anti_flood") and sender.id not in cfg.get("approved_users", []):
                now_t = time.time()
                key = (owner_id, sender.id)
                hist = [t for t in PV_FLOOD_TRACKER.get(key, []) if now_t - t < 10]
                hist.append(now_t)
                PV_FLOOD_TRACKER[key] = hist
                if len(hist) > 5:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    return

            if cfg.get("pv_lock"):
                if not sender.is_contact and sender.id not in cfg.get("approved_users", []):
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    return

            if cfg.get("away_mode"):
                try:
                    await message.reply_text(f"> {cfg.get('away_text')}")
                except Exception:
                    pass

    @app.on_message(filters.me & filters.text, group=2)
    async def self_commands(client: Client, message: Message):
        text = message.text.strip()
        cmd = text.lower()
        cfg = get_user(owner_id)

        if cfg.get("typing_mode"):
            try:
                await client.send_chat_action(message.chat.id, "typing")
            except Exception:
                pass

        if cmd in [".panel", "پنل", "راهنما", ".help"]:
            if HELPER_USERNAME:
                try:
                    results = await client.get_inline_bot_results(HELPER_USERNAME, f"panel_{owner_id}")
                    if results.results:
                        await message.delete()
                        await client.send_inline_bot_result(
                            message.chat.id,
                            results.query_id,
                            results.results[0].id
                        )
                        return
                except Exception:
                    pass
            panel_txt, _ = build_self_panel_ui(owner_id, "cmds")
            await message.edit_text(panel_txt)
            return

        elif cmd in [".bal", "موجودی"]:
            await message.edit_text(
                f"**وضعیت حساب**\n\n"
                f"> **موجودی:** `{cfg['diamonds']}` الماس\n"
                f"> **آمار بازی:** `{cfg.get('wins', 0)}` برد / `{cfg.get('losses', 0)}` باخت\n"
                f"> **تعرفه ساعتی:** `{SYS_CFG['hourly_cost']}` الماس"
            )
            return

        elif cmd in [".ping", "پینگ"]:
            start = time.time()
            await message.edit_text("...")
            ms = round((time.time() - start) * 1000, 2)
            await message.edit_text(f"> **پینگ اتصال:** `{ms} ms`")
            return

        elif cmd.startswith(".purge"):
            parts = cmd.split()
            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
            limit = min(limit, 50)
            deleted = 0
            async for msg in client.get_chat_history(message.chat.id, limit=limit + 5):
                if msg.from_user and msg.from_user.id == owner_id:
                    try:
                        await msg.delete()
                        deleted += 1
                        if deleted >= limit:
                            break
                    except Exception:
                        pass
            return

        elif cmd == ".mute":
            target_id = message.reply_to_message.from_user.id if message.reply_to_message else message.chat.id
            if target_id == owner_id:
                return
            if target_id not in cfg["muted_users"]:
                cfg["muted_users"].append(target_id)
                save_data(USERS_DB)
            await message.edit_text(f"> کاربر `{target_id}` در **لیست سکوت** ثبت شد.")
            return

        elif cmd == ".unmute":
            target_id = message.reply_to_message.from_user.id if message.reply_to_message else message.chat.id
            if target_id in cfg["muted_users"]:
                cfg["muted_users"].remove(target_id)
                save_data(USERS_DB)
            await message.edit_text(f"> کاربر `{target_id}` از **لیست سکوت** خارج شد.")
            return

        elif cmd == ".enemy":
            if not message.reply_to_message or not message.reply_to_message.from_user:
                await message.edit_text("> روی پیام کاربر مورد نظر **ریپلای** کنید.")
                return
            target_id = message.reply_to_message.from_user.id
            if target_id == owner_id:
                return
            if target_id not in cfg["enemies"]:
                cfg["enemies"].append(target_id)
                save_data(USERS_DB)
            await message.edit_text(f"> واکنش خودکار برای `{target_id}` **فعال** شد.")
            return

        elif cmd == ".unenemy":
            if not message.reply_to_message or not message.reply_to_message.from_user:
                await message.edit_text("> روی پیام کاربر مورد نظر **ریپلای** کنید.")
                return
            target_id = message.reply_to_message.from_user.id
            if target_id in cfg["enemies"]:
                cfg["enemies"].remove(target_id)
                save_data(USERS_DB)
            await message.edit_text(f"> واکنش خودکار برای `{target_id}` **غیرفعال** شد.")
            return

        elif cmd.startswith(".setenemy "):
            new_txt = text.split(" ", 1)[1].strip()
            cfg["enemy_text"] = new_txt
            save_data(USERS_DB)
            await message.edit_text("> **متن واکنش خودکار** به‌روزرسانی شد.")
            return

        elif cmd == ".block":
            target_id = message.reply_to_message.from_user.id if message.reply_to_message else message.chat.id
            if target_id != owner_id:
                await client.block_user(target_id)
                await message.edit_text(f"> کاربر `{target_id}` **مسدود** شد.")
            return

        elif cmd == ".unblock":
            target_id = message.reply_to_message.from_user.id if message.reply_to_message else message.chat.id
            if target_id != owner_id:
                await client.unblock_user(target_id)
                await message.edit_text(f"> مسدودیت کاربر `{target_id}` **لغو** شد.")
            return

        elif cmd == ".ok":
            target_id = message.reply_to_message.from_user.id if message.reply_to_message else message.chat.id
            if target_id not in cfg["approved_users"]:
                cfg["approved_users"].append(target_id)
                save_data(USERS_DB)
            await message.edit_text(f"> دسترسی پی‌وی برای `{target_id}` **تایید** شد.")
            return

        elif cmd == ".unok":
            target_id = message.reply_to_message.from_user.id if message.reply_to_message else message.chat.id
            if target_id in cfg["approved_users"]:
                cfg["approved_users"].remove(target_id)
                save_data(USERS_DB)
            await message.edit_text(f"> دسترسی پی‌وی برای `{target_id}` **لغو** شد.")
            return

        elif cmd.startswith(".setaway "):
            new_txt = text.split(" ", 1)[1].strip()
            cfg["away_text"] = new_txt
            save_data(USERS_DB)
            await message.edit_text("> **متن منشی خودکار** ذخیره شد.")
            return

        elif cmd in [".save", "ذخیره"]:
            if not message.reply_to_message:
                await message.edit_text("> روی پیام یا مدیای مورد نظر **ریپلای** کنید.")
                return
            await message.delete()
            rep = message.reply_to_message
            try:
                await rep.copy("me")
            except Exception:
                file_path = await client.download_media(rep)
                if file_path:
                    await client.send_document("me", file_path)
                    os.remove(file_path)
            return

        elif cmd in [".id", ".info", "ایدی"]:
            if message.reply_to_message and message.reply_to_message.from_user:
                u = message.reply_to_message.from_user
                uname = f"@{u.username}" if u.username else "—"
                await message.edit_text(
                    f"**مشخصات کاربر**\n\n"
                    f"> **نام:** {u.first_name}\n"
                    f"> **یوزرنیم:** {uname}\n"
                    f"> **شناسه:** `{u.id}`"
                )
            else:
                await message.edit_text(f"> **شناسه شما:** `{owner_id}`\n> **شناسه چت:** `{message.chat.id}`")
            return

        elif cmd.startswith(".font "):
            raw = text.split(" ", 1)[1]
            src = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
            dst = "𝒶𝒷𝒸𝒹𝑒𝒻𝑔𝒽𝒾𝒿𝓀𝓁𝓂𝓃𝑜𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏𝒜ℬ𝒞𝒟ℰℱ𝒢𝒋ℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵"
            await message.edit_text(raw.translate(str.maketrans(src, dst)))
            return

        elif cmd.startswith(".calc "):
            expr = text.split(" ", 1)[1].strip()
            if not all(c in set("0123456789+-*/().% ") for c in expr):
                await message.edit_text("> عبارت نامعتبر است.")
                return
            try:
                res = eval(expr, {"__builtins__": None}, {})
                await message.edit_text(f"> `{expr}` = **{res}**")
            except Exception:
                await message.edit_text("> خطا در محاسبه.")
            return

        elif cmd.startswith(".spam "):
            parts = text.split(" ", 2)
            if len(parts) < 3 or not parts[1].isdigit():
                await message.edit_text("> **فرمت صحیح:** `.spam 5 متن`")
                return
            count = min(int(parts[1]), 15)
            msg_body = parts[2]
            await message.delete()
            for _ in range(count):
                await client.send_message(message.chat.id, msg_body)
                await asyncio.sleep(0.45)
            return

        if not text.startswith(".") and not text.startswith("/"):
            try:
                if cfg.get("spoiler_mode"):
                    await message.edit_text(f"||{text}||")
                elif cfg.get("bold_mode"):
                    await message.edit_text(f"**{text}**")
                elif cfg.get("italic_mode"):
                    await message.edit_text(f"__{text}__")
            except Exception:
                pass

# ================= بخش گروهی: دوئل + انتقال الماس با ریپلای =================
def build_bet_keyboard(bet_id: str, p1_bal: int, amount: int, p2_bal: int = None, finished: bool = False):
    if not finished:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"موجودی میزبان: {p1_bal} 💎", callback_data=f"ginfo_{bet_id}"),
                InlineKeyboardButton(f"مبلغ شرط: {amount} 💎", callback_data=f"ginfo_{bet_id}")
            ],
            [
                InlineKeyboardButton(f"قبول چالش ({amount} 💎)", callback_data=f"gbet_{bet_id}"),
                InlineKeyboardButton("لغو", callback_data=f"gcanc_{bet_id}")
            ]
        ])
    else:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"میزبان: {p1_bal} 💎", callback_data="noop"),
                InlineKeyboardButton(f"حریف: {p2_bal} 💎", callback_data="noop")
            ]
        ])

@manager_bot.on_message(filters.group & filters.text)
async def group_commands(client: Client, message: Message):
    if not message.from_user or not message.text:
        return
    uid = message.from_user.id
    if uid in SYS_CFG.get("banned_users", []):
        return

    text = message.text.strip()
    persian_to_en = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
    norm_text = text.translate(persian_to_en)

    if norm_text == "موجودی":
        u_data = get_user(uid)
        await message.reply_text(
            f"**{message.from_user.first_name}**",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"موجودی: {u_data['diamonds']} 💎", callback_data="noop"),
                    InlineKeyboardButton(f"برد: {u_data.get('wins', 0)} | باخت: {u_data.get('losses', 0)}", callback_data="noop")
                ]
            ])
        )
        return

    if norm_text.startswith("انتقال ") or (norm_text.startswith("+") and norm_text[1:].isdigit()):
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.reply_text("برای انتقال الماس، روی پیام کاربر مورد نظر ریپلای کنید (مثال: `انتقال 50`).")
            return

        target_user = message.reply_to_message.from_user
        if target_user.is_bot:
            await message.reply_text("انتقال به ربات امکان‌پذیر نیست.")
            return
        if target_user.id == uid:
            await message.reply_text("انتقال به حساب خودتان مجاز نیست.")
            return

        amt_str = norm_text.replace("انتقال ", "").replace("+", "").strip()
        if not amt_str.isdigit() or int(amt_str) <= 0:
            return

        amount = int(amt_str)
        sender_data = get_user(uid)
        if sender_data["diamonds"] < amount:
            await message.reply_text(
                f"موجودی شما کافی نیست.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"موجودی فعلی: {sender_data['diamonds']} 💎", callback_data="noop")]
                ])
            )
            return

        receiver_data = get_user(target_user.id)
        sender_data["diamonds"] -= amount
        receiver_data["diamonds"] += amount
        save_data(USERS_DB)

        await message.reply_text(
            f"**انتقال الماس انجام شد**\n\n"
            f"از: {message.from_user.first_name}\n"
            f"به: {target_user.first_name}\n"
            f"مبلغ: **`{amount}` الماس**",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(f"{message.from_user.first_name}: {sender_data['diamonds']} 💎", callback_data="noop"),
                    InlineKeyboardButton(f"{target_user.first_name}: {receiver_data['diamonds']} 💎", callback_data="noop")
                ]
            ])
        )
        return

    if norm_text.startswith("بازی "):
        if SYS_CFG.get("maintenance") and uid != ROOT_ADMIN:
            await message.reply_text("سیستم موقتاً در حال بروزرسانی است.")
            return

        parts = norm_text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            return
        amount = int(parts[1])
        min_b = SYS_CFG.get("min_bet", 1)
        max_b = SYS_CFG.get("max_bet", 10000)

        if amount < min_b or amount > max_b:
            await message.reply_text(f"مبلغ شرط باید بین `{min_b}` تا `{max_b}` الماس باشد.")
            return

        p1_name = message.from_user.first_name
        p1_data = get_user(uid)

        if p1_data["diamonds"] < amount:
            await message.reply_text(
                f"موجودی شما برای ثبت این شرط کافی نیست.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"موجودی فعلی: {p1_data['diamonds']} 💎", callback_data="noop")]
                ])
            )
            return

        bet_id = f"{message.chat.id}_{uid}_{int(time.time())}"
        GROUP_BETS[bet_id] = {
            "p1": uid,
            "p1_name": p1_name,
            "amount": amount,
            "chat_id": message.chat.id
        }

        await message.reply_text(
            f"**دوئل الماس**\n\n"
            f"میزبان: **{p1_name}**\n"
            f"ورودی: `{amount}` الماس\n"
            f"جایزه: **`{amount * 2}` الماس**",
            reply_markup=build_bet_keyboard(bet_id, p1_data["diamonds"], amount, finished=False)
        )

# ================= منوی اصلی کاربران =================
def main_keyboard(user_id: int):
    is_active = user_id in ACTIVE_CLIENTS
    cost = SYS_CFG.get("hourly_cost", 2)
    buttons = []
    if is_active:
        buttons.append([InlineKeyboardButton("توقف و خاموش کردن سلف", callback_data="stop_self")])
    else:
        buttons.append([InlineKeyboardButton(f"فعال‌سازی سلف‌بات ({cost} 💎 / ساعت)", callback_data="start_install")])

    buttons.append([
        InlineKeyboardButton("کیف پول و آمار", callback_data="my_balance"),
        InlineKeyboardButton("انتقال الماس", callback_data="transfer_diamond")
    ])
    buttons.append([
        InlineKeyboardButton("ثبت کد هدیه", callback_data="redeem_gift"),
        InlineKeyboardButton("راهنمای استفاده", callback_data="user_guide")
    ])

    if user_id == ROOT_ADMIN:
        buttons.append([InlineKeyboardButton("پنل مدیریت کل", callback_data="admin_panel")])

    return InlineKeyboardMarkup(buttons)

def get_system_stats():
    try:
        ram = f"{psutil.virtual_memory().percent}%"
    except Exception:
        ram = "—"
    try:
        cpu = f"{psutil.cpu_percent()}%"
    except Exception:
        cpu = "—"
    return cpu, ram

def build_admin_panel():
    cpu, ram = get_system_stats()
    total_diamonds = sum(u.get("diamonds", 0) for u in USERS_DB.values())
    maint_status = "فعال" if SYS_CFG.get("maintenance") else "غیرفعال"
    cost = SYS_CFG.get("hourly_cost", 2)
    w_bonus = SYS_CFG.get("welcome_bonus", 0)

    win_rigged = sum(1 for u in USERS_DB.values() if u.get("rig_mode") == "win")
    lose_rigged = sum(1 for u in USERS_DB.values() if u.get("rig_mode") == "lose")

    btns = [
        [
            InlineKeyboardButton("افزودن الماس", callback_data="adm_add_diamond"),
            InlineKeyboardButton("کسر الماس", callback_data="adm_sub_diamond")
        ],
        [
            InlineKeyboardButton(f"وضعیت بازی کاربران (برد: {win_rigged} | باخت: {lose_rigged})", callback_data="adm_rig_menu")
        ],
        [
            InlineKeyboardButton("ساخت کد هدیه", callback_data="adm_make_gift"),
            InlineKeyboardButton("هدیه همگانی", callback_data="adm_gift_all")
        ],
        [
            InlineKeyboardButton("ارسال اطلاعیه", callback_data="adm_broadcast"),
            InlineKeyboardButton("پرونده کاربر", callback_data="adm_user_info")
        ],
        [
            InlineKeyboardButton(f"تعرفه: {cost} 💎", callback_data="adm_set_cost"),
            InlineKeyboardButton(f"هدیه ورود: {w_bonus} 💎", callback_data="adm_set_bonus")
        ],
        [
            InlineKeyboardButton("سقف شرط‌بندی", callback_data="adm_bet_limits"),
            InlineKeyboardButton(f"تعمیرات: {maint_status}", callback_data="adm_toggle_maint")
        ],
        [
            InlineKeyboardButton("مسدود / آزادسازی", callback_data="adm_ban_toggle"),
            InlineKeyboardButton(f"سلف‌های فعال ({len(ACTIVE_CLIENTS)})", callback_data="adm_active_list")
        ],
        [
            InlineKeyboardButton("بروزرسانی", callback_data="admin_panel"),
            InlineKeyboardButton("منوی اصلی", callback_data="back_main")
        ]
    ]

    text = (
        f"**داشبورد مدیریت کل**\n\n"
        f"> **کاربران ثبت‌شده:** `{len(USERS_DB)}`\n"
        f"> **سلف‌های آنلاین:** `{len(ACTIVE_CLIENTS)}`\n"
        f"> **کل موجودی کاربران:** `{total_diamonds}` الماس\n"
        f"> **کل رقابت‌ها:** `{SYS_CFG.get('total_games', 0)}` دست (`{SYS_CFG.get('total_volume', 0)}` 💎)\n"
        f"> **کدهای هدیه فعال:** `{len(SYS_CFG.get('gift_codes', {}))}`\n"
        f"> **وضعیت سرور:** CPU `{cpu}` | RAM `{ram}`\n"
        f"> **زمان:** `{datetime.now(ZoneInfo('Asia/Tehran')).strftime('%H:%M:%S')}`"
    )
    return text, InlineKeyboardMarkup(btns)

@manager_bot.on_message(filters.private & filters.command("start"))
async def start_cmd(client: Client, message: Message):
    uid = message.from_user.id
    if uid in SYS_CFG.get("banned_users", []) and uid != ROOT_ADMIN:
        await message.reply_text("دسترسی شما به این ربات محدود شده است.")
        return

    USER_STATES.pop(uid, None)
    u_data = get_user(uid)
    cost = SYS_CFG.get("hourly_cost", 2)
    status_txt = "فعال" if uid in ACTIVE_CLIENTS else "خاموش"

    await message.reply_text(
        f"**سلام {message.from_user.first_name}**\n\n"
        f"موجودی کیف پول: **`{u_data['diamonds']}` الماس**\n"
        f"وضعیت سلف‌بات: `{status_txt}`\n"
        f"تعرفه استفاده: `{cost}` الماس در ساعت\n\n"
        f"از منوی زیر حساب خود را مدیریت کنید:",
        reply_markup=main_keyboard(uid)
    )

@manager_bot.on_callback_query()
async def handle_callbacks(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    data = query.data
    u_data = get_user(uid)

    if data == "noop":
        await query.answer()
        return

    if uid in SYS_CFG.get("banned_users", []) and uid != ROOT_ADMIN:
        await query.answer("حساب شما مسدود است.", show_alert=True)
        return

    if data == "user_guide":
        await query.answer()
        guide_txt = (
            "**راهنمای استفاده**\n\n"
            "**۱. فعال‌سازی سلف‌بات**\n"
            "• روی دکمه **فعال‌سازی سلف‌بات** بزنید و شماره خود را وارد کنید.\n"
            "• کد تایید ارسال‌شده به تلگرام را **با فاصله بین اعداد** بفرستید (مثال: `1 2 3 4 5`).\n\n"
            "**۲. کنترل پنل در چت‌ها**\n"
            "• پس از اتصال، در هر چت یا گروهی کلمه `پنل` را بفرستید تا پنل شیشه‌ای باز شود.\n\n"
            "**۳. دوئل و انتقال الماس در گروه**\n"
            "• برای دوئل در گروه عبارت `بازی 20` را بفرستید.\n"
            "• برای انتقال الماس در گروه، روی پیام فرد ریپلای کرده و بنویسید `انتقال 50`."
        )
        await query.message.edit_text(
            guide_txt,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_main")]])
        )
        return

    # --- دکمه‌های پنل اینلاین هلپر ---
    if data.startswith("hlp_"):
        if data.startswith("hlp_cat_"):
            await query.answer()
            cat = data.split("_")[2]
            text, kb = build_self_panel_ui(uid, f"cat_{cat}")
            await query.edit_message_text(text, reply_markup=kb)
            return

        parts = data.split("_")
        action = parts[1]
        owner_id = int(parts[2])
        if uid != owner_id:
            await query.answer("این پنل متعلق به شما نیست.", show_alert=True)
            return
        if owner_id not in ACTIVE_CLIENTS:
            await query.answer("سلف‌بات شما خاموش است.", show_alert=True)
            return

        cfg = get_user(owner_id)
        app = ACTIVE_CLIENTS[owner_id]

        if action == "tname":
            cfg["time_name"] = not cfg.get("time_name", False)
            if cfg["time_name"] and not cfg.get("orig_name"):
                me = await app.get_me()
                cfg["orig_name"] = me.first_name or "User"
            elif not cfg["time_name"] and cfg.get("orig_name"):
                await app.update_profile(first_name=cfg["orig_name"])
            save_data(USERS_DB)
            await query.answer("ساعت نام تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_time")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "tbio":
            cfg["time_bio"] = not cfg.get("time_bio", False)
            if cfg["time_bio"] and not cfg.get("orig_bio"):
                chat = await app.get_chat("me")
                cfg["orig_bio"] = chat.bio or ""
            elif not cfg["time_bio"]:
                await app.update_profile(bio=cfg.get("orig_bio", ""))
            save_data(USERS_DB)
            await query.answer("ساعت بیو تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_time")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "font":
            cur = cfg.get("font_style", 1)
            nxt = 1 if cur >= len(FONT_STYLES) else cur + 1
            cfg["font_style"] = nxt
            save_data(USERS_DB)
            await query.answer(f"فونت: {FONT_STYLES[nxt][1]}")
            text, kb = build_self_panel_ui(owner_id, "cat_time")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "pv":
            cfg["pv_lock"] = not cfg.get("pv_lock", False)
            save_data(USERS_DB)
            await query.answer("قفل پی‌وی تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_sec")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "away":
            cfg["away_mode"] = not cfg.get("away_mode", False)
            save_data(USERS_DB)
            await query.answer("وضعیت منشی تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_asst")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "flood":
            cfg["anti_flood"] = not cfg.get("anti_flood", False)
            save_data(USERS_DB)
            await query.answer("آنتی‌اسپم پی‌وی تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_sec")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "nofwd":
            cfg["no_forward"] = not cfg.get("no_forward", False)
            save_data(USERS_DB)
            await query.answer("فیلتر فوروارد تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_sec")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "type":
            cfg["typing_mode"] = not cfg.get("typing_mode", False)
            save_data(USERS_DB)
            await query.answer("حالت تایپینگ تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_txt")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "read":
            cfg["auto_read"] = not cfg.get("auto_read", False)
            save_data(USERS_DB)
            await query.answer("سین خودکار تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_txt")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "bold":
            cfg["bold_mode"] = not cfg.get("bold_mode", False)
            if cfg["bold_mode"]:
                cfg["italic_mode"] = False
                cfg["spoiler_mode"] = False
            save_data(USERS_DB)
            await query.answer("حالت متن ضخیم تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_txt")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "ital":
            cfg["italic_mode"] = not cfg.get("italic_mode", False)
            if cfg["italic_mode"]:
                cfg["bold_mode"] = False
                cfg["spoiler_mode"] = False
            save_data(USERS_DB)
            await query.answer("حالت متن کج تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_txt")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "spoil":
            cfg["spoiler_mode"] = not cfg.get("spoiler_mode", False)
            if cfg["spoiler_mode"]:
                cfg["bold_mode"] = False
                cfg["italic_mode"] = False
            save_data(USERS_DB)
            await query.answer("حالت اسپویلر تغییر کرد.")
            text, kb = build_self_panel_ui(owner_id, "cat_txt")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "cmds":
            await query.answer()
            text, kb = build_self_panel_ui(owner_id, "cmds")
            await query.edit_message_text(text, reply_markup=kb)
            return

        elif action == "close":
            await query.answer("پنل بسته شد.")
            await query.edit_message_text("پنل بسته شد.")
            return

        text, kb = build_self_panel_ui(owner_id, "main")
        await query.edit_message_text(text, reply_markup=kb)
        return

    # --- اطلاعات میز بازی ---
    if data.startswith("ginfo_"):
        bet_id = data.replace("ginfo_", "")
        bet = GROUP_BETS.get(bet_id)
        if not bet:
            await query.answer("این میز بازی بسته شده است.", show_alert=True)
            return
        p1_bal = get_user(bet["p1"])["diamonds"]
        await query.answer(
            f"میزبان: {bet['p1_name']} ({p1_bal} الماس)\n"
            f"ورودی بازی: {bet['amount']} الماس\n"
            f"موجودی شما: {u_data['diamonds']} الماس",
            show_alert=True
        )
        return

    # --- پذیرش شرط‌بندی گروهی ---
    if data.startswith("gbet_"):
        bet_id = data.replace("gbet_", "")
        bet = GROUP_BETS.get(bet_id)
        if not bet:
            await query.answer("این میز بازی قبلاً انجام یا لغو شده است.", show_alert=True)
            return

        p1_id = bet["p1"]
        p1_name = bet["p1_name"]
        amount = bet["amount"]
        p2_id = uid
        p2_name = query.from_user.first_name

        if p2_id == p1_id:
            await query.answer("شما میزبان این بازی هستید.", show_alert=True)
            return

        p1_data = get_user(p1_id)
        p2_data = get_user(p2_id)

        if p1_data["diamonds"] < amount:
            GROUP_BETS.pop(bet_id, None)
            await query.message.edit_text(f"بازی لغو شد؛ موجودی **{p1_name}** کافی نیست.")
            return

        if p2_data["diamonds"] < amount:
            await query.answer(
                f"موجودی شما ({p2_data['diamonds']} الماس) برای ورود به این بازی کافی نیست.",
                show_alert=True
            )
            return

        GROUP_BETS.pop(bet_id, None)

        p1_data["diamonds"] -= amount
        p2_data["diamonds"] -= amount

        p1_mode = p1_data.get("rig_mode", "normal")
        p2_mode = p2_data.get("rig_mode", "normal")

        score_map = {"win": 1, "normal": 0, "lose": -1}
        s1 = score_map.get(p1_mode, 0)
        s2 = score_map.get(p2_mode, 0)

        if s1 > s2:
            winner_id, winner_name = p1_id, p1_name
            loser_id, loser_name = p2_id, p2_name
        elif s2 > s1:
            winner_id, winner_name = p2_id, p2_name
            loser_id, loser_name = p1_id, p1_name
        else:
            if random.choice([True, False]):
                winner_id, winner_name = p1_id, p1_name
                loser_id, loser_name = p2_id, p2_name
            else:
                winner_id, winner_name = p2_id, p2_name
                loser_id, loser_name = p1_id, p1_name

        winner_data = get_user(winner_id)
        loser_data = get_user(loser_id)

        prize = amount * 2
        winner_data["diamonds"] += prize
        winner_data["wins"] = winner_data.get("wins", 0) + 1
        loser_data["losses"] = loser_data.get("losses", 0) + 1

        SYS_CFG["total_games"] = SYS_CFG.get("total_games", 0) + 1
        SYS_CFG["total_volume"] = SYS_CFG.get("total_volume", 0) + prize
        save_sys(SYS_CFG)
        save_data(USERS_DB)

        await query.message.edit_text(
            f"**نتیجه دوئل**\n\n"
            f"برنده: **{winner_name}** (`+{prize}` 💎)\n"
            f"بازنده: **{loser_name}** (`-{amount}` 💎)",
            reply_markup=build_bet_keyboard(bet_id, p1_data["diamonds"], amount, p2_data["diamonds"], finished=True)
        )
        return

    elif data.startswith("gcanc_"):
        bet_id = data.replace("gcanc_", "")
        bet = GROUP_BETS.get(bet_id)
        if not bet:
            await query.answer("این بازی فعال نیست.", show_alert=True)
            return
        if uid != bet["p1"] and uid != ROOT_ADMIN:
            await query.answer("فقط میزبان می‌تواند بازی را لغو کند.", show_alert=True)
            return
        GROUP_BETS.pop(bet_id, None)
        await query.message.edit_text(f"میز بازی توسط **{bet['p1_name']}** لغو شد.")
        return

    # --- منوی کاربری ---
    if data == "start_install":
        if SYS_CFG.get("maintenance") and uid != ROOT_ADMIN:
            await query.answer("سیستم موقتاً در حال بروزرسانی است.", show_alert=True)
            return
        if uid in ACTIVE_CLIENTS:
            await query.answer("سلف‌بات شما فعال است.", show_alert=True)
            return

        cost = SYS_CFG.get("hourly_cost", 2)
        if u_data["diamonds"] < cost:
            await query.answer(
                f"موجودی کافی نیست. حداقل به {cost} الماس نیاز دارید.",
                show_alert=True
            )
            return

        session_file = os.path.join(SESSIONS_DIR, f"user_{uid}.session")
        if os.path.exists(session_file):
            try:
                session_path = os.path.join(SESSIONS_DIR, f"user_{uid}")
                app = Client(
                    session_path,
                    api_id=API_ID,
                    api_hash=API_HASH,
                    device_model="Samsung Galaxy S24",
                    system_version="Android 14",
                    app_version="11.4.2"
                )
                await app.start()
                u_data["diamonds"] -= cost
                u_data["last_charge"] = time.time()
                save_data(USERS_DB)
                register_self_handlers(app, uid)
                ACTIVE_CLIENTS[uid] = app
                TIME_TASKS[uid] = asyncio.create_task(clock_worker(uid, app))
                await query.message.edit_text(
                    f"**سلف‌بات روشن شد**\n\n"
                    f"کسر شده: `{cost}` الماس\n"
                    f"موجودی باقیمانده: `{u_data['diamonds']}` الماس",
                    reply_markup=main_keyboard(uid)
                )
                return
            except Exception:
                if os.path.exists(session_file):
                    os.remove(session_file)

        USER_STATES[uid] = {"step": "awaiting_phone"}
        await query.message.edit_text(
            "**اتصال حساب — گام ۱ از ۳**\n\n"
            "شماره تلفن اکانت تلگرام خود را به همراه پیش‌شماره وارد کنید.\n"
            "مثال: `+989123456789`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("انصراف", callback_data="back_main")]])
        )

    elif data == "stop_self":
        await disconnect_user_self(uid, remove_session=False)
        await query.message.edit_text(
            "**سلف‌بات متوقف شد**\n\n"
            "کسر الماس ساعتی متوقف گردید.",
            reply_markup=main_keyboard(uid)
        )

    elif data == "my_balance":
        status = "فعال" if uid in ACTIVE_CLIENTS else "خاموش"
        await query.answer(
            f"موجودی: {u_data['diamonds']} الماس\n"
            f"آمار دوئل: {u_data.get('wins', 0)} برد / {u_data.get('losses', 0)} باخت\n"
            f"وضعیت سلف: {status}\n"
            f"شناسه شما: {uid}",
            show_alert=True
        )

    elif data == "transfer_diamond":
        if u_data["diamonds"] <= 0:
            await query.answer("موجودی الماس شما صفر است.", show_alert=True)
            return
        USER_STATES[uid] = {"step": "transfer_target"}
        await query.message.edit_text(
            "**انتقال الماس**\n\n"
            f"موجودی قابل انتقال: `{u_data['diamonds']}` الماس\n"
            "شناسه عددی (User ID) کاربر مقصد را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("انصراف", callback_data="back_main")]])
        )

    elif data == "redeem_gift":
        USER_STATES[uid] = {"step": "redeem_code"}
        await query.message.edit_text(
            "**ثبت کد هدیه**\n\n"
            "کد هدیه خود را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("انصراف", callback_data="back_main")]])
        )

    # ================= پنل مدیریت کل =================
    elif data == "admin_panel" and uid == ROOT_ADMIN:
        await query.answer()
        panel_text, panel_markup = build_admin_panel()
        await query.message.edit_text(panel_text, reply_markup=panel_markup)

    elif data == "adm_rig_menu" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_rig_uid"}
        special_lines = []
        for u_str, u_info in USERS_DB.items():
            rm = u_info.get("rig_mode", "normal")
            if rm == "win":
                special_lines.append(f"• `{u_str}` — برد حتمی")
            elif rm == "lose":
                special_lines.append(f"• `{u_str}` — باخت حتمی")
        special_txt = "\n".join(special_lines) if special_lines else "موردی ثبت نشده است."

        await query.message.edit_text(
            f"**تنظیم وضعیت بازی کاربران**\n\n"
            f"اکانت‌های دارای وضعیت خاص:\n{special_txt}\n\n"
            f"شناسه عددی کاربر مورد نظر را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data.startswith("setrig_") and uid == ROOT_ADMIN:
        parts = data.split("_")
        mode_choice = parts[1]
        target_id = int(parts[2])
        t_data = get_user(target_id)
        t_data["rig_mode"] = mode_choice
        save_data(USERS_DB)

        mode_names = {
            "win": "برد حتمی",
            "lose": "باخت حتمی",
            "normal": "عادی (۵۰-۵۰)"
        }
        await query.answer(f"وضعیت کاربر {target_id}: {mode_names[mode_choice]}", show_alert=True)
        panel_text, panel_markup = build_admin_panel()
        await query.message.edit_text(
            f"وضعیت بازی کاربر `{target_id}` به **{mode_names[mode_choice]}** تغییر یافت.\n\n" + panel_text,
            reply_markup=panel_markup
        )

    elif data == "adm_add_diamond" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_add_uid"}
        await query.message.edit_text(
            "**افزودن الماس**\n\nشناسه عددی کاربر را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data == "adm_sub_diamond" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_sub_uid"}
        await query.message.edit_text(
            "**کسر الماس**\n\nشناسه عددی کاربر را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data == "adm_make_gift" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_gift_amount"}
        await query.message.edit_text(
            "**ساخت کد هدیه**\n\nتعداد الماس کد هدیه را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data == "adm_gift_all" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_gift_all_val"}
        await query.message.edit_text(
            "**هدیه همگانی**\n\nتعداد الماس اهدایی به کل کاربران را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data == "adm_broadcast" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_broadcast_msg"}
        await query.message.edit_text(
            "**ارسال اطلاعیه همگانی**\n\nمتن پیام را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data == "adm_user_info" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_lookup_uid"}
        await query.message.edit_text(
            "**استعلام پرونده کاربر**\n\nشناسه عددی کاربر را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data == "adm_set_cost" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_new_cost"}
        await query.message.edit_text(
            f"**تغییر تعرفه ساعتی**\n\n"
            f"مقدار فعلی: `{SYS_CFG.get('hourly_cost', 2)}` الماس\n"
            f"مقدار جدید را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data == "adm_set_bonus" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_new_bonus"}
        await query.message.edit_text(
            f"**تغییر هدیه ثبت‌نام کاربران جدید**\n\n"
            f"مقدار فعلی: `{SYS_CFG.get('welcome_bonus', 0)}` الماس\n"
            f"مقدار جدید را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data == "adm_bet_limits" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_bet_range"}
        await query.message.edit_text(
            f"**تنظیم محدوده شرط‌بندی**\n\n"
            f"محدوده فعلی: `{SYS_CFG.get('min_bet', 1)}` تا `{SYS_CFG.get('max_bet', 10000)}` الماس\n"
            f"حداقل و حداکثر جدید را با فاصله وارد کنید (مثال: `5 500`):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data == "adm_toggle_maint" and uid == ROOT_ADMIN:
        SYS_CFG["maintenance"] = not SYS_CFG.get("maintenance", False)
        save_sys(SYS_CFG)
        await query.answer("وضعیت سیستم تغییر کرد.")
        panel_text, panel_markup = build_admin_panel()
        await query.message.edit_text(panel_text, reply_markup=panel_markup)

    elif data == "adm_ban_toggle" and uid == ROOT_ADMIN:
        await query.answer()
        USER_STATES[uid] = {"step": "adm_ban_uid"}
        await query.message.edit_text(
            "**مسدودسازی / آزادسازی کاربر**\n\nشناسه عددی کاربر را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel")]])
        )

    elif data == "adm_active_list" and uid == ROOT_ADMIN:
        await query.answer()
        btns = []
        for u in list(ACTIVE_CLIENTS.keys()):
            bal = get_user(u)["diamonds"]
            btns.append([InlineKeyboardButton(f"قطع اتصال {u} ({bal} 💎)", callback_data=f"kick_{u}")])
        btns.append([InlineKeyboardButton("بازگشت", callback_data="admin_panel")])
        await query.message.edit_text(
            f"**سلف‌های فعال ({len(ACTIVE_CLIENTS)})**\n\nبرای قطع اتصال هر اکانت روی آن بزنید:",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif data.startswith("kick_") and uid == ROOT_ADMIN:
        target_uid = int(data.split("_")[1])
        await disconnect_user_self(target_uid, remove_session=True)
        await query.answer(f"سلف کاربر {target_uid} قطع شد.", show_alert=True)
        panel_text, panel_markup = build_admin_panel()
        await query.message.edit_text(panel_text, reply_markup=panel_markup)

    elif data == "back_main":
        await query.answer()
        USER_STATES.pop(uid, None)
        status_txt = "فعال" if uid in ACTIVE_CLIENTS else "خاموش"
        await query.message.edit_text(
            f"**منوی اصلی**\n\n"
            f"موجودی کیف پول: **`{u_data['diamonds']}` الماس**\n"
            f"وضعیت سلف‌بات: `{status_txt}`",
            reply_markup=main_keyboard(uid)
        )

# ================= پردازش ورودی‌های متنی =================
@manager_bot.on_message(filters.private & filters.text & ~filters.command("start"))
async def text_router(client: Client, message: Message):
    uid = message.from_user.id
    if uid not in USER_STATES:
        return

    state = USER_STATES[uid]
    step = state["step"]
    text = message.text.strip()
    u_data = get_user(uid)

    if step == "adm_rig_uid" and uid == ROOT_ADMIN:
        if not text.isdigit():
            await message.reply_text("شناسه عددی نامعتبر است:")
            return
        tid = int(text)
        t_data = get_user(tid)
        cur_mode = t_data.get("rig_mode", "normal")
        mode_labels = {"win": "برد حتمی", "lose": "باخت حتمی", "normal": "عادی (۵۰-۵۰)"}
        USER_STATES.pop(uid, None)

        await message.reply_text(
            f"**وضعیت بازی کاربر `{tid}`**\n\n"
            f"وضعیت فعلی: `{mode_labels.get(cur_mode, 'عادی')}`",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("برد حتمی", callback_data=f"setrig_win_{tid}"),
                    InlineKeyboardButton("باخت حتمی", callback_data=f"setrig_lose_{tid}")
                ],
                [
                    InlineKeyboardButton("عادی (۵۰-۵۰)", callback_data=f"setrig_normal_{tid}")
                ],
                [
                    InlineKeyboardButton("بازگشت", callback_data="admin_panel")
                ]
            ])
        )
        return

    if step == "redeem_code":
        code_in = text.upper()
        gifts = SYS_CFG.get("gift_codes", {})
        if code_in not in gifts:
            await message.reply_text("کد هدیه نامعتبر است یا قبلاً استفاده شده است.", reply_markup=main_keyboard(uid))
            USER_STATES.pop(uid, None)
            return
        reward = gifts.pop(code_in)
        save_sys(SYS_CFG)
        u_data["diamonds"] += reward
        save_data(USERS_DB)
        USER_STATES.pop(uid, None)
        await message.reply_text(
            f"**کد هدیه ثبت شد**\n\n"
            f"دریافتی: `{reward}` الماس\n"
            f"موجودی فعلی: `{u_data['diamonds']}` الماس",
            reply_markup=main_keyboard(uid)
        )

    elif step == "transfer_target":
        if not text.isdigit():
            await message.reply_text("شناسه عددی نامعتبر است:")
            return
        target_id = int(text)
        if target_id == uid:
            await message.reply_text("انتقال به حساب خودتان مجاز نیست.")
            return
        if str(target_id) not in USERS_DB:
            await message.reply_text("کاربر مورد نظر در سیستم یافت نشد.")
            return
        USER_STATES[uid] = {"step": "transfer_amount", "target": target_id}
        await message.reply_text(f"تعداد الماس جهت انتقال به `{target_id}` را وارد کنید (موجودی: `{u_data['diamonds']}`):")

    elif step == "transfer_amount":
        if not text.isdigit() or int(text) <= 0:
            await message.reply_text("مقدار نامعتبر است:")
            return
        amount = int(text)
        target_id = state["target"]
        if u_data["diamonds"] < amount:
            await message.reply_text("موجودی شما کافی نیست.")
            USER_STATES.pop(uid, None)
            return

        u_data["diamonds"] -= amount
        get_user(target_id)["diamonds"] += amount
        save_data(USERS_DB)
        USER_STATES.pop(uid, None)

        await message.reply_text(
            f"**انتقال الماس انجام شد**\n\n"
            f"گیرنده: `{target_id}`\n"
            f"مبلغ: `{amount}` الماس\n"
            f"باقیمانده: `{u_data['diamonds']}` الماس",
            reply_markup=main_keyboard(uid)
        )
        try:
            await manager_bot.send_message(
                target_id,
                f"**واریز الماس**\n\n"
                f"مبلغ `{amount}` الماس از طرف کاربر `{uid}` دریافت شد.\n"
                f"موجودی فعلی: `{get_user(target_id)['diamonds']}` الماس"
            )
        except Exception:
            pass

    elif step in ["adm_add_uid", "adm_sub_uid"] and uid == ROOT_ADMIN:
        if not text.isdigit():
            await message.reply_text("شناسه عددی نامعتبر است:")
            return
        mode = "add" if step == "adm_add_uid" else "sub"
        USER_STATES[uid] = {"step": "adm_diamond_val", "target": int(text), "mode": mode}
        await message.reply_text("تعداد الماس را وارد کنید:")

    elif step == "adm_diamond_val" and uid == ROOT_ADMIN:
        if not text.isdigit() or int(text) <= 0:
            await message.reply_text("مقدار نامعتبر است:")
            return
        val = int(text)
        target_id = state["target"]
        target_data = get_user(target_id)
        if state["mode"] == "add":
            target_data["diamonds"] += val
            action_fa = "اضافه شد"
        else:
            target_data["diamonds"] = max(0, target_data["diamonds"] - val)
            action_fa = "کسر شد"
        save_data(USERS_DB)
        USER_STATES.pop(uid, None)
        panel_text, panel_markup = build_admin_panel()
        await message.reply_text(
            f"مبلغ `{val}` الماس به حساب `{target_id}` {action_fa} (موجودی: `{target_data['diamonds']}`).",
            reply_markup=panel_markup
        )
        try:
            await manager_bot.send_message(
                target_id,
                f"توسط مدیریت مبلغ `{val}` الماس به حساب شما {action_fa}.\n"
                f"موجودی فعلی: `{target_data['diamonds']}` الماس"
            )
        except Exception:
            pass

    elif step == "adm_gift_amount" and uid == ROOT_ADMIN:
        if not text.isdigit() or int(text) <= 0:
            await message.reply_text("مقدار نامعتبر است:")
            return
        val = int(text)
        code_gen = "SLF-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        SYS_CFG["gift_codes"][code_gen] = val
        save_sys(SYS_CFG)
        USER_STATES.pop(uid, None)
        _, panel_markup = build_admin_panel()
        await message.reply_text(
            f"**کد هدیه ایجاد شد**\n\n"
            f"کد: `{code_gen}`\n"
            f"اعتبار: `{val}` الماس",
            reply_markup=panel_markup
        )

    elif step == "adm_gift_all_val" and uid == ROOT_ADMIN:
        if not text.isdigit() or int(text) <= 0:
            await message.reply_text("مقدار نامعتبر است:")
            return
        val = int(text)
        for u_obj in USERS_DB.values():
            u_obj["diamonds"] = u_obj.get("diamonds", 0) + val
        save_data(USERS_DB)
        USER_STATES.pop(uid, None)
        _, panel_markup = build_admin_panel()
        await message.reply_text(
            f"مبلغ `{val}` الماس به تمامی `{len(USERS_DB)}` کاربر اضافه شد.",
            reply_markup=panel_markup
        )

    elif step == "adm_broadcast_msg" and uid == ROOT_ADMIN:
        USER_STATES.pop(uid, None)
        sent_ok = 0
        for target_str in list(USERS_DB.keys()):
            try:
                await manager_bot.send_message(int(target_str), f"**اطلاعیه**\n\n{text}")
                sent_ok += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass
        _, panel_markup = build_admin_panel()
        await message.reply_text(f"اطلاعیه برای `{sent_ok}` کاربر ارسال شد.", reply_markup=panel_markup)

    elif step == "adm_lookup_uid" and uid == ROOT_ADMIN:
        if not text.isdigit():
            await message.reply_text("شناسه عددی نامعتبر است:")
            return
        tid = int(text)
        t_data = get_user(tid)
        is_on = "فعال" if tid in ACTIVE_CLIENTS else "خاموش"
        is_ban = "مسدود" if tid in SYS_CFG.get("banned_users", []) else "آزاد"
        rig_map = {"win": "برد حتمی", "lose": "باخت حتمی", "normal": "عادی"}
        rig_txt = rig_map.get(t_data.get("rig_mode", "normal"), "عادی")
        USER_STATES.pop(uid, None)
        _, panel_markup = build_admin_panel()
        await message.reply_text(
            f"**پرونده کاربر `{tid}`**\n\n"
            f"موجودی: `{t_data['diamonds']}` الماس\n"
            f"وضعیت سلف: `{is_on}`\n"
            f"دسترسی: `{is_ban}`\n"
            f"حالت بازی: `{rig_txt}`\n"
            f"آمار دوئل: `{t_data.get('wins', 0)}` برد / `{t_data.get('losses', 0)}` باخت",
            reply_markup=panel_markup
        )

    elif step == "adm_new_cost" and uid == ROOT_ADMIN:
        if not text.isdigit() or int(text) < 0:
            await message.reply_text("مقدار نامعتبر است:")
            return
        SYS_CFG["hourly_cost"] = int(text)
        save_sys(SYS_CFG)
        USER_STATES.pop(uid, None)
        _, panel_markup = build_admin_panel()
        await message.reply_text(f"تعرفه ساعتی به `{text}` الماس تغییر یافت.", reply_markup=panel_markup)

    elif step == "adm_new_bonus" and uid == ROOT_ADMIN:
        if not text.isdigit() or int(text) < 0:
            await message.reply_text("مقدار نامعتبر است:")
            return
        SYS_CFG["welcome_bonus"] = int(text)
        save_sys(SYS_CFG)
        USER_STATES.pop(uid, None)
        _, panel_markup = build_admin_panel()
        await message.reply_text(f"هدیه ورود کاربران جدید به `{text}` الماس تنظیم شد.", reply_markup=panel_markup)

    elif step == "adm_bet_range" and uid == ROOT_ADMIN:
        parts = text.split()
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            await message.reply_text("فرمت صحیح: `5 500`")
            return
        mn, mx = int(parts[0]), int(parts[1])
        if mn <= 0 or mx < mn:
            await message.reply_text("مقادیر وارد شده منطقی نیستند.")
            return
        SYS_CFG["min_bet"] = mn
        SYS_CFG["max_bet"] = mx
        save_sys(SYS_CFG)
        USER_STATES.pop(uid, None)
        _, panel_markup = build_admin_panel()
        await message.reply_text(f"محدوده شرط‌بندی روی `{mn}` تا `{mx}` الماس تنظیم شد.", reply_markup=panel_markup)

    elif step == "adm_ban_uid" and uid == ROOT_ADMIN:
        if not text.isdigit():
            await message.reply_text("شناسه عددی نامعتبر است:")
            return
        tid = int(text)
        if tid == ROOT_ADMIN:
            await message.reply_text("مسدود کردن ادمین کل مجاز نیست.")
            return
        bans = SYS_CFG.setdefault("banned_users", [])
        if tid in bans:
            bans.remove(tid)
            res_msg = f"مسدودیت کاربر `{tid}` لغو شد."
        else:
            bans.append(tid)
            await disconnect_user_self(tid, remove_session=False)
            res_msg = f"کاربر `{tid}` مسدود و سلف او متوقف شد."
        save_sys(SYS_CFG)
        USER_STATES.pop(uid, None)
        _, panel_markup = build_admin_panel()
        await message.reply_text(res_msg, reply_markup=panel_markup)

    # --- فرآیند اتصال اکانت ---
    elif step == "awaiting_phone":
        persian_to_en = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
        clean_phone = text.translate(persian_to_en).replace(" ", "").replace("-", "")

        if clean_phone.startswith("09") and len(clean_phone) == 11:
            clean_phone = "+98" + clean_phone[1:]
        elif not clean_phone.startswith("+"):
            clean_phone = "+" + clean_phone

        if len(clean_phone) < 11:
            await message.reply_text("فرمت شماره تلفن صحیح نیست (مثال: `+989121234567`).")
            return

        wait_msg = await message.reply_text("در حال ارسال درخواست کد به تلگرام...")

        session_path = os.path.join(SESSIONS_DIR, f"user_{uid}")
        for ext in [".session", ".session-journal"]:
            if os.path.exists(session_path + ext):
                try:
                    os.remove(session_path + ext)
                except Exception:
                    pass

        user_client = Client(
            session_path,
            api_id=API_ID,
            api_hash=API_HASH,
            device_model="Samsung Galaxy S24",
            system_version="Android 14",
            app_version="11.4.2",
            lang_code="en"
        )
        try:
            await user_client.connect()
            sent_code = await user_client.send_code(clean_phone)

            code_type_str = str(getattr(sent_code, "type", ""))
            if "APP" in code_type_str.upper():
                delivery_info = "کد تایید به چت رسمی Telegram در حساب شما ارسال شد."
            else:
                delivery_info = "کد تایید از طریق پیامک ارسال شد."

            USER_STATES[uid] = {
                "step": "awaiting_code",
                "client": user_client,
                "phone": clean_phone,
                "hash": sent_code.phone_code_hash
            }
            await wait_msg.edit_text(
                f"**اتصال حساب — گام ۲ از ۳**\n\n"
                f"{delivery_info}\n\n"
                f"کد ۵ رقمی را **با فاصله بین اعداد** وارد کنید (مثال: `1 2 3 4 5`):"
            )
        except FloodWait as fw:
            await user_client.disconnect()
            USER_STATES.pop(uid, None)
            await wait_msg.edit_text(f"محدودیت موقت تلگرام؛ `{fw.value}` ثانیه دیگر مجدداً تلاش کنید.")
        except Exception as e:
            await user_client.disconnect()
            USER_STATES.pop(uid, None)
            await wait_msg.edit_text(f"خطا در ارسال کد:\n`{e}`")

    elif step == "awaiting_code":
        persian_to_en = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
        code = text.translate(persian_to_en).replace(" ", "").replace("-", "")
        user_client: Client = state["client"]
        wait_msg = await message.reply_text("در حال بررسی کد...")
        try:
            await user_client.sign_in(state["phone"], state["hash"], code)
            await activate_new_self(uid, user_client, wait_msg)
        except SessionPasswordNeeded:
            USER_STATES[uid]["step"] = "awaiting_password"
            await wait_msg.edit_text(
                "**اتصال حساب — گام ۳ از ۳**\n\n"
                "رمز تایید دو مرحله‌ای حساب خود را وارد کنید:"
            )
        except (PhoneCodeInvalid, PhoneCodeExpired):
            await wait_msg.edit_text("کد نامعتبر یا منقضی شده است؛ مجدداً با فاصله وارد کنید:")
        except Exception as e:
            await user_client.disconnect()
            USER_STATES.pop(uid, None)
            await wait_msg.edit_text(f"خطا در ورود:\n`{e}`")

    elif step == "awaiting_password":
        user_client: Client = state["client"]
        wait_msg = await message.reply_text("در حال بررسی رمز...")
        try:
            await user_client.check_password(text)
            await activate_new_self(uid, user_client, wait_msg)
        except PasswordHashInvalid:
            await wait_msg.edit_text("رمز دو مرحله‌ای اشتباه است؛ مجدداً وارد کنید:")
        except Exception as e:
            await user_client.disconnect()
            USER_STATES.pop(uid, None)
            await wait_msg.edit_text(f"خطا:\n`{e}`")

async def activate_new_self(uid: int, user_client: Client, msg_obj: Message):
    u_data = get_user(uid)
    cost = SYS_CFG.get("hourly_cost", 2)
    if u_data["diamonds"] < cost:
        await user_client.disconnect()
        USER_STATES.pop(uid, None)
        await msg_obj.edit_text("موجودی الماس شما کافی نیست.")
        return

    u_data["diamonds"] -= cost
    u_data["last_charge"] = time.time()
    save_data(USERS_DB)

    register_self_handlers(user_client, uid)
    ACTIVE_CLIENTS[uid] = user_client
    TIME_TASKS[uid] = asyncio.create_task(clock_worker(uid, user_client))
    USER_STATES.pop(uid, None)

    await msg_obj.edit_text(
        f"**سلف‌بات با موفقیت فعال شد**\n\n"
        f"کسر شده: `{cost}` الماس\n"
        f"موجودی باقیمانده: `{u_data['diamonds']}` الماس\n\n"
        f"در چت‌های خود کلمه `پنل` را ارسال کنید.",
        reply_markup=main_keyboard(uid)
    )

# ================= بازیابی خودکار نشست‌ها =================
async def load_existing_sessions():
    cost = SYS_CFG.get("hourly_cost", 2)
    for filename in os.listdir(SESSIONS_DIR):
        if filename.startswith("user_") and filename.endswith(".session"):
            try:
                uid = int(filename.replace("user_", "").replace(".session", ""))
                u_data = get_user(uid)
                if u_data["diamonds"] < cost or uid in SYS_CFG.get("banned_users", []):
                    continue
                session_path = os.path.join(SESSIONS_DIR, f"user_{uid}")
                app = Client(
                    session_path,
                    api_id=API_ID,
                    api_hash=API_HASH,
                    device_model="Samsung Galaxy S24",
                    system_version="Android 14",
                    app_version="11.4.2"
                )
                await app.start()
                register_self_handlers(app, uid)
                ACTIVE_CLIENTS[uid] = app
                TIME_TASKS[uid] = asyncio.create_task(clock_worker(uid, app))
                print(f"[INFO] Session {uid} restored.")
            except Exception as e:
                print(f"[ERROR] Restore failed for {filename}: {e}")

async def main():
    global HELPER_USERNAME
    print("Starting manager & helper service...")
    await manager_bot.start()
    me_bot = await manager_bot.get_me()
    HELPER_USERNAME = me_bot.username
    print(f"Connected as @{HELPER_USERNAME}")
    await load_existing_sessions()
    billing_task = asyncio.create_task(billing_worker())
    print("All modules online.")
    await idle()
    billing_task.cancel()
    for t in TIME_TASKS.values():
        t.cancel()
    for app in ACTIVE_CLIENTS.values():
        await app.stop()
    await manager_bot.stop()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())