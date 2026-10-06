import asyncio
import logging
import re

from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from aiogram.exceptions import TelegramBadRequest

from config import (
    BOT_TOKEN,
    PAYMENT_GROUP_ID,
    PUBLIC_CHANNEL_ID,
    SIGNAL_BOT,
    ADMIN_IDS
)

from packages import PACKAGE_MAP, get_active_price

from spreadsheet import (
    save_member
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "[%(levelname)s] "
        "%(name)s: "
        "%(message)s"
    )
)

logger = logging.getLogger("main")


# =========================================================
# BOT
# =========================================================

bot = Bot(
    token=BOT_TOKEN
)

dp = Dispatcher()

# =========================================================
# IGNORE INCOMING GROUP MESSAGES
# =========================================================

class IgnoreGroupMessagesMiddleware(BaseMiddleware):
    """
    Abaikan semua pesan masuk dari group/supergroup.

    Private chat tetap diproses untuk semua user.
    Pemeriksaan admin hanya berlaku pada handler admin.
    Pesan keluar bot dan callback tidak diblokir.
    """

    async def __call__(self, handler, event, data):
        chat = getattr(event, "chat", None)

        if chat and chat.type in ("group", "supergroup"):
            logger.info(
                "GROUP MESSAGE IGNORED | chat_id=%s | type=%s",
                chat.id,
                chat.type
            )
            return None

        return await handler(event, data)


dp.message.middleware(IgnoreGroupMessagesMiddleware())

# =========================================================
# PAYMENT / TEMP STORAGE
# =========================================================

user_packages = {}
user_proofs = {}
user_payment_status = {}


# =========================================================
# PERFORMANCE SETTINGS
# =========================================================

PERFORMANCE_LOT = 0.01

DOLLAR_PER_PIP_LOT_001 = 0.10


# =========================================================
# PERFORMANCE RESULT
# =========================================================

TP1_PIPS = 70
TP2_PIPS = 150
SL_PIPS = 50


# =========================================================
# PACKAGE ACCESS
# =========================================================

def package_has_group_access(package_key: str) -> bool:
    """Semua paket hanya mendapatkan akses Signal AI."""
    return False


# =========================================================
# PACKAGE DATA
# =========================================================

def get_package_data(
    package_key: str
) -> dict:

    data = dict(
        PACKAGE_MAP[package_key]
    )

    data["price"] = get_active_price(
        package_key
    )

    return data


# =========================================================
# ADMIN
# =========================================================

def is_admin(
    user_id: int
) -> bool:

    try:

        return int(user_id) in [
            int(x)
            for x in ADMIN_IDS
        ]

    except Exception:

        return False


# =========================================================
# SAFE CALLBACK
# =========================================================

async def safe_callback_answer(
    callback: CallbackQuery,
    text: str = "",
    show_alert: bool = False
):

    try:

        await callback.answer(
            text,
            show_alert=show_alert
        )

    except TelegramBadRequest:

        pass

    except Exception:

        pass


# =========================================================
# REMOVE KEYBOARD
# =========================================================

async def remove_keyboard(
    message: Message
):

    try:

        await message.edit_reply_markup(
            reply_markup=None
        )

    except TelegramBadRequest as e:

        error_text = str(e).lower()

        if "message is not modified" not in error_text:

            logger.warning(
                "Gagal menghapus keyboard: %s",
                e
            )

    except Exception as e:

        logger.warning(
            "Gagal edit reply markup: %s",
            e
        )


# =========================================================
# FORMAT RUPIAH
# =========================================================

def format_rupiah(
    value
):

    try:

        return f"{int(value):,}".replace(
            ",",
            "."
        )

    except Exception:

        return str(value)


# =========================================================
# FORMAT USD
# =========================================================

def format_usd(
    value
):

    if value > 0:

        return f"+${value:.2f}"

    if value < 0:

        return f"-${abs(value):.2f}"

    return "$0.00"


# =========================================================
# FORMAT PRICE
# =========================================================

def format_price(
    value
):

    if value is None:

        return "-"

    return f"{value:.2f}"


# =========================================================
# MONTH INDONESIA
# =========================================================

MONTHS_ID = {

    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember"

}


def format_date_indonesia(
    date_obj
):

    return (
        f"{date_obj.day} "
        f"{MONTHS_ID[date_obj.month]} "
        f"{date_obj.year}"
    )


# =========================================================
# PARSE DATE
# =========================================================

def parse_performance_date(
    text: str
):

    patterns = [

        r"(\d{2})-(\d{2})-(\d{4})",

        r"(\d{2})/(\d{2})/(\d{4})",

        r"(\d{4})-(\d{2})-(\d{2})",

        r"(\d{4})/(\d{2})/(\d{2})"

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if not match:

            continue

        try:

            values = [
                int(x)
                for x in match.groups()
            ]

            if len(values) != 3:

                continue

            if values[0] > 31:

                year = values[0]
                month = values[1]
                day = values[2]

            else:

                day = values[0]
                month = values[1]
                year = values[2]

            return datetime(
                year,
                month,
                day
            )

        except ValueError:

            return None

    return None


# =========================================================
# PARSE PERFORMANCE
# =========================================================

def parse_performance(
    text: str
):

    results = []

    lines = text.splitlines()

    for raw_line in lines:

        line = raw_line.strip()

        if not line:

            continue

        line = line.replace(
            "📅",
            ""
        )

        line = line.replace(
            "`",
            ""
        )

        line = line.strip()

        # =================================================
        # SKIP DATE ONLY
        # =================================================

        if re.search(
            r"\d{2}[-/]\d{2}[-/]\d{4}",
            line
        ):

            if not re.search(
                r"\d{1,2}:\d{2}",
                line
            ):

                continue

        # =================================================
        # PENDING
        # =================================================

        pending_match = re.search(

            r"(?P<time>\d{1,2}:\d{2})"
            r"\s*(?:\||-)?\s*"
            r"PENDING",

            line,

            re.IGNORECASE

        )

        if pending_match:

            results.append({

                "direction": None,

                "time":
                    pending_match.group(
                        "time"
                    ),

                "entry": None,

                "hit_price": None,

                "result":
                    "PENDING"

            })

            continue

        # =================================================
        # NO SIGNAL
        # =================================================

        no_signal_match = re.search(

            r"(?P<time>\d{1,2}:\d{2})"
            r"\s*(?:\||-)?\s*"
            r"NO\s*SIGNAL",

            line,

            re.IGNORECASE

        )

        if no_signal_match:

            results.append({

                "direction": None,

                "time":
                    no_signal_match.group(
                        "time"
                    ),

                "entry": None,

                "hit_price": None,

                "result":
                    "NO SIGNAL"

            })

            continue

        # =================================================
        # SIGNAL
        # =================================================

        signal_match = re.search(

            r"^\s*"

            r"(?P<direction>[BS])"

            r"\s+"

            r"(?P<time>\d{1,2}:\d{2})"

            r"\s*\|\s*"

            r"(?P<entry>\d+(?:\.\d+)?)"

            r"\s*\|\s*"

            r"(?P<hit>\d+(?:\.\d+)?)"

            r"\s*\|\s*"

            r"(?P<result>TP1|TP2|SL)"

            r"\s*$",

            line,

            re.IGNORECASE

        )

        if signal_match:

            try:

                entry = float(
                    signal_match.group(
                        "entry"
                    )
                )

                hit_price = float(
                    signal_match.group(
                        "hit"
                    )
                )

            except Exception:

                logger.warning(
                    "Harga tidak valid: %s",
                    line
                )

                continue

            results.append({

                "direction":
                    signal_match.group(
                        "direction"
                    ).upper(),

                "time":
                    signal_match.group(
                        "time"
                    ),

                "entry":
                    entry,

                "hit_price":
                    hit_price,

                "result":
                    signal_match.group(
                        "result"
                    ).upper()

            })

            continue

        logger.warning(
            "Performance line tidak dikenali: %s",
            line
        )

    return results


# =========================================================
# RESULT PIPS
# =========================================================

def get_result_pips(
    direction,
    entry,
    hit_price
):

    try:

        direction = str(
            direction
        ).upper().strip()

        entry = float(entry)
        hit_price = float(hit_price)

        if direction == "B":

            return round(
                (hit_price - entry) * 10
            )

        if direction == "S":

            return round(
                (entry - hit_price) * 10
            )

        return 0

    except Exception:

        return 0


# =========================================================
# RESULT PNL
# =========================================================

def get_result_pnl(
    direction,
    entry,
    hit_price
):

    pips = get_result_pips(
        direction,
        entry,
        hit_price
    )

    return (
        pips
        * DOLLAR_PER_PIP_LOT_001
    )


# =========================================================
# BUILD PERFORMANCE
# =========================================================

def build_performance_message(
    performance,
    performance_date=None
):

    signals = [

        item

        for item in performance

        if item["result"] in (
            "TP1",
            "TP2",
            "SL"
        )

    ]

    total = len(
        signals
    )

    tp1_count = sum(

        1

        for item in signals

        if item["result"] == "TP1"

    )

    tp2_count = sum(

        1

        for item in signals

        if item["result"] == "TP2"

    )

    sl_count = sum(

        1

        for item in signals

        if item["result"] == "SL"

    )

    pending_count = sum(

        1

        for item in performance

        if item["result"] == "PENDING"

    )

    no_signal_count = sum(

        1

        for item in performance

        if item["result"] == "NO SIGNAL"

    )

    wins = (
        tp1_count
        + tp2_count
    )

    if total > 0:

        winrate = (
            wins / total
        ) * 100

    else:

        winrate = 0

    total_pips = sum(

        get_result_pips(
            item["direction"],
            item["entry"],
            item["hit_price"]
        )

        for item in signals

    )

    pnl = sum(

        get_result_pnl(
            item["direction"],
            item["entry"],
            item["hit_price"]
        )

        for item in signals

    )

    if performance_date is None:

        performance_date = datetime.now()

    date_text = format_date_indonesia(
        performance_date
    )

    lines = []

    for item in performance:

        direction = item["direction"]
        time = item["time"]
        result = item["result"]

        if result == "PENDING":

            lines.append(
                f"- 🕐 {time} | "
                f"⏳ <b>PENDING</b>"
            )

            continue

        if result == "NO SIGNAL":

            lines.append(
                f"- 🕐 {time} | "
                f"⚪ <b>NO SIGNAL</b>"
            )

            continue

        entry = format_price(
            item["entry"]
        )

        hit_price = format_price(
            item["hit_price"]
        )

        if result == "TP1":

            result_icon = "✅ TP1"

        elif result == "TP2":

            result_icon = "🏆 TP2"

        else:

            result_icon = "❌ SL"

        lines.append(

            f"{direction} 🕐 {time} | "
            f"{entry} → {hit_price} | "
            f"{result_icon}"

        )

    performance_lines = "\n".join(
        lines
    )

    pnl_text = format_usd(
        pnl
    )

    return f"""
📊 <b>XAU AI ASSISTANT GOLD</b>
━━━━━━━━━━━━━━━━━━
<b>PERFORMANCE {total} SIGNAL</b>

📅 <b>{date_text}</b>

{performance_lines}

━━━━━━━━━━━━━━━━━━
📈 <b>HASIL</b>

📊 Signal      : <b>{total}</b>
✅ TP1         : <b>{tp1_count}</b>
🏆 TP2         : <b>{tp2_count}</b>
❌ SL          : <b>{sl_count}</b>
⏳ Pending     : <b>{pending_count}</b>
⚪ No Signal   : <b>{no_signal_count}</b>

🎯 Winrate     : <b>{winrate:.0f}%</b>
📏 Total       : <b>{total_pips:+d} Pips</b>
💰 PNL         : <b>{pnl_text}</b>

━━━━━━━━━━━━━━━━━━
🤖 <b>AI ASSISTANT GOLD</b>

Analisa XAUUSD berbasis AI
+ Smart Money Concept.

🚀 <b>Dapatkan signal AI Assistant Gold
secara realtime dan terstruktur.</b>
"""


# =========================================================
# PACKAGE KEYBOARD
# =========================================================

def build_package_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🥇 1 BULAN | Rp299.000", callback_data="pkg_1month")],
            [InlineKeyboardButton(text="🥈 6 BULAN | Rp500.000", callback_data="pkg_6month")],
            [InlineKeyboardButton(text="🥉 12 BULAN | Rp900.000", callback_data="pkg_12month")],
            [InlineKeyboardButton(text="👑 3 TAHUN | Rp1.500.000", callback_data="pkg_permanent")]
        ]
    )


# =========================================================
# PACKAGE CHOICE TEXT
# =========================================================

def build_package_choice_text() -> str:
    return """
💎 <b>PILIH MEMBERSHIP PLAN</b>

━━━━━━━━━━━━━━━━━━

🥇 <b>1 BULAN</b>
💰 <b>Rp299.000</b>

🤖 Signal AI / AI Assistant
📊 Analisa XAUUSD
🧠 Smart Money Concept

━━━━━━━━━━━━━━━━━━

🥈 <b>6 BULAN</b>
💰 <b>Rp500.000</b>

🤖 Signal AI / AI Assistant
📊 Analisa XAUUSD
🧠 Smart Money Concept

━━━━━━━━━━━━━━━━━━

🥉 <b>12 BULAN</b>
💰 <b>Rp900.000</b>

🤖 Signal AI / AI Assistant
📊 Analisa XAUUSD
🧠 Smart Money Concept

━━━━━━━━━━━━━━━━━━

👑 <b>3 TAHUN</b>
💰 <b>Rp1.500.000</b>

🤖 Signal AI / AI Assistant
📊 Analisa XAUUSD
🧠 Smart Money Concept

━━━━━━━━━━━━━━━━━━

✨ <b>SEMUA PAKET:</b>

✅ Signal AI / AI Assistant Telegram
✅ Analisa XAUUSD
✅ Smart Money Concept
✅ Market Intelligence

ℹ️ <b>Tidak ada akses Grup Diskusi &amp; Sharing.</b>

Silakan pilih paket.
"""


# =========================================================
# SEND PAYMENT INFO
# =========================================================

async def send_payment_info(
    user_id: int,
    chat_id: int,
    package_key: str
) -> bool:

    if package_key not in PACKAGE_MAP:
        logger.warning("Package key tidak dikenali: %s", package_key)
        return False

    user_packages[user_id] = package_key
    user_proofs.pop(user_id, None)
    user_payment_status[user_id] = "WAITING_PROOF"

    data = get_package_data(package_key)

    payment_text = f"""
💳 <b>AKTIVASI SIGNAL AI</b>

━━━━━━━━━━━━━━━━━━

📦 <b>Paket</b>
{data['label']}

💰 <b>Total Pembayaran</b>
Rp {format_rupiah(data['price'])}

━━━━━━━━━━━━━━━━━━

🤖 <b>SIGNAL AI / AI ASSISTANT</b>

Akses AI Assistant Telegram
untuk analisa XAUUSD berbasis
Smart Money Concept.

━━━━━━━━━━━━━━━━━━

📌 <b>INSTRUKSI PEMBAYARAN</b>

1️⃣ Scan QRIS
2️⃣ Lakukan pembayaran sesuai nominal
3️⃣ Screenshot bukti pembayaran
4️⃣ Kirim screenshot tersebut ke chat ini

📸 Pastikan bukti pembayaran
terlihat jelas dan nominalnya terbaca.

━━━━━━━━━━━━━━━━━━

⏳ Setelah bukti pembayaran dikirim,
bot akan langsung meneruskannya
kepada Admin untuk pengecekan.

Tidak perlu mengisi Nama, Broker,
atau Gmail.

Terima kasih telah bergabung
bersama <b>XAU AI Assistant Gold</b>.
"""

    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile("assets/qris.jpg"),
            caption=payment_text,
            parse_mode="HTML"
        )
        return True
    except Exception as e:
        logger.exception("Gagal mengirim QRIS | user=%s | error=%s", user_id, e)
        return False


# =========================================================
# START
# =========================================================

@dp.message(
    CommandStart()
)
async def start(
    message: Message
):

    logger.info(
        "START diterima | user_id=%s | username=%s | text=%s",
        message.from_user.id,
        message.from_user.username,
        message.text
    )

    payload = None

    if message.text and " " in message.text:

        payload = message.text.split(
            maxsplit=1
        )[1].strip()

    if payload and payload in PACKAGE_MAP:

        logger.info(
            "Deep-link paket | user_id=%s | package=%s",
            message.from_user.id,
            payload
        )

        sent = await send_payment_info(

            user_id=message.from_user.id,

            chat_id=message.chat.id,

            package_key=payload

        )

        if sent:

            return

    await message.answer(

        build_package_choice_text(),

        reply_markup=build_package_keyboard(),

        parse_mode="HTML"

    )


# =========================================================
# PILIH PACKAGE
# =========================================================

@dp.callback_query(
    F.data.startswith("pkg_")
)
async def show_payment(
    callback: CallbackQuery
):

    await remove_keyboard(
        callback.message
    )

    package_key = callback.data.replace(
        "pkg_",
        ""
    )

    sent = await send_payment_info(

        user_id=callback.from_user.id,

        chat_id=callback.message.chat.id,

        package_key=package_key

    )

    if not sent:

        await safe_callback_answer(

            callback,

            "Paket tidak ditemukan.",

            True

        )

        return

    await safe_callback_answer(

        callback,

        "Paket berhasil dipilih"

    )


# =========================================================
# UPLOAD REQUEST
# =========================================================

@dp.callback_query(F.data == "upload")
async def upload_request(callback: CallbackQuery):
    await callback.message.answer(
        """
📸 <b>UPLOAD BUKTI PEMBAYARAN</b>

Silakan kirim screenshot atau foto
bukti pembayaran QRIS ke chat ini.

Pastikan nominal dan bukti pembayaran
terlihat jelas.

Setelah dikirim, bukti akan langsung
diteruskan kepada Admin.
""",
        parse_mode="HTML"
    )
    await safe_callback_answer(callback, "Silakan upload bukti pembayaran")


# =========================================================
# RECEIVE PAYMENT PROOF
# =========================================================

@dp.message(F.photo)
async def receive_payment(message: Message):
    user_id = message.from_user.id
    package_key = user_packages.get(user_id)

    if not package_key:
        await message.answer(
            """
⚠️ <b>PAKET BELUM DIPILIH</b>

Silakan pilih paket terlebih dahulu
melalui /start.
""",
            parse_mode="HTML"
        )
        return

    try:
        data = get_package_data(package_key)
    except Exception:
        await message.answer("❌ Data paket tidak ditemukan. Silakan mulai kembali melalui /start.")
        return

    proof = message.photo[-1].file_id
    user_proofs[user_id] = proof
    user_payment_status[user_id] = "PROOF_SENT"

    username = f"@{message.from_user.username}" if message.from_user.username else "-"
    full_name = message.from_user.full_name or "-"

    admin_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ APPROVE", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ REJECT", callback_data=f"reject_{user_id}")
        ]]
    )

    admin_text = f"""
📥 <b>PAYMENT VERIFICATION</b>

━━━━━━━━━━━━━━━━━━

👤 <b>DATA USER</b>

Nama Telegram:
<b>{full_name}</b>

Username:
<b>{username}</b>

Telegram ID:
<code>{user_id}</code>

━━━━━━━━━━━━━━━━━━

📦 <b>PAKET</b>
{data['label']}

💰 <b>TOTAL</b>
Rp {format_rupiah(data['price'])}

🤖 <b>AKSES</b>
Signal AI / AI Assistant Only

━━━━━━━━━━━━━━━━━━

📸 <b>Bukti pembayaran terlampir.</b>

🟡 <b>MENUNGGU PERSETUJUAN ADMIN</b>

Silakan pilih tindakan:
"""

    try:
        await bot.send_photo(
            chat_id=PAYMENT_GROUP_ID,
            photo=proof,
            caption=admin_text,
            reply_markup=admin_keyboard,
            parse_mode="HTML"
        )
        logger.info(
            "Payment proof dikirim | user=%s | username=%s | package=%s | price=%s",
            user_id, username, package_key, data["price"]
        )
    except Exception as e:
        logger.exception("Gagal mengirim payment proof | user=%s", user_id)
        user_payment_status[user_id] = "WAITING_PROOF"
        await message.answer(
            """
❌ <b>BUKTI BELUM BERHASIL DIKIRIM KE ADMIN</b>

Terjadi kendala saat meneruskan bukti pembayaran.
Silakan kirim ulang screenshot pembayaran.
""",
            parse_mode="HTML"
        )
        return

    await message.answer(
        """
✅ <b>BUKTI PEMBAYARAN DITERIMA</b>

━━━━━━━━━━━━━━━━━━

Baik, transaksi kamu sedang di-check.

🟡 <b>Saat ini pembayaran sedang menunggu
persetujuan Admin.</b>

Mohon tunggu konfirmasi dari Admin.

Tidak perlu mengirim data tambahan
seperti Nama, Broker, atau Gmail.
""",
        parse_mode="HTML"
    )


# =========================================================
# TEXT MESSAGE HANDLER
# =========================================================

@dp.message(F.text)
async def text_message_handler(message: Message):
    text = message.text or ""

    if text.startswith("/"):
        return

    if not is_admin(message.from_user.id):
        user_id = message.from_user.id
        package_key = user_packages.get(user_id)

        if package_key:
            status = user_payment_status.get(user_id, "WAITING_PROOF")

            if status == "PROOF_SENT":
                await message.answer(
                    """
🟡 <b>PEMBAYARAN SEDANG DIVERIFIKASI</b>

Bukti pembayaran kamu sudah diteruskan
kepada Admin.

Mohon tunggu persetujuan Admin.
""",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    """
📸 Silakan kirim <b>screenshot bukti pembayaran</b>
ke chat ini setelah melakukan pembayaran.
""",
                    parse_mode="HTML"
                )
        else:
            await message.answer(
                "Silakan gunakan /start untuk memilih paket.",
                parse_mode="HTML"
            )
        return

    await process_performance_message(message)


# =========================================================
# APPROVE MEMBER
# =========================================================

@dp.callback_query(F.data.startswith("approve_"))
async def approve(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await safe_callback_answer(callback, "Anda bukan admin.", True)
        return

    await remove_keyboard(callback.message)

    try:
        user_id = int(callback.data.split("_", 1)[1])
    except Exception:
        await safe_callback_answer(callback, "User ID tidak valid.", True)
        return

    package_key = user_packages.get(user_id)

    if not package_key:
        await safe_callback_answer(callback, "Data paket tidak ditemukan.", True)
        return

    try:
        data = get_package_data(package_key)
        user = await bot.get_chat(user_id)
    except Exception as e:
        logger.exception("Gagal mengambil data user/package | user=%s", user_id)
        await safe_callback_answer(callback, "Gagal mengambil data user.", True)
        return

    now = datetime.now()
    expired = (now + timedelta(days=data["days"])).strftime("%d-%m-%Y")

    username = user.username or ""
    full_name = user.full_name or ""

    member_data = {
        "telegram_id": user_id,
        "username": username,
        "nama": full_name,
        "paket": data["label"],
        "harga": data["price"],
        "register": now.strftime("%d-%m-%Y"),
        "expired": expired,
        "status": "ACTIVE"
    }

    try:
        saved = await asyncio.to_thread(save_member, member_data)
        if saved is False:
            raise RuntimeError("save_member mengembalikan False")
    except Exception as e:
        logger.exception("Gagal menyimpan membership | user=%s", user_id)
        await safe_callback_answer(
            callback,
            "Gagal menyimpan membership ke Google Sheets.",
            True
        )
        await callback.message.answer(
            f"""
❌ <b>AKTIVASI GAGAL</b>

Membership belum diaktifkan karena data gagal disimpan.

User ID:
<code>{user_id}</code>

Error:
<code>{e}</code>
""",
            parse_mode="HTML"
        )
        return

    member_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🤖 MASUK AI ASSISTANT",
                url=SIGNAL_BOT
            )
        ]]
    )

    member_text = f"""
🎉 <b>MEMBERSHIP AKTIF</b>

━━━━━━━━━━━━━━━━━━

📦 <b>Paket</b>
{data['label']}

💰 <b>Pembayaran</b>
Rp {format_rupiah(data['price'])}

⏳ <b>Berlaku Sampai</b>
{expired}

━━━━━━━━━━━━━━━━━━

🚀 <b>AKSES PREMIUM</b>

✅ Signal AI / AI Assistant Telegram
✅ Analisa XAUUSD
✅ Smart Money Concept
✅ Market Intelligence

━━━━━━━━━━━━━━━━━━

🤖 Klik tombol di bawah untuk mulai
menggunakan AI Assistant.

Selamat trading bersama
<b>XAU AI Assistant Gold</b> 🤖
"""

    try:
        await bot.send_message(
            chat_id=user_id,
            text=member_text,
            reply_markup=member_keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.exception("Membership tersimpan tetapi akses gagal dikirim | user=%s", user_id)
        await callback.message.answer(
            f"""
⚠️ <b>MEMBERSHIP TERSIMPAN</b>

Data membership sudah tersimpan,
tetapi pesan akses gagal dikirim.

User ID:
<code>{user_id}</code>

Error:
<code>{e}</code>
""",
            parse_mode="HTML"
        )

    await callback.message.answer(
        f"""
✅ <b>MEMBER BERHASIL DIAKTIFKAN</b>

📦 Paket:
<b>{data['label']}</b>

💰 Harga:
<b>Rp {format_rupiah(data['price'])}</b>

🤖 Akses:
<b>Signal AI / AI Assistant Only</b>

👥 Grup:
<b>Tidak ada</b>
""",
        parse_mode="HTML"
    )

    await safe_callback_answer(callback, "Member aktif")

    user_packages.pop(user_id, None)
    user_proofs.pop(user_id, None)
    user_payment_status.pop(user_id, None)


# =========================================================
# REJECT MEMBER
# =========================================================

@dp.callback_query(
    F.data.startswith("reject_")
)
async def reject(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user.id
    ):

        await safe_callback_answer(

            callback,

            "Anda bukan admin.",

            True

        )

        return

    await remove_keyboard(
        callback.message
    )

    user_id = int(
        callback.data.split("_")[1]
    )

    reject_text = """
❌ <b>PEMBAYARAN BELUM DIVERIFIKASI</b>

━━━━━━━━━━━━━━━━━━

Mohon:

📌 Periksa kembali bukti pembayaran
📌 Pastikan nominal sesuai
📌 Hubungi Admin jika membutuhkan bantuan

Admin siap membantu proses aktivasi Anda.
"""

    try:

        await bot.send_message(

            chat_id=user_id,

            text=reject_text,

            parse_mode="HTML"

        )

    except Exception as e:

        logger.warning(
            "Gagal mengirim reject ke user %s: %s",
            user_id,
            e
        )

    await callback.message.answer(

        """
❌ <b>PAYMENT DITOLAK</b>

User telah menerima notifikasi
bahwa pembayaran belum dapat
diverifikasi.
""",

        parse_mode="HTML"

    )

    await safe_callback_answer(

        callback,

        "Payment rejected"

    )

    # =====================================================
    # CLEANUP
    # =====================================================

    user_packages.pop(
        user_id,
        None
    )

    user_proofs.pop(
        user_id,
        None
    )

    user_payment_status.pop(
        user_id,
        None
    )


# =========================================================
# ADMIN SEND MESSAGE
# =========================================================

@dp.message(
    F.text.startswith("/sent")
)
async def sent_to_user(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):

        return

    parts = message.text.split(
        maxsplit=2
    )

    if len(parts) < 3:

        await message.answer(

            "⚠️ Format salah.\n\n"

            "Gunakan:\n"

            "<code>/sent [telegram_id] [pesan]</code>",

            parse_mode="HTML"

        )

        return

    target_id_str = parts[1]

    text_to_send = parts[2]

    if not target_id_str.isdigit():

        await message.answer(

            "⚠️ Telegram ID harus berupa angka."

        )

        return

    target_id = int(
        target_id_str
    )

    try:

        await bot.send_message(

            chat_id=target_id,

            text=text_to_send

        )

        await message.answer(

            f"✅ <b>Pesan berhasil dikirim</b>\n\n"
            f"🆔 Target: <code>{target_id}</code>\n"
            f"💬 Isi: {text_to_send}",

            parse_mode="HTML"

        )

    except Exception as e:

        await message.answer(

            f"❌ <b>Pesan gagal dikirim</b>\n\n"
            f"🆔 Target: <code>{target_id}</code>\n"
            f"⚠️ Error: <code>{e}</code>",

            parse_mode="HTML"

        )


# =========================================================
# PERFORMANCE PROCESSOR
# =========================================================

async def process_performance_message(
    message: Message
):

    if not is_admin(
        message.from_user.id
    ):

        return

    text = message.text or ""

    if not text:

        return

    # =====================================================
    # DATE
    # =====================================================

    performance_date = parse_performance_date(
        text
    )

    # =====================================================
    # PARSE
    # =====================================================

    performance = parse_performance(
        text
    )

    if not performance:

        await message.answer(

            """
⚠️ <b>FORMAT PERFORMANCE TIDAK TERBACA</b>

Gunakan format:

<code>📅 26-08-2026

S 07:00 | 4652 | 4645 | TP1
B 08:00 | 4636 | 4651 | TP2
09:00 | PENDING
10:00 | PENDING
12:00 | NO SIGNAL
B 13:00 | 4637 | 4632 | SL</code>
""",

            parse_mode="HTML"

        )

        return

    # =====================================================
    # COUNT SIGNAL
    # =====================================================

    signal_count = sum(

        1

        for item in performance

        if item["result"] in (
            "TP1",
            "TP2",
            "SL"
        )

    )

    logger.info(

        "Performance diterima | "
        "admin=%s | total_rows=%s | signals=%s | date=%s",

        message.from_user.id,

        len(performance),

        signal_count,

        performance_date

    )

    # =====================================================
    # BUILD
    # =====================================================

    final_message = build_performance_message(

        performance,

        performance_date

    )

    # =====================================================
    # CTA
    # =====================================================

    cta_keyboard = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="🚀 AKTIFKAN AI ASSISTANT GOLD",

                    url=SIGNAL_BOT

                )

            ]

        ]

    )

    # =====================================================
    # SEND CHANNEL
    # =====================================================

    try:

        await bot.send_message(

            chat_id=PUBLIC_CHANNEL_ID,

            text=final_message,

            reply_markup=cta_keyboard,

            parse_mode="HTML"

        )

        logger.info(

            "Performance berhasil dikirim | "
            "channel=%s | signals=%s",

            PUBLIC_CHANNEL_ID,

            signal_count

        )

        date_text = (

            format_date_indonesia(
                performance_date
            )

            if performance_date

            else "Tidak diketahui"

        )

        await message.answer(

            f"""
✅ <b>PERFORMANCE TERKIRIM</b>

📅 Tanggal : <b>{date_text}</b>
📊 Signal : <b>{signal_count}</b>
📢 Channel : <code>{PUBLIC_CHANNEL_ID}</code>

Performance berhasil diposting
ke Channel Umum.
""",

            parse_mode="HTML"

        )

    except Exception as e:

        logger.exception(
            "Gagal mengirim performance ke channel."
        )

        await message.answer(

            f"""
❌ <b>GAGAL MENGIRIM PERFORMANCE</b>

⚠️ Error:
<code>{e}</code>

Pastikan bot sudah menjadi
<b>ADMIN</b> di Channel Umum
dan memiliki izin posting.
""",

            parse_mode="HTML"

        )


# =========================================================
# PERFORMANCE ADMIN
# =========================================================

# Pesan teks user biasa ditangani oleh text_message_handler.
# Admin tetap dapat mengirim format performance ke channel.


# =========================================================
# MAIN
# =========================================================

async def main():

    logger.info(
        "=========================================="
    )

    logger.info(
        "🤖 XAU AI Assistant Bot Running..."
    )

    logger.info(
        "=========================================="
    )

    logger.info(
        "📊 Performance → Channel aktif"
    )

    logger.info(
        "📢 Public Channel ID: %s",
        PUBLIC_CHANNEL_ID
    )

    logger.info(
        "💳 Payment Group ID: %s",
        PAYMENT_GROUP_ID
    )

    logger.info(
        "👨‍💼 Admin IDs: %s",
        ADMIN_IDS
    )

    logger.info(
        "🎯 TP1 = %s Pips | TP2 = %s Pips | SL = -%s Pips",
        TP1_PIPS,
        TP2_PIPS,
        SL_PIPS
    )

    logger.info(
        "🤖 Semua paket = Signal AI / AI Assistant ONLY"
    )

    logger.info(
        "👥 Group Access = NONAKTIF untuk semua paket"
    )

    logger.info(
        "📝 User tidak diminta Nama / Broker / Gmail"
    )

    # =====================================================
    # START TELEGRAM BOT
    # =====================================================

    await dp.start_polling(
        bot
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "Bot dihentikan manual."
        )
